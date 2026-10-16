"""Tüm sayfaların ortak temeli ve basit kart/etiket yardımcıları."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class BasePage(QWidget):
    title = "Sayfa"

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(24, 20, 24, 20)
        self.root.setSpacing(12)
        header = QHBoxLayout()
        self.title_label = QLabel(self.title)
        self.title_label.setObjectName("pageTitle")
        header.addWidget(self.title_label)
        header.addStretch(1)
        self.header_extra = QHBoxLayout()
        header.addLayout(self.header_extra)
        self.root.addLayout(header)


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(8)
    return frame, layout


def kv_row(label: str, value: str) -> QWidget:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    lab = QLabel(label)
    lab.setObjectName("dim")
    lab.setMinimumWidth(180)
    val = QLabel(value)
    val.setTextInteractionFlags(
        val.textInteractionFlags()
        | __import__("PySide6.QtGui", fromlist=["Qt"]).Qt.TextSelectableByMouse
    )
    h.addWidget(lab)
    h.addWidget(val, 1)
    return w
