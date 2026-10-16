"""Kullanım / kota bilgileri sayfası (API sağlıyorsa)."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton

from .base_page import BasePage, card, kv_row
from .workers import Task


class UsagePage(BasePage):
    title = "Kullanım / Kota Bilgileri"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        c, l = card()
        l.addWidget(QLabel(
            "Bilgiler GET /v1/quota ucundan alınır. Kota verisi sağlayıcı "
            "tarafından sunuluyorsa gösterilir; tahmin üretilmez."
        ))
        self.refresh_btn = QPushButton("Kota Bilgisini Yenile")
        self.refresh_btn.clicked.connect(self.refresh)
        l.addWidget(self.refresh_btn)

        self.window_bar = QProgressBar()
        self.window_bar.setRange(0, 100)
        l.addWidget(QLabel("Kayan pencere kullanımı (5 dk)"))
        l.addWidget(self.window_bar)
        self.window_row = kv_row("Pencere:", "-")
        l.addWidget(self.window_row)

        self.daily_bar = QProgressBar()
        self.daily_bar.setRange(0, 100)
        l.addWidget(QLabel("Günlük kullanım"))
        l.addWidget(self.daily_bar)
        self.daily_row = kv_row("Günlük:", "-")
        l.addWidget(self.daily_row)

        self.credit_row = kv_row("Kalan kredi (CR):", "-")
        self.held_row = kv_row("Bekleyen kredi (CR):", "-")
        self.level_row = kv_row("Kota seviyesi:", "-")
        self.reset_row = kv_row("Pencere sıfırlanma:", "-")
        self.daily_reset_row = kv_row("Günlük sıfırlanma (UTC):", "-")
        for w in (self.credit_row, self.held_row, self.level_row,
                  self.reset_row, self.daily_reset_row):
            l.addWidget(w)
        self.root.addWidget(c)
        self.root.addStretch(1)

    def _set_row(self, row: QWidget, value: str) -> None:
        row.findChildren(QLabel)[1].setText(value)

    def refresh(self) -> None:
        self.refresh_btn.setEnabled(False)

        def job():
            client = self.ctx.make_client()
            try:
                return client.get_quota()
            finally:
                client.close()

        def done(q):
            self.refresh_btn.setEnabled(True)
            if q.used_tokens is not None and q.cap:
                pct = int((q.usage_ratio or 0) * 100)
                self.window_bar.setValue(min(100, pct))
                self._set_row(
                    self.window_row,
                    f"{q.used_tokens:,} / {q.cap:,} token "
                    f"(%{pct}, {q.window_minutes} dk pencere)",
                )
            else:
                self._set_row(self.window_row, "Veri sağlanmadı")
            if q.daily_used_tokens is not None and q.daily_limit_tokens:
                pct = int(q.daily_used_tokens * 100 / q.daily_limit_tokens)
                self.daily_bar.setValue(min(100, pct))
                self._set_row(
                    self.daily_row,
                    f"{q.daily_used_tokens:,} / {q.daily_limit_tokens:,} token (%{pct})",
                )
            else:
                self._set_row(self.daily_row, "Günlük sınır yok")
            self._set_row(self.credit_row, str(q.remaining_cr))
            self._set_row(self.held_row, str(q.held_cr))
            self._set_row(self.level_row, q.level)
            self._set_row(self.reset_row, q.reset_at or "-")
            self._set_row(self.daily_reset_row, q.daily_reset_at or "-")

        def fail(exc):
            self.refresh_btn.setEnabled(True)
            self._set_row(self.level_row, f"Alınamadı: {exc}")

        Task(job, on_done=done, on_error=fail).start()
