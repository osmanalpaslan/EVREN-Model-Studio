"""API baÄŸlantÄ± testi sayfasÄ±."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton

from .. import __version__
from ..secrets import mask_api_key
from .base_page import BasePage, card, kv_row
from .workers import Task


class ConnectionPage(BasePage):
    title = "API BaÄŸlantÄ± Testi"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        c, l = card()
        l.addWidget(QLabel(
            "Bu test kimlik doÄŸrulamasÄ±z saÄŸlÄ±k uÃ§larÄ±nÄ±, model listesini ve "
            "kota ucunu sÄ±rayla dener. GerÃ§ek model Ã§aÄŸrÄ±sÄ± yapÄ±lmaz; token "
            "harcanmaz."
        ))
        self.result = kv_row("SonuÃ§:", "-")
        l.addWidget(self.result)
        self.run_btn = QPushButton("BaÄŸlantÄ± Testini BaÅŸlat")
        self.run_btn.clicked.connect(self.run)
        l.addWidget(self.run_btn)
        self.root.addWidget(c)

        c2, l2 = card()
        l2.addWidget(QLabel("Test gÃ¼nlÃ¼ÄŸÃ¼"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(360)
        l2.addWidget(self.log)
        self.root.addWidget(c2)
        self.root.addStretch(1)

    def _append(self, msg: str) -> None:
        from datetime import datetime

        self.log.appendPlainText(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def run(self) -> None:
        self.run_btn.setEnabled(False)
        self.log.clear()
        self._append(f"Uygulama sÃ¼rÃ¼mÃ¼: {__version__}")
        self._append(f"API adresi: {self.ctx.settings.base_url}")
        self._append(f"Anahtar (maskeli): {mask_api_key(self.ctx.api_key()) or 'YOK'}")

        def job():
            if not self.ctx.has_api_key():
                raise PermissionError(
                    "API anahtarÄ± tanÄ±mlÄ± deÄŸil. Ayarlar sayfasÄ±ndan girin."
                )
            client = self.ctx.make_client(log_sink=lambda m: None)
            try:
                out = []
                out.append("healthz: " + str(client.healthz()))
                out.append("readyz: " + str(client.readyz()))
                models = client.list_models()
                out.append(f"models: {len(models)} model eriÅŸilebilir")
                quota = client.get_quota()
                out.append(
                    f"quota: seviye={quota.level}, kalan_kredi={quota.remaining_cr} CR"
                )
                terms = client.terms_status()
                out.append(
                    f"terms: sÃ¼rÃ¼m={terms.get('current_version')}, "
                    f"kabul_durumu={terms.get('accepted')}"
                )
                return out
            finally:
                client.close()

        def done(lines):
            for line in lines:
                self._append("BAÅARILI â€” " + line)
            self.result.findChildren(QLabel)[1].setText(
                f"BAÄLANTI SAÄLAM ({len(lines)} adÄ±m)"
            )
            self.run_btn.setEnabled(True)

        def fail(exc):
            self._append(f"BAÅARISIZ â€” {exc}")
            self.result.findChildren(QLabel)[1].setText(f"HATA: {exc}")
            self.run_btn.setEnabled(True)

        Task(job, on_done=done, on_error=fail).start()
