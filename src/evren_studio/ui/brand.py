"""Uygulama markası: ay-yıldız, uygulama simgesi (cam karo) ve canlı animasyonlar.

AY-YILDIZ — Türk Bayrağı Tüzüğü ölçüleri (G = bayrağın genişliği):
  A ay dış merkezinin uçkurluktan uzaklığı 1/2 G · B dış ay dairesi çapı 0,5 G · C ay iç ve dış daireleri
  merkezleri arası 1/16 G · D ay iç dairesi çapı 0,4 G · E yıldız dairesinin ay iç dairesinden uzaklığı 1/3 G ·
  F yıldız dairesi çapı 1/4 G · yıldızın bir ucu aya bakar.
  E, resmî çizimde iç ay dairesinin SOL kenarından yıldız dairesinin SOL kenarına ölçülür. Wikimedia "Flag of
  Turkey" SVG'si (G = 60000) ile doğrulandı: dış ay merkezi x = 30000, iç ay merkezi 33750, yıldızın aya bakan ucu
  41750 → yıldız merkezi uçkurluktan 0,8208 G, dış ay merkezinden 0,3208 G.
  DÜZELTME (2026-11-12): eski kod E'yi DIŞ ay merkezinden ölçüyordu; büyük boyutlarda yıldız 0,1375 G fazla
  uzaktaydı (≤32 px'teki "sıkı" yerleşim rastlantıyla doğruya yakındı). Artık her boyutta aynı, yasal geometri.

UYGULAMA SİMGESİ (2026-11-12, iOS 27 "Liquid Glass" dili): yuvarlatılmış kare (süperelips, iOS simge biçimi)
bayrak kırmızısı #E30A17 çevresinde hafif geçişli zemin, üstünde bayraktaki gibi BEYAZ ay-yıldız; üst yarıda cam
ışığı ve ince belirgin kenar (iOS 27: gölge yerine tanımlı kenar). Pencere/görev çubuğu, .ico, kurulum sihirbazı,
kenar çubuğu ve yanıt başlığında aynı simge.

SAYDAM İŞARET (`pixmap`): zeminsiz ay-yıldız; renk temaya göre (kullanıcı isteği 2026-10-17): koyu tema → beyaz,
açık tema → bayrak kırmızısı.

ANİMASYONLAR: `BrandMark` karşılama logosu — halka kayarak hilale dönüşür (iç ay dairesi 1/16 G'ye kayar), yıldız
72° dönerek (yıldızın kendi simetrisi: son hâli yine yasal yön) yerine oturur, camdan ışık geçer; sonra hafif nefes
alan ışıma. `BusyStar` çalışma göstergesi — yıldız 72° adımlarla parıldayarak döner. Windows'ta "animasyonları
göster" kapalıysa (erişilebilirlik) animasyon oynatılmaz, son hâl çizilir. Görünmezken zamanlayıcı durur.
"""
from __future__ import annotations

import math
import os
import time

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import QWidget

from . import theme

FLAG_RED = "#E30A17"
FLAG_WHITE = "#FFFFFF"
# Cam karo zemini: bayrak kırmızısı ortada, üstte bir ton açık, altta bir ton koyu (geçiş kırmızının çevresinde kalır)
TILE_TOP = "#F2323F"
TILE_BOTTOM = "#C5081A"

# Bayrak birimi G = 48 ile koordinatlar (dış ay merkezi = 0,0)
_G = 48.0
_R_OUT = 0.25 * _G                 # 12   — B/2
_R_IN = 0.20 * _G                  # 9,6  — D/2
_IN_DX = _G / 16                   # 3    — C
_R_STAR = _G / 8                   # 6    — F/2
_E = _G / 3                        # 16   — E: iç ay dairesinin sol kenarı → yıldız dairesinin sol kenarı
_STAR_CX = _IN_DX - _R_IN + _E + _R_STAR    # 15,4 = 0,3208 G (dış ay merkezinden yıldız merkezine)
_MARK_W = _STAR_CX + _R_STAR + _R_OUT       # işaretin genişliği (dış ayın sol kenarı → yıldızın sağ ucu)


