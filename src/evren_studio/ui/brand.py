"""Uygulama simgesi (ay-yıldız) ve canlı çalışma göstergesi.

AY-YILDIZ — Türk Bayrağı Kanunu oranları (G = bayrak genişliği):
  dış ay dairesi çapı 0,5 G · iç ay dairesi çapı 0,4 G · iç ay merkezi dış ay
  merkezinden 1/16 G sağda · yıldız dairesi çapı 1/4 G · dış ay merkezi ile
  yıldız dairesi arası 1/3 G · yıldızın bir ucu hilale bakar.
Arka plan YOKTUR (saydam). Renk temaya göre (kullanıcı isteği 2026-10-17):
  koyu tema → beyaz (bayraktaki gibi), açık tema → bayrak kırmızısı #E30A17.

ÇALIŞMA GÖSTERGESİ — `BusyStar`: model çalışırken dönen ve "nefes alan" beş
köşeli yıldız (Claude Code'daki canlı simgeye benzer). Görünmezken zamanlayıcı
durur, işlemci harcamaz.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QWidget

from . import theme

FLAG_RED = "#E30A17"
FLAG_WHITE = "#FFFFFF"

# Bayrak birimi G = 48 ile koordinatlar (dış ay merkezi = 0,0)
_G = 48.0
_R_OUT = 0.25 * _G                 # 12
_R_IN = 0.20 * _G                  # 9.6
_IN_DX = _G / 16                   # 3
_R_STAR = _G / 8                   # 6
_STAR_CX = _G / 3 + _R_STAR        # 22 (yıldız dairesinin sol kenarı merkezden 1/3 G)
# Küçük boyutlarda (≤32 px) yıldız hilalin ağzına yaklaştırılır; biçim ve oranlar
# aynı kalır, yalnız aradaki boşluk azalır → simge %20 büyür, 16 px'te okunur.
_STAR_CX_COMPACT = 15.5
COMPACT_MAX = 32


def brand_color(palette: theme.Palette | None = None) -> str:
    p = palette or theme.current()
    return FLAG_WHITE if p.name == "koyu" else FLAG_RED


def star_path(cx: float, cy: float, r: float, angle_deg: float = 180.0) -> QPainterPath:
    """Beş köşeli yıldız; ilk uç `angle_deg` yönünde (180 = sola, hilale doğru)."""
    inner = r * 0.381966   # düzenli beş köşeli yıldız iç/dış oranı
    path = QPainterPath()
    for i in range(10):
        rr = r if i % 2 == 0 else inner
        a = math.radians(angle_deg + i * 36)
        pt = QPointF(cx + rr * math.cos(a), cy + rr * math.sin(a))
        if i == 0:
            path.moveTo(pt)
        else:
            path.lineTo(pt)
    path.closeSubpath()
    return path


def crescent_star_path(size: float, margin: float = 0.06, compact: bool = False) -> QPainterPath:
    """`size`×`size` tuvalde ortalanmış ay-yıldız yolu (bayrak oranlarıyla)."""
    star_cx = _STAR_CX_COMPACT if compact else _STAR_CX
    box_x0, box_w = -_R_OUT, star_cx + _R_STAR + _R_OUT
    usable = size * (1 - 2 * margin)
    k = usable / box_w
    ox = size * margin - box_x0 * k                  # dış ay merkezinin x'i
    oy = size / 2
    outer = QPainterPath()
    outer.addEllipse(QPointF(ox, oy), _R_OUT * k, _R_OUT * k)
    inner = QPainterPath()
    inner.addEllipse(QPointF(ox + _IN_DX * k, oy), _R_IN * k, _R_IN * k)
    path = outer.subtracted(inner)
    path.addPath(star_path(ox + star_cx * k, oy, _R_STAR * k))
    path.setFillRule(Qt.WindingFill)
    return path


def pixmap(size: int = 32, color: str | None = None, ratio: float = 2.0) -> QPixmap:
    px = QPixmap(int(size * ratio), int(size * ratio))
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color or brand_color()))
    p.drawPath(crescent_star_path(size * ratio, compact=size <= COMPACT_MAX))
    p.end()
    px.setDevicePixelRatio(ratio)
    return px


def app_icon(color: str | None = None) -> QIcon:
    """Pencere/görev çubuğu simgesi: birden çok boyut, saydam zemin."""
    ic = QIcon()
    for s in (16, 20, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(pixmap(s, color, ratio=1.0))
    return ic


ICO_SIZES = (16, 20, 24, 32, 48, 64, 128, 256)


def save_ico(path: str, color: str = FLAG_RED) -> bool:
    """Masaüstü kısayolu / görev çubuğu için çok boyutlu, saydam .ico yazar.

    Her boyut ayrı çizilir (≤32 px sıkı yerleşim); girdiler PNG olarak gömülür
    (Windows Vista+ ICO biçimi). Renk: masaüstü zemini bilinmediği için kırmızı.
    """
    import struct

    from PySide6.QtCore import QBuffer, QByteArray, QIODevice

    blobs = []
    for s in ICO_SIZES:
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.WriteOnly)
        if not pixmap(s, color, ratio=1.0).toImage().save(buf, "PNG"):
            return False
        buf.close()
        blobs.append((s, bytes(data)))
    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries, payload = b"", b""
    for s, png in blobs:
        dim = 0 if s >= 256 else s
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset + len(payload))
        payload += png
    with open(path, "wb") as f:
        f.write(header + entries + payload)
    return True


class BusyStar(QWidget):
    """Model çalışırken dönen ve nefes alan beş köşeli yıldız."""

    FPS = 30

    def __init__(self, size: int = 14, color: str | None = None, parent=None):
        super().__init__(parent)
        self._size = size
        self._color = color
        self._angle = 0.0
        self._phase = 0.0
        self.setFixedSize(QSize(size, size))
        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / self.FPS))
        self._timer.timeout.connect(self._advance)

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    @property
    def running(self) -> bool:
        return self._timer.isActive()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self.start()

    def hideEvent(self, e) -> None:
        self.stop()
        super().hideEvent(e)

    def _advance(self) -> None:
        self._angle = (self._angle + 4.0) % 360          # ~3 sn'de tam tur
        self._phase = (self._phase + 2 * math.pi / (self.FPS * 1.4)) % (2 * math.pi)
        self.update()

    def paintEvent(self, _e) -> None:
        s = float(self._size)
        pulse = 0.5 + 0.5 * math.sin(self._phase)         # 0..1
        r = s / 2 * (0.78 + 0.22 * pulse)
        color = QColor(self._color or brand_color())
        color.setAlphaF(0.65 + 0.35 * pulse)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawPath(star_path(s / 2, s / 2, r, 270 + self._angle))
        p.end()
