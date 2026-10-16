"""EVREN Durum Ä°zleme AjanÄ± sayfasÄ±.

KullanÄ±cÄ± baÅŸlatmalÄ± 30 dakikalÄ±k izleme (5 dakikada bir kontrol).
Rapor TÃ¼rkÃ§e hazÄ±rlanÄ±r; belirsiz ve kesin bulgular ayrÄ±lÄ±r.
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
    title = "EVREN Durum Ä°zleme"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self.agent: MonitorAgent | None = None

        c, l = card()
        l.addWidget(QLabel(
            "Bu ajan, seÃ§ili duyuru sayfasÄ±nÄ± ve EVREN API saÄŸlÄ±k uÃ§larÄ±nÄ± "
            "(token harcamadan) izler. Ä°zlemeyi baÅŸlattÄ±ÄŸÄ±nÄ±zda sayfa her "
            "5 dakikada bir kontrol edilir ve toplam 30 dakika sÃ¼rer "
            "(baÅŸlangÄ±Ã§ dahil normal koÅŸullarda 7 kontrol). GerÃ§ek model "
            "testi yalnÄ±zca siz iÅŸaretlediyseniz yapÄ±lÄ±r ve token harcar.\n\n"
            "Not: EVREN duyuru API'si platform giriÅŸi istediÄŸinden izlenen "
            "sayfa varsayÄ±lan olarak herkese aÃ§Ä±k ana sayfadÄ±r. Ayarlar'dan "
            "farklÄ± bir duyuru adresi seÃ§ebilirsiniz."
        ))
        self.url_row = kv_row("Ä°zlenen sayfa:", ctx.settings.announcement_url)
        l.addWidget(self.url_row)
        l.addWidget(QLabel("Kalan sÃ¼re: -"))

        opts = QHBoxLayout()
        self.real_test = QCheckBox("GerÃ§ek model testi yap (token harcar)")
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
        self.start_btn = QPushButton("Ä°zlemeyi BaÅŸlat")
        self.start_btn.clicked.connect(self.start)
        self.stop_btn = QPushButton("Ä°zlemeyi Durdur")
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
        self.state_row = kv_row("Durum:", "Ã§alÄ±ÅŸmÄ±yor")
        l.addWidget(self.state_row)
        self.root.addWidget(c)

        c2, l2 = card()
        l2.addWidget(QLabel("CanlÄ± kontrol kaydÄ±"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(280)
        l2.addWidget(self.log)
        self.root.addWidget(c2, 1)

        c3, l3 = card()
        l3.addWidget(QLabel("Ä°zleme raporu (30 dakika sonunda veya durdurunca)"))
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        l3.addWidget(self.report)
        self.root.addWidget(c3, 1)

        self._check_resume()

    # ---- devam seÃ§eneÄŸi ------------------------------------------------

    def _check_resume(self) -> None:
        open_session = self.ctx.db.get_open_monitor_session()
        if not open_session:
            return
        resume_btn = QPushButton(
            f"YarÄ±m kalan izlemeye devam et (#{open_session['id']}, "
            f"baÅŸlangÄ±Ã§ {open_session['started_at'][:16].replace('T', ' ')})"
        )
        resume_btn.clicked.connect(self.start)
        self.root.insertWidget(1, resume_btn)
        self.state_row.findChildren(QLabel)[1].setText(
            "Ã¶nceki izleme yarÄ±m kaldÄ± â€” devam seÃ§eneÄŸi yukarÄ±da"
        )

    # ---- model seÃ§imi ------------------------------------------------------

    def pick_model(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        models = ["glm-5.3", "auto", "deepseek-v4-flash", "mimo-v2.6-pro",
                  "qwen3.8-flash-next", "gemma-4-31b"]
        current = self.test_model_btn.text()
        model, ok = QInputDialog.getItem(
            self, "Test Modeli", "Hangi modelle gerÃ§ek istek testi yapÄ±lsÄ±n?",
            models, models.index(current) if current in models else 0, False,
        )
        if ok:
            self.test_model_btn.setText(model)
            self.ctx.settings.monitor_test_model = model
            self.ctx.save_settings()

    # ---- izleme yaÅŸam dÃ¶ngÃ¼sÃ¼ ------------------------------------------------

    def start(self) -> None:
        if self.agent and self.agent.is_running():
            return
        if not self.ctx.has_api_key():
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self, "API AnahtarÄ± Yok",
                "Ä°zleme, API saÄŸlÄ±k kontrolleri iÃ§in anahtar gerektirir. "
                "Ã–nce Ayarlar'dan anahtarÄ±nÄ±zÄ± girin."
            )
            return

        # AyarlarÄ± kalÄ±cÄ±laÅŸtÄ±r
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
            status = "âœ“" if result.ok else "âœ—"
            line = f"[{result.kind}] {status} {result.detail}"
            if result.change_detected and result.change_summary:
                line += f" | DEÄÄ°ÅÄ°KLÄ°K: {result.change_summary}"
            self.log.appendPlainText(line)
            elapsed = _time.monotonic() - start_time
            pct = int(min(100, elapsed * 100 / (self.agent.duration_minutes * 60)))
            self.progress.setValue(pct)
            remaining = max(0, self.agent.duration_minutes - elapsed / 60)
            self.state_row.findChildren(QLabel)[1].setText(
                f"Ã§alÄ±ÅŸÄ±yor â€” kalan ~{remaining:.0f} dk"
            )

        def on_state(state):
            self.start_btn.setEnabled(state != "running")
            self.stop_btn.setEnabled(state == "running")
            if state == "completed":
                self.state_row.findChildren(QLabel)[1].setText(
                    "tamamlandÄ± (30 dakika)"
                )
                self.progress.setValue(100)
            elif state == "stopped_by_user":
                self.state_row.findChildren(QLabel)[1].setText("kullanÄ±cÄ± durdurdu")

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
        self.state_row.findChildren(QLabel)[1].setText("baÅŸlatÄ±ldÄ±â€¦")

    def stop(self) -> None:
        if self.agent and self.agent.is_running():
            self.agent.stop()