def brand_color(palette: theme.Palette | None = None) -> str:
    p = palette or theme.current()
    return FLAG_WHITE if p.name == "koyu" else FLAG_RED


def animations_enabled() -> bool:
    """Windows "animasyonları göster" ayarı (SPI_GETCLIENTAREAANIMATION); testlerde EVREN_STUDIO_NO_ANIM=1."""
    if os.environ.get("EVREN_STUDIO_NO_ANIM"):
        return False
    if os.name != "nt":
        return True
    try:
        import ctypes

        val = ctypes.c_int(1)
        if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(val), 0):
            return bool(val.value)
    except (AttributeError, OSError):
        pass
    return True


# ---- geometri ------------------------------------------------------------------------------------------------------


def star_path(cx: float, cy: float, r: float, angle_deg: float = 180.0) -> QPainterPath:
    """Beş köşeli düzgün yıldız; ilk uç `angle_deg` yönünde (180 = sola, aya doğru)."""
    inner = r * 0.381966   # düzgün beş köşeli yıldızın iç/dış yarıçap oranı
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


def mark_path(ox: float, oy: float, k: float, inner_dx: float = _IN_DX, star_scale: float = 1.0,
              star_rot: float = 0.0) -> QPainterPath:
    """Dış ay merkezi (ox, oy), ölçek k (bayrak birimi → piksel). Animasyon için iç ay kayması, yıldız ölçeği ve
    dönüşü verilebilir; varsayılanlar yasal son hâldir."""
    outer = QPainterPath()
    outer.addEllipse(QPointF(ox, oy), _R_OUT * k, _R_OUT * k)
    inner = QPainterPath()
    inner.addEllipse(QPointF(ox + inner_dx * k, oy), _R_IN * k, _R_IN * k)
    path = outer.subtracted(inner)
    if star_scale > 0.001:
        path.addPath(star_path(ox + _STAR_CX * k, oy, _R_STAR * k * star_scale, 180.0 + star_rot))
    # Çift-tek kuralı: animasyonda iç ay dış ayın tam içindeyken (kayma < 0,05 G) sonuç HALKADIR; "winding" kuralı
    # halkanın içini de dolduruyordu. Yıldız aya değmez (yasal geometride en yakın uç iç ay dairesinin içinde kalır).
    path.setFillRule(Qt.OddEvenFill)
    return path


def crescent_star_path(size: float, margin: float = 0.06) -> QPainterPath:
    """`size`×`size` tuvalde ortalanmış ay-yıldız yolu (bayrak oranlarıyla, her boyutta aynı)."""
    k = size * (1 - 2 * margin) / _MARK_W
    return mark_path(size * margin + _R_OUT * k, size / 2, k)


def squircle_path(rect: QRectF, n: float = 5.0, steps: int = 160) -> QPainterPath:
    """iOS simge biçimine yakın süperelips (|x|^n + |y|^n = 1)."""
    cx, cy = rect.center().x(), rect.center().y()
    a, b = rect.width() / 2, rect.height() / 2
    path = QPainterPath()
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        pt = QPointF(cx + a * math.copysign(abs(c) ** (2 / n), c), cy + b * math.copysign(abs(s) ** (2 / n), s))
        if i == 0:
            path.moveTo(pt)
        else:
            path.lineTo(pt)
    path.closeSubpath()
    return path


# ---- çizim ---------------------------------------------------------------------------------------------------------


