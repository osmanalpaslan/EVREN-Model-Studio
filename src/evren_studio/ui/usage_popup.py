"""Model seçicinin yanındaki kullanım düğmesi ve grafikli açıklama paneli.

Düğme, EVREN günlük token kotasından KALAN yüzdeyi küçük bir halka ile
gösterir; tıklanınca panel açılır:
- Günlük kullanım (halka grafik): kalan / kullanılan / sıfırlanma saati
- 5 dakikalık hız penceresi (çubuk): kısa sürede çok token kullanılırsa beklenir
- Kredi: kalan ve devam eden istekler için ayrılmış (held) kredi
- Bu oturumun token kullanımı (yanıtlardaki usage alanlarından)
- Ücretli sağlayıcı seçiliyse bu ayki TAHMİNİ harcama / bütçe

Veri `GET /v1/quota` yanıtıdır (gerçek API alanları, 2026-10-19); ağ isteğini
SessionView arka planda yapar (R-04), burası yalnızca çizer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import theme

# docs/knowledge/MODEL_CAPABILITIES.md "Fiyat" (2026-10-15 snapshot): free_until
FREE_UNTIL = "1 Kasım 2026"
FREE_UNTIL_DATE = date(2026, 11, 1)

LEVEL_TEXT = {
    "ok": ("Normal", "Sınırlar rahat; istekler beklemeden işlenir."),
    "warn": ("Yoğun", "Sınıra yaklaşıldı; yanıtlar yavaşlayabilir."),
    "warning": ("Yoğun", "Sınıra yaklaşıldı; yanıtlar yavaşlayabilir."),
    "critical": ("Kritik", "Sınır dolmak üzere veya doldu; istekler reddedilebilir."),
    "throttled": ("Yavaşlatıldı", "Kısa süreli sınır doldu; istekler bekletiliyor."),
    "limited": ("Sınırda", "Sınır doldu; sıfırlanana kadar istekler reddedilebilir."),
    "exceeded": ("Sınır aşıldı", "Sıfırlanana kadar yeni istekler reddedilir."),
}


@dataclass
class UsageSnapshot:
    quota: object | None = None             # api.client.QuotaInfo
    error: str = ""
    session_in: int = 0
    session_out: int = 0
    paid_name: str = ""                     # seçili model ücretliyse sağlayıcı adı
    paid_spent: float = 0.0
    paid_limit: float = 0.0
    updated: datetime | None = None
    extra: dict = field(default_factory=dict)


# ---- biçimlendirme -----------------------------------------------------------------


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fmt_tokens(n: float | None) -> str:
    if n is None:
        return "?"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f} M".replace(".", ",")
    if n >= 10_000:
        return f"{n / 1000:.1f} B".replace(".", ",")
    return f"{int(n):,}".replace(",", ".")


def fmt_cr(v) -> str:
    n = _num(v)
    if n is None:
        return str(v)
    return (f"{n:,.0f}" if n == int(n) else f"{n:,.2f}").replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(r: float) -> str:
    v = r * 100
    s = f"{v:.1f}" if 0 < v < 10 or 90 < v < 100 else f"{v:.0f}"
    return "%" + s.replace(".", ",")


def fmt_time(iso: str | None, with_day: bool = False) -> str:
    if not iso:
        return "?"
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return str(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone()
    now = datetime.now().astimezone()
    if not with_day or local.date() == now.date():
        prefix = "bugün " if with_day else ""
    elif (local.date() - now.date()).days == 1:
        prefix = "yarın "
    else:
        prefix = local.strftime("%d.%m ")
    return prefix + local.strftime("%H:%M")


def daily_ratio(q) -> float | None:
    """Günlük kotanın KULLANILAN oranı (0–1)."""
    used, limit = _num(getattr(q, "daily_used_tokens", None)), _num(getattr(q, "daily_limit_tokens", None))
    if used is None or not limit:
        return None
    return max(0.0, min(1.0, used / limit))


def window_ratio(q) -> float | None:
    r = _num(getattr(q, "usage_ratio", None))
    if r is not None:
        return max(0.0, min(1.0, r))
    used, cap = _num(getattr(q, "used_tokens", None)), _num(getattr(q, "cap", None))
    return max(0.0, min(1.0, used / cap)) if used is not None and cap else None


def ratio_color(used: float) -> str:
    p = theme.current()
    if used >= 0.9:
        return p.danger
    if used >= 0.7:
        return p.warning
    return p.success


# ---- grafikler ----------------------------------------------------------------------


def ring_pixmap(remaining: float | None, color: str, size: int = 16) -> QPixmap:
    ratio = 2
    px = QPixmap(size * ratio, size * ratio)
    px.setDevicePixelRatio(ratio)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    w = 2.6
    rect = QRectF(w / 2 + 0.5, w / 2 + 0.5, size - w - 1, size - w - 1)
    p.setPen(QPen(QColor(theme.current().border_strong), w))
    p.drawEllipse(rect)
    if remaining is not None:
        pen = QPen(QColor(color), w)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 90 * 16, int(-360 * 16 * remaining))
    p.end()
    return px


class Donut(QWidget):
    """Halka grafik: dolu kısım KALAN oran; ortada yüzde."""

    def __init__(self, size: int = 92, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.remaining: float | None = None
        self.color = theme.current().success

    def set_value(self, remaining: float | None, color: str) -> None:
        self.remaining, self.color = remaining, color
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = 9
        rect = QRectF(w / 2 + 1, w / 2 + 1, self.width() - w - 2, self.height() - w - 2)
        pal = theme.current()
        p.setPen(QPen(QColor(pal.border), w))
        p.drawEllipse(rect)
        if self.remaining is not None:
            pen = QPen(QColor(self.color), w)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawArc(rect, 90 * 16, int(-360 * 16 * self.remaining))
        p.setPen(QColor(pal.text))
        f = QFont(self.font())
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() + 2)
        p.setFont(f)
        txt = fmt_pct(self.remaining) if self.remaining is not None else "?"
        p.drawText(rect.adjusted(0, -8, 0, -8), Qt.AlignCenter, txt)
        f.setBold(False)
        f.setPointSizeF(f.pointSizeF() - 3.5)
        p.setFont(f)
        p.setPen(QColor(pal.text_dim))
        p.drawText(rect.adjusted(0, 16, 0, 16), Qt.AlignCenter, "kalan")
        p.end()


class Meter(QWidget):
    """İnce yatay çubuk: dolu kısım KULLANILAN oran."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self.used: float | None = None
        self.color = theme.current().success

    def set_value(self, used: float | None, color: str) -> None:
        self.used, self.color = used, color
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.current().border))
        p.drawRoundedRect(r, 4, 4)
        if self.used:
            p.setBrush(QColor(self.color))
            p.drawRoundedRect(QRectF(0, 0, max(8.0, self.width() * self.used), self.height()), 4, 4)
        p.end()


