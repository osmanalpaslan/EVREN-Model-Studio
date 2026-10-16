"""Fare tekerleği koruması.

Qt'de sayı kutuları (QSpinBox), açılır listeler (QComboBox) ve kaydırıcılar,
fare yalnızca üzerinden geçerken bile tekerlekle değer değiştirir. Uzun
Ayarlar sayfasında aşağı kaydırırken ayarlar farkında olmadan değişiyordu.

Bu filtre uygulama genelinde çalışır: alan odakta (tıklanmış) değilse
tekerlek olayı alana değil, kaydırma alanına iletilir; sayfa kayar, değer
değişmez. Alana tıklandıktan sonra tekerlek bilinçli kullanım sayılır.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QAbstractSlider,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QScrollBar,
    QWidget,
)

GUARDED = (QAbstractSpinBox, QComboBox, QAbstractSlider)


def _scroll_target(w: QWidget) -> QWidget | None:
    p = w.parentWidget()
    while p is not None:
        if isinstance(p, QAbstractScrollArea):
            return p.viewport()
        p = p.parentWidget()
    return None


class WheelGuard(QObject):
    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt adı)
        if event.type() == QEvent.Wheel and isinstance(obj, GUARDED):
            # Kaydırma çubuğu da bir QAbstractSlider'dır; ona dokunma.
            if isinstance(obj, QScrollBar):
                return False
            if not obj.hasFocus():
                target = _scroll_target(obj)
                if target is not None:
                    QApplication.sendEvent(target, event)
                return True
        if event.type() == QEvent.Polish and isinstance(obj, GUARDED):
            # Tekerlekle odak kazanılmasın (Qt.WheelFocus yerine StrongFocus)
            if obj.focusPolicy() == Qt.WheelFocus:
                obj.setFocusPolicy(Qt.StrongFocus)
        return False


_guard: WheelGuard | None = None


def install(app: QApplication) -> WheelGuard:
    global _guard
    if _guard is None:
        _guard = WheelGuard(app)
        app.installEventFilter(_guard)
    return _guard
