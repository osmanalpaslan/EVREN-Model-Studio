"""Ayarlar > Geliştirici gözlemi kartı (gozlem.py): aç/kapat, durum, şimdi gönder, kayıtları aç."""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import gozlem
from .workers import Task


class GozlemCard(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.enabled = QCheckBox("Hata ve anormallikleri kaydet, projenin deposuna gönder")
        l.addWidget(self.enabled)
        info = QLabel("Çökme, Qt uyarısı, beklenmeyen API hatası ve ajan anormallikleri (döngü, test bozma, "
                      "adım sınırı…) kaydedilir. Depo herkese açık olduğu için gönderilmeden önce temizlenir: "
                      "API anahtarı, kullanıcı adı, dosya yolları ve sohbet içeriği gitmez. Gönderim yalnız "
                      "uygulama EVREN-Model-Studio kaynağından çalışırken ve git oturumunuz açıkken yapılır "
                      f"({gozlem.BRANCH} dalı); geliştirme oturumu başında bu kayıtlar size bildirilir.")
        info.setWordWrap(True)
        info.setProperty("role", "dim")
        l.addWidget(info)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        l.addWidget(self.status)
        row = QHBoxLayout()
        self.send_btn = QPushButton("Şimdi gönder")
        self.send_btn.clicked.connect(self.send_now)
        open_btn = QPushButton("Kayıtları aç")
        open_btn.setToolTip("Bu bilgisayardaki gözlem kuyruğunun klasörünü açar")
        open_btn.clicked.connect(self.open_folder)
        row.addWidget(self.send_btn)
        row.addWidget(open_btn)
        row.addStretch(1)
        l.addLayout(row)
        self.refresh()

    def refresh(self) -> None:
        try:
            d = gozlem.durum()
        except Exception:
            d = {"toplam": 0, "bekleyen": 0, "son_gonderim": "", "son_hata": "", "depo": ""}
        parts = [f"Bu bilgisayarda {d['toplam']} gözlem, gönderilmeyi bekleyen {d['bekleyen']}."]
        parts.append(f"Son gönderim: {d['son_gonderim'][:16].replace('T', ' ')} (UTC)." if d["son_gonderim"]
                     else "Henüz gönderilmedi.")
        if not d["depo"]:
            parts.append("Gönderilecek depo bulunamadı: gözlemler yalnız bu bilgisayarda tutulur.")
        if d["son_hata"]:
            parts.append(f"Son gönderim hatası: {d['son_hata']}")
        self.status.setText(" ".join(parts))

    def send_now(self, _=None) -> None:
        self.send_btn.setEnabled(False)
        self.status.setText("Gönderiliyor…")

        def done(msg):
            self.send_btn.setEnabled(True)
            self.refresh()
            self.status.setText(f"{msg} {self.status.text()}")

        def fail(exc):
            self.send_btn.setEnabled(True)
            self.status.setText(f"Gönderilemedi: {gozlem.temizle(exc)}")

        Task(gozlem.gonder, on_done=done, on_error=fail).start()

    def open_folder(self, _=None) -> None:
        d = gozlem.gercek_veri_dizini() / "gozlem"
        d.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))
