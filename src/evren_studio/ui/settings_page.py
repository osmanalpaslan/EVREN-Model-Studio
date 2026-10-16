"""Ayarlar sayfası: anahtar yönetimi, sağlayıcılar, bağlantı, model, ajan, görünüm, veri.

- Her alanın yanında varsayılan değer yazar.
- "Varsayılanlara döndür" tüm ayarları önerilen değerlere çeker (API anahtarı,
  veri klasörü ve son proje listesi korunur); kaydetmeden önce onay ister.
- Sayfa her açıldığında değerler güncel ayarlardan yeniden yüklenir.
- Fare tekerleği odaklanmamış alanları değiştirmez (bkz. wheel_guard.py).
- "Ücretli Sağlayıcılar" kartı: OpenAI/Anthropic anahtarları (yine Credential
  Manager), adım adım alma rehberi, panel bağlantıları ve aylık bütçe (tahmini).
"""
from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

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
from ..config import Settings, default_data_dir
from ..api.providers import PRICES_AS_OF, PROVIDERS
from ..budget import current_state, format_usd
from ..secrets import delete_api_key, load_api_key, mask_api_key, save_api_key
from .base_page import BasePage, card, kv_row
from .workers import Task

PAID_PROVIDERS = ("openai", "anthropic")

DEFAULTS = Settings()
# Varsayılana dönerken KORUNAN alanlar (kullanıcının verisi/konumu)
PRESERVED_ON_RESET = {"data_dir", "recent_workspaces", "code_workdir"}
PROTOCOLS = (
    ("otomatik", "Otomatik (önerilir) — yerel araç çağrısı, reddedilirse metin"),
    ("yerel", "Yerel function calling (tools)"),
    ("metin", "Metin protokolü (<arac_cagrisi> blokları)"),
)
FALLBACK_MODEL_IDS = ["glm-5.3", "deepseek-v4.1-flash", "deepseek-v4-flash", "mimo-v2.6-pro",
                      "qwen3.8-flash-next", "gemma-4-31b", "auto"]


