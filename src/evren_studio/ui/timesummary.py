"""F5 #8 "Zaman nereye gitti": tur süresinin model / araç / bekleme dağılımı ve küçük çubuk grafik.

Veri: asistan mesajlarının `meta.duration_s` (model çağrısı) ve araç sonuçlarının `meta.duration_s` (koşucu ölçer,
2026-10-24). Kalan süre "bekleme" (onay, kota penceresi, ağ, arayüz). Kısa turda (MIN_TOTAL_S altı) kart çıkmaz.
"""
from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from . import theme

MIN_TOTAL_S = 60.0
MIN_STEPS = 3


def breakdown(messages: list[dict], total_s: float, switches: int = 0) -> dict | None:
    """Tur mesajlarından dağılım; kısa/az adımlı turda None (kart gereksiz, R-22)."""
    model_s, steps = 0.0, 0
    tools: dict[str, float] = defaultdict(float)
    failed = 0
    for m in messages:
        meta = m.get("meta") or {}
        if m.get("role") == "assistant":
            steps += 1
            model_s += float(meta.get("duration_s") or 0)
        elif m.get("role") == "tool":
            tools[m.get("name") or "?"] += float(meta.get("duration_s") or 0)
            failed += bool(meta.get("error"))
    if total_s < MIN_TOTAL_S or steps < MIN_STEPS:
        return None
    tool_s = sum(tools.values())
    wait_s = max(0.0, total_s - model_s - tool_s)
    top = sorted(tools.items(), key=lambda kv: -kv[1])[:3]
    return {"total": total_s, "model": model_s, "tools": tool_s, "wait": wait_s, "steps": steps,
            "failed": failed, "switches": switches, "top": [(n, s) for n, s in top if s >= 1]}


def _fmt(sec: float) -> str:
    sec = int(round(sec))
    return f"{sec // 60} dk {sec % 60} sn" if sec >= 60 else f"{sec} sn"


class _Bar(QWidget):
    def __init__(self, parts: list[tuple[float, str]], parent=None):
        super().__init__(parent)
        self.parts = parts
        self.setFixedHeight(10)

    def paintEvent(self, _e) -> None:
        total = sum(v for v, _c in self.parts) or 1
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        x = 0.0
        w = self.width()
        for v, color in self.parts:
            seg = w * v / total
            if seg > 0:
                p.setBrush(QColor(color))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRectF(x, 0, max(seg - 2, 1), self.height()), 3, 3)
            x += seg
        p.end()


class TimeSummaryCard(QFrame):
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("ToolCard")
        pal = theme.current()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        title = QLabel(f"Zaman nereye gitti — toplam {_fmt(data['total'])}, {data['steps']} adım")
        title.setStyleSheet("font-weight: 600;")
        lay.addWidget(title)
        colors = (pal.accent, pal.success, pal.warning)        # iki temada da ayırt edilir
        lay.addWidget(_Bar([(data["model"], colors[0]), (data["tools"], colors[1]), (data["wait"], colors[2])]))
        legend = (f"<span style='color:{colors[0]}'>■</span> model {_fmt(data['model'])}   "
                  f"<span style='color:{colors[1]}'>■</span> araç/komut {_fmt(data['tools'])}   "
                  f"<span style='color:{colors[2]}'>■</span> bekleme/diğer {_fmt(data['wait'])}")
        lab = QLabel(legend)
        lab.setTextFormat(Qt.RichText)
        lay.addWidget(lab)
        extra = []
        if data["top"]:
            extra.append("En uzun araçlar: " + ", ".join(f"{n} {_fmt(s)}" for n, s in data["top"]))
        if data["failed"]:
            extra.append(f"Hatalı adım: {data['failed']}")
        if data["switches"]:
            extra.append(f"Motor değişimi: {data['switches']}")
        if extra:
            info = QLabel(" · ".join(extra))
            info.setProperty("role", "dim")
            info.setWordWrap(True)
            lay.addWidget(info)
