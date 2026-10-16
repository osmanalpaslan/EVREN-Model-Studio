"""Hata merkezi: kalıcı hata kayıtları ve kurtarma önerileri."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from PySide6.QtCore import Qt

from .base_page import BasePage, card


class ErrorsPage(BasePage):
    title = "Hata Merkezi"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        splitter = QSplitter(Qt.Vertical)

        c, l = card()
        l.addWidget(QLabel(
            "Tüm hatalar sınıflandırılmış olarak yerel veritabanına kaydedilir. "
            "Bir satır seçtiğinizde kayıt ayrıntıları ve geçmiş çözüm "
            "önerileri aşağıda gösterilir. API anahtarı ve mesaj içerikleri "
            "maskelenerek saklanır."
        ))
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "#", "Zaman", "İşlem", "Model", "HTTP", "Özet",
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.Stretch
        )
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.cellClicked.connect(self.show_detail)
        l.addWidget(self.table)
        refresh_btn = QPushButton("Yenile")
        refresh_btn.clicked.connect(self.refresh)
        l.addWidget(refresh_btn)
        splitter.addWidget(c)

        c2, l2 = card()
        l2.addWidget(QLabel("Kayıt ayrıntıları ve kurtarma notları"))
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        l2.addWidget(self.detail)
        splitter.addWidget(c2)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.root.addWidget(splitter, 1)
        self.refresh()

    def refresh(self) -> None:
        rows = self.ctx.db.list_errors(limit=200)
        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            vals = [
                str(r["id"]), r["created_at"][:19].replace("T", " "),
                r["operation"] or "-", r["model"] or "-",
                str(r["http_status"] or "-"),
                (r["message"] or "")[:90],
            ]
            for col, v in enumerate(vals):
                self.table.setItem(i, col, QTableWidgetItem(v))
        if not rows:
            self.detail.setPlainText("Kayıtlı hata yok.")

    def show_detail(self, row: int, _col: int) -> None:
        err_id = int(self.table.item(row, 0).text())
        rows = [r for r in self.ctx.db.list_errors(limit=500) if r["id"] == err_id]
        if not rows:
            return
        r = rows[0]
        similar = self.ctx.db.find_similar_errors(r["signature"] or "", limit=3)
        lines = [
            f"HATA KAYDI #{r['id']}",
            f"Zaman: {r['created_at']} | Sürüm: {r['app_version']}",
            f"İşlem: {r['operation']} | Model: {r['model'] or '-'}",
            f"API yolu: {r['api_path'] or '-'} | HTTP: {r['http_status'] or '-'}",
            f"Hata kodu: {r['error_code'] or '-'}",
            f"Mesaj (maskeli): {r['message']}",
            f"İstek kimliği: {r['request_id'] or '-'}",
            f"Retry-After: {r['retry_after'] or '-'}",
            f"İzleme durumu: {r['monitor_state'] or '-'}",
            f"Bağlam: {r['context'] or '-'}",
            "",
            f"Denenen çözüm: {r['attempted_fix'] or '-'}",
            f"Çözüm sonucu: {r['fix_result'] or '-'}",
            f"Sonraki adımlar: {r['next_steps'] or '-'}",
            "",
            f"İmza: {r['signature'] or '-'}",
            f"Aynı imzada geçmiş kayıt sayısı: {len(similar)}",
        ]
        for s in similar:
            if s["id"] != r["id"]:
                lines.append(
                    f"  - #{s['id']} ({s['created_at'][:10]}): "
                    f"{s['fix_result'] or 'sonuç kaydedilmemiş'}"
                )
        lines += [
            "",
            "Süreç notu: Aynı imzalı önceki kayıtlardaki BAŞARILI çözümler "
            "doğrulanarak, BAŞARISIZ çözümler yeni bilgi olmadan tekrar "
            "denenmeden uygulanır. Ayrıntılar: docs/knowledge/RECOVERY_PLAYBOOK.md",
        ]
        self.detail.setPlainText("\n".join(lines))