def paint_tile(p: QPainter, rect: QRectF, *, inner_dx: float = _IN_DX, star_scale: float = 1.0,
               star_rot: float = 0.0, sheen: float | None = None, mark_alpha: float = 1.0) -> None:
    """Cam karo: kırmızı süperelips + beyaz ay-yıldız + cam ışığı + ince kenar. `sheen` 0..1 → çapraz ışık geçişi."""
    s = rect.width()
    shape = squircle_path(rect)
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    bg = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    bg.setColorAt(0.0, QColor(TILE_TOP))
    bg.setColorAt(0.5, QColor(FLAG_RED))
    bg.setColorAt(1.0, QColor(TILE_BOTTOM))
    p.setBrush(bg)
    p.drawPath(shape)
    p.setClipPath(shape)
    # Cam ışığı: üst yarıda yumuşak beyaz
    light = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.top() + s * 0.62))
    light.setColorAt(0.0, QColor(255, 255, 255, 74))
    light.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setBrush(light)
    p.drawRect(rect)
    if sheen is not None and 0.0 < sheen < 1.0:
        # Çapraz ışık bandı sol üstten sağ alta geçer
        d = s * 2.2
        pos = -s * 0.8 + d * sheen
        band = QLinearGradient(QPointF(rect.left() + pos - s * 0.35, rect.top()),
                               QPointF(rect.left() + pos + s * 0.35, rect.top() + s * 0.7))
        band.setColorAt(0.0, QColor(255, 255, 255, 0))
        band.setColorAt(0.5, QColor(255, 255, 255, 92))
        band.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(band)
        p.drawRect(rect)
    # Ay-yıldız: küçük boyutlarda okunsun diye biraz daha büyük
    frac = 0.70 if s <= 24 else 0.64
    k = s * frac / _MARK_W
    ox = rect.left() + (s - _MARK_W * k) / 2 + _R_OUT * k
    oy = rect.center().y()
    white = QColor(FLAG_WHITE)
    white.setAlphaF(max(0.0, min(1.0, mark_alpha)))
    p.setBrush(white)
    p.drawPath(mark_path(ox, oy, k, inner_dx, star_scale, star_rot))
    p.setClipping(False)
    # Tanımlı kenar (iOS 27): üstte parlak, altta silik ince çizgi
    if s >= 20:
        rim = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        rim.setColorAt(0.0, QColor(255, 255, 255, 120))
        rim.setColorAt(1.0, QColor(255, 255, 255, 18))
        p.setPen(QPen(rim, max(1.0, s / 96), Qt.SolidLine))
        p.setBrush(Qt.NoBrush)
        inset = max(0.5, s / 192)
        p.drawPath(squircle_path(rect.adjusted(inset, inset, -inset, -inset)))
    p.restore()


_TILE_CACHE: dict[tuple[int, float], QPixmap] = {}


def tile_pixmap(size: int = 32, ratio: float = 2.0) -> QPixmap:
    """Cam karo simgesi (temadan bağımsız; önbellekli)."""
    key = (int(size), float(ratio))
    px = _TILE_CACHE.get(key)
    if px is None:
        px = QPixmap(int(size * ratio), int(size * ratio))
        px.fill(Qt.transparent)
        p = QPainter(px)
        paint_tile(p, QRectF(0, 0, size * ratio, size * ratio))
        p.end()
        px.setDevicePixelRatio(ratio)
        _TILE_CACHE[key] = px
    return px


def pixmap(size: int = 32, color: str | None = None, ratio: float = 2.0) -> QPixmap:
    """Zeminsiz ay-yıldız (renk temaya göre)."""
    px = QPixmap(int(size * ratio), int(size * ratio))
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color or brand_color()))
    p.drawPath(crescent_star_path(size * ratio))
    p.end()
    px.setDevicePixelRatio(ratio)
    return px


ICO_SIZES = (16, 20, 24, 32, 48, 64, 128, 256)


def app_icon() -> QIcon:
    """Pencere/görev çubuğu simgesi: cam karo, birden çok boyut."""
    ic = QIcon()
    for s in ICO_SIZES:
        ic.addPixmap(tile_pixmap(s, ratio=1.0))
    return ic


