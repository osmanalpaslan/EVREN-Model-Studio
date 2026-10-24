"""Modeller sayfası: canlı liste, yetenekler, doğrulama ve sağlık durumu."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config import TASK_LABELS
from .base_page import BasePage, card
from .workers import Task


def _yes(v: bool) -> str:
    return "Evet" if v else "Hayır"


class ModelsPage(BasePage):
    title = "Modeller"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self.model_objects: dict[str, object] = {}

        c, l = card()
        l.addWidget(QLabel(
            "Canlı model listesi GET /v1/models ucundan alınır. Yetenekler "
            "sağlayıcının bildirdiği kayıt defteridir; bir modelin listede "
            "olması o anda sağlıklı olduğu anlamına gelmez."
        ))
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Model", "Görev", "Bağlam (token)", "Araç çağrısı", "Görsel",
            "Akış", "Ücretsizlik bitişi", "Son test", "Son hata",
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        l.addWidget(self.table)
        self.root.addWidget(c, 1)

        c2, l2 = card()
        l2.addWidget(QLabel("Seçili model yetenekleri"))
        self.detail = QLabel("Tablodan bir model seçin.")
        self.detail.setWordWrap(True)
        self.detail.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        l2.addWidget(self.detail)
        self.table.cellClicked.connect(self.show_detail)
        self.root.addWidget(c2)

        # ---- A12: Auto Pro gerçek kullanım özeti ----
        c3, l3 = card()
        l3.addWidget(QLabel("<b>Auto Pro — son 24 saat</b> (gerçek kullanımdan; motor hızı günden güne değişir)"))
        self.change_label = QLabel("")
        self.change_label.setWordWrap(True)
        self.change_label.setVisible(False)
        l3.addWidget(self.change_label)
        self.stats = QTableWidget(0, 8)
        self.stats.setHorizontalHeaderLabels([
            "Model", "Çağrı", "Hata", "Ortanca hız (token/sn)", "İlk yanıt (sn)", "Yedeğe geçiş", "Kalite", "Sıra durumu",
        ])
        self.stats.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.stats.setEditTriggers(QTableWidget.NoEditTriggers)
        self.stats.setMinimumHeight(140)
        l3.addWidget(self.stats)
        self.stats_hint = QLabel("Henüz kayıt yok: Auto Pro kullandıkça dolar.")
        self.stats_hint.setProperty("role", "dim")
        l3.addWidget(self.stats_hint)
        self.root.addWidget(c3)
        self.refresh_stats()

        self.refresh_btn = self._make_refresh_btn()
        self.header_extra.addWidget(self.refresh_btn)
        self.refresh_models()

    def _make_refresh_btn(self):
        from PySide6.QtWidgets import QPushButton

        b = QPushButton("Model Listesini Yenile")
        b.clicked.connect(self.refresh_models)
        return b

    def set_models(self, models: list) -> None:
        self.ctx.set_models(models)
        self.model_objects = {m.id: m for m in models}
        self.table.setRowCount(0)
        for m in models:
            row = self.table.rowCount()
            self.table.insertRow(row)
            health = self.ctx.db.get_model_health(m.id)
            caps = m.capabilities or {}
            values = [
                m.id,
                TASK_LABELS.get(m.task, m.task),
                f"{m.context_length:,}" if m.context_length else "-",
                _yes(m.supports_tools),
                _yes(m.supports_vision),
                _yes(m.supports_stream),
                m.free_until or "-",
                (health["last_test_at"][:16].replace("T", " ") + (
                    " ✓" if health["healthy"] else " ✗") if health else "test edilmedi"),
                (health["last_error"] or "-") if health else "-",
            ]
            for col, v in enumerate(values):
                item = QTableWidgetItem(str(v))
                if col in (3, 4, 5):
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)

    def refresh(self) -> None:
        """Sayfa her açıldığında yalnız kullanım özetini yeniler (ağ isteği yok)."""
        self.refresh_stats()

    def refresh_stats(self) -> None:
        from datetime import datetime, timezone

        from ..agent import modelstats, router

        try:
            rows = self.ctx.db.recent_model_calls(24)
            health = {r["model"]: dict(r) for r in self.ctx.db.all_model_health()}
        except Exception:
            rows, health = [], {}
        summ = modelstats.summary(rows)
        qual = modelstats.quality(rows)
        pen = modelstats.penalized(rows)
        now = datetime.now(timezone.utc)
        self.stats.setRowCount(0)
        for model, st in sorted(summ.items(), key=lambda kv: -kv[1]["calls"]):
            r = self.stats.rowCount()
            self.stats.insertRow(r)
            cooling = router._unhealthy(health, model, now)
            q = qual.get(model) or {}
            score = q.get("score")
            # A5: puan az örnekte gösterilir ama kural yalnız QUALITY_MIN_CALLS çağrıdan sonra işler
            kalite = "-" if score is None else f"{score:.2f}"
            durum = ("bekleme süresinde (sona alındı)" if cooling else
                     "kalite nedeniyle geride" if model in pen else "normal")
            vals = [model, st["calls"], f"%{int(st['error_rate'] * 100)}", st["tps"] or "-",
                    st["first_chunk_s"] or "-", st["switches"], kalite, durum]
            tips = {6: ", ".join(f"{k}: {n}" for k, n in sorted((q.get("events") or {}).items())) or "kalite olayı yok",
                    7: pen.get(model, "")}
            for col, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                if tips.get(col):
                    item.setToolTip(tips[col])
                if col:
                    item.setTextAlignment(Qt.AlignCenter)
                self.stats.setItem(r, col, item)
        self.stats_hint.setVisible(not summ)
        ch = getattr(self.ctx, "model_list_change", None)
        if ch and (ch[0] or ch[1]):
            self.change_label.setText("⚠ Model listesi değişti — kalkan: " + (", ".join(ch[0]) or "-")
                                      + " · eklenen: " + (", ".join(ch[1]) or "-")
                                      + ". Yeni modeller ölçülmeden Auto Pro sırasına girmez.")
            self.change_label.setVisible(True)

    def show_detail(self, row: int, _col: int) -> None:
        mid = self.table.item(row, 0).text()
        m = self.model_objects.get(mid)
        if not m:
            return
        caps = m.capabilities or {}
        lines = [
            f"Model: {m.id}",
            f"Görev türü: {TASK_LABELS.get(m.task, m.task)}",
            f"Modaliteler: {', '.join(m.modalities) or '-'}",
            f"Bağlam penceresi: {m.context_length or '-'} token",
            f"Varsayılan en fazla çıktı: {m.default_max_output_tokens or '-'}",
            f"Araç çağrısı (function calling): {_yes(m.supports_tools)}",
            f"Görsel girdi: {_yes(m.supports_vision)}",
            f"Yapılandırılmış çıktı (response_format): "
            f"{_yes(bool(caps.get('response_format')))}",
            f"reasoning_effort: {_yes(bool(caps.get('reasoning_effort')))}"
            + (f" ({', '.join(caps['reasoning_effort_values'])})"
               if caps.get("reasoning_effort_values") else ""),
            f"thinking anahtarı: {_yes(bool(caps.get('thinking')))}",
            f"seed/top_k/stop: {_yes(bool(caps.get('seed')))}/"
            f"{_yes(bool(caps.get('top_k')))}/{_yes(bool(caps.get('stop')))}",
            f"Fiyat: girdi {m.prompt_token_price} CR/token, çıktı "
            f"{m.completion_token_price} CR/token"
            + (f", {m.free_until} tarihine kadar ücretsiz" if m.free_until else ""),
            "",
            "Not: Yetenekler sağlayıcı kayıt defterinden gelir; kullanım "
            "sırasında model sağlıksızsa 503 'sağlıklı endpoint yok' hatası "
            "alınabilir. Bu durum sağlayıcı kaynaklıdır.",
        ]
        self.detail.setText("\n".join(lines))

    def refresh_models(self) -> None:
        self.refresh_btn.setEnabled(False)

        def job():
            client = self.ctx.make_client()
            try:
                return client.list_models()
            finally:
                client.close()

        def done(models):
            self.refresh_btn.setEnabled(True)
            self.set_models(models)

        def fail(exc):
            self.refresh_btn.setEnabled(True)
            self.table.setRowCount(0)
            self.detail.setText(
                f"Model listesi alınamadı: {exc}\n"
                "Bağlantı testi sayfasından durumu kontrol edin."
            )

        Task(job, on_done=done, on_error=fail).start()
