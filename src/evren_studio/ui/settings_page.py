"""Ayarlar sayfası: anahtar yönetimi, model tercihleri, zaman aşımı, tema."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..agent.permissions import MODE_HINTS, MODES
from ..secrets import delete_api_key, load_api_key, mask_api_key, save_api_key
from .base_page import BasePage, card, kv_row


class SettingsPage(BasePage):
    title = "Ayarlar"
    settings_saved = Signal()

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        s = ctx.settings

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        col = QVBoxLayout(inner)
        col.setSpacing(12)

        # ---- API anahtarı ----
        c, l = card()
        l.addWidget(section("API Anahtarı (Windows Credential Manager)"))
        l.addWidget(hint(
            "Anahtar kaynak koda, ayar dosyasına veya loglara yazılmaz; "
            "Windows'un kimlik bilgisi kasasında saklanır ve maskeli gösterilir."
        ))
        self.key_row = kv_row("Kayıtlı anahtar:", mask_api_key(load_api_key()) or "yok")
        l.addWidget(self.key_row)
        row = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("Yeni anahtar (yapıştırın)…")
        show_btn = QPushButton("Göster/Gizle")
        show_btn.clicked.connect(
            lambda: self.key_input.setEchoMode(
                QLineEdit.Normal
                if self.key_input.echoMode() == QLineEdit.Password
                else QLineEdit.Password
            )
        )
        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self.save_key)
        del_btn = QPushButton("Anahtarı Sil")
        del_btn.clicked.connect(self.delete_key)
        row.addWidget(self.key_input, 1)
        row.addWidget(show_btn)
        row.addWidget(save_btn)
        row.addWidget(del_btn)
        l.addLayout(row)
        col.addWidget(c)

        # ---- bağlantı ----
        c, l = card()
        l.addWidget(section("Bağlantı"))
        self.base_url = QLineEdit(s.base_url)
        l.addWidget(kv_row_widget("API adresi:", self.base_url))
        self.announcement_url = QLineEdit(s.announcement_url)
        l.addWidget(kv_row_widget("Duyuru sayfası (izlenecek URL):", self.announcement_url))
        col.addWidget(c)

        # ---- model tercihleri ----
        c, l = card()
        l.addWidget(section("Model Tercihleri"))
        self.default_model = QComboBox()
        self.default_model.setEditable(True)
        self.default_model.addItems([
            "glm-5.3", "auto", "deepseek-v4-flash", "deepseek-v4.1-flash",
            "mimo-v2.6-pro", "qwen3.8-flash-next", "gemma-4-31b",
        ])
        self.default_model.setCurrentText(s.default_model)
        l.addWidget(kv_row_widget("Varsayılan sohbet modeli:", self.default_model))
        self.auto_switch = QCheckBox(
            "Hata durumunda otomatik model değiştirme (önerilmez)"
        )
        self.auto_switch.setChecked(s.auto_model_switch)
        l.addWidget(self.auto_switch)
        col.addWidget(c)

        # ---- istek davranışı ----
        c, l = card()
        l.addWidget(section("İstek Davranışı"))
        self.timeout = QDoubleSpinBox()
        self.timeout.setRange(10, 600)
        self.timeout.setSuffix(" sn")
        self.timeout.setValue(s.timeout_seconds)
        l.addWidget(kv_row_widget("Zaman aşımı:", self.timeout))
        self.retries = QSpinBox()
        self.retries.setRange(0, 5)
        self.retries.setValue(s.max_retries)
        l.addWidget(kv_row_widget(
            "Otomatik tekrar sınırı (429/5xx):", self.retries
        ))
        self.streaming = QCheckBox("Yanıtları akış halinde göster (önerilir)")
        self.streaming.setChecked(s.stream_responses)
        l.addWidget(self.streaming)
        col.addWidget(c)

        # ---- kod ajanı ----
        c, l = card()
        l.addWidget(section("Kod Ajanı"))
        l.addWidget(hint(
            "Kod ajanı yalnızca seçtiğiniz proje klasöründe çalışır. Komutlar hiçbir "
            "modda onaysız çalışmaz; dosya değişiklikleri sağ paneldeki "
            "“Değişiklikler” sekmesinden geri alınabilir."
        ))
        self.agent_mode = QComboBox()
        for key, label in MODES.items():
            self.agent_mode.addItem(f"{label} — {MODE_HINTS[key]}", key)
        self.agent_mode.setCurrentIndex(max(0, self.agent_mode.findData(s.agent_mode)))
        l.addWidget(kv_row_widget("Varsayılan çalışma modu:", self.agent_mode))
        self.tool_protocol = QComboBox()
        for key, label in (("otomatik", "Otomatik (önerilir) — yerel araç çağrısı, reddedilirse metin"),
                           ("yerel", "Yerel function calling (tools)"),
                           ("metin", "Metin protokolü (<arac_cagrisi> blokları)")):
            self.tool_protocol.addItem(label, key)
        self.tool_protocol.setCurrentIndex(max(0, self.tool_protocol.findData(s.tool_protocol)))
        l.addWidget(kv_row_widget("Araç protokolü:", self.tool_protocol))
        self.max_steps = QSpinBox()
        self.max_steps.setRange(5, 200)
        self.max_steps.setValue(s.agent_max_steps)
        l.addWidget(kv_row_widget("Tur başına en fazla adım:", self.max_steps))
        self.cmd_timeout = QSpinBox()
        self.cmd_timeout.setRange(10, 1800)
        self.cmd_timeout.setSuffix(" sn")
        self.cmd_timeout.setValue(s.command_timeout_seconds)
        l.addWidget(kv_row_widget("Komut zaman aşımı:", self.cmd_timeout))
        self.output_limit = QSpinBox()
        self.output_limit.setRange(2000, 200000)
        self.output_limit.setSingleStep(1000)
        self.output_limit.setSuffix(" karakter")
        self.output_limit.setValue(s.tool_output_limit)
        l.addWidget(kv_row_widget("Araç çıktısı sınırı (modele):", self.output_limit))
        self.show_reasoning = QCheckBox("Modelin düşünce sürecini göster (glm-5.3 gibi muhakeme modelleri)")
        self.show_reasoning.setChecked(s.show_reasoning)
        l.addWidget(self.show_reasoning)
        self.send_enter = QCheckBox("Enter ile gönder (kapalıysa Ctrl+Enter)")
        self.send_enter.setChecked(s.send_with_enter)
        l.addWidget(self.send_enter)
        col.addWidget(c)

        # ---- veri ve görünüm ----
        c, l = card()
        l.addWidget(section("Veri ve Görünüm"))
        self.data_dir = QLineEdit(str(ctx.data_dir()))
        browse = QPushButton("…")
        browse.clicked.connect(self.browse_data_dir)
        l.addWidget(kv_row_with("Yerel verilerin konumu:", self.data_dir, browse))
        self.theme = QComboBox()
        self.theme.addItems(["koyu", "açık"])
        self.theme.setCurrentText(s.theme)
        l.addWidget(kv_row_widget("Tema:", self.theme))
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 16)
        self.font_size.setValue(s.font_size)
        l.addWidget(kv_row_widget("Yazı boyutu (pt):", self.font_size))
        self.retention = QSpinBox()
        self.retention.setRange(7, 365)
        self.retention.setSuffix(" gün")
        self.retention.setValue(s.error_log_retention_days)
        l.addWidget(kv_row_widget("Hata kayıtlarını saklama süresi:", self.retention))
        col.addWidget(c)

        # ---- dışa aktarma / silme ----
        c, l = card()
        l.addWidget(section("Veri Dışa Aktarma ve Silme"))
        export_btn = QPushButton("Tüm Verileri Dışa Aktar (JSON)")
        export_btn.clicked.connect(self.export_data)
        purge_btn = QPushButton("Eski Hata Kayıtlarını Temizle")
        purge_btn.clicked.connect(self.purge_errors)
        wipe_btn = QPushButton("Tüm Sohbetleri ve Kayıtları Sil")
        wipe_btn.clicked.connect(self.wipe_data)
        l.addWidget(export_btn)
        l.addWidget(purge_btn)
        l.addWidget(wipe_btn)
        col.addWidget(c)

        c, l = card()
        l.addWidget(kv_row("Uygulama sürümü:", __version__))
        col.addWidget(c)
        col.addStretch(1)

        save_all = QPushButton("Tüm Ayarları Kaydet")
        save_all.setProperty("variant", "primary")
        save_all.clicked.connect(self.save_all)
        col.addWidget(save_all)
        scroll.setWidget(inner)
        self.root.addWidget(scroll, 1)

    # ---- eylemler --------------------------------------------------------

    def save_key(self) -> None:
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Boş Anahtar", "Yeni anahtar alanı boş.")
            return
        try:
            save_api_key(key)
        except Exception as exc:
            QMessageBox.critical(
                self, "Güvenli Saklama Başarısız",
                f"Anahtar Windows Credential Manager'a yazılamadı:\n{exc}\n\n"
                "Düz metin dosyaya geçilmez; lütfen Windows kimlik bilgisi "
                "hizmetinin çalıştığını kontrol edin."
            )
            return
        self.ctx.api_key(refresh=True)
        self.key_input.clear()
        self.key_row.findChildren(QLabel)[1].setText(
            mask_api_key(load_api_key()) + " (güncellendi)"
        )

    def delete_key(self) -> None:
        if QMessageBox.question(
            self, "Anahtarı Sil",
            "API anahtarı Windows Credential Manager'dan silinsin mi?",
        ) == QMessageBox.Yes:
            delete_api_key()
            self.ctx.api_key(refresh=True)
            self.key_row.findChildren(QLabel)[1].setText("yok")

    def browse_data_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Veri klasörü seç")
        if d:
            self.data_dir.setText(d)

    def save_all(self) -> None:
        s = self.ctx.settings
        s.base_url = self.base_url.text().strip() or s.base_url
        s.announcement_url = self.announcement_url.text().strip()
        s.default_model = self.default_model.currentText()
        s.auto_model_switch = self.auto_switch.isChecked()
        s.timeout_seconds = float(self.timeout.value())
        s.max_retries = int(self.retries.value())
        s.stream_responses = self.streaming.isChecked()
        s.data_dir = self.data_dir.text().strip()
        s.theme = self.theme.currentText()
        s.font_size = int(self.font_size.value())
        s.error_log_retention_days = int(self.retention.value())
        s.agent_mode = self.agent_mode.currentData()
        s.tool_protocol = self.tool_protocol.currentData()
        s.agent_max_steps = int(self.max_steps.value())
        s.command_timeout_seconds = int(self.cmd_timeout.value())
        s.tool_output_limit = int(self.output_limit.value())
        s.show_reasoning = self.show_reasoning.isChecked()
        s.send_with_enter = self.send_enter.isChecked()
        self.ctx.save_settings()
        self.settings_saved.emit()
        QMessageBox.information(self, "Kaydedildi", "Ayarlar kaydedildi.")

    def export_data(self) -> None:
        import json

        path, _ = QFileDialog.getSaveFileName(
            self, "Verileri Dışa Aktar", "evren-studio-veri.json", "JSON (*.json)"
        )
        if not path:
            return
        db = self.ctx.db
        data = {
            "sessions": [
                {**dict(r), "messages": db.get_session_messages(r["id"])}
                for r in db.list_sessions(limit=100000)
            ],
            "chats": [dict(r) for r in self.ctx.db.list_chats()],
            "errors": [dict(r) for r in self.ctx.db.list_errors(limit=10000)],
            "model_health": [dict(r) for r in self.ctx.db.all_model_health()],
        }
        from pathlib import Path

        Path(path).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def purge_errors(self) -> None:
        n = self.ctx.db.purge_old_errors(self.ctx.settings.error_log_retention_days)
        QMessageBox.information(
            self, "Temizlendi", f"{n} eski hata kaydı silindi."
        )

    def wipe_data(self) -> None:
        if QMessageBox.question(
            self, "Tüm Verileri Sil",
            "TÜM oturumlar, sohbetler, hata kayıtları ve izleme kayıtları silinecek. "
            "API anahtarı ve proje dosyalarınız silinmez. Devam edilsin mi?",
        ) == QMessageBox.Yes:
            self.ctx.db.wipe_user_data()
            QMessageBox.information(self, "Tamamlandı", "Yerel veriler silindi.")


def kv_row_widget(label: str, widget: QWidget) -> QWidget:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    lab = QLabel(label)
    lab.setObjectName("dim")
    lab.setMinimumWidth(220)
    h.addWidget(lab)
    h.addWidget(widget, 1)
    return w


def kv_row_with(label: str, widget: QWidget, extra: QWidget) -> QWidget:
    w = kv_row_widget(label, widget)
    w.layout().addWidget(extra)
    return w


def section(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setProperty("role", "h2")
    return lab


def hint(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setProperty("role", "dim")
    lab.setWordWrap(True)
    return lab
