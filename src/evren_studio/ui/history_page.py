"""Sohbetler ve projeler: geçmiş listesi, arama, açma, dışa aktarma."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from .base_page import BasePage, card


class HistoryPage(BasePage):
    title = "Sohbetler ve Projeler"

    def __init__(self, ctx, parent=None, open_chat_callback=None):
        super().__init__(ctx, parent)
        self.open_chat_callback = open_chat_callback

        c, l = card()
        l.addWidget(QLabel(
            "Sohbet geçmişi yerel SQLite veritabanında saklanır. Projeler "
            "(Code Studio) aşama 2'de eklenecek; bu liste yalnızca gerçek "
            "kaydı olan sohbetleri gösterir."
        ))
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Sohbet başlığında ara…")
        self.search.textChanged.connect(self.refresh)
        search_row.addWidget(self.search, 1)
        l.addLayout(search_row)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self.open_selected)
        l.addWidget(self.list)

        btns = QHBoxLayout()
        open_btn = QPushButton("Sohbeti Aç")
        open_btn.clicked.connect(self.open_selected)
        export_btn = QPushButton("Dışa Aktar")
        export_btn.clicked.connect(self.export_selected)
        delete_btn = QPushButton("Sil")
        delete_btn.clicked.connect(self.delete_selected)
        btns.addWidget(open_btn)
        btns.addWidget(export_btn)
        btns.addStretch(1)
        btns.addWidget(delete_btn)
        l.addLayout(btns)
        self.root.addWidget(c, 1)

    def refresh(self) -> None:
        self.list.clear()
        for c in self.ctx.db.list_chats(search=self.search.text().strip()):
            item = QListWidgetItem(
                f"#{c['id']}  {c['title']}   —  {c['model']}  "
                f"({c['updated_at'][:16].replace('T', ' ')})"
            )
            item.setData(0x0100, c["id"])
            self.list.addItem(item)

    def _selected_id(self) -> int | None:
        item = self.list.currentItem()
        return item.data(0x0100) if item else None

    def open_selected(self) -> None:
        chat_id = self._selected_id()
        if chat_id and self.open_chat_callback:
            self.open_chat_callback(chat_id)

    def export_selected(self) -> None:
        chat_id = self._selected_id()
        if not chat_id:
            return
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Sohbeti Dışa Aktar", f"sohbet-{chat_id}.md", "Markdown (*.md)"
        )
        if path:
            from pathlib import Path

            Path(path).write_text(
                self.ctx.db.export_chat_markdown(chat_id), encoding="utf-8"
            )

    def delete_selected(self) -> None:
        chat_id = self._selected_id()
        if not chat_id:
            return
        if QMessageBox.question(
            self, "Sohbeti Sil",
            f"Sohbet #{chat_id} ve tüm mesajları silinsin mi? Geri alınamaz.",
        ) == QMessageBox.Yes:
            self.ctx.db.delete_chat(chat_id)
            self.refresh()
