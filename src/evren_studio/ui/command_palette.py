"""E10 komut paleti (Ctrl+Shift+P): sayfalar, modlar, /komutlar, görünüm ayarları, profiller, şablonlar tek listede."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

_TR = str.maketrans("ÇĞİIÖŞÜçğıöşü", "cgiiosucgiosu")


def norm(text: str) -> str:
    """Türkçe harf ve büyük/küçük duyarsız arama anahtarı ("İçe" ≈ "ice")."""
    return text.translate(_TR).lower()


@dataclass
class Action:
    title: str
    group: str
    run: Callable[[], None]
    keywords: str = ""
    shortcut: str = ""


def match(actions: list[Action], query: str) -> list[Action]:
    """Her sözcük başlıkta/grupta/anahtar sözcüklerde geçmeli; başlığı sorguyla başlayanlar önce."""
    words = [w for w in norm(query).split() if w]
    if not words:
        return list(actions)
    out = []
    for a in actions:
        hay = norm(f"{a.title} {a.group} {a.keywords}")
        if all(w in hay for w in words):
            out.append(a)
    q = norm(query).strip()

    def score(a: Action) -> int:
        head = norm(a.title.split(" — ", 1)[0])           # komut açıklaması sıralamayı etkilemesin
        if head.startswith(q):
            return 0
        if any(t.startswith(w) for t in head.split() for w in words):
            return 1
        if norm(a.group).startswith(q):
            return 2
        return 3
    return sorted(out, key=score)


class CommandPalette(QDialog):
    def __init__(self, actions: list[Action], parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("CommandPalette")
        self.actions_ = actions
        self.chosen: Action | None = None
        self.resize(620, 420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Komut ara… (ör. otomatik, ayarlar, profil, sade görünüm)")
        self.edit.textChanged.connect(self._fill)
        self.edit.returnPressed.connect(self._run_current)
        self.edit.installEventFilter(self)
        lay.addWidget(self.edit)
        self.list = QListWidget()
        self.list.setObjectName("CommandPopup")
        self.list.itemActivated.connect(lambda _it: self._run_current())
        lay.addWidget(self.list, 1)
        self._fill("")
        self.edit.setFocus()

    def _fill(self, text: str) -> None:
        self.list.clear()
        for a in match(self.actions_, text)[:80]:
            label = f"{a.group}: {a.title}" + (f"    {a.shortcut}" if a.shortcut else "")
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, a)
            self.list.addItem(it)
        if self.list.count():
            self.list.setCurrentRow(0)

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent

        if obj is self.edit and ev.type() == QEvent.KeyPress and ev.key() in (Qt.Key_Down, Qt.Key_Up):
            row = self.list.currentRow() + (1 if ev.key() == Qt.Key_Down else -1)
            self.list.setCurrentRow(max(0, min(self.list.count() - 1, row)))
            return True
        return super().eventFilter(obj, ev)

    def _run_current(self) -> None:
        it = self.list.currentItem()
        if it is None:
            return
        self.chosen = it.data(Qt.UserRole)
        self.accept()
