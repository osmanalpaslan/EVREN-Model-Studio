"""Ayarlar sayfasÄ±: anahtar yÃ¶netimi, model tercihleri, zaman aÅŸÄ±mÄ±, tema."""
from __future__ import annotations

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
from ..secrets import delete_api_key, load_api_key, mask_api_key, save_api_key
from .base_page import BasePage, card, kv_row


class SettingsPage(BasePage):
    title = "Ayarlar"

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        s = ctx.settings

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        col = QVBoxLayout(inner)
        col.setSpacing(12)

        # ---- API anahtarÄ± ----
        c, l = card()
        l.addWidget(QLabel("API AnahtarÄ± (Windows Credential Manager)"))
        l.addWidget(QLabel(
            "Anahtar kaynak koda, ayar dosyasÄ±na veya loglara yazÄ±lmaz; "
            "Windows'un kimlik bilgisi kasasÄ±nda saklanÄ±r ve maskeli gÃ¶sterilir."
        ))
        self.key_row = kv_row("KayÄ±tlÄ± anahtar:", mask_api_key(load_api_key()) or "yok")
        l.addWidget(self.key_row)
        row = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("Yeni anahtar (yapÄ±ÅŸtÄ±rÄ±n)â€¦")
        show_btn = QPushButton("GÃ¶ster/Gizle")
        show_btn.clicked.connect(
            lambda: self.key_input.setEchoMode(
                QLineEdit.Normal
                if self.key_input.echoMode() == QLineEdit.Password
                else QLineEdit.Password
            )
        )
        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self.save_key)
        del_btn = QPushButton("AnahtarÄ± Sil")
        del_btn.clicked.connect(self.delete_key)
        row.addWidget(self.key_input, 1)
        row.addWidget(show_btn)
        row.addWidget(save_btn)
        row.addWidget(del_btn)
        l.addLayout(row)
        col.addWidget(c)

        # ---- baÄŸlantÄ± ----
        c, l = card()
        l.addWidget(QLabel("BaÄŸlantÄ±"))
        self.base_url = QLineEdit(s.base_url)
        l.addWidget(kv_row_widget("API adresi:", self.base_url))
        self.announcement_url = QLineEdit(s.announcement_url)
        l.addWidget(kv_row_widget("Duyuru sayfasÄ± (izlenecek URL):", self.announcement_url))
        col.addWidget(c)

        # ---- model tercihleri ----
        c, l = card()
        l.addWidget(QLabel("Model Tercihleri"))
        self.default_model = QComboBox()
        self.default_model.setEditable(True)
        self.default_model.addItems([
            "glm-5.3", "auto", "deepseek-v4-flash", "deepseek-v4.1-flash",
            "mimo-v2.6-pro", "qwen3.8-flash-next", "gemma-4-31b",
        ])
        self.default_model.setCurrentText(s.default_model)
        l.addWidget(kv_row_widget("VarsayÄ±lan sohbet modeli:", self.default_model))
        self.auto_switch = QCheckBox(
            "Hata durumunda otomatik model deÄŸiÅŸtirme (Ã¶nerilmez)"
        )
        self.auto_switch.setChecked(s.auto_model_switch)
        l.addWidget(self.auto_switch)
        col.addWidget(c)

        # ---- istek davranÄ±ÅŸÄ± ----
        c, l = card()
        l.addWidget(QLabel("Ä°stek DavranÄ±ÅŸÄ±"))
        self.timeout = QDoubleSpinBox()
        self.timeout.setRange(10, 600)
        self.timeout.setSuffix(" sn")
        self.timeout.setValue(s.timeout_seconds)
        l.addWidget(kv_row_widget("Zaman aÅŸÄ±mÄ±:", self.timeout))
        self.retries = QSpinBox()
        self.retries.setRange(0, 5)
        self.retries.setValue(s.max_retries)
        l.addWidget(kv_row_widget(
            "Otomatik tekrar sÄ±nÄ±rÄ± (429/5xx):", self.retries
        ))
        self.streaming = QCheckBox("YanÄ±tlarÄ± akÄ±ÅŸ halinde gÃ¶ster (Ã¶nerilir)")
        self.streaming.setChecked(s.stream_responses)
        l.addWidget(self.streaming)
        col.addWidget(c)

        # ---- veri ve gÃ¶rÃ¼nÃ¼m ----
        c, l = card()
        l.addWidget(QLabel("Veri ve GÃ¶rÃ¼nÃ¼m")
        )
        self.data_dir = QLineEdit(str(ctx.data_dir()))
        browse = QPushButton("â€¦")
        browse.clicked.connect(self.browse_data_dir)
        l.addWidget(kv_row_with("Yerel verilerin konumu:", self.data_dir, browse))
        self.theme = QComboBox()
        self.theme.addItems(["koyu", "aÃ§Ä±k"])
        self.theme.setCurrentText(s.theme)
        l.addWidget(kv_row_widget("Tema:", self.theme))
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 16)
        self.font_size.setValue(s.font_size)
        l.addWidget(kv_row_widget("YazÄ± boyutu (pt):", self.font_size))
        self.retention = QSpinBox()
        self.retention.setRange(7, 365)
        self.retention.setSuffix(" gÃ¼n")
        self.retention.setValue(s.error_log_retention_days)
        l.addWidget(kv_row_widget("Hata kayÄ±tlarÄ±nÄ± saklama sÃ¼resi:", self.retention))
        self.automation = QComboBox()
        self.automation.addItems(["onayli", "yarÄ± otomatik"])
        self.automation.setCurrentText(s.automation_level)
        l.addWidget(kv_row_widget("Onay/otomasyon seviyesi:", self.automation))
        col.addWidget(c)

        # ---- dÄ±ÅŸa aktarma / silme ----
        c, l = card()
        l.addWidget(QLabel("Veri DÄ±ÅŸa Aktarma ve Silme"))
        export_btn = QPushButton("TÃ¼m Verileri DÄ±ÅŸa Aktar (JSON)")
        export_btn.clicked.connect(self.export_data)
        purge_btn = QPushButton("Eski Hata KayÄ±tlarÄ±nÄ± Temizle")
        purge_btn.clicked.connect(self.purge_errors)
        wipe_btn = QPushButton("TÃ¼m Sohbetleri ve KayÄ±tlarÄ± Sil")
        wipe_btn.clicked.connect(self.wipe_data)
        l.addWidget(export_btn)
        l.addWidget(purge_btn)
        l.addWidget(wipe_btn)
        col.addWidget(c)

        c, l = card()
        l.addWidget(kv_row("Uygulama sÃ¼rÃ¼mÃ¼:", __version__))
        col.addWidget(c)
        col.addStretch(1)

        save_all = QPushButton("TÃ¼m AyarlarÄ± Kaydet")
        save_all.clicked.connect(self.save_all)
        col.addWidget(save_all)
        scroll.setWidget(inner)
        self.root.addWidget(scroll, 1)

    # ---- eylemler --------------------------------------------------------

    def save_key(self) -> None:
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "BoÅŸ Anahtar", "Yeni anahtar alanÄ± boÅŸ.")
            return
        try:
            save_api_key(key)
        except Exception as exc:
            QMessageBox.critical(
                self, "GÃ¼venli Saklama BaÅŸarÄ±sÄ±z",
                f"Anahtar Windows Credential Manager'a yazÄ±lamadÄ±:\n{exc}\n\n"
                "DÃ¼z metin dosyaya geÃ§ilmez; lÃ¼tfen Windows kimlik bilgisi "
                "hizmetinin Ã§alÄ±ÅŸtÄ±ÄŸÄ±nÄ± kontrol edin."
            )
            return
        self.ctx.api_key(refresh=True)
        self.key_input.clear()
        self.key_row.findChildren(QLabel)[1].setText(
            mask_api_key(load_api_key()) + " (gÃ¼ncellendi)"
        )

    def delete_key(self) -> None:
        if QMessageBox.question(
            self, "AnahtarÄ± Sil",
            "API anahtarÄ± Windows Credential Manager'dan silinsin mi?",
        ) == QMessageBox.Yes:
            delete_api_key()
            self.ctx.api_key(refresh=True)
            self.key_row.findChildren(QLabel)[1].setText("yok")

    def browse_data_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Veri klasÃ¶rÃ¼ seÃ§")
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
        s.automation_level = self.automation.currentText()
        self.ctx.save_settings()
        QMessageBox.information(self, "Kaydedildi", "Ayarlar kaydedildi.")

    def export_data(self) -> None:
        import json

        path, _ = QFileDialog.getSaveFileName(
            self, "Verileri DÄ±ÅŸa Aktar", "evren-studio-veri.json", "JSON (*.json)"
        )
        if not path:
            return
        data = {
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
            self, "Temizlendi", f"{n} eski hata kaydÄ± silindi."
        )

    def wipe_data(self) -> None:
        if QMessageBox.question(
            self, "TÃ¼m Verileri Sil",
            "TÃœM sohbetler, hata kayÄ±tlarÄ± ve izleme kayÄ±tlarÄ± silinecek. "
            "API anahtarÄ± silinmez. Devam edilsin mi?",
        ) == QMessageBox.Yes:
            self.ctx.db._script(
                "DELETE FROM messages; DELETE FROM chats;"
                " DELETE FROM error_records; DELETE FROM monitor_checks;"
                " DELETE FROM monitor_sessions; DELETE FROM model_health;"
            )
            self.ctx.db._commit()
            QMessageBox.information(self, "TamamlandÄ±", "Yerel veriler silindi.")


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
