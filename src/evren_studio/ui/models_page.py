"""Modeller sayfasÄ±: canlÄ± liste, yetenekler, doÄŸrulama ve saÄŸlÄ±k durumu."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config import TASK_LABELS
from .base_page import BasePage, card
from .workers import Task


def _yes(v: bool) -> str:
    return "Evet" if v else "HayÄ±r"


class ModelsPage(BasePage):
    title = "Modeller"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self.model_objects: dict[str, object] = {}

        c, l = card()
        l.addWidget(QLabel(
            "CanlÄ± model listesi GET /v1/models ucundan alÄ±nÄ±r. Yetenekler "
            "saÄŸlayÄ±cÄ±nÄ±n bildirdiÄŸi kayÄ±t defteridir; bir modelin listede "
            "olmasÄ± o anda saÄŸlÄ±klÄ± olduÄŸu anlamÄ±na gelmez."
        ))
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Model", "GÃ¶rev", "BaÄŸlam (token)", "AraÃ§ Ã§aÄŸrÄ±sÄ±", "GÃ¶rsel",
            "AkÄ±ÅŸ", "Ãœcretsizlik bitiÅŸi", "Son test", "Son hata",
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        l.addWidget(self.table)
        self.root.addWidget(c, 1)

        c2, l2 = card()
        l2.addWidget(QLabel("SeÃ§ili model yetenekleri"))
        self.detail = QLabel("Tablodan bir model seÃ§in.")
        self.detail.setWordWrap(True)
        self.detail.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        l2.addWidget(self.detail)
        self.table.cellClicked.connect(self.show_detail)
        self.root.addWidget(c2)

        self.refresh_btn = self._make_refresh_btn()
        self.header_extra.addWidget(self.refresh_btn)
        self.refresh_models()

    def _make_refresh_btn(self):
        from PySide6.QtWidgets import QPushButton

        b = QPushButton("Model Listesini Yenile")
        b.clicked.connect(self.refresh_models)
        return b

    def set_models(self, models: list) -> None:
        self.model_objects = {m.id: m for m in models}
        self.table.setRowCount(0)
        for m in models:
            row = self.table.rowCount()
            self.table.insertRow(row)
            health = self.ctx.db.get_model_health(m.id)
            caps = m.capabilities or {}
            values = [
                m.id,
                TASK_LABELS.get(m.task, m.task),
                f"{m.context_length:,}" if m.context_length else "-",
                _yes(m.supports_tools),
                _yes(m.supports_vision),
                _yes(m.supports_stream),
                m.free_until or "-",
                (health["last_test_at"][:16].replace("T", " ") + (
                    " âœ“" if health["healthy"] else " âœ—") if health else "test edilmedi"),
                (health["last_error"] or "-") if health else "-",
            ]
            for col, v in enumerate(values):
                item = QTableWidgetItem(str(v))
                if col in (3, 4, 5):
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)

    def show_detail(self, row: int, _col: int) -> None:
        mid = self.table.item(row, 0).text()
        m = self.model_objects.get(mid)
        if not m:
            return
        caps = m.capabilities or {}
        lines = [
            f"Model: {m.id}",
            f"GÃ¶rev tÃ¼rÃ¼: {TASK_LABELS.get(m.task, m.task)}",
            f"Modaliteler: {', '.join(m.modalities) or '-'}",
            f"BaÄŸlam penceresi: {m.context_length or '-'} token",
            f"VarsayÄ±lan en fazla Ã§Ä±ktÄ±: {m.default_max_output_tokens or '-'}",
            f"AraÃ§ Ã§aÄŸrÄ±sÄ± (function calling): {_yes(m.supports_tools)}",
            f"GÃ¶rsel girdi: {_yes(m.supports_vision)}",
            f"YapÄ±landÄ±rÄ±lmÄ±ÅŸ Ã§Ä±ktÄ± (response_format): "
            f"{_yes(bool(caps.get('response_format')))}",
            f"reasoning_effort: {_yes(bool(caps.get('reasoning_effort')))}"
            + (f" ({', '.join(caps['reasoning_effort_values'])})"
               if caps.get("reasoning_effort_values") else ""),
            f"thinking anahtarÄ±: {_yes(bool(caps.get('thinking')))}",
            f"seed/top_k/stop: {_yes(bool(caps.get('seed')))}/"
            f"{_yes(bool(caps.get('top_k')))}/{_yes(bool(caps.get('stop')))}",
            f"Fiyat: girdi {m.prompt_token_price} CR/token, Ã§Ä±ktÄ± "
            f"{m.completion_token_price} CR/token"
            + (f", {m.free_until} tarihine kadar Ã¼cretsiz" if m.free_until else ""),
            "",
            "Not: Yetenekler saÄŸlayÄ±cÄ± kayÄ±t defterinden gelir; kullanÄ±m "
            "sÄ±rasÄ±nda model saÄŸlÄ±ksÄ±zsa 503 'saÄŸlÄ±klÄ± endpoint yok' hatasÄ± "
            "alÄ±nabilir. Bu durum saÄŸlayÄ±cÄ± kaynaklÄ±dÄ±r.",
        ]
        self.detail.setText("\n".join(lines))

    def refresh_models(self) -> None:
        self.refresh_btn.setEnabled(False)

        def job():
            client = self.ctx.make_client()
            try:
                return client.list_models()
            finally:
                client.close()

        def done(models):
            self.refresh_btn.setEnabled(True)
            self.set_models(models)

        def fail(exc):
            self.refresh_btn.setEnabled(True)
            self.table.setRowCount(0)
            self.detail.setText(
                f"Model listesi alÄ±namadÄ±: {exc}\n"
                "BaÄŸlantÄ± testi sayfasÄ±ndan durumu kontrol edin."
            )

        Task(job, on_done=done, on_error=fail).start()