def section(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setProperty("role", "h2")
    return lab


def hint(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setProperty("role", "dim")
    lab.setWordWrap(True)
    return lab


def kv_row_widget(label: str, widget: QWidget, default: str | None = None) -> QWidget:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    lab = QLabel(label)
    lab.setObjectName("dim")
    lab.setMinimumWidth(240)
    h.addWidget(lab)
    h.addWidget(widget, 1)
    if default is not None:
        d = QLabel(f"varsayılan: {default}")
        d.setProperty("role", "faint")
        d.setMinimumWidth(150)
        h.addWidget(d)
    return w


def link(text: str, url: str) -> str:
    return f'<a href="{url}">{text}</a>'


def kv_row_with(label: str, widget: QWidget, extra: QWidget) -> QWidget:
    w = kv_row_widget(label, widget)
    w.layout().addWidget(extra)
    return w


class SettingsPage(BasePage):
    title = "Ayarlar"
    settings_saved = Signal()

    def __init__(self, ctx, parent=None):
        super().__init__(ctx, parent)
        reset_btn = QPushButton("Varsayılanlara döndür")
        reset_btn.setToolTip("Tüm ayarları önerilen değerlere döndürür (API anahtarı silinmez)")
        reset_btn.clicked.connect(self.reset_defaults)
        self.header_extra.addWidget(reset_btn)
        save_top = QPushButton("Kaydet")
        save_top.setProperty("variant", "primary")
        save_top.clicked.connect(self.save_all)
        self.header_extra.addWidget(save_top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        col = QVBoxLayout(inner)
        col.setSpacing(12)
        d = DEFAULTS

        # ---- API anahtarı ----
        c, l = card()
        l.addWidget(section("EVREN API Anahtarı (Windows Credential Manager)"))
        l.addWidget(hint(
            "Anahtar kaynak koda, ayar dosyasına veya loglara yazılmaz; Windows'un kimlik "
            "bilgisi kasasında saklanır ve maskeli gösterilir. “Varsayılanlara döndür” "
            "anahtarı silmez."
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
                QLineEdit.Normal if self.key_input.echoMode() == QLineEdit.Password
                else QLineEdit.Password))
        save_btn = QPushButton("Anahtarı kaydet")
        save_btn.clicked.connect(self.save_key)
        del_btn = QPushButton("Anahtarı sil")
        del_btn.setProperty("variant", "danger")
        del_btn.clicked.connect(self.delete_key)
        row.addWidget(self.key_input, 1)
        row.addWidget(show_btn)
        row.addWidget(save_btn)
        row.addWidget(del_btn)
        l.addLayout(row)
        col.addWidget(c)

        # ---- ücretli sağlayıcılar ----
        self._prov: dict[str, dict] = {}
        c, l = card()
        l.addWidget(section("Ücretli Sağlayıcılar (isteğe bağlı)"))
        l.addWidget(hint(
            "EVREN ücretsizdir. OpenAI veya Anthropic modellerini de kullanmak isterseniz kendi "
            "ücretli API anahtarınızı girin; anahtarlar EVREN anahtarı gibi Windows Credential "
            "Manager'da saklanır. Bu modellere gönderdiğiniz mesajlar ve proje dosyası içerikleri "
            "o şirketin sunucularına gider. Bu iki entegrasyon belgelere göre yazıldı, henüz "
            "gerçek anahtarla doğrulanmadı."))
        for pid in PAID_PROVIDERS:
            l.addWidget(self._provider_block(pid))

        # bütçe
        l.addWidget(section("Aylık bütçe (ücretli sağlayıcıların toplamı)"))
        self.budget = QDoubleSpinBox()
        self.budget.setRange(0, 10_000)
        self.budget.setDecimals(2)
        self.budget.setSingleStep(1)
        self.budget.setPrefix("$ ")
        l.addWidget(kv_row_widget("Aylık sınır:", self.budget, f"${d.monthly_budget_usd:.0f}"))
        self.budget_enforce = QCheckBox("Sınıra ulaşınca her yeni istekten önce onay iste (önerilir)")
        l.addWidget(self.budget_enforce)
        self.spend_label = QLabel()
        self.spend_label.setWordWrap(True)
        l.addWidget(self.spend_label)
        l.addWidget(hint(
            f"Harcama, yanıtlardaki token sayıları ve {PRICES_AS_OF} tarihli fiyat listesiyle "
            "TAHMİN edilir; %80'de bir kez uyarılır. Gerçek tutar ve kalan kredi için sağlayıcı "
            "panelindeki Usage sayfasına bakın (kalan kredi API'den okunamıyor). Sağlayıcı "
            "panelinde ayrıca bir harcama sınırı koymanız önerilir."))
        col.addWidget(c)

        # ---- bağlantı ----
        c, l = card()
        l.addWidget(section("Bağlantı"))
        self.base_url = QLineEdit()
        l.addWidget(kv_row_widget("API adresi:", self.base_url, "evren-llmapi…/v1"))
        self.announcement_url = QLineEdit()
        l.addWidget(kv_row_widget("Duyuru sayfası (izlenecek URL):", self.announcement_url,
                                  "evren.ssyz.org.tr"))
        col.addWidget(c)

        # ---- model tercihleri ----
        c, l = card()
        l.addWidget(section("Model Tercihleri"))
        self.default_model = QComboBox()
        self.default_model.setEditable(True)
        l.addWidget(kv_row_widget("Varsayılan model:", self.default_model, d.default_model))
        self.auto_switch = QCheckBox("Hata durumunda otomatik model değiştirme (önerilmez)")
        l.addWidget(self.auto_switch)
        l.addWidget(hint(f"Varsayılan: {'açık' if d.auto_model_switch else 'kapalı'}"))
        col.addWidget(c)

        # ---- istek davranışı ----
        c, l = card()
        l.addWidget(section("İstek Davranışı"))
        self.timeout = QDoubleSpinBox()
        self.timeout.setRange(10, 600)
        self.timeout.setDecimals(0)
        self.timeout.setSuffix(" sn")
        l.addWidget(kv_row_widget("Zaman aşımı:", self.timeout, f"{d.timeout_seconds:.0f} sn"))
        self.retries = QSpinBox()
        self.retries.setRange(0, 5)
        l.addWidget(kv_row_widget("Otomatik tekrar sınırı (429/5xx):", self.retries, str(d.max_retries)))
        self.streaming = QCheckBox("Yanıtları akış halinde göster (önerilir)")
        l.addWidget(self.streaming)
        col.addWidget(c)

        # ---- kod ajanı ----
        c, l = card()
        l.addWidget(section("Kod Ajanı"))
        l.addWidget(hint(
            "Kod ajanı yalnızca seçtiğiniz proje klasöründe çalışır. Komutlar hiçbir modda "
            "onaysız çalışmaz; dosya değişiklikleri sağ paneldeki “Değişiklikler” "
            "sekmesinden geri alınabilir."
        ))
        self.agent_mode = QComboBox()
        for key, label in MODES.items():
            self.agent_mode.addItem(f"{label} — {MODE_HINTS[key]}", key)
        l.addWidget(kv_row_widget("Varsayılan çalışma modu:", self.agent_mode, MODES[d.agent_mode]))
        self.tool_protocol = QComboBox()
        for key, label in PROTOCOLS:
            self.tool_protocol.addItem(label, key)
        l.addWidget(kv_row_widget("Araç protokolü:", self.tool_protocol, d.tool_protocol))
        self.max_steps = QSpinBox()
        self.max_steps.setRange(5, 200)
        l.addWidget(kv_row_widget("Tur başına en fazla adım:", self.max_steps, str(d.agent_max_steps)))
        self.cmd_timeout = QSpinBox()
        self.cmd_timeout.setRange(10, 1800)
        self.cmd_timeout.setSuffix(" sn")
        l.addWidget(kv_row_widget("Komut zaman aşımı:", self.cmd_timeout, f"{d.command_timeout_seconds} sn"))
        self.output_limit = QSpinBox()
        self.output_limit.setRange(2000, 200000)
        self.output_limit.setSingleStep(1000)
        self.output_limit.setSuffix(" karakter")
        l.addWidget(kv_row_widget("Araç çıktısı sınırı (modele):", self.output_limit,
                                  f"{d.tool_output_limit:,}".replace(",", ".")))
        self.auto_compact = QCheckBox("Uzun konuşmaları otomatik özetle (önerilir)")
        l.addWidget(self.auto_compact)
        l.addWidget(hint(
            "Özet, yeni mesaj gönderilmeden önce yapılır; uzun bir görev sırasında yalnızca "
            "güvenli noktada (araç sonuçlarından sonra) yapılır ve ajan kendiliğinden devam eder. "
            "Eşik: modelin bağlamının yüzdesi veya üst sınır (token), hangisi önce gelirse."))
        self.compact_percent = QSpinBox()
        self.compact_percent.setRange(40, 90)
        self.compact_percent.setSuffix(" %")
        l.addWidget(kv_row_widget("Özet eşiği (bağlamın):", self.compact_percent, f"%{d.auto_compact_percent}"))
        self.compact_max = QSpinBox()
        self.compact_max.setRange(10_000, 900_000)
        self.compact_max.setSingleStep(10_000)
        self.compact_max.setSuffix(" token")
        l.addWidget(kv_row_widget("Özet eşiği üst sınırı:", self.compact_max,
                                  f"{d.auto_compact_max_tokens:,}".replace(",", ".")))
        self.compact_model = QComboBox()
        self.compact_model.setEditable(True)
        l.addWidget(kv_row_widget("Özeti üreten model:", self.compact_model, d.auto_compact_model))
        l.addWidget(hint("Boş bırakırsanız oturumun modeli kullanılır. Hızlı bir model önerilir: "
                         "aynı özet glm-5.3 ile ~150 sn, deepseek-v4-flash ile ~40 sn sürdü."))
        self.show_reasoning = QCheckBox("Modelin düşünce sürecini göster (muhakeme modelleri)")
        l.addWidget(self.show_reasoning)
        self.send_enter = QCheckBox("Enter ile gönder (kapalıysa Ctrl+Enter)")
        l.addWidget(self.send_enter)
        col.addWidget(c)

        # ---- veri ve görünüm ----
        c, l = card()
        l.addWidget(section("Veri ve Görünüm"))
        self.data_dir = QLineEdit()
        browse = QPushButton("…")
        browse.clicked.connect(self.browse_data_dir)
        l.addWidget(kv_row_with("Yerel verilerin konumu:", self.data_dir, browse))
        self.theme = QComboBox()
        self.theme.addItems(["koyu", "açık"])
        l.addWidget(kv_row_widget("Tema:", self.theme, d.theme))
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 16)
        self.font_size.setSuffix(" pt")
        l.addWidget(kv_row_widget("Yazı boyutu:", self.font_size, f"{d.font_size} pt"))
        self.retention = QSpinBox()
        self.retention.setRange(7, 365)
        self.retention.setSuffix(" gün")
        l.addWidget(kv_row_widget("Hata kayıtlarını saklama süresi:", self.retention,
                                  f"{d.error_log_retention_days} gün"))
        l.addWidget(hint("Tema ve yazı boyutu kaydedince uygulanır; bazı bileşenler "
                         "yeniden başlatmada tamamen güncellenir."))
        col.addWidget(c)

        # ---- dışa aktarma / silme ----
        c, l = card()
        l.addWidget(section("Veri Dışa Aktarma ve Silme"))
        export_btn = QPushButton("Tüm verileri dışa aktar (JSON)")
        export_btn.clicked.connect(self.export_data)
        purge_btn = QPushButton("Eski hata kayıtlarını temizle")
        purge_btn.clicked.connect(self.purge_errors)
        wipe_btn = QPushButton("Tüm oturumları ve kayıtları sil")
        wipe_btn.setProperty("variant", "danger")
        wipe_btn.clicked.connect(self.wipe_data)
        for b in (export_btn, purge_btn, wipe_btn):
            l.addWidget(b)
        col.addWidget(c)

        c, l = card()
        l.addWidget(kv_row("Uygulama sürümü:", __version__))
        col.addWidget(c)
        col.addStretch(1)

        save_all = QPushButton("Tüm ayarları kaydet")
        save_all.setProperty("variant", "primary")
        save_all.clicked.connect(self.save_all)
        col.addWidget(save_all)
        scroll.setWidget(inner)
        self.root.addWidget(scroll, 1)
        self.load_values()

    # ---- formu doldur / oku ------------------------------------------------

    def refresh(self) -> None:
        self.load_values()

    def load_values(self, s: Settings | None = None) -> None:
        s = s or self.ctx.settings
        self.base_url.setText(s.base_url)
        self.announcement_url.setText(s.announcement_url)
        ids = [m.id for m in self.ctx.chat_models()] or FALLBACK_MODEL_IDS
        self.default_model.clear()
        self.default_model.addItems(ids)
        self.default_model.setCurrentText(s.default_model)
        self.auto_switch.setChecked(s.auto_model_switch)
        self.timeout.setValue(s.timeout_seconds)
        self.retries.setValue(s.max_retries)
        self.streaming.setChecked(s.stream_responses)
        self.agent_mode.setCurrentIndex(max(0, self.agent_mode.findData(s.agent_mode)))
        self.tool_protocol.setCurrentIndex(max(0, self.tool_protocol.findData(s.tool_protocol)))
        self.max_steps.setValue(s.agent_max_steps)
        self.cmd_timeout.setValue(s.command_timeout_seconds)
        self.output_limit.setValue(s.tool_output_limit)
        self.show_reasoning.setChecked(s.show_reasoning)
        self.send_enter.setChecked(s.send_with_enter)
        self.auto_compact.setChecked(s.auto_compact)
        self.compact_percent.setValue(s.auto_compact_percent)
        self.compact_max.setValue(s.auto_compact_max_tokens)
        self.compact_model.clear()
        self.compact_model.addItems([""] + ids)
        self.compact_model.setCurrentText(s.auto_compact_model)
        self.data_dir.setText(s.data_dir or str(default_data_dir()))
        self.theme.setCurrentText(s.theme if s.theme in ("koyu", "açık") else "koyu")
        self.font_size.setValue(s.font_size)
        self.retention.setValue(s.error_log_retention_days)
        self.budget.setValue(s.monthly_budget_usd)
        self.budget_enforce.setChecked(s.budget_enforce)
        self._refresh_provider_rows()
        self._refresh_spend(s)

    def _collect(self, s: Settings) -> None:
        s.base_url = self.base_url.text().strip() or DEFAULTS.base_url
        s.announcement_url = self.announcement_url.text().strip() or DEFAULTS.announcement_url
        s.default_model = self.default_model.currentText().strip() or DEFAULTS.default_model
        s.auto_model_switch = self.auto_switch.isChecked()
        s.timeout_seconds = float(self.timeout.value())
        s.max_retries = int(self.retries.value())
        s.stream_responses = self.streaming.isChecked()
        s.agent_mode = self.agent_mode.currentData()
        s.tool_protocol = self.tool_protocol.currentData()
        s.agent_max_steps = int(self.max_steps.value())
        s.command_timeout_seconds = int(self.cmd_timeout.value())
        s.tool_output_limit = int(self.output_limit.value())
        s.show_reasoning = self.show_reasoning.isChecked()
        s.send_with_enter = self.send_enter.isChecked()
        s.auto_compact = self.auto_compact.isChecked()
        s.auto_compact_percent = int(self.compact_percent.value())
        s.auto_compact_max_tokens = int(self.compact_max.value())
        s.auto_compact_model = self.compact_model.currentText().strip()
        data_dir = self.data_dir.text().strip()
        s.data_dir = "" if not data_dir or Path(data_dir) == default_data_dir() else data_dir
        s.theme = self.theme.currentText()
        s.font_size = int(self.font_size.value())
        s.error_log_retention_days = int(self.retention.value())
        s.monthly_budget_usd = float(self.budget.value())
        s.budget_enforce = self.budget_enforce.isChecked()

    def changed_fields(self) -> list[str]:
        """Varsayılandan farklı olan ayarların adları (bilgi amaçlı)."""
        cur = self.ctx.settings
        return [f.name for f in fields(Settings)
                if f.name not in PRESERVED_ON_RESET and getattr(cur, f.name) != getattr(DEFAULTS, f.name)]

    # ---- eylemler --------------------------------------------------------

    def save_all(self) -> None:
        self._collect(self.ctx.settings)
        self.ctx.save_settings()
        self.settings_saved.emit()
        QMessageBox.information(self, "Kaydedildi", "Ayarlar kaydedildi.")

    def reset_defaults(self) -> None:
        changed = self.changed_fields()
        detail = ("Varsayılandan farklı ayarlar: " + ", ".join(changed)) if changed else \
            "Tüm ayarlar zaten varsayılan değerde."
        if QMessageBox.question(
            self, "Varsayılanlara döndür",
            "Tüm ayarlar önerilen varsayılan değerlere döndürülüp kaydedilecek.\n"
            "API anahtarı, veri klasörü ve son proje listesi korunur.\n\n" + detail
            + "\n\nDevam edilsin mi?",
        ) != QMessageBox.Yes:
            return
        s = self.ctx.settings
        fresh = Settings()
        for f in fields(Settings):
            if f.name not in PRESERVED_ON_RESET:
                setattr(s, f.name, getattr(fresh, f.name))
        self.ctx.save_settings()
        self.load_values()
        self.settings_saved.emit()
        QMessageBox.information(self, "Varsayılanlar yüklendi",
                                "Ayarlar varsayılan değerlere döndürüldü ve kaydedildi.")

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
        self.key_row.findChildren(QLabel)[1].setText(mask_api_key(load_api_key()) + " (güncellendi)")
        self.settings_saved.emit()

    def delete_key(self) -> None:
        if QMessageBox.question(
            self, "Anahtarı Sil", "API anahtarı Windows Credential Manager'dan silinsin mi?",
        ) == QMessageBox.Yes:
            delete_api_key()
            self.ctx.api_key(refresh=True)
            self.key_row.findChildren(QLabel)[1].setText("yok")

    # ---- ücretli sağlayıcılar ----------------------------------------------

    def _provider_block(self, pid: str) -> QWidget:
        info = PROVIDERS[pid]
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 6, 0, 6)
        v.setSpacing(6)
        badge = "" if info.verified else "  ·  doğrulanmadı"
        title = QLabel(f"<b>{info.name}</b>  <span style='color:#d9a441'>ücretli{badge}</span>")
        v.addWidget(title)
        steps = "".join(f"<li>{s}</li>" for s in info.steps)
        how = QLabel(f"Anahtar nasıl alınır:<ol style='margin-top:2px'>{steps}</ol>")
        how.setWordWrap(True)
        how.setProperty("role", "dim")
        v.addWidget(how)
        links = QLabel(" · ".join([
            link("API anahtarları", info.keys_url),
            link("Kredi / faturalama", info.billing_url),
            link("Kullanım", info.usage_url),
            link("Belgeler", info.docs_url),
        ]))
        links.setOpenExternalLinks(True)
        v.addWidget(links)
        for n in info.notes:
            v.addWidget(hint("• " + n))
        key_row = kv_row(f"Kayıtlı {info.name} anahtarı:", "yok")
        v.addWidget(key_row)
        row = QHBoxLayout()
        inp = QLineEdit()
        inp.setEchoMode(QLineEdit.Password)
        inp.setPlaceholderText(f"{info.name} API anahtarı ({info.key_prefix}…) yapıştırın")
        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(lambda _=False, p=pid: self.save_provider_key(p))
        test_btn = QPushButton("Bağlantıyı doğrula")
        test_btn.setToolTip("Model listesini ister (ücretsiz bir istek; token harcamaz)")
        test_btn.clicked.connect(lambda _=False, p=pid: self.verify_provider(p))
        del_btn = QPushButton("Sil")
        del_btn.setProperty("variant", "danger")
        del_btn.clicked.connect(lambda _=False, p=pid: self.delete_provider_key(p))
        row.addWidget(inp, 1)
        for b in (save_btn, test_btn, del_btn):
            row.addWidget(b)
        v.addLayout(row)
        status = QLabel("")
        status.setWordWrap(True)
        status.setProperty("role", "dim")
        v.addWidget(status)
        self._prov[pid] = {"key_label": key_row.findChildren(QLabel)[1], "input": inp,
                           "status": status, "test": test_btn}
        return box

    def _refresh_provider_rows(self) -> None:
        for pid, w in self._prov.items():
            key = self.ctx.provider_key(pid, refresh=True)
            w["key_label"].setText(mask_api_key(key) if key else "yok")

    def _refresh_spend(self, s: Settings | None = None) -> None:
        s = s or self.ctx.settings
        spend = self.ctx.db.month_spend()
        st = current_state(self.ctx.db, s.monthly_budget_usd, s.budget_enforce)
        per = ", ".join(f"{PROVIDERS[p].name} {format_usd(v)}" for p, v in spend.items() if p in PROVIDERS)
        self.spend_label.setText(f"<b>Bu ayki tahmini harcama:</b> {st.text().replace('bu ay tahmini ', '')}"
                                 + (f"  ({per})" if per else ""))

    def save_provider_key(self, pid: str) -> None:
        w = self._prov[pid]
        key = w["input"].text().strip()
        name = PROVIDERS[pid].name
        if not key:
            QMessageBox.warning(self, "Boş Anahtar", f"{name} anahtar alanı boş.")
            return
        if not key.startswith(PROVIDERS[pid].key_prefix):
            if QMessageBox.question(
                self, "Anahtar biçimi",
                f"{name} anahtarları genellikle “{PROVIDERS[pid].key_prefix}” ile başlar. "
                "Yine de kaydedilsin mi?",
            ) != QMessageBox.Yes:
                return
        try:
            save_api_key(key, pid)
        except Exception as exc:
            QMessageBox.critical(
                self, "Güvenli Saklama Başarısız",
                f"{name} anahtarı Windows Credential Manager'a yazılamadı:\n{exc}\n\n"
                "Düz metin dosyaya geçilmez.")
            return
        w["input"].clear()
        self._refresh_provider_rows()
        w["key_label"].setText(w["key_label"].text() + " (güncellendi)")
        w["status"].setText("Kaydedildi. “Bağlantıyı doğrula” ile deneyebilirsiniz.")
        self.settings_saved.emit()       # model seçicide bu sağlayıcının modelleri açılır

    def delete_provider_key(self, pid: str) -> None:
        name = PROVIDERS[pid].name
        if QMessageBox.question(
            self, "Anahtarı Sil", f"{name} API anahtarı Windows Credential Manager'dan silinsin mi?",
        ) != QMessageBox.Yes:
            return
        delete_api_key(pid)
        self._refresh_provider_rows()
        self._prov[pid]["status"].setText("")
        self.settings_saved.emit()

    def verify_provider(self, pid: str) -> None:
        w = self._prov[pid]
        name = PROVIDERS[pid].name
        if not self.ctx.has_provider_key(pid):
            w["status"].setText(f"Önce {name} anahtarını kaydedin.")
            return
        w["status"].setText("Bağlanılıyor…")
        w["test"].setEnabled(False)

        def job():
            client = self.ctx.make_client_for(pid)
            try:
                return client.list_models()
            finally:
                close = getattr(client, "close", None)
                if close:
                    close()

        def done(models):
            w["test"].setEnabled(True)
            ids = ", ".join(m.id for m in models[:6]) or "katalogdaki model bulunamadı"
            w["status"].setText(f"✓ Bağlantı başarılı — kullanılabilir modeller: {ids}")

        def fail(exc):
            w["test"].setEnabled(True)
            w["status"].setText(f"✗ Bağlantı başarısız: {exc}")

        Task(job, on_done=done, on_error=fail).start()

    def browse_data_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Veri klasörü seç")
        if d:
            self.data_dir.setText(d)

    def export_data(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Verileri Dışa Aktar", "evren-studio-veri.json", "JSON (*.json)")
        if not path:
            return
        db = self.ctx.db
        data = {
            "sessions": [{**dict(r), "messages": db.get_session_messages(r["id"])}
                         for r in db.list_sessions(limit=100000)],
            "chats": [dict(r) for r in db.list_chats()],
            "errors": [dict(r) for r in db.list_errors(limit=10000)],
            "model_health": [dict(r) for r in db.all_model_health()],
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        QMessageBox.information(self, "Dışa aktarıldı", f"Veriler kaydedildi:\n{path}")

    def purge_errors(self) -> None:
        n = self.ctx.db.purge_old_errors(self.ctx.settings.error_log_retention_days)
        QMessageBox.information(self, "Temizlendi", f"{n} eski hata kaydı silindi.")

    def wipe_data(self) -> None:
        if QMessageBox.question(
            self, "Tüm Verileri Sil",
            "TÜM oturumlar, sohbetler, hata kayıtları ve izleme kayıtları silinecek. "
            "API anahtarı ve proje dosyalarınız silinmez. Devam edilsin mi?",
        ) == QMessageBox.Yes:
            self.ctx.db.wipe_user_data()
            self.settings_saved.emit()
            QMessageBox.information(self, "Tamamlandı", "Yerel veriler silindi.")
