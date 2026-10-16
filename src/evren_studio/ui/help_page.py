"""YardÄ±m ve tanÄ±lama sayfasÄ±."""
from __future__ import annotations

import platform
import sys

from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton

from .. import __version__
from .base_page import BasePage, card, kv_row
from .workers import Task


class HelpPage(BasePage):
    title = "YardÄ±m ve TanÄ±lama"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        c, l = card()
        l.addWidget(QLabel("Sistem Bilgisi"))
        l.addWidget(kv_row("Uygulama:", f"EVREN Model Studio {__version__}"))
        l.addWidget(kv_row("Python:", sys.version.split()[0]))
        l.addWidget(kv_row("Ä°ÅŸletim sistemi:", platform.platform()))
        l.addWidget(kv_row("Veri konumu:", str(ctx.data_dir())))
        l.addWidget(kv_row(
            "VeritabanÄ±:", str(ctx.data_dir() / "evren.db")
        ))
        diag_btn = QPushButton("TanÄ±lama Ã‡alÄ±ÅŸtÄ±r")
        diag_btn.clicked.connect(self.run_diag)
        l.addWidget(diag_btn)
        self.root.addWidget(c)

        c2, l2 = card()
        l2.addWidget(QLabel("HÄ±zlÄ± KullanÄ±m"))
        l2.addWidget(QLabel(
            "1. Ayarlar > API AnahtarÄ± bÃ¶lÃ¼mÃ¼nden EVREN anahtarÄ±nÄ±zÄ± girin.\n"
            "2. API BaÄŸlantÄ± Testi sayfasÄ±ndan baÄŸlantÄ±yÄ± doÄŸrulayÄ±n.\n"
            "3. Chat sayfasÄ±nda model seÃ§ip sohbet edin; yanÄ±tlar akÄ±ÅŸ "
            "halinde gelir ve yerel olarak kaydedilir.\n"
            "4. Hata alÄ±rsanÄ±z Hata Merkezi'nden TÃ¼rkÃ§e aÃ§Ä±klamayÄ± ve Ã¶nerilen "
            "Ã§Ã¶zÃ¼mÃ¼ okuyun.\n"
            "5. SaÄŸlayÄ±cÄ± kaynaklÄ± sorunlardan ÅŸÃ¼pheleniyorsanÄ±z EVREN Durum "
            "Ä°zleme'yi 30 dakikalÄ±k izleme iÃ§in baÅŸlatÄ±n.\n\n"
            "503 'saÄŸlÄ±klÄ± endpoint yok' hatasÄ± yerel bilgisayar hatasÄ± "
            "deÄŸildir; genellikle model geÃ§ici olarak kapasitede deÄŸildir. "
            "Bekleyip yeniden denemek veya baÅŸka doÄŸrulanmÄ±ÅŸ bir model "
            "seÃ§mek yeterlidir."
        ))
        self.root.addWidget(c2)

        c3, l3 = card()
        l3.addWidget(QLabel("TanÄ±lama Ã§Ä±ktÄ±sÄ±"))
        self.diag = QPlainTextEdit()
        self.diag.setReadOnly(True)
        self.diag.setMaximumHeight(300)
        l3.addWidget(self.diag)
        self.root.addWidget(c3)
        self.root.addStretch(1)

    def run_diag(self) -> None:
        self.diag.clear()

        def job():
            lines = []
            try:
                import keyring

                lines.append(f"keyring arka ucu: {keyring.get_keyring()}")
            except Exception as exc:
                lines.append(f"keyring sorunu: {exc}")
            try:
                import httpx

                lines.append(f"httpx sÃ¼rÃ¼mÃ¼: {httpx.__version__}")
            except Exception as exc:
                lines.append(f"httpx sorunu: {exc}")
            try:
                import PySide6

                lines.append(f"PySide6 sÃ¼rÃ¼mÃ¼: {PySide6.__version__}")
            except Exception as exc:
                lines.append(f"PySide6 sorunu: {exc}")
            lines.append(f"API anahtarÄ± tanÄ±mlÄ±: {self.ctx.has_api_key()}")
            lines.append(f"API adresi: {self.ctx.settings.base_url}")
            try:
                if self.ctx.has_api_key():
                    client = self.ctx.make_client()
                    try:
                        lines.append(f"healthz: {client.healthz()}")
                        lines.append(f"readyz: {client.readyz()}")
                    finally:
                        client.close()
                else:
                    lines.append("API testi atlandÄ± (anahtar yok)")
            except Exception as exc:
                lines.append(f"API testi hatasÄ±: {exc}")
            return lines

        def done(lines):
            self.diag.setPlainText("\n".join(lines))

        def fail(exc):
            self.diag.setPlainText(f"TanÄ±lama hatasÄ±: {exc}")

        Task(job, on_done=done, on_error=fail).start()
