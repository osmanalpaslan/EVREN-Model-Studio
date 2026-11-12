"""Ekran geçişleri (2026-11-12, kullanıcı onayı "ekran geçişlerinde yumuşak animasyon").

iOS hissi: kısa (≈0,2 sn), yumuşak çapraz geçiş + yeni sayfanın birkaç piksel aşağıdan "yerine oturması".
Yöntem: geçişten hemen önce eski görünümün anlık görüntüsü (grab) alınır, yeni sayfaya geçilir, görüntü üstte saydamlaşarak
kaybolur. Opaklık efekti yalnız TEK bir resim etiketinde (karmaşık sayfaya efekt uygulanmaz: çizim maliyeti düşük, metin
kutuları bozulmaz). Katman fare olaylarını GEÇİRİR: yeni sayfa hemen kullanılabilir; sayfa geçişi (currentWidget) anında
olur, yalnız görünüm canlandırılır.
Windows'ta "animasyonları göster" kapalıysa ve testte (EVREN_STUDIO_NO_ANIM) geçiş anında olur (brand.animations_enabled).
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QEvent, QPoint, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsOpacityEffect, QStackedWidget, QWidget

from . import brand, theme

OVERLAY_NAME = "GecisKatmani"
FADE_MS = 200
RISE_PX = 8


@dataclass
class Snapshot:
    old: QWidget
    pixmap: QPixmap


class Overlay(QWidget):
    """Eski görünümün görüntüsü; yığının TAMAMINI kaplar ve yığın boyu değişince ona uyar (2026-11-12: sayfaya geçerken
    sağ panel gizlenip orta alan genişliyordu; yalnız eski genişliği kaplayan görüntünün sağında yeni sayfa hemen
    beliriyordu). Görüntünün kaplamadığı yer zemin rengiyle dolar; fare olaylarını geçirir."""

    def __init__(self, stack: QStackedWidget, snap: Snapshot):
        super().__init__(stack)
        self.setObjectName(OVERLAY_NAME)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.snapshot = snap.pixmap
        self._at = snap.old.geometry().topLeft()
        self._bg = QColor(theme.current().bg)
        self.setGeometry(stack.rect())
        stack.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Resize and isinstance(obj, QWidget):
            self.setGeometry(obj.rect())
        return False

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), self._bg)
        p.drawPixmap(self._at, self.snapshot)
        p.end()


def can_animate(stack: QStackedWidget) -> bool:
    cur = stack.currentWidget()
    return (brand.animations_enabled() and stack.isVisible() and cur is not None and cur.isVisible()
            and stack.width() > 1 and stack.height() > 1)


def begin(stack: QStackedWidget) -> Snapshot | None:
    """Geçişten ÖNCE çağrılır: o an görünen sayfanın görüntüsü (canlandırılamıyorsa None)."""
    if not can_animate(stack):
        return None
    cur = stack.currentWidget()
    return Snapshot(cur, cur.grab())


def _set(stack: QStackedWidget, target: QWidget | int) -> QWidget | None:
    if isinstance(target, int):
        stack.setCurrentIndex(target)
    else:
        stack.setCurrentWidget(target)
    return stack.currentWidget()


def finish(snap: Snapshot | None, stack: QStackedWidget, target: QWidget | int, *, ms: int = FADE_MS,
           rise: int = RISE_PX, force: bool = False, defer: bool = False) -> Overlay | None:
    """Sayfayı değiştirir; anlık görüntü varsa üstte saydamlaşarak kaybolur. `force`: aynı sayfada da canlandır (ör. başka
    oturum açılınca akışın içeriği değişir). `defer`: eski uyumluluk; canlandırma her zaman ağır iş (sayfanın ilk düzeni,
    geçmiş çizimi) bittikten sonraki olay turunda başlar."""
    new = _set(stack, target)
    if snap is None or new is None or (new is snap.old and not force) or snap.pixmap.isNull():
        return None
    overlay = Overlay(stack, snap)
    effect = QGraphicsOpacityEffect(overlay)
    effect.setOpacity(1.0)
    overlay.setGraphicsEffect(effect)
    overlay.show()
    overlay.raise_()
    fade = QPropertyAnimation(effect, b"opacity", overlay)
    fade.setDuration(ms)
    fade.setStartValue(1.0)
    fade.setEndValue(0.0)
    fade.setEasingCurve(QEasingCurve.OutCubic)
    fade.finished.connect(overlay.deleteLater)
    slide = None
    if rise and new is not snap.old:
        end = new.pos()
        start = end + QPoint(0, rise)
        # Sayfaya bağlı ve bitince kendini siler: katman (görüntü) silinse de sayfa yerine oturur
        slide = QPropertyAnimation(new, b"pos", new)
        slide.setDuration(ms)
        slide.setStartValue(start)
        slide.setEndValue(end)
        slide.setEasingCurve(QEasingCurve.OutCubic)
        new.move(start)

    def run() -> None:
        fade.start()
        if slide is not None:
            slide.start(QAbstractAnimation.DeleteWhenStopped)

    # Canlandırma HER ZAMAN bir sonraki olay turunda başlar: yeni sayfanın ilk düzeni/çizimi (ilk açılışta ~250 ms)
    # o turda biter; Qt animasyon saatini ilk zamanlayıcı olayından işlettiği için hemen başlatılırsa ilk kareler
    # kayboluyordu (ölçüldü). Bu sürede eski görüntü üstte durur, sonra yumuşakça kaybolur.
    QTimer.singleShot(0, overlay, run)
    return overlay


def switch(stack: QStackedWidget, target: QWidget | int, **kw) -> Overlay | None:
    """Tek adım: görüntü al + geç + canlandır."""
    return finish(begin(stack), stack, target, **kw)
