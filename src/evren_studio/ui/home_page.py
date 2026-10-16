"""Ana sayfa: sistem durumu özeti."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from .base_page import BasePage, card, kv_row
from .workers import Task


class HomePage(BasePage):
    title = "Sistem Durumu"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setSpacing(12)

        c1, l1 = card()
        l1.addWidget(QLabel("Genel Durum"))
        self.key_row = kv_row("API anahtarı:", "-")
        self.base_row = kv_row("API adresi:", ctx.settings.base_url)
        self.model_row = kv_row("Kayıtlı model sayısı:", "-")
        self.last_error_row = kv_row("Son hata kaydı:", "-")
        self.monitor_row = kv_row("İzleme durumu:", "-")
        for w in (self.key_row, self.base_row, self.model_row,
                  self.last_error_row, self.monitor_row):
            l1.addWidget(w)
        self.check_btn = QPushButton("Hızlı Durum Kontrolü")
        self.check_btn.clicked.connect(self.run_check)
        l1.addWidget(self.check_btn)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        l1.addWidget(self.status_label)
        lay.addWidget(c1)

        c2, l2 = card()
        l2.addWidget(QLabel("Bilgi"))
        info = QLabel(
            "EVREN Model Studio, EVREN LLM API'si üzerinden sohbet ve kod "
            "yardımı sunan yerel bir Windows uygulamasıdır. Sohbetleriniz ve "
            "hata kayıtları yalnızca bu bilgisayarda saklanır. Her API "
            "isteği, mesaj içeriğinizi EVREN sunucularına gönderir.\n\n"
            "Sol menüden oturum başlatabilir; Modeller, Kota ve Ayarlar sayfalarını açabilirsiniz."
        )
        info.setWordWrap(True)
        l2.addWidget(info)
        lay.addWidget(c2)
        lay.addStretch(1)
        scroll.setWidget(inner)
        self.root.addWidget(scroll, 1)
        self.refresh()

    def refresh(self) -> None:
        key = self.ctx.masked_key()
        self.key_row.findChildren(QLabel)[1].setText(
            f"{key} (Windows Credential Manager)" if key else
            "Tanımlı değil — Ayarlar'dan girin"
        )
        errors = self.ctx.db.list_errors(limit=1)
        if errors:
            e = errors[0]
            self.last_error_row.findChildren(QLabel)[1].setText(
                f"#{e['id']} {e['created_at']} — {e['message'][:60]}"
            )
        else:
            self.last_error_row.findChildren(QLabel)[1].setText("Hata kaydı yok")
        open_mon = self.ctx.db.get_open_monitor_session()
        if open_mon:
            self.monitor_row.findChildren(QLabel)[1].setText(
                f"Yarım kalan izleme var (#{open_mon['id']}) — Durum İzleme "
                "sayfasından devam edebilirsiniz"
            )
        else:
            self.monitor_row.findChildren(QLabel)[1].setText("İzleme çalışmıyor")

    def run_check(self) -> None:
        self.check_btn.setEnabled(False)
        self.status_label.setText("Kontrol ediliyor…")

        def job():
            client = self.ctx.make_client()
            out = []
            out.append(("healthz", client.healthz()))
            out.append(("readyz", client.readyz()))
            models = client.list_models()
            out.append(("models", f"{len(models)} model"))
            return out

        def done(results):
            self.check_btn.setEnabled(True)
            text = " | ".join(f"{k}: {v}" for k, v in results)
            self.status_label.setText("Sonuç: " + text)
            models_val = [v for k, v in results if k == "models"]
            if models_val:
                self.model_row.findChildren(QLabel)[1].setText(models_val[0])
            self.status_label.setProperty("ok", True)

        def fail(exc):
            self.check_btn.setEnabled(True)
            self.status_label.setText(f"Kontrol başarısız: {exc}")
            self.status_label.setProperty("ok", False)

        Task(job, on_done=done, on_error=fail).start()
