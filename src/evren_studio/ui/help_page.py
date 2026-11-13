"""Yardım ve tanılama sayfası."""
from __future__ import annotations

import platform
import sys

from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton

from .. import __version__
from .base_page import BasePage, card, kv_row
from .workers import Task


class HelpPage(BasePage):
    title = "Yardım ve Tanılama"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        c, l = card()
        l.addWidget(QLabel("Sistem Bilgisi"))
        l.addWidget(kv_row("Uygulama:", f"EVREN Studio {__version__}"))
        l.addWidget(kv_row("Python:", sys.version.split()[0]))
        l.addWidget(kv_row("İşletim sistemi:", platform.platform()))
        l.addWidget(kv_row("Veri konumu:", str(ctx.data_dir())))
        l.addWidget(kv_row(
            "Veritabanı:", str(ctx.data_dir() / "evren.db")
        ))
        diag_btn = QPushButton("Tanılama Çalıştır")
        diag_btn.clicked.connect(self.run_diag)
        l.addWidget(diag_btn)
        self.update_btn = QPushButton("Güncellemeleri denetle")
        self.update_btn.clicked.connect(self.check_updates)
        l.addWidget(self.update_btn)
        self.update_label = QLabel("")
        self.update_label.setWordWrap(True)
        l.addWidget(self.update_label)
        self.root.addWidget(c)

        c2, l2 = card()
        l2.addWidget(QLabel("Hızlı Kullanım"))
        quick = QLabel(
            "1. Ayarlar > Sağlayıcılar ve anahtarlar > “Sağlayıcı ekle” ile EVREN anahtarınızı girin (ücretsiz).\n"
            "2. Sol üstten “Yeni oturum”a tıklayın ve bir proje klasörü seçin "
            "(veya klasörsüz sohbet edin).\n"
            "3. Görevi yazın. Ajan dosyaları okur; değişiklik ve komutlar için "
            "çalışma moduna göre onayınızı ister (Plan / Onaylı / Otomatik düzenleme).\n"
            "4. Sağ paneldeki Değişiklikler sekmesinden her değişikliği görebilir ve "
            "geri alabilirsiniz; Görevler sekmesi ajanın planını gösterir.\n"
            "5. Mesaj kutusunda / yazarak komutları görün: /init proje hafızası "
            "(EVREN.md) oluşturur, /ozet uzun konuşmayı özetler, /plan salt okunur moda geçer.\n"
            "6. Hata alırsanız Hata Merkezi'nden Türkçe açıklamayı okuyun; sağlayıcı "
            "kaynaklı sorunlarda EVREN Durum İzleme'yi başlatın.\n\n"
            "Kısayollar: Enter gönder · Shift+Enter / Alt+Enter yeni satır · Esc durdur · Ctrl+N yeni "
            "oturum · Ctrl+B kenar çubuğu · Ctrl+J sağ panel · Ctrl+K ara · Ctrl+, ayarlar\n\n"
            "503 'sağlıklı endpoint yok' hatası yerel bilgisayar hatası değildir; genellikle "
            "model geçici olarak kapasitede değildir. Bekleyip yeniden denemek veya başka "
            "doğrulanmış bir model seçmek yeterlidir."
        )
        quick.setWordWrap(True)
        l2.addWidget(quick)
        self.root.addWidget(c2)

        c3, l3 = card()
        l3.addWidget(QLabel("Tanılama çıktısı"))
        self.diag = QPlainTextEdit()
        self.diag.setReadOnly(True)
        self.diag.setMaximumHeight(300)
        l3.addWidget(self.diag)
        self.root.addWidget(c3)
        self.root.addStretch(1)

    def check_updates(self) -> None:
        """Elle denetim (C2): günlük sınır ve "atla" yok sayılır; yeni sürüm varsa ana penceredeki kart açılır."""
        from .. import updates

        self.update_btn.setEnabled(False)
        self.update_label.setText("GitHub'daki son sürüme bakılıyor…")

        def done(info) -> None:
            self.update_btn.setEnabled(True)
            if info is None:
                self.update_label.setText(f"Güncelsiniz (EVREN Studio {__version__}) — ya da GitHub'a ulaşılamadı.")
                return
            self.update_label.setText(f"Yeni sürüm: {info.version}. İndirme kartı oturum ekranında açıldı.")
            win = self.window()
            if hasattr(win, "_show_update"):
                win._show_update(info)

        def failed(_exc) -> None:
            self.update_btn.setEnabled(True)
            self.update_label.setText("Denetlenemedi (internet bağlantısını kontrol edin).")

        Task(lambda: updates.check(__version__), on_done=done, on_error=failed).start()

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

                lines.append(f"httpx sürümü: {httpx.__version__}")
            except Exception as exc:
                lines.append(f"httpx sorunu: {exc}")
            try:
                import PySide6

                lines.append(f"PySide6 sürümü: {PySide6.__version__}")
            except Exception as exc:
                lines.append(f"PySide6 sorunu: {exc}")
            lines.append(f"API anahtarı tanımlı: {self.ctx.has_api_key()}")
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
                    lines.append("API testi atlandı (anahtar yok)")
            except Exception as exc:
                lines.append(f"API testi hatası: {exc}")
            return lines

        def done(lines):
            self.diag.setPlainText("\n".join(lines))

        def fail(exc):
            self.diag.setPlainText(f"Tanılama hatası: {exc}")

        Task(job, on_done=done, on_error=fail).start()
