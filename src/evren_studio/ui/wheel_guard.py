"""Fare tekerleği koruması.

Qt'de sayı kutuları (QSpinBox), açılır listeler (QComboBox) ve kaydırıcılar,
fare yalnızca üzerinden geçerken bile tekerlekle değer değiştirir. Uzun
Ayarlar sayfasında aşağı kaydırırken ayarlar farkında olmadan değişiyordu.

Alan odakta (tıklanmış) değilse tekerlek olayı alana değil, kaydırma alanına
iletilir; sayfa kayar, değer değişmez. Alana tıklandıktan sonra tekerlek
bilinçli kullanım sayılır.

PERFORMANS (2026-10-17): önceden UYGULAMA GENELİ olay filtresiydi; Python'da
yazıldığı için uygulamadaki HER olay (çizim, düzen, fare) Python'a gidip
geliyordu — 200 mesajlık oturum açılışında 69 bin çağrı (~10 sn), ekran
geçişlerinde %25 yavaşlık. Artık filtre yalnız korunan alanlara takılır:
`protect(kök)` pencere kurulunca ve her ekran açılışında çağrılır, yeni
eklenen alanlar da böylece kapsanır (R-12).
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
        # Yalnız korunan alanlara takılı olduğundan burada tür denetimi gerekmez.
        if event.type() == QEvent.Wheel and not obj.hasFocus():
            target = _scroll_target(obj)
            if target is not None:
                QApplication.sendEvent(target, event)
            return True
        return False


_guard: WheelGuard | None = None
_MARK = "_wheel_guard"


def _get_guard() -> WheelGuard:
    global _guard
    if _guard is None:
        _guard = WheelGuard(QApplication.instance())
    return _guard


def protect(root: QWidget) -> int:
    """`root` altındaki korunmamış sayı/liste/kaydırıcı alanlarını korur. Dönüş: yeni sayısı."""
    guard = _get_guard()
    n = 0
    for w in root.findChildren(QWidget):
        # Kaydırma çubuğu da bir QAbstractSlider'dır; ona dokunma.
        if not isinstance(w, GUARDED) or isinstance(w, QScrollBar) or w.property(_MARK):
            continue
        w.installEventFilter(guard)
        w.setProperty(_MARK, True)
        # Tekerlekle odak kazanılmasın (Qt.WheelFocus yerine StrongFocus)
        if w.focusPolicy() == Qt.WheelFocus:
            w.setFocusPolicy(Qt.StrongFocus)
        n += 1
    return n


def install(app: QApplication) -> WheelGuard:
    """Geriye uyumluluk: korumayı hazırlar (artık uygulama geneli filtre KURMAZ)."""
    return _get_guard()