def save_ico(path: str) -> bool:
    """Masaüstü kısayolu / görev çubuğu için çok boyutlu .ico (cam karo; her boyut ayrı çizilir, PNG gömülü —
    Windows Vista+ ICO biçimi)."""
    import struct

    from PySide6.QtCore import QBuffer, QByteArray, QIODevice

    blobs = []
    for s in ICO_SIZES:
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.WriteOnly)
        if not tile_pixmap(s, ratio=1.0).toImage().save(buf, "PNG"):
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


# ---- yumuşatma eğrileri --------------------------------------------------------------------------------------------


def _clamp(t: float) -> float:
    return 0.0 if t < 0 else 1.0 if t > 1 else t


def ease_out_cubic(t: float) -> float:
    t = _clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    t = _clamp(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_back(t: float, s: float = 1.70158) -> float:
    t = _clamp(t)
    return 1 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2


def _phase(ms: float, start: float, dur: float) -> float:
    return _clamp((ms - start) / dur)


# ---- karşılama logosu ----------------------------------------------------------------------------------------------


class BrandMark(QWidget):
    """Canlı karşılama logosu: cam karo + ay-yıldız oluşumu + nefes alan ışıma.

    Zaman çizelgesi (ms): karo 0-450 (ölçek 0,82→1 geri sekmeli, saydamlık) · hilal 150-800 (iç ay 0 → 1/16 G kayar:
    halka hilale dönüşür) · yıldız 550-1150 (ölçek 0→1, dönüş -72°→0) · ışık 800-1300 · sonra ışıma (4 sn'lik nefes)."""

    INTRO_MS = 1300.0
    INTRO_FPS = 60
    IDLE_FPS = 12

    def __init__(self, size: int = 84, parent=None):
        super().__init__(parent)
        self._tile = size
        self.setFixedSize(QSize(int(size * 1.6), int(size * 1.6)))
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self._t0: float | None = None
        self._ms = self.INTRO_MS if not animations_enabled() else 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # -- durum --

    @property
    def intro_done(self) -> bool:
        return self._ms >= self.INTRO_MS

    @property
    def running(self) -> bool:
        return self._timer.isActive()

    def state(self, ms: float | None = None) -> dict[str, float]:
        """Verilen andaki çizim değerleri (test ve çizim aynı hesabı kullanır)."""
        ms = self._ms if ms is None else ms
        tile_t = _phase(ms, 0, 450)
        cres_t = _phase(ms, 150, 650)
        star_t = _phase(ms, 550, 600)
        sheen_t = _phase(ms, 800, 500)
        idle = max(0.0, ms - self.INTRO_MS) / 1000.0
        return {
            "scale": 0.82 + 0.18 * ease_out_back(tile_t, 1.2),
            "opacity": ease_out_cubic(tile_t),
            "inner_dx": _IN_DX * ease_in_out_cubic(cres_t),
            "star_scale": ease_out_back(star_t, 1.6) if star_t > 0 else 0.0,
            "star_rot": -72.0 * (1 - ease_out_cubic(star_t)),
            "sheen": sheen_t if 0 < sheen_t < 1 else -1.0,
            "glow": 0.30 * ease_out_cubic(_phase(ms, 300, 900)) + (0.08 * math.sin(2 * math.pi * idle / 4.0)
                                                                    if idle > 0 else 0.0),
        }

    def replay(self) -> None:
        """Animasyonu baştan oynatır (animasyon kapalıysa son hâl)."""
        self._ms = 0.0 if animations_enabled() else self.INTRO_MS
        self._t0 = None
        self._start()
        self.update()

    def _start(self) -> None:
        if not self.isVisible():
            return
        if not animations_enabled():
            self._ms = max(self._ms, self.INTRO_MS)
            self._timer.stop()
            return
        self._timer.setInterval(int(1000 / (self.IDLE_FPS if self.intro_done else self.INTRO_FPS)))
        if not self._timer.isActive():
            self._t0 = time.monotonic() - self._ms / 1000.0
            self._timer.start()

    def _tick(self) -> None:
        if self._t0 is None:
            self._t0 = time.monotonic() - self._ms / 1000.0
        was_intro = not self.intro_done
        self._ms = (time.monotonic() - self._t0) * 1000.0
        if was_intro and self.intro_done:
            self._timer.setInterval(int(1000 / self.IDLE_FPS))
        self.update()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self._start()

    def hideEvent(self, e) -> None:
        self._timer.stop()
        super().hideEvent(e)

    def paintEvent(self, _e) -> None:
        st = self.state()
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(w / 2, h / 2)
        # Işıma: karonun arkasında kırmızı hale
        if st["glow"] > 0.01:
            g = QRadialGradient(c, w / 2)
            red = QColor(FLAG_RED)
            red.setAlphaF(min(1.0, st["glow"]))
            g.setColorAt(0.0, red)
            red.setAlphaF(0.0)
            g.setColorAt(1.0, red)
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawEllipse(c, w / 2, h / 2)
        size = self._tile * st["scale"]
        p.setOpacity(st["opacity"])
        p.setTransform(QTransform())
        rect = QRectF(c.x() - size / 2, c.y() - size / 2, size, size)
        paint_tile(p, rect, inner_dx=st["inner_dx"], star_scale=st["star_scale"], star_rot=st["star_rot"],
                   sheen=st["sheen"] if st["sheen"] >= 0 else None)
        p.end()


# ---- çalışma göstergesi --------------------------------------------------------------------------------------------


class BusyStar(QWidget):
    """Model çalışırken parıldayan yıldız: 72° adımlarla döner (her adımda yıldız aynı yasal yöne oturur), dönüş
    sırasında büyüyüp parlar, adım arasında kısa durur. Görünmezken zamanlayıcı durur, işlemci harcamaz."""

    FPS = 30
    STEP_S = 0.75            # bir 72° dönüşün süresi
    HOLD_S = 0.45            # adımlar arası duruş

    def __init__(self, size: int = 14, color: str | None = None, parent=None):
        super().__init__(parent)
        self._size = size
        self._color = color
        self._frame = 0
        self._angle = 0.0
        self._glow = 0.0
        self.setFixedSize(QSize(size, size))
        self.setFocusPolicy(Qt.NoFocus)
        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / self.FPS))
        self._timer.timeout.connect(self._advance)

    def start(self) -> None:
        if not self._timer.isActive() and animations_enabled():
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

    @classmethod
    def pose(cls, t: float) -> tuple[float, float]:
        """t saniyede (açı derece, parıltı 0..1)."""
        cycle = cls.STEP_S + cls.HOLD_S
        n, rem = divmod(t, cycle)
        if rem < cls.STEP_S:
            u = rem / cls.STEP_S
            angle = 72.0 * (n + ease_in_out_cubic(u))
            glow = math.sin(math.pi * u)
        else:
            angle, glow = 72.0 * (n + 1), 0.0
        return angle % 360.0, glow

    def _advance(self) -> None:
        self._frame += 1
        self._angle, self._glow = self.pose(self._frame / self.FPS)
        self.update()

    def paintEvent(self, _e) -> None:
        s = float(self._size)
        r = s / 2 * (0.80 + 0.20 * self._glow)
        color = QColor(self._color or brand_color())
        color.setAlphaF(0.72 + 0.28 * self._glow)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        if self._glow > 0.05 and s >= 12:
            halo = QRadialGradient(QPointF(s / 2, s / 2), s / 2)
            hc = QColor(color)
            hc.setAlphaF(0.22 * self._glow)
            halo.setColorAt(0.0, hc)
            hc.setAlphaF(0.0)
            halo.setColorAt(1.0, hc)
            p.setBrush(halo)
            p.drawEllipse(QPointF(s / 2, s / 2), s / 2, s / 2)
        p.setBrush(color)
        p.drawPath(star_path(s / 2, s / 2, r, 180.0 + self._angle))
        p.end()
