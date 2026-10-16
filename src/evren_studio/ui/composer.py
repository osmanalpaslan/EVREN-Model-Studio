"""Mesaj yazma kutusu: çok satırlı giriş, mod ve model seçici, gönder/durdur."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..agent.permissions import MODE_HINTS, MODES
from . import icons, theme

SLASH_COMMANDS = {
    "/yeni": "Yeni oturum başlat",
    "/plan": "Plan moduna geç (salt okunur)",
    "/onayli": "Onaylı moda geç",
    "/otomatik": "Otomatik düzenleme moduna geç",
    "/model": "Modeli değiştir: /model glm-5.3",
    "/init": "Projeyi inceleyip EVREN.md proje hafızası oluştur",
    "/ozet": "Uzun konuşmayı özetleyip bağlamı küçült",
    "/disa-aktar": "Oturumu Markdown olarak dışa aktar",
    "/yardim": "Komutları ve kısayolları göster",
}

MODE_ICONS = {"plan": "map", "onayli": "shield", "otomatik": "pencil"}


class ComposerEdit(QPlainTextEdit):
    submit = Signal()
    escape = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ComposerEdit")
        self.send_with_enter = True
        self.setTabChangesFocus(True)
        self.document().contentsChanged.connect(self._grow)
        self._grow()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            mods = e.modifiers()
            if self.send_with_enter and not (mods & Qt.ShiftModifier):
                self.submit.emit()
                return
            if not self.send_with_enter and (mods & Qt.ControlModifier):
                self.submit.emit()
                return
        if e.key() == Qt.Key_Escape:
            self.escape.emit()
            return
        super().keyPressEvent(e)

    def _grow(self) -> None:
        total = self.document().size().height()
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded if total > 12 else Qt.ScrollBarAlwaysOff)
        lines = max(1, min(total, 12))
        lh = self.fontMetrics().lineSpacing()
        self.setFixedHeight(int(lines * lh + 16))

    def insert_at_cursor(self, text: str) -> None:
        cur = self.textCursor()
        cur.insertText(text)
        self.setTextCursor(cur)
        self.setFocus()


class Composer(QWidget):
    submitted = Signal(str)
    stop_requested = Signal()
    mode_changed = Signal(str)
    model_changed = Signal(str)
    attach_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._model = ""
        self._mode = "onayli"
        self._agentic = True
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        self.hint = QLabel()
        self.hint.setProperty("role", "faint")
        self.hint.setWordWrap(True)
        self.hint.setVisible(False)
        outer.addWidget(self.hint)

        self.frame = QFrame()
        self.frame.setObjectName("Composer")
        fl = QVBoxLayout(self.frame)
        fl.setContentsMargins(14, 10, 10, 8)
        fl.setSpacing(6)
        self.edit = ComposerEdit()
        self.edit.setPlaceholderText("EVREN'e bir görev verin veya soru sorun…  (/ komutlar, @ dosya)")
        self.edit.submit.connect(self._submit)
        self.edit.escape.connect(self.stop_requested.emit)
        self.edit.textChanged.connect(self._on_text)
        self.edit.installEventFilter(self)
        fl.addWidget(self.edit)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.attach_btn = self._chip("paperclip", "Dosya ekle (@)")
        self.attach_btn.setToolTip("Proje dosyasını mesaja ekle")
        self.attach_btn.clicked.connect(self.attach_requested.emit)
        row.addWidget(self.attach_btn)

        self.mode_btn = self._chip("shield", MODES["onayli"])
        self.mode_btn.setPopupMode(QToolButton.InstantPopup)
        self.mode_menu = QMenu(self)
        group = QActionGroup(self)
        self.mode_actions: dict[str, QAction] = {}
        for key, label in MODES.items():
            act = QAction(icons.icon(MODE_ICONS[key], size=16), f"{label} — {MODE_HINTS[key]}", self)
            act.setCheckable(True)
            act.triggered.connect(lambda _=False, k=key: self.set_mode(k, emit=True))
            group.addAction(act)
            self.mode_menu.addAction(act)
            self.mode_actions[key] = act
        self.mode_btn.setMenu(self.mode_menu)
        row.addWidget(self.mode_btn)

        self.model_btn = self._chip("cpu", "model")
        self.model_btn.setPopupMode(QToolButton.InstantPopup)
        self.model_menu = QMenu(self)
        self.model_btn.setMenu(self.model_menu)
        row.addWidget(self.model_btn)

        row.addStretch(1)
        self.context_label = QLabel("")
        self.context_label.setProperty("role", "faint")
        row.addWidget(self.context_label)
        self.send_btn = QPushButton()
        self.send_btn.setObjectName("SendButton")
        self.send_btn.setFixedSize(30, 30)
        self.send_btn.setIconSize(QSize(18, 18))
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(self._on_send_clicked)
        row.addWidget(self.send_btn)
        fl.addLayout(row)
        outer.addWidget(self.frame)

        self.footer = QLabel("EVREN hata yapabilir; önemli değişiklikleri gözden geçirin. "
                             "Mesajlar ve dosya içerikleri EVREN API'sine gönderilir.")
        self.footer.setProperty("role", "faint")
        self.footer.setAlignment(Qt.AlignCenter)
        outer.addWidget(self.footer)
        self.set_mode("onayli")
        self._update_send()

    def _chip(self, icon_name: str, text: str) -> QToolButton:
        b = QToolButton()
        b.setProperty("variant", "chip")
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b.setIcon(icons.icon(icon_name, size=15))
        b.setIconSize(QSize(15, 15))
        b.setText(text)
        b.setCursor(Qt.PointingHandCursor)
        return b

    def eventFilter(self, obj, event) -> bool:
        if obj is self.edit and event.type() in (event.Type.FocusIn, event.Type.FocusOut):
            self.frame.setProperty("focus", event.type() == event.Type.FocusIn)
            self.frame.style().unpolish(self.frame)
            self.frame.style().polish(self.frame)
        return super().eventFilter(obj, event)

    # -- durum --

    def set_agentic(self, agentic: bool) -> None:
        self._agentic = agentic
        self.mode_btn.setVisible(agentic)
        self.attach_btn.setVisible(agentic)
        self.edit.setPlaceholderText(
            "EVREN'e bir görev verin veya soru sorun…  (/ komutlar, @ dosya)" if agentic
            else "Mesajınızı yazın…  (/ komutlar)")

    def set_mode(self, mode: str, emit: bool = False) -> None:
        if mode not in MODES:
            return
        self._mode = mode
        self.mode_btn.setText(MODES[mode])
        self.mode_btn.setIcon(icons.icon(MODE_ICONS[mode], size=15))
        self.mode_btn.setToolTip(MODE_HINTS[mode])
        self.mode_actions[mode].setChecked(True)
        if emit:
            self.mode_changed.emit(mode)

    def mode(self) -> str:
        return self._mode

    def set_models(self, models: list, current: str) -> None:
        """models: [(id, açıklama, araç_destekli)]"""
        self.model_menu.clear()
        group = QActionGroup(self.model_menu)
        for mid, desc, tools in models:
            label = mid + (f"   ·  {desc}" if desc else "")
            act = QAction(label, self.model_menu)
            act.setCheckable(True)
            act.setChecked(mid == current)
            act.setToolTip("Yerel araç çağrısı destekli" if tools else "Metin protokolü ile çalışır")
            act.triggered.connect(lambda _=False, m=mid: self.set_model(m, emit=True))
            group.addAction(act)
            self.model_menu.addAction(act)
        self.set_model(current)

    def set_model(self, model: str, emit: bool = False) -> None:
        self._model = model
        self.model_btn.setText(model or "model seçin")
        for act in self.model_menu.actions():
            act.setChecked(act.text().split("   ·")[0] == model)
        if emit:
            self.model_changed.emit(model)

    def model(self) -> str:
        return self._model

    def set_running(self, running: bool) -> None:
        self._running = running
        self._update_send()

    def set_context(self, used_tokens: int, limit: int | None) -> None:
        if not used_tokens:
            self.context_label.setText("")
            return
        def k(n: int) -> str:
            return f"{n / 1000:.1f}k" if n < 100_000 else f"{n // 1000}k"
        if limit:
            pct = min(100, int(used_tokens * 100 / limit))
            self.context_label.setText(f"bağlam ~{k(used_tokens)} / {k(limit)} ({pct}%)")
        else:
            self.context_label.setText(f"bağlam ~{k(used_tokens)}")

    def _update_send(self) -> None:
        p = theme.current()
        self.send_btn.setProperty("running", self._running)
        self.send_btn.style().unpolish(self.send_btn)
        self.send_btn.style().polish(self.send_btn)
        if self._running:
            self.send_btn.setIcon(icons.icon("stop", p.bg, 18))
            self.send_btn.setToolTip("Durdur (Esc)")
            self.send_btn.setEnabled(True)
        else:
            has_text = bool(self.edit.toPlainText().strip())
            self.send_btn.setIcon(icons.icon("send", p.on_accent if has_text else p.text_faint, 18))
            self.send_btn.setToolTip("Gönder (Enter) — yeni satır: Shift+Enter")
            self.send_btn.setEnabled(has_text)

    def _on_text(self) -> None:
        self._update_send()
        text = self.edit.toPlainText()
        if text.startswith("/") and "\n" not in text:
            word = text.split(" ")[0]
            matches = [f"{c}  —  {d}" for c, d in SLASH_COMMANDS.items() if c.startswith(word)]
            self.hint.setText("\n".join(matches) if matches else "Bilinmeyen komut. /yardim yazın.")
            self.hint.setVisible(True)
        else:
            self.hint.setVisible(False)

    def _on_send_clicked(self) -> None:
        if self._running:
            self.stop_requested.emit()
        else:
            self._submit()

    def _submit(self) -> None:
        if self._running:
            return
        text = self.edit.toPlainText().strip()
        if not text:
            return
        self.edit.clear()
        self.submitted.emit(text)

    def set_text(self, text: str) -> None:
        self.edit.setPlainText(text)
        cur = self.edit.textCursor()
        cur.movePosition(QTextCursor.End)
        self.edit.setTextCursor(cur)
        self.edit.setFocus()

    def focus(self) -> None:
        self.edit.setFocus()
