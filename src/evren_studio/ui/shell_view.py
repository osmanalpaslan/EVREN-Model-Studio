"""Terminal sekmesinin "Kabuk" görünümü (Madde 20 C4): agent/ptyshell.PtyShell'i çizer ve tuşları ona gönderir.

Ekran 50 ms'de bir (değiştiyse) yeniden çizilir; okuyucu iş parçacığı yalnız "değişti" işareti koyar (R-11: Qt bileşeni
yalnız ana iş parçacığından güncellenir). Kabuk ilk kez görünür olunca başlar, proje değişince yeniden başlar,
sekme/uygulama kapanınca süreç sonlandırılır.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontMetrics, QGuiApplication, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit

from ..agent import ptyshell
from . import theme


class ShellView(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TerminalView")
        self.setReadOnly(True)
        self.setFont(theme.code_font(9))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setUndoRedoEnabled(False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setPlaceholderText("Etkileşimli PowerShell (proje klasöründe). Buraya tıklayıp yazın.")
        self.root: str | None = None
        self.shell: ptyshell.PtyShell | None = None
        self._dirty = False
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._paint_if_dirty)
        from PySide6.QtCore import QCoreApplication

        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop)             # uygulama kapanırken kabuk süreci de kapanır

    # -- kabuk yaşamı --
    def set_root(self, root: str | None) -> None:
        if root == self.root:
            return
        self.root = root
        self.stop()
        if root and self.isVisible():
            self.start()

    def start(self) -> None:
        if self.shell is not None or not self.root:
            return
        if not ptyshell.available():
            self.setPlainText("Etkileşimli kabuk bu sistemde kullanılamıyor (pywinpty/pyte eksik). "
                              "Alttaki komut satırı çalışmaya devam eder.")
            return
        cols, rows = self._grid()
        sh = ptyshell.PtyShell(self.root, cols, rows, on_output=self._mark)
        try:
            sh.start()
        except Exception as exc:                           # ör. ConPTY yok (eski Windows)
            self.setPlainText(f"Kabuk başlatılamadı: {exc}")
            return
        self.shell = sh
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        sh, self.shell = self.shell, None
        if sh is not None:
            sh.close()
        self.clear()

    def restart(self) -> None:
        self.stop()
        self.start()

    def _mark(self) -> None:                               # okuyucu iş parçacığından: yalnız işaret
        self._dirty = True

    def _paint_if_dirty(self) -> None:
        if not self._dirty or self.shell is None:
            return
        self._dirty = False
        bar = self.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 2
        self.setPlainText("\n".join(self.shell.lines()))
        row, col = self.shell.cursor()
        doc = self.document()
        block = doc.findBlockByNumber(min(row, doc.blockCount() - 1))
        cur = QTextCursor(block)
        cur.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, min(col, max(0, block.length() - 1)))
        self.setTextCursor(cur)
        if at_bottom:
            bar.setValue(bar.maximum())

    def _grid(self) -> tuple[int, int]:
        fm = QFontMetrics(self.font())
        w = max(1, fm.horizontalAdvance("M"))
        h = max(1, fm.lineSpacing())
        vp = self.viewport().size()
        return max(40, vp.width() // w - 1), max(10, vp.height() // h)

    # -- Qt olayları --
    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.shell is None and self.root:
            QTimer.singleShot(0, self, self.start)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.shell is not None:
            self.shell.resize(*self._grid())

    def keyPressEvent(self, event) -> None:
        if self.shell is None:
            return super().keyPressEvent(event)
        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        if ctrl and event.key() == Qt.Key_C and self.textCursor().hasSelection():
            self.copy()                                    # seçim varken Ctrl+C kopyalar; yoksa komutu keser (\x03)
        elif ctrl and event.key() == Qt.Key_V:
            self.shell.write(QGuiApplication.clipboard().text().replace("\r\n", "\r").replace("\n", "\r"))
        else:
            seq = key_sequence(event.key(), event.modifiers(), event.text())
            if seq:
                self.shell.write(seq)
        event.accept()

    def focusNextPrevChild(self, _next: bool) -> bool:     # Tab tuşu odak değiştirmesin, kabuğa gitsin
        return False

    def closeEvent(self, event) -> None:
        self.stop()
        super().closeEvent(event)


def key_sequence(key, mods, text: str) -> str:
    """Qt tuşu → kabuğa gidecek dizi (Ctrl+V / seçimli Ctrl+C keyPressEvent'te ayrıca ele alınır)."""
    ctrl = bool(mods & Qt.ControlModifier)
    names = {Qt.Key_Return: "Return", Qt.Key_Enter: "Enter", Qt.Key_Backspace: "Backspace", Qt.Key_Tab: "Tab",
             Qt.Key_Escape: "Escape", Qt.Key_Up: "Up", Qt.Key_Down: "Down", Qt.Key_Left: "Left", Qt.Key_Right: "Right",
             Qt.Key_Home: "Home", Qt.Key_End: "End", Qt.Key_Delete: "Delete", Qt.Key_Insert: "Insert",
             Qt.Key_PageUp: "PageUp", Qt.Key_PageDown: "PageDown"}
    if key in names:
        return ptyshell.KEYS[names[key]]
    if ctrl and Qt.Key_A <= key <= Qt.Key_Z:
        return ptyshell.ctrl_key(chr(key))
    return text or ""
