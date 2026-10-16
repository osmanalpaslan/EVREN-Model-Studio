"""EVREN Durum İzleme Ajanı sayfası.

Kullanıcı başlatmalı 30 dakikalık izleme (5 dakikada bir kontrol).
Rapor Türkçe hazırlanır; belirsiz ve kesin bulgular ayrılır.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ..monitor import MonitorAgent
from .base_page import BasePage, card, kv_row


class MonitorPage(BasePage):
    title = "EVREN Durum İzleme"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self.agent: MonitorAgent | None = None

        c, l = card()
        l.addWidget(QLabel(
            "Bu ajan, seçili duyuru sayfasını ve EVREN API sağlık uçlarını "
            "(token harcamadan) izler. İzlemeyi başlattığınızda sayfa her "
            "5 dakikada bir kontrol edilir ve toplam 30 dakika sürer "
            "(başlangıç dahil normal koşullarda 7 kontrol). Gerçek model "
            "testi yalnızca siz işaretlediyseniz yapılır ve token harcar.\n\n"
            "Not: EVREN duyuru API'si platform girişi istediğinden izlenen "
            "sayfa varsayılan olarak herkese açık ana sayfadır. Ayarlar'dan "
            "farklı bir duyuru adresi seçebilirsiniz."
        ))
        self.url_row = kv_row("İzlenen sayfa:", ctx.settings.announcement_url)
        l.addWidget(self.url_row)
        l.addWidget(QLabel("Kalan süre: -"))

        opts = QHBoxLayout()
        self.real_test = QCheckBox("Gerçek model testi yap (token harcar)")
        self.real_test.setChecked(ctx.settings.monitor_real_model_test)
        self.model_label = QLabel("Test modeli:")
        self.test_model_btn = QPushButton(ctx.settings.monitor_test_model)
        self.test_model_btn.clicked.connect(self.pick_model)
        opts.addWidget(self.real_test)
        opts.addWidget(self.model_label)
        opts.addWidget(self.test_model_btn)
        opts.addStretch(1)
        l.addLayout(opts)

        btns = QHBoxLayout()
        self.start_btn = QPushButton("İzlemeyi Başlat")
        self.start_btn.clicked.connect(self.start)
        self.stop_btn = QPushButton("İzlemeyi Durdur")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        btns.addWidget(self.start_btn)
        btns.addWidget(self.stop_btn)
        btns.addStretch(1)
        l.addLayout(btns)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        l.addWidget(self.progress)
        self.state_row = kv_row("Durum:", "çalışmıyor")
        l.addWidget(self.state_row)
        self.root.addWidget(c)

        c2, l2 = card()
        l2.addWidget(QLabel("Canlı kontrol kaydı"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(280)
        l2.addWidget(self.log)
        self.root.addWidget(c2, 1)

        c3, l3 = card()
        l3.addWidget(QLabel("İzleme raporu (30 dakika sonunda veya durdurunca)"))
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        l3.addWidget(self.report)
        self.root.addWidget(c3, 1)

        self._check_resume()

    # ---- devam seçeneği ------------------------------------------------

    def _check_resume(self) -> None:
        open_session = self.ctx.db.get_open_monitor_session()
        if not open_session:
            return
        resume_btn = QPushButton(
            f"Yarım kalan izlemeye devam et (#{open_session['id']}, "
            f"başlangıç {open_session['started_at'][:16].replace('T', ' ')})"
        )
        resume_btn.clicked.connect(self.start)
        self.root.insertWidget(1, resume_btn)
        self.state_row.findChildren(QLabel)[1].setText(
            "önceki izleme yarım kaldı — devam seçeneği yukarıda"
        )

    # ---- model seçimi ------------------------------------------------------

    def pick_model(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        models = ["glm-5.3", "auto", "deepseek-v4-flash", "mimo-v2.6-pro",
                  "qwen3.8-flash-next", "gemma-4-31b"]
        current = self.test_model_btn.text()
        model, ok = QInputDialog.getItem(
            self, "Test Modeli", "Hangi modelle gerçek istek testi yapılsın?",
            models, models.index(current) if current in models else 0, False,
        )
        if ok:
            self.test_model_btn.setText(model)
            self.ctx.settings.monitor_test_model = model
            self.ctx.save_settings()

    # ---- izleme yaşam döngüsü ------------------------------------------------

    def start(self) -> None:
        if self.agent and self.agent.is_running():
            return
        if not self.ctx.has_api_key():
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self, "API Anahtarı Yok",
                "İzleme, API sağlık kontrolleri için anahtar gerektirir. "
                "Önce Ayarlar'dan anahtarınızı girin."
            )
            return

        # Ayarları kalıcılaştır
        self.ctx.settings.monitor_real_model_test = self.real_test.isChecked()
        self.ctx.settings.announcement_url = (
            self.url_row.findChildren(QLabel)[1].text()
        )
        self.ctx.save_settings()
        self.log.clear()
        self.report.clear()

        try:
            client = self.ctx.make_client()
        except RuntimeError as exc:
            self.state_row.findChildren(QLabel)[1].setText(str(exc))
            return

        import time as _time

        start_time = _time.monotonic()

        def on_check(result):
            status = "✓" if result.ok else "✗"
            line = f"[{result.kind}] {status} {result.detail}"
            if result.change_detected and result.change_summary:
                line += f" | DEĞİŞİKLİK: {result.change_summary}"
            self.log.appendPlainText(line)
            elapsed = _time.monotonic() - start_time
            pct = int(min(100, elapsed * 100 / (self.agent.duration_minutes * 60)))
            self.progress.setValue(pct)
            remaining = max(0, self.agent.duration_minutes - elapsed / 60)
            self.state_row.findChildren(QLabel)[1].setText(
                f"çalışıyor — kalan ~{remaining:.0f} dk"
            )

        def on_state(state):
            self.start_btn.setEnabled(state != "running")
            self.stop_btn.setEnabled(state == "running")
            if state == "completed":
                self.state_row.findChildren(QLabel)[1].setText(
                    "tamamlandı (30 dakika)"
                )
                self.progress.setValue(100)
            elif state == "stopped_by_user":
                self.state_row.findChildren(QLabel)[1].setText("kullanıcı durdurdu")

        def on_finished(report_obj):
            self.report.setPlainText(self.agent.report_markdown(report_obj))
            client.close()

        self.agent = MonitorAgent(
            db=self.ctx.db,
            target_url=self.ctx.settings.announcement_url,
            interval_minutes=self.ctx.settings.monitor_interval_minutes,
            duration_minutes=self.ctx.settings.monitor_duration_minutes,
            client=client,
            real_model_test=self.real_test.isChecked(),
            test_model=self.test_model_btn.text(),
            on_check=on_check,
            on_finished=on_finished,
            on_state_change=on_state,
        )
        self.agent.start()
        self.state_row.findChildren(QLabel)[1].setText("başlatıldı…")

    def stop(self) -> None:
        if self.agent and self.agent.is_running():
            self.agent.stop()
