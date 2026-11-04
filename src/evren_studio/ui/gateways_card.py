"""Ayarlar > Sağlayıcılar: tek anahtarla çok model sunan ağ geçitleri (OpenRouter, Kilo, OpenAI uyumlu).

Kullanıcı (2026-11-01): "kilo gibi birden fazla motor var ise ekleyeceğimiz daha minimal bir api anahtarı
tasarımı". Akış: "Sağlayıcı ekle" → tür seç → (adres) → anahtar → "Modelleri getir" (ücretsiz `/models`
isteği; token harcamaz) → kullanılacak modelleri işaretle → Kaydet. Anahtar yalnız Credential Manager'da
(`gw-…_api_key`); ayarlarda yalnız tür, ad, adres ve model adları durur. Bu modeller elle seçilir; Auto Pro'nun
otomatik sırasına GİRMEZ (habersiz ücretli kullanım olmasın). Gerçek anahtarla doğrulanmadı (R-17).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..api.compat_client import split_model
from ..api.providers import GATEWAY_KINDS, gateway_id
from ..secrets import delete_api_key, load_api_key, mask_api_key, save_api_key
from .workers import Task

MAX_LIST = 400          # OpenRouter yüzlerce model döndürür; filtre kutusu var


class GatewayDialog(QDialog):
    """Yeni ağ geçidi ekleme ya da var olanı düzenleme penceresi."""

    def __init__(self, ctx, gateway: dict | None = None, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.existing = dict(gateway or {})
        self.setWindowTitle("Sağlayıcı ekle" if not gateway else f"Sağlayıcı: {gateway.get('name', '')}")
        self.setMinimumWidth(560)
        v = QVBoxLayout(self)
        self.kind = QComboBox()
        for kind, k in GATEWAY_KINDS.items():
            self.kind.addItem(k["name"], kind)
        if gateway:
            self.kind.setCurrentIndex(max(0, self.kind.findData(gateway.get("kind"))))
            self.kind.setEnabled(False)
        v.addWidget(QLabel("Tür:"))
        v.addWidget(self.kind)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setProperty("role", "dim")
        self.note.setOpenExternalLinks(True)
        v.addWidget(self.note)
        self.name = QLineEdit(gateway.get("name", "") if gateway else "")
        self.name.setPlaceholderText("Görünen ad (boş: tür adı)")
        v.addWidget(self.name)
        self.base = QLineEdit(gateway.get("base_url", "") if gateway else "")
        self.base.setPlaceholderText("Sunucu adresi (ör. http://localhost:1234/v1)")
        v.addWidget(self.base)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        old_key = load_api_key(gateway["id"]) if gateway else None
        self.key.setPlaceholderText(f"Kayıtlı anahtar: {mask_api_key(old_key)} — değiştirmek için yazın"
                                    if old_key else "API anahtarı (yapıştırın)")
        v.addWidget(self.key)
        row = QHBoxLayout()
        self.fetch_btn = QPushButton("Modelleri getir")
        self.fetch_btn.setToolTip("Sağlayıcının model listesini ister (ücretsiz; token harcamaz)")
        self.fetch_btn.clicked.connect(self.fetch_models)
        row.addWidget(self.fetch_btn)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Model ara (ör. claude, gpt, deepseek)…")
        self.filter.textChanged.connect(self._apply_filter)
        row.addWidget(self.filter, 1)
        v.addLayout(row)
        self.models = QListWidget()
        self.models.setMinimumHeight(180)
        v.addWidget(self.models)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setProperty("role", "dim")
        v.addWidget(self.status)
        for m in (gateway or {}).get("models") or []:
            self._add_model(m, True)
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setText("Kaydet")
        btns.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        btns.accepted.connect(self.save)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self._kind_changed()
        self.result_gateway: dict | None = None

    # ---- yardımcılar ----
    def _kind(self) -> str:
        return self.kind.currentData()

    def _kind_changed(self, *_a) -> None:
        k = GATEWAY_KINDS[self._kind()]
        links = " · ".join(f"<a href='{u}'>{t}</a>" for t, u in (("Anahtar al", k["keys_url"]),
                                                                  ("Belgeler", k["docs_url"])) if u)
        self.note.setText(k["note"] + ("<br>" + links if links else "")
                          + "<br>Ücretli olabilir · uygulamada harcama tahmin edilemez · doğrulanmadı.")
        if not self.existing:
            self.base.setText(k["base_url"])
        self.base.setVisible(self._kind() == "openai_uyumlu" or not k["base_url"] or bool(self.existing))

    def _add_model(self, model: str, checked: bool) -> None:
        it = QListWidgetItem(model)
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.models.addItem(it)

    def _apply_filter(self, text: str) -> None:
        t = (text or "").lower()
        for i in range(self.models.count()):
            it = self.models.item(i)
            it.setHidden(bool(t) and t not in it.text().lower() and it.checkState() != Qt.Checked)

    def checked_models(self) -> list[str]:
        return [self.models.item(i).text() for i in range(self.models.count())
                if self.models.item(i).checkState() == Qt.Checked]

    def _key_value(self) -> str:
        typed = self.key.text().strip()
        if typed:
            return typed
        return (load_api_key(self.existing["id"]) or "") if self.existing else ""

    # ---- eylemler ----
    def fetch_models(self) -> None:
        base, key = self.base.text().strip(), self._key_value()
        if not base:
            self.status.setText("Önce sunucu adresini yazın.")
            return
        self.status.setText("Model listesi isteniyor…")
        self.fetch_btn.setEnabled(False)
        from ..api.compat_client import CompatClient

        def job():
            c = CompatClient(base, key or "yok", "gw-gecici", timeout=30.0, max_retries=0)
            try:
                return [split_model(m.id)[1] for m in c.list_models()]
            finally:
                c.close()

        def done(ids):
            self.fetch_btn.setEnabled(True)
            keep = set(self.checked_models())
            self.models.clear()
            for m in sorted(set(ids) | keep)[:MAX_LIST]:
                self._add_model(m, m in keep)
            self._apply_filter(self.filter.text())
            self.status.setText(f"{len(ids)} model bulundu"
                                + (f" (ilk {MAX_LIST} gösteriliyor; arama kutusunu kullanın)" if len(ids) > MAX_LIST else "")
                                + ". Kullanacaklarınızı işaretleyin.")

        def fail(exc):
            self.fetch_btn.setEnabled(True)
            self.status.setText(f"✗ Model listesi alınamadı: {exc}")

        Task(job, on_done=done, on_error=fail).start()

    def save(self) -> None:
        kind = self._kind()
        base = self.base.text().strip() or GATEWAY_KINDS[kind]["base_url"]
        if not base.startswith(("http://", "https://")):
            self.status.setText("Sunucu adresi http:// veya https:// ile başlamalı.")
            return
        models = self.checked_models()
        if not models:
            self.status.setText("En az bir model işaretleyin (önce “Modelleri getir”).")
            return
        pid = self.existing.get("id") or gateway_id(kind, {g["id"] for g in self.ctx.gateways()})
        typed = self.key.text().strip()
        if typed:
            try:
                save_api_key(typed, pid)
            except Exception as exc:
                QMessageBox.critical(self, "Güvenli Saklama Başarısız",
                                     f"Anahtar Windows Credential Manager'a yazılamadı:\n{exc}\n\n"
                                     "Düz metin dosyaya geçilmez.")
                return
        elif not self.existing and kind != "openai_uyumlu":
            self.status.setText("API anahtarını girin.")
            return
        self.result_gateway = {"id": pid, "kind": kind, "name": self.name.text().strip()
                               or GATEWAY_KINDS[kind]["name"], "base_url": base, "models": models}
        self.accept()


class GatewaysSection(QWidget):
    """Kayıtlı ağ geçitleri listesi + "Sağlayıcı ekle"."""

    def __init__(self, ctx, on_changed=None, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.on_changed = on_changed or (lambda: None)
        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(0, 6, 0, 0)
        head = QHBoxLayout()
        title = QLabel("<b>Ağ geçitleri</b> — tek anahtarla çok model (OpenRouter, Kilo, OpenAI uyumlu)")
        title.setWordWrap(True)
        head.addWidget(title, 1)
        self.add_btn = QPushButton("Sağlayıcı ekle")
        self.add_btn.setProperty("variant", "primary")
        self.add_btn.clicked.connect(lambda _=None: self.edit(None))
        head.addWidget(self.add_btn)
        self.v.addLayout(head)
        self.rows = QVBoxLayout()
        self.v.addLayout(self.rows)
        self.refresh()

    def refresh(self) -> None:
        while self.rows.count():
            w = self.rows.takeAt(0).widget()
            if w is not None:
                w.hide()                        # R-33: eski satır yenisinin üstünde görünmesin
                w.deleteLater()
        gws = self.ctx.gateways()
        if not gws:
            empty = QLabel("Henüz ağ geçidi yok. “Sağlayıcı ekle” ile OpenRouter, Kilo ya da OpenAI uyumlu bir "
                           "sunucu ekleyebilirsiniz.")
            empty.setWordWrap(True)
            empty.setProperty("role", "dim")
            self.rows.addWidget(empty)
            return
        for g in gws:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 2, 0, 2)
            key = load_api_key(g["id"])
            lab = QLabel(f"<b>{g.get('name')}</b> · {len(g.get('models') or [])} model · "
                         f"anahtar {mask_api_key(key) if key else 'yok'}")
            lab.setToolTip(", ".join(g.get("models") or []))
            h.addWidget(lab, 1)
            ed = QPushButton("Düzenle")
            ed.clicked.connect(lambda _=None, gw=g: self.edit(gw))
            rm = QPushButton("Sil")
            rm.setProperty("variant", "danger")
            rm.clicked.connect(lambda _=None, gw=g: self.remove(gw))
            h.addWidget(ed)
            h.addWidget(rm)
            self.rows.addWidget(row)

    def _store(self, gws: list[dict]) -> None:
        self.ctx.settings.gateways = gws
        self.ctx.save_settings()                # sync_gateways: model seçicide görünür
        self.refresh()
        self.on_changed()

    def edit(self, gateway: dict | None) -> None:
        dlg = GatewayDialog(self.ctx, gateway, self)
        if dlg.exec() != QDialog.Accepted or not dlg.result_gateway:
            return
        new = dlg.result_gateway
        gws = [g for g in self.ctx.gateways() if g["id"] != new["id"]] + [new]
        self._store(gws)

    def remove(self, gateway: dict) -> None:
        if QMessageBox.question(self, "Sağlayıcıyı sil",
                                f"{gateway.get('name')} ve anahtarı silinsin mi?") != QMessageBox.Yes:
            return
        try:
            delete_api_key(gateway["id"])
        except Exception:
            pass
        self._store([g for g in self.ctx.gateways() if g["id"] != gateway["id"]])