def _dim(text: str, faint: bool = False) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setProperty("role", "faint" if faint else "dim")
    return lab


def _title(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setStyleSheet("font-weight: 600;")
    return lab


# ---- panel -------------------------------------------------------------------------


class UsagePanel(QFrame):
    refresh_requested = Signal()
    details_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setObjectName("UsagePanel")
        self.setFixedWidth(360)
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(16, 14, 16, 12)
        self.root.setSpacing(10)
        self.body = QWidget()
        self.body_l = QVBoxLayout(self.body)
        self.body_l.setContentsMargins(0, 0, 0, 0)
        self.body_l.setSpacing(10)
        self.root.addWidget(self.body)
        foot = QHBoxLayout()
        self.updated = _dim("", faint=True)
        foot.addWidget(self.updated, 1)
        self.refresh_btn = QPushButton("Yenile")
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        foot.addWidget(self.refresh_btn)
        more = QPushButton("Ayrıntılar")
        more.clicked.connect(lambda: (self.hide(), self.details_requested.emit()))
        foot.addWidget(more)
        self.root.addLayout(foot)

    def _clear(self) -> None:
        while self.body_l.count():
            item = self.body_l.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
            elif item.layout() is not None:
                lay = item.layout()
                while lay.count():
                    sub = lay.takeAt(0).widget()
                    if sub is not None:
                        sub.setParent(None)
                        sub.deleteLater()

    def show_loading(self) -> None:
        self.refresh_btn.setEnabled(False)
        self.updated.setText("Güncelleniyor…")

    def set_snapshot(self, s: UsageSnapshot) -> None:
        self.refresh_btn.setEnabled(True)
        self._clear()
        pal = theme.current()
        q = s.quota
        head = QHBoxLayout()
        head.addWidget(_title("EVREN kullanımı"), 1)
        if q is not None:
            level = str(getattr(q, "level", "") or "")
            name, _desc = LEVEL_TEXT.get(level, (level or "?", ""))
            badge = QLabel(name)
            badge.setObjectName("UsageBadge")
            col = pal.success if level == "ok" else pal.warning if level in ("warn", "warning") else pal.danger
            badge.setStyleSheet(f"color: {col}; border: 1px solid {col}; border-radius: 9px; "
                                f"padding: 1px 8px; font-weight: 600;")
            head.addWidget(badge)
        self.body_l.addLayout(head)

        if q is None:
            self.body_l.addWidget(_dim("Kota bilgisi alınamadı" + (f": {s.error}" if s.error else ".")
                                       + " İnternet bağlantınızı ve API anahtarınızı kontrol edip "
                                         "Yenile'ye basın."))
        else:
            level = str(getattr(q, "level", "") or "")
            if LEVEL_TEXT.get(level):
                self.body_l.addWidget(_dim(LEVEL_TEXT[level][1], faint=True))
            # günlük
            used_r = daily_ratio(q)
            row = QHBoxLayout()
            row.setSpacing(14)
            donut = Donut()
            donut.set_value(None if used_r is None else 1 - used_r, ratio_color(used_r or 0))
            row.addWidget(donut)
            col = QVBoxLayout()
            col.setSpacing(3)
            col.addWidget(_title("Günlük token kotası"))
            col.addWidget(_dim(f"Kalan: {fmt_tokens(_num(q.daily_remaining_tokens))} token"))
            col.addWidget(_dim(f"Kullanılan: {fmt_tokens(_num(q.daily_used_tokens))} / "
                               f"{fmt_tokens(_num(q.daily_limit_tokens))}"))
            col.addWidget(_dim(f"Sıfırlanma: {fmt_time(q.daily_reset_at, with_day=True)}", faint=True))
            col.addStretch(1)
            row.addLayout(col, 1)
            self.body_l.addLayout(row)
            self.body_l.addWidget(_dim("Günlük sınır dolarsa yeni istekler sıfırlanma saatine kadar "
                                       "reddedilir. Uzun ajan görevleri ve büyük dosyalar daha çok "
                                       "token harcar.", faint=True))
            # 5 dk pencere
            wr = window_ratio(q)
            minutes = getattr(q, "window_minutes", None) or 5
            self.body_l.addWidget(_title(f"{minutes} dakikalık hız penceresi"))
            meter = Meter()
            meter.set_value(wr, ratio_color(wr or 0))
            self.body_l.addWidget(meter)
            self.body_l.addWidget(_dim(
                f"{fmt_tokens(_num(q.used_tokens))} / {fmt_tokens(_num(q.cap))} token "
                f"({fmt_pct(wr or 0)}) · yenilenme {fmt_time(q.reset_at)}"))
            self.body_l.addWidget(_dim("Kısa sürede çok token kullanılırsa pencere yenilenene kadar "
                                       "birkaç dakika beklemek gerekebilir.", faint=True))
            # kredi
            self.body_l.addWidget(_title("Kredi"))
            self.body_l.addWidget(_dim(f"Kalan: {fmt_cr(q.remaining_cr)} cr · Ayrılmış (held): "
                                       f"{fmt_cr(q.held_cr)} cr"))
            if datetime.now().date() < FREE_UNTIL_DATE:
                self.body_l.addWidget(_dim(f"EVREN modellerinin fiyatı şu an 0 cr/token (ücretsiz dönem "
                                           f"{FREE_UNTIL}'e kadar): kullanım krediden düşmez, yalnız "
                                           "token kotası sayılır.", faint=True))
            else:
                self.body_l.addWidget(_dim("Ücretsiz dönem bitti; güncel fiyatlar için Modeller "
                                           "sayfasına bakın.", faint=True))
        # oturum
        if s.session_in or s.session_out:
            self.body_l.addWidget(_title("Bu oturum"))
            self.body_l.addWidget(_dim(f"Girdi {fmt_tokens(s.session_in)} · Çıktı "
                                       f"{fmt_tokens(s.session_out)} token"))
        # ücretli
        if s.paid_name:
            from ..budget import format_usd

            self.body_l.addWidget(_title(f"{s.paid_name} — bu ay (tahmini)"))
            r = s.paid_spent / s.paid_limit if s.paid_limit else 0
            meter = Meter()
            meter.set_value(min(1.0, r), ratio_color(r))
            self.body_l.addWidget(meter)
            self.body_l.addWidget(_dim(f"{format_usd(s.paid_spent)} / {format_usd(s.paid_limit)} "
                                       "aylık bütçe (tüm ücretli sağlayıcılar). Gerçek tutar için "
                                       "sağlayıcı panelinize bakın."))
        self.updated.setText("Son güncelleme " + (s.updated.strftime("%H:%M:%S") if s.updated else "—"))
        self.adjustSize()


class UsageChip(QToolButton):
    """Model seçicinin yanındaki küçük düğme: halka + kalan günlük yüzde."""

    refresh_requested = Signal()
    details_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("variant", "chip")
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(15, 15))
        self.setCursor(Qt.PointingHandCursor)
        self.snapshot = UsageSnapshot()
        self.panel = UsagePanel(self)
        self.panel.refresh_requested.connect(self._refresh)
        self.panel.details_requested.connect(self.details_requested.emit)
        self.clicked.connect(self.open_panel)
        self.set_snapshot(UsageSnapshot())

    def _refresh(self) -> None:
        self.panel.show_loading()
        self.refresh_requested.emit()

    def set_snapshot(self, s: UsageSnapshot) -> None:
        self.snapshot = s
        q = s.quota
        used = daily_ratio(q) if q is not None else None
        if used is None:
            self.setIcon(ring_pixmap(None, theme.current().text_faint))
            self.setText("Kullanım")
            self.setToolTip("EVREN kullanımı: " + (s.error or "henüz alınmadı") + " — ayrıntı için tıklayın")
        else:
            wr = window_ratio(q) or 0
            color = ratio_color(max(used, wr if wr >= 0.8 else 0))
            self.setIcon(ring_pixmap(1 - used, color))
            self.setText(fmt_pct(1 - used))
            self.setToolTip(f"Günlük kotadan kalan: {fmt_pct(1 - used)} "
                            f"({fmt_tokens(_num(q.daily_remaining_tokens))} token) — ayrıntı için tıklayın")
        if self.panel.isVisible():
            self.panel.set_snapshot(s)

    def open_panel(self) -> None:
        self.panel.set_snapshot(self.snapshot)
        self.panel.adjustSize()
        g = self.mapToGlobal(QPoint(0, 0))
        x = g.x() + self.width() - self.panel.width()
        x = max(8, x)
        y = g.y() - self.panel.sizeHint().height() - 6     # yazma kutusunun ÜSTÜNDE açılır
        self.panel.move(x, max(8, y))
        self.panel.show()
        self._refresh()
