"""Chat sayfasÄ±: akÄ±ÅŸlÄ± sohbet, iptal, model seÃ§imi, hata kurtarma."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..api.client import CancelToken
from ..api.errors import ApiError, ErrorKind
from .base_page import BasePage
from .workers import Task

ROLE_LABELS = {"user": "Siz", "assistant": "Asistan", "system": "Sistem"}


class MessageWidget(QWidget):
    """Tek bir sohbet mesajÄ± (Markdown destekli, kopyalanabilir)."""

    def __init__(self, role: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        head = QHBoxLayout()
        who = QLabel(ROLE_LABELS.get(role, role))
        who.setObjectName("msgRole")
        copy_btn = QPushButton("Kopyala")
        copy_btn.setFixedHeight(22)
        copy_btn.clicked.connect(self._copy)
        head.addWidget(who)
        head.addStretch(1)
        head.addWidget(copy_btn)
        lay.addLayout(head)
        self.body = QPlainTextEdit()
        self.body.setReadOnly(True)
        self.body.setObjectName("msgBody")
        # TÃ¼rkÃ§e karakterler iÃ§in eÅŸit geniÅŸlikli font karÄ±ÅŸÄ±klÄ±ÄŸÄ±nÄ± Ã¶nle
        f = QFont("Consolas")
        f.setStyleHint(QFont.Monospace)
        f.setPointSize(10)
        self.body.setFont(f)
        self.body.setFrameShape(QPlainTextEdit.NoFrame)
        lay.addWidget(self.body)

    def _copy(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.body.toPlainText())

    def append_text(self, text: str) -> None:
        self.body.setPlainText(self.body.toPlainText() + text)

    def set_text(self, text: str) -> None:
        self.body.setPlainText(text)


class ChatPage(BasePage):
    title = "Chat"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        self.chat_id: int | None = None
        self.cancel_token: CancelToken | None = None
        self.streaming_widget: MessageWidget | None = None
        self.pending_user_text: str = ""
        self._advice_for_last_error: object | None = None

        bar = QHBoxLayout()
        self.new_btn = QPushButton("Yeni Sohbet")
        self.new_btn.clicked.connect(self.new_chat)
        self.rename_btn = QPushButton("Yeniden AdlandÄ±r")
        self.rename_btn.clicked.connect(self.rename_chat)
        self.export_btn = QPushButton("DÄ±ÅŸa Aktar (Markdown)")
        self.export_btn.clicked.connect(self.export_chat)
        self.delete_btn = QPushButton("Sohbeti Sil")
        self.delete_btn.clicked.connect(self.delete_chat)
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(220)
        self.model_info = QLabel("")
        self.model_info.setObjectName("dim")
        for w in (self.new_btn, self.rename_btn, self.export_btn, self.delete_btn):
            bar.addWidget(w)
        bar.addStretch(1)
        bar.addWidget(QLabel("Model:"))
        bar.addWidget(self.model_combo)
        self.root.addLayout(bar)
        self.root.addWidget(self.model_info)

        splitter = QSplitter(Qt.Vertical)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.messages_host = QWidget()
        self.messages_lay = QVBoxLayout(self.messages_host)
        self.messages_lay.setAlignment(Qt.AlignTop)
        self.messages_lay.setSpacing(6)
        self.scroll.setWidget(self.messages_host)
        splitter.addWidget(self.scroll)

        input_host = QWidget()
        input_lay = QVBoxLayout(input_host)
        input_lay.setContentsMargins(0, 6, 0, 0)
        self.input = QPlainTextEdit()
        self.input.setPlaceholderText(
            "MesajÄ±nÄ±zÄ± yazÄ±nâ€¦ (Ctrl+Enter ile gÃ¶nderin)"
        )
        self.input.setFixedHeight(110)
        input_lay.addWidget(self.input)
        btns = QHBoxLayout()
        self.send_btn = QPushButton("GÃ¶nder")
        self.send_btn.clicked.connect(self.send)
        self.stop_btn = QPushButton("Ä°ptal Et")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.cancel_send)
        self.state_label = QLabel("")
        self.state_label.setObjectName("dim")
        btns.addWidget(self.state_label, 1)
        btns.addWidget(self.stop_btn)
        btns.addWidget(self.send_btn)
        input_lay.addLayout(btns)
        splitter.addWidget(input_host)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        self.root.addWidget(splitter, 1)

        self.model_combo.currentIndexChanged.connect(self.show_model_info)
        self.new_chat()

    # ---- model listesi -----------------------------------------------------

    def set_models(self, models: list) -> None:
        current = self.model_combo.currentText()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        chat_models = [m for m in models if m.supports_chat]
        for m in chat_models:
            self.model_combo.addItem(m.id)
        if current:
            idx = self.model_combo.findText(current)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
        self.model_combo.blockSignals(False)
        pref = self.ctx.settings.default_model
        idx = self.model_combo.findText(pref)
        if idx >= 0 and not current:
            self.model_combo.setCurrentIndex(idx)
        self.show_model_info()

    def show_model_info(self) -> None:
        mid = self.model_combo.currentText()
        if not mid:
            self.model_info.setText("")
            return
        hint = ""
        if mid == "auto":
            hint = " | auto: akÄ±llÄ± yÃ¶nlendirme (seÃ§im sunucuda yapÄ±lÄ±r)"
        self.model_info.setText(f"SeÃ§ili model: {mid}{hint}")

    # ---- sohbet yÃ¶netimi ------------------------------------------------------

    def new_chat(self) -> None:
        model = self.model_combo.currentText() or self.ctx.settings.default_model
        self.chat_id = self.ctx.db.create_chat(model=model)
        self.clear_messages()
        self.state_label.setText(f"Yeni sohbet #{self.chat_id}")

    def clear_messages(self) -> None:
        while self.messages_lay.count():
            item = self.messages_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def load_chat(self, chat_id: int) -> None:
        self.chat_id = chat_id
        self.clear_messages()
        rows = self.ctx.db.get_messages(chat_id)
        for r in rows:
            w = MessageWidget(r["role"])
            w.set_text(r["content"] or "")
            self.messages_lay.addWidget(w)
        self.state_label.setText(f"Sohbet #{chat_id} yÃ¼klendi ({len(rows)} mesaj)")
        self.scroll_to_bottom()

    def rename_chat(self) -> None:
        if not self.chat_id:
            return
        from PySide6.QtWidgets import QInputDialog

        title, ok = QInputDialog.getText(self, "Sohbeti AdlandÄ±r",
                                         "Yeni baÅŸlÄ±k:", text=self.current_title())
        if ok and title.strip():
            self.ctx.db.rename_chat(self.chat_id, title.strip())

    def current_title(self) -> str:
        for c in self.ctx.db.list_chats():
            if c["id"] == self.chat_id:
                return c["title"]
        return ""

    def export_chat(self) -> None:
        if not self.chat_id:
            return
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Sohbeti DÄ±ÅŸa Aktar", f"sohbet-{self.chat_id}.md",
            "Markdown (*.md)"
        )
        if path:
            from pathlib import Path

            Path(path).write_text(
                self.ctx.db.export_chat_markdown(self.chat_id),
                encoding="utf-8",
            )
            self.state_label.setText(f"DÄ±ÅŸa aktarÄ±ldÄ±: {path}")

    def delete_chat(self) -> None:
        if not self.chat_id:
            return
        confirm = QMessageBox.question(
            self, "Sohbeti Sil",
            "Bu sohbeti ve tÃ¼m mesajlarÄ±nÄ± silmek istediÄŸinize emin misiniz? "
            "Bu iÅŸlem geri alÄ±namaz."
        )
        if confirm == QMessageBox.Yes:
            self.ctx.db.delete_chat(self.chat_id)
            self.new_chat()

    # ---- gÃ¶nderim ------------------------------------------------------------

    def send(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            return
        if not self.ctx.has_api_key():
            QMessageBox.warning(
                self, "API AnahtarÄ± Yok",
                "Ã–nce Ayarlar sayfasÄ±ndan API anahtarÄ±nÄ±zÄ± girin.\n"
                "Anahtar Windows Credential Manager'da gÃ¼venle saklanÄ±r."
            )
            return
        if self.send_btn.isEnabled() is False:
            return

        model = self.model_combo.currentText()
        if not model:
            QMessageBox.warning(self, "Model SeÃ§ilmedi",
                                "LÃ¼tfen bir sohbet modeli seÃ§in.")
            return

        self.pending_user_text = text
        self.input.clear()
        user_w = MessageWidget("user")
        user_w.set_text(text)
        self.messages_lay.addWidget(user_w)

        history = [
            {"role": r["role"], "content": r["content"]}
            for r in self.ctx.db.get_messages(self.chat_id)
        ]
        history.append({"role": "user", "content": text})
        self.ctx.db.add_message(self.chat_id, "user", text)

        # Ä°lk mesajda sohbeti otomatik adlandÄ±r
        if len(history) == 1:
            short = text[:40] + ("â€¦" if len(text) > 40 else "")
            self.ctx.db.rename_chat(self.chat_id, short)

        assistant_w = MessageWidget("assistant")
        self.messages_lay.addWidget(assistant_w)
        self.streaming_widget = assistant_w
        self.scroll_to_bottom()

        self.set_busy(True)
        self.cancel_token = CancelToken()
        stream = self.ctx.settings.stream_responses
        self.state_label.setText("YanÄ±t bekleniyorâ€¦" if stream else "YanÄ±t alÄ±nÄ±yor (akÄ±ÅŸ kapalÄ±)â€¦")

        def on_delta(chunk: str, finish: str) -> None:
            assistant_w.append_text(chunk)
            self.scroll_to_bottom()

        def on_reasoning(chunk: str) -> None:
            pass  # MVP: muhakeme akÄ±ÅŸÄ± gÃ¶sterilmez, yalnÄ±zca kaydedilir

        def job():
            client = self.ctx.make_client(log_sink=lambda m: None)
            max_tokens = None
            try:
                return client.chat(
                    model, history, max_tokens=max_tokens, stream=stream,
                    cancel=self.cancel_token, on_delta=on_delta,
                    on_reasoning=on_reasoning,
                )
            finally:
                client.close()

        def done(result):
            cancelled = result.finish_reason == "cancelled_by_user"
            content = result.content or (result.reasoning if not cancelled else "")
            if cancelled:
                content = (assistant_w.body.toPlainText() or "") + "\n\n[iptal edildi]"
            assistant_w.set_text(content or "")
            self.ctx.db.add_message(
                self.chat_id, "assistant", content or "", model=result.model,
                reasoning=result.reasoning or None, request_id=result.request_id,
            )
            routed = f" (yÃ¶nlendirilen: {result.routed_model})" if result.routed_model else ""
            self.state_label.setText(
                f"TamamlandÄ±{routed} â€” finish: {result.finish_reason}"
            )
            self.set_busy(False)
            self.scroll_to_bottom()

        def fail(exc: Exception):
            self.handle_chat_error(exc, assistant_w, model)

        Task(job, on_done=done, on_error=fail).start()

    def cancel_send(self) -> None:
        if self.cancel_token:
            self.cancel_token.cancel()
            self.state_label.setText("Ä°ptal istendiâ€¦")

    def set_busy(self, busy: bool) -> None:
        self.send_btn.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)
        if not busy:
            self.cancel_token = None
            self.streaming_widget = None

    def scroll_to_bottom(self) -> None:
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    # ---- hata iÅŸleme (kurtarma sÃ¼reci) --------------------------------------

    def handle_chat_error(self, exc: Exception, widget: MessageWidget,
                          model: str) -> None:
        self.set_busy(False)
        if isinstance(exc, ApiError):
            # 1) Kaydet  2) GeÃ§miÅŸ Ã§Ã¶zÃ¼m ara  3) KullanÄ±cÄ±ya TÃ¼rkÃ§e Ã¶neri sun
            open_mon = self.ctx.db.get_open_monitor_session()
            monitor_state = (
                f"izleme #{open_mon['id']} Ã§alÄ±ÅŸÄ±yor" if open_mon
                else "izleme kapalÄ±"
            )
            error_id = self.ctx.recovery.record_error(
                exc, monitor_state=monitor_state,
                context=f"chat_id={self.chat_id}, kullanÄ±cÄ± mesajÄ±: "
                        f"'{self.pending_user_text[:60]}'",
            )
            advice = self.ctx.recovery.advise(exc)
            lines = [f"HATA (kayÄ±t #{error_id}): {exc}", ""]
            lines.append(f"OlasÄ± kaynak: {advice.source_guess}")
            if advice.auto_retry_happened:
                lines.append("Otomatik yeniden denemeler yapÄ±ldÄ± ve tÃ¼kendi.")
            for i, step in enumerate(advice.recommended_steps, 1):
                lines.append(f"  {i}. {step}")
            if exc.kind == ErrorKind.UNKNOWN_RESULT and exc.request_id:
                lines.append("")
                lines.append("Ä°steÄŸin sunucuda tamamlanÄ±p tamamlanmadÄ±ÄŸÄ± "
                             "sorgulanÄ±yorâ€¦")
            widget.set_text("\n".join(lines))
            self.state_label.setText(
                f"Hata: {exc.kind.value} â€” ayrÄ±ntÄ±lar mesajda ve Hata Merkezi'nde"
            )

            # Belirsiz sonuÃ§: durum sorgusu (otomatik TEKRAR GÃ–NDERÄ°M yok)
            if exc.kind == ErrorKind.UNKNOWN_RESULT:
                def qjob():
                    client = self.ctx.make_client()
                    try:
                        return client.resolve_unknown_request(exc.request_id)
                    finally:
                        client.close()

                def qdone(status):
                    terminal = status.get("execution_terminal", "unknown")
                    note = status.get("note", "")
                    extra = (
                        f"\n\n[Ä°stek durumu: {terminal}"
                        + (f" â€” {note}" if note else "") + "]"
                    )
                    widget.set_text(widget.body.toPlainText() + extra)

                def qfail(exc2):
                    widget.set_text(
                        widget.body.toPlainText()
                        + "\n\n[Ä°stek durumu sorgulanamadÄ±; sonuÃ§ belirsiz "
                          "kaldÄ±. AynÄ± uzun isteÄŸi otomatik tekrar gÃ¶ndermek "
                          "gÃ¼venli deÄŸil; isterseniz mesajÄ± yeniden gÃ¶nderin.]"
                    )

                Task(qjob, on_done=qdone, on_error=qfail).start()
        else:
            widget.set_text(f"Beklenmeyen yerel hata: {exc}")
            self.state_label.setText("Yerel hata â€” ayrÄ±ntÄ±lar iÃ§in YardÄ±m sayfasÄ±")
