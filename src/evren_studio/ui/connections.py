"""Ayarlar > Sağlayıcılar ve anahtarlar: TÜM API anahtarları ve motorlar tek yerde (2026-11-12).

Kullanıcı: "open ai ve claude code apilerini girmek için ayrı ayrı alanlar var. bu şekilde olmamalı; kilo code api
girişi gibi daha kolay ve basit bir ekran gibi bütün api anahtarları ve motorları eklemek için genel bir alan olmalı."

Örnek alınan: Kilo Code masaüstü ayarları (kilo.ai/docs/desktop/settings/ai) — "AI Providers" listesi, sağ üstte
"Add AI Provider"; popüler sağlayıcılar ya da özel sağlayıcı (ad, adres, anahtar, model adları); eklenenler listede
düzenle/sil; bağlantı hatası satırın yanında nedeniyle ("Credentials rejected", "Couldn't reach the provider"…).

Akış: "Sağlayıcı ekle" → sağlayıcıyı seç (popüler kutular + aranabilir tam liste + "Özel sağlayıcı") → anahtarı yapıştır
(gerekiyorsa adres) → "Bağlantıyı dene" (ücretsiz model listesi isteği; token harcamaz) → modelleri işaretle → Kaydet.

SAKLAMA DEĞİŞMEDİ (veri taşıma yok, eski anahtarlar kendiliğinden listede): EVREN / OpenAI / Anthropic / Tavily anahtarları
kendi adlarıyla Windows Credential Manager'da; diğer tüm OpenAI uyumlu sağlayıcılar (ağ geçitleri, Gemini, DeepSeek,
yerel Ollama…) `settings.gateways` + `gw-…_api_key`. Anahtar asla ayar dosyasına/loga yazılmaz. Ağ geçidi modelleri elle
seçilir, Auto Pro'nun otomatik sırasına girmez (habersiz ücretli kullanım olmasın). Ücretli sağlayıcılar gerçek
anahtarla DOĞRULANMADI (R-17); uçların varlığı anahtarsız yoklamayla doğrulandı (bkz. api/providers.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..api.compat_client import split_model
from ..api.errors import ErrorKind
from ..api.providers import CATALOG, GATEWAY_KINDS, KEYLESS_KINDS, PROVIDERS, gateway_id
from ..secrets import delete_api_key, mask_api_key, save_api_key
from . import theme
from .workers import Task

MAX_LIST = 400                       # OpenRouter/Kilo yüzlerce model döndürür; arama kutusu var
KEY_SLOTS = ("evren", "openai", "anthropic", "tavily")      # kendi adıyla saklanan sabit anahtar yuvaları
POPULAR = ("evren", "openai", "anthropic", "gemini", "deepseek", "openrouter")
# Popüler kutuların kısa alt yazısı (uzun açıklama kutuya sığmıyordu: ui_denetim KESIK 3, 2026-11-12)
TILE_SUB = {"evren": "Ücretsiz · önerilen", "openai": "GPT · ücretli", "anthropic": "Claude · ücretli",
            "gemini": "Gemini · ücretli", "deepseek": "DeepSeek · ücretli", "openrouter": "Tek anahtar · çok model"}
GROUPS = (("populer", "Popüler"), ("diger", "Diğer sağlayıcılar"), ("gecit", "Ağ geçitleri — tek anahtarla çok model"),
          ("yerel", "Bu bilgisayarda (ücretsiz, anahtarsız)"), ("ozel", "Özel"), ("arac", "Araç anahtarları"))
_GROUP_OF = {"openrouter": "gecit", "kilo": "gecit", "vercel": "gecit", "huggingface": "gecit",
             "ollama": "yerel", "lmstudio": "yerel", "openai_uyumlu": "ozel"}


@dataclass(frozen=True)
class Template:
    key: str                 # "evren" | "openai" | "anthropic" | "tavily" | ağ geçidi türü
    name: str
    group: str
    blurb: str
    gateway: bool            # True: settings.gateways kaydı (OpenAI uyumlu); False: sabit anahtar yuvası
    key_required: bool
    key_prefix: str
    keys_url: str
    docs_url: str
    steps: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


def templates() -> list[Template]:
    out = [Template("evren", "EVREN", "populer", "Ücretsiz — uygulamanın varsayılan motoru (önerilen).", False, True,
                    PROVIDERS["evren"].key_prefix, PROVIDERS["evren"].keys_url, PROVIDERS["evren"].docs_url,
                    steps=("evren.ssyz.org.tr adresinde ücretsiz hesap açın.",
                           "Hesabınızdaki API anahtarını kopyalayıp aşağıya yapıştırın."))]
    for pid, name, blurb in (("openai", "OpenAI", "Ücretli — GPT modelleri."),
                             ("anthropic", "Anthropic (Claude)", "Ücretli — Claude modelleri.")):
        p = PROVIDERS[pid]
        out.append(Template(pid, name, "populer", blurb, False, True, p.key_prefix, p.keys_url, p.docs_url,
                            p.steps, p.notes))
    for kind, k in GATEWAY_KINDS.items():
        group = "populer" if kind in POPULAR else _GROUP_OF.get(kind, "diger")
        name = "Özel sağlayıcı (OpenAI uyumlu adres)" if kind == "openai_uyumlu" else k["name"]
        out.append(Template(kind, name, group, k["note"], True, kind not in KEYLESS_KINDS, k["key_prefix"],
                            k["keys_url"], k["docs_url"]))
    out.append(Template("tavily", "Tavily (web araması)", "arac",
                        "Ajanın internette araması için (ücretsiz aylık kota; anahtarsız da sınırlı çalışır).", False,
                        True, "tvly-", "https://app.tavily.com", "https://docs.tavily.com"))
    rank = {k: i for i, k in enumerate(POPULAR)}
    out.sort(key=lambda t: rank.get(t.key, len(rank)))       # popüler sırası kutularla aynı; diğerleri yerinde
    return out


def template(key: str) -> Template:
    for t in templates():
        if t.key == key:
            return t
    return next(t for t in templates() if t.key == "openai_uyumlu")


@dataclass
class Connection:
    id: str                  # anahtar yuvası adı ya da ağ geçidi kimliği (gw-…)
    template: str
    name: str
    detail: str
    key_mask: str
    configured: bool         # anahtarı var (anahtarsız türlerde: kayıtlı)


def connections(ctx) -> list[Connection]:
    """Bağlı (ya da EVREN için her zaman gösterilen) sağlayıcılar, listedeki sırayla."""
    ev = ctx.api_key()
    out = [Connection("evren", "evren", "EVREN", "ücretsiz · varsayılan motor" if ev else
                      "anahtar yok — ücretsiz EVREN anahtarı ekleyin", mask_api_key(ev) if ev else "", bool(ev))]
    for pid in ("openai", "anthropic"):
        key = ctx.provider_key(pid)
        if key:
            n = sum(1 for m in CATALOG if m.provider == pid)
            out.append(Connection(pid, pid, template(pid).name, f"ücretli · {n} model", mask_api_key(key), True))
    for g in ctx.gateways():
        kind = g.get("kind", "openai_uyumlu")
        key = ctx.provider_key(g["id"])
        n = len(g.get("models") or [])
        cost = "ücretsiz · yerel" if kind in KEYLESS_KINDS else "ücretli olabilir"
        out.append(Connection(g["id"], kind, g.get("name") or template(kind).name, f"{cost} · {n} model",
                              mask_api_key(key) if key else "", True))
    tv = ctx.provider_key("tavily")
    if tv:
        out.append(Connection("tavily", "tavily", "Tavily", "web araması", mask_api_key(tv), True))
    return out


# ---- bağlantı denemesi ve kayıt (Qt'siz; testte doğrudan çağrılır) --------------------------------------------


def describe_error(exc: BaseException) -> str:
    """Kilo Code'daki gibi satırda gösterilecek kısa neden."""
    kind = getattr(exc, "kind", None)
    status = getattr(exc, "status", None)
    # ApiError'ın str()'i uygulamanın Türkçe açıklamasıdır; sağlayıcının ham mesajı `message`'da (Gemini geçersiz
    # anahtarda 401 değil 400 + "Please pass a valid API key" döndürür — ham mesaja bakılmazsa "beklenmeyen" görünür)
    low = f"{getattr(exc, 'message', '')} {exc}".lower()
    if kind is ErrorKind.AUTH or status in (401, 403) or any(
            s in low for s in ("api key", "api_key", "unauthorized", "authentication", "no credentials",
                               "invalid key", "incorrect api key", "anahtar")):
        return "Anahtar reddedildi — anahtarı kontrol edin."
    if kind is ErrorKind.QUOTA_EXHAUSTED:
        return "Kredi bitti — sağlayıcı panelinden kredi yükleyin."
    if kind is ErrorKind.RATE_LIMIT or status == 429:
        return "Hız sınırına takıldı — biraz sonra yeniden deneyin."
    if kind in (ErrorKind.NETWORK, ErrorKind.TIMEOUT) or isinstance(exc, OSError) or "connect" in low:
        return "Sağlayıcıya ulaşılamadı — internet bağlantısını ya da sunucu adresini kontrol edin."
    if kind is ErrorKind.NOT_FOUND or status == 404:
        return "Adres bulunamadı (404) — sunucu adresini kontrol edin."
    if kind in (ErrorKind.SERVER_ERROR, ErrorKind.SERVER_UNAVAILABLE) or (status or 0) >= 500:
        return "Sağlayıcı hatası — daha sonra yeniden deneyin."
    return f"Beklenmeyen yanıt: {str(exc)[:160]}"


def probe(ctx, tkey: str, key: str, base_url: str = "") -> list[str]:
    """Bağlantıyı dener (model listesi; ücretsiz, token harcamaz). Model kimlikleri; hata durumunda istisna."""
    if tkey == "tavily":
        from ..agent import websearch
        from ..api.errors import ApiError

        if not websearch.usage(key):
            raise ApiError(ErrorKind.AUTH, "Tavily anahtarı geçersiz ya da Tavily'ye ulaşılamadı", status=401)
        return []
    if tkey == "evren":
        from ..api.client import EvrenClient

        client: Any = EvrenClient(base_url=ctx.settings.base_url, api_key=key, timeout=30.0, max_retries=0)
    elif tkey == "openai":
        from ..api.openai_client import OpenAIClient

        client = OpenAIClient(key, timeout=30.0, max_retries=0)
    elif tkey == "anthropic":
        from ..api.anthropic_client import AnthropicClient

        client = AnthropicClient(key, timeout=30.0, max_retries=0)
    else:
        from ..api.compat_client import CompatClient

        client = CompatClient(base_url or GATEWAY_KINDS.get(tkey, {}).get("base_url", ""), key or "",
                              "gw-gecici", timeout=30.0, max_retries=0)
    try:
        return [split_model(m.id)[1] for m in client.list_models()]
    finally:
        close = getattr(client, "close", None)
        if close:
            close()


def stored_key(ctx, conn_id: str) -> str:
    return (ctx.api_key() if conn_id == "evren" else ctx.provider_key(conn_id)) or ""


def _refresh_key_cache(ctx, conn_id: str) -> None:
    if conn_id == "evren":
        ctx.api_key(refresh=True)
    else:
        ctx.provider_key(conn_id, refresh=True)


def save_connection(ctx, tkey: str, key: str, *, conn_id: str | None = None, name: str = "", base_url: str = "",
                    models: list[str] | None = None) -> str:
    """Anahtarı Credential Manager'a, ağ geçidi bilgisini (anahtarsız) ayarlara yazar; bağlantı kimliği."""
    if tkey in KEY_SLOTS:
        if key:
            save_api_key(key, tkey)
        _refresh_key_cache(ctx, tkey)
        return tkey
    gws = ctx.gateways()
    pid = conn_id or gateway_id(tkey, {g["id"] for g in gws})
    if key:
        save_api_key(key, pid)
    entry = {"id": pid, "kind": tkey, "name": name or template(tkey).name,
             "base_url": base_url or GATEWAY_KINDS.get(tkey, {}).get("base_url", ""), "models": list(models or [])}
    ctx.settings.gateways = [g for g in gws if g["id"] != pid] + [entry]
    ctx.save_settings()                      # sync_gateways: modeller seçicide görünür
    _refresh_key_cache(ctx, pid)
    return pid


def remove_connection(ctx, conn_id: str) -> None:
    try:
        delete_api_key(conn_id)
    except Exception:                        # kasada yoksa da kayıt silinir
        pass
    if conn_id.startswith("gw-"):
        ctx.settings.gateways = [g for g in ctx.gateways() if g["id"] != conn_id]
        ctx.save_settings()
    _refresh_key_cache(ctx, conn_id)


def _link(text: str, url: str) -> str:
    return f"<a href='{url}'>{text}</a>"


def _badge(text: str) -> QLabel:
    lab = QLabel("".join(w[0] for w in text.replace("(", " ").split()[:2]).upper()[:2] or "?")
    lab.setObjectName("ConnBadge")
    lab.setAlignment(Qt.AlignCenter)
    lab.setFixedSize(34, 34)
    return lab


# ---- ekleme / düzenleme penceresi -----------------------------------------------------------------------------


class ConnectionDialog(QDialog):
    """Sağlayıcı seç → anahtar (+ adres) → bağlantıyı dene → modeller → Kaydet. `conn_id` verilirse düzenleme."""

    def __init__(self, ctx, template_key: str | None = None, conn_id: str | None = None, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.conn_id = conn_id
        self.existing = next((g for g in ctx.gateways() if g["id"] == conn_id), None) if conn_id else None
        self.result_id: str | None = None
        self.tpl: Template | None = None
        self.setWindowTitle("Sağlayıcıyı düzenle" if conn_id else "Sağlayıcı ekle")
        self.setMinimumSize(620, 560)
        root = QVBoxLayout(self)
        self.pages = QStackedWidget()
        root.addWidget(self.pages)
        self.pages.addWidget(self._build_picker())
        self.pages.addWidget(self._build_form())
        if conn_id:
            key = (self.existing or {}).get("kind") or conn_id
            self.open_template(key)
            self.back_btn.setVisible(False)
        elif template_key:
            self.open_template(template_key)

    # -- 1. sayfa: seçim --
    def _build_picker(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        title = QLabel("Sağlayıcı ekle")
        title.setProperty("role", "h1")
        v.addWidget(title)
        sub = QLabel("Bir sağlayıcı seçin; anahtarını yapıştırın. Anahtarlar yalnız Windows Credential Manager'da saklanır.")
        sub.setWordWrap(True)
        sub.setProperty("role", "dim")
        v.addWidget(sub)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Sağlayıcı ara (ör. gemini, groq, ollama)…")
        self.search.textChanged.connect(self._filter)
        v.addWidget(self.search)
        grid = QGridLayout()
        grid.setSpacing(8)
        self.tiles: dict[str, QPushButton] = {}
        for i, key in enumerate(POPULAR):
            t = template(key)
            b = QPushButton(f"{t.name}\n{TILE_SUB.get(key, '')}")
            b.setToolTip(t.blurb)
            b.setObjectName("ProviderTile")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=None, k=key: self.open_template(k))
            grid.addWidget(b, i // 3, i % 3)
            self.tiles[key] = b
        v.addLayout(grid)
        all_lab = QLabel("Tüm sağlayıcılar")
        all_lab.setProperty("role", "section")
        v.addWidget(all_lab)
        self.all_list = QListWidget()
        self.all_list.setObjectName("ProviderList")
        self.all_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)     # uzun satır "…" ile kısalır
        self.all_list.setTextElideMode(Qt.ElideRight)
        for gkey, glabel in GROUPS:
            items = [t for t in templates() if t.group == gkey]
            if not items:
                continue
            head = QListWidgetItem(glabel)
            head.setFlags(Qt.NoItemFlags)
            head.setData(Qt.UserRole, "")
            f = head.font()
            f.setBold(True)
            head.setFont(f)
            self.all_list.addItem(head)
            for t in items:
                it = QListWidgetItem(f"   {t.name}  —  {t.blurb}")
                it.setData(Qt.UserRole, t.key)
                it.setToolTip(t.blurb)
                self.all_list.addItem(it)
        self.all_list.itemClicked.connect(lambda it: it.data(Qt.UserRole) and self.open_template(it.data(Qt.UserRole)))
        v.addWidget(self.all_list, 1)
        cancel = QPushButton("Vazgeç")
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(cancel)
        v.addLayout(row)
        return page

    def _filter(self, text: str) -> None:
        q = (text or "").strip().lower()
        for key, b in self.tiles.items():
            t = template(key)
            b.setVisible(not q or q in (t.name + " " + t.blurb + " " + key).lower())
        visible_in_group = False
        for i in range(self.all_list.count() - 1, -1, -1):          # sondan başa: başlık kendi grubuna bakar
            it = self.all_list.item(i)
            key = it.data(Qt.UserRole)
            if key:
                hit = not q or q in (it.text() + " " + key).lower()
                it.setHidden(not hit)
                visible_in_group = visible_in_group or hit
            else:
                it.setHidden(not visible_in_group)
                visible_in_group = False

    # -- 2. sayfa: form --
    def _build_form(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        head = QHBoxLayout()
        self.back_btn = QPushButton("← Geri")
        self.back_btn.setProperty("variant", "ghost")
        self.back_btn.clicked.connect(lambda _=None: self.pages.setCurrentIndex(0))
        head.addWidget(self.back_btn)
        self.form_title = QLabel()
        self.form_title.setProperty("role", "h1")
        head.addWidget(self.form_title, 1)
        v.addLayout(head)
        self.blurb = QLabel()
        self.blurb.setWordWrap(True)
        self.blurb.setProperty("role", "dim")
        v.addWidget(self.blurb)
        self.links = QLabel()
        self.links.setOpenExternalLinks(True)
        self.links.setWordWrap(True)
        v.addWidget(self.links)
        self.steps = QLabel()
        self.steps.setWordWrap(True)
        self.steps.setProperty("role", "dim")
        v.addWidget(self.steps)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Görünen ad (isteğe bağlı)")
        v.addWidget(self.name)
        self.base = QLineEdit()
        self.base.setPlaceholderText("Sunucu adresi (ör. http://localhost:1234/v1)")
        v.addWidget(self.base)
        key_row = QHBoxLayout()
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        key_row.addWidget(self.key, 1)
        self.show_key = QPushButton("Göster")
        self.show_key.setCheckable(True)
        self.show_key.toggled.connect(
            lambda on: self.key.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        key_row.addWidget(self.show_key)
        self.test_btn = QPushButton("Bağlantıyı dene")
        self.test_btn.setToolTip("Model listesini ister (ücretsiz; token harcamaz)")
        self.test_btn.clicked.connect(self.test)
        key_row.addWidget(self.test_btn)
        v.addLayout(key_row)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        self.models_box = QWidget()
        mv = QVBoxLayout(self.models_box)
        mv.setContentsMargins(0, 0, 0, 0)
        mrow = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Model ara (ör. claude, gpt, deepseek)…")
        self.filter.textChanged.connect(self._apply_filter)
        mrow.addWidget(self.filter, 1)
        self.manual = QLineEdit()
        self.manual.setPlaceholderText("Model adını elle ekle")
        self.manual.returnPressed.connect(self._add_manual)
        mrow.addWidget(self.manual, 1)
        add_btn = QPushButton("Ekle")
        add_btn.clicked.connect(self._add_manual)
        mrow.addWidget(add_btn)
        mv.addLayout(mrow)
        self.models = QListWidget()
        self.models.setMinimumHeight(160)
        mv.addWidget(self.models, 1)
        v.addWidget(self.models_box, 1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Vazgeç")
        cancel.clicked.connect(self.reject)
        self.save_btn = QPushButton("Kaydet")
        self.save_btn.setProperty("variant", "primary")
        self.save_btn.clicked.connect(self.save)
        btns.addWidget(cancel)
        btns.addWidget(self.save_btn)
        v.addLayout(btns)
        return page

    def open_template(self, key: str) -> None:
        t = template(key)
        self.tpl = t
        self.form_title.setText(t.name)
        self.blurb.setText(t.blurb + ("" if not t.gateway or t.key in KEYLESS_KINDS else
                                      " · Ücretli olabilir; harcamayı sağlayıcı panelinden izleyin."))
        links = [(_link("Anahtar al", t.keys_url)) if t.keys_url else "", _link("Belgeler", t.docs_url) if t.docs_url else ""]
        self.links.setText(" · ".join(x for x in links if x))
        self.steps.setText("".join(f"{i}. {s}<br>" for i, s in enumerate(t.steps, 1)))
        self.steps.setVisible(bool(t.steps))
        self.name.setVisible(t.gateway)
        self.name.setText((self.existing or {}).get("name", ""))
        custom = t.key in KEYLESS_KINDS
        self.base.setVisible(t.gateway and (custom or bool(self.existing)))
        self.base.setText((self.existing or {}).get("base_url") or GATEWAY_KINDS.get(t.key, {}).get("base_url", ""))
        old = stored_key(self.ctx, self.conn_id) if self.conn_id else ""
        need = "isteğe bağlı" if not t.key_required else (f"{t.key_prefix}…" if t.key_prefix else "yapıştırın")
        self.key.setPlaceholderText(f"Kayıtlı anahtar: {mask_api_key(old)} — değiştirmek için yazın" if old
                                    else f"API anahtarı ({need})")
        self.key.clear()
        self.models_box.setVisible(t.gateway)
        self.models.clear()
        for m in (self.existing or {}).get("models") or []:
            self._add_model(m, True)
        self.status.setText("")
        self.pages.setCurrentIndex(1)
        self.key.setFocus()

    def _key_value(self) -> str:
        typed = self.key.text().strip()
        if typed:
            return typed
        return stored_key(self.ctx, self.conn_id) if self.conn_id else ""

    def _add_model(self, model: str, checked: bool) -> None:
        for i in range(self.models.count()):
            if self.models.item(i).text() == model:
                return
        it = QListWidgetItem(model)
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.models.addItem(it)

    def _add_manual(self) -> None:
        m = self.manual.text().strip()
        if m:
            self._add_model(m, True)
            self.manual.clear()

    def _apply_filter(self, text: str) -> None:
        q = (text or "").lower()
        for i in range(self.models.count()):
            it = self.models.item(i)
            it.setHidden(bool(q) and q not in it.text().lower() and it.checkState() != Qt.Checked)

    def checked_models(self) -> list[str]:
        return [self.models.item(i).text() for i in range(self.models.count())
                if self.models.item(i).checkState() == Qt.Checked]

    def _set_status(self, ok: bool | None, text: str) -> None:
        self.status.setText(text)
        role = None if ok is None else ("success" if ok else "danger")
        theme.style(self.status, lambda p, r=role: f"color: {getattr(p, r)};" if r else "")

    # -- eylemler --
    def test(self) -> None:
        t = self.tpl
        if t is None:
            return
        key = self._key_value()
        if t.key_required and not key:
            self._set_status(False, "Önce anahtarı yapıştırın.")
            return
        base = self.base.text().strip()
        self._set_status(None, "Bağlanılıyor…")
        self.test_btn.setEnabled(False)

        def done(ids: list[str]) -> None:
            self.test_btn.setEnabled(True)
            if t.gateway:
                keep = set(self.checked_models())
                self.models.clear()
                for m in sorted(set(ids) | keep)[:MAX_LIST]:
                    self._add_model(m, m in keep)
                self._apply_filter(self.filter.text())
            more = f" (ilk {MAX_LIST} gösteriliyor; arayın)" if len(ids) > MAX_LIST else ""
            tail = " Kullanacaklarınızı işaretleyin." if t.gateway else ""
            self._set_status(True, f"✓ Bağlandı · {len(ids)} model{more}.{tail}" if t.key != "tavily"
                             else "✓ Bağlandı · Tavily anahtarı geçerli.")

        def fail(exc: BaseException) -> None:
            self.test_btn.setEnabled(True)
            self._set_status(False, "✗ " + describe_error(exc))

        Task(lambda: probe(self.ctx, t.key, key, base), on_done=done, on_error=fail).start()

    def save(self) -> None:
        t = self.tpl
        if t is None:
            return
        typed = self.key.text().strip()
        has_old = bool(self.conn_id and stored_key(self.ctx, self.conn_id))
        if t.key_required and not typed and not has_old:
            self._set_status(False, "API anahtarını yapıştırın.")
            return
        if typed and t.key_prefix and not typed.startswith(t.key_prefix):
            if QMessageBox.question(self, "Anahtar biçimi",
                                    f"{t.name} anahtarları genellikle “{t.key_prefix}” ile başlar. "
                                    "Yine de kaydedilsin mi?") != QMessageBox.Yes:
                return
        base = self.base.text().strip() or GATEWAY_KINDS.get(t.key, {}).get("base_url", "")
        models = self.checked_models()
        if t.gateway:
            if not base.startswith(("http://", "https://")):
                self._set_status(False, "Sunucu adresi http:// veya https:// ile başlamalı.")
                return
            if not models:
                self._set_status(False, "En az bir model işaretleyin (önce “Bağlantıyı dene”) ya da adını elle ekleyin.")
                return
        try:
            self.result_id = save_connection(self.ctx, t.key, typed, conn_id=self.conn_id,
                                             name=self.name.text().strip(), base_url=base, models=models)
        except Exception as exc:
            QMessageBox.critical(self, "Güvenli Saklama Başarısız",
                                 f"Anahtar Windows Credential Manager'a yazılamadı:\n{exc}\n\nDüz metin dosyaya geçilmez.")
            return
        self.accept()


# ---- liste ------------------------------------------------------------------------------------------------------


class ConnectionsSection(QWidget):
    """Bağlı sağlayıcılar listesi + "Sağlayıcı ekle" (Kilo Code'daki "AI Providers" bölümü gibi)."""

    changed = Signal()

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._status: dict[str, tuple[bool | None, str]] = {}
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        head = QHBoxLayout()
        intro = QLabel("Modeller ve araçlar için tüm API anahtarları burada. EVREN ücretsizdir; başka sağlayıcı "
                       "eklediğinizde modelleri model seçicide görünür.")
        intro.setWordWrap(True)
        intro.setProperty("role", "dim")
        head.addWidget(intro, 1)
        self.add_btn = QPushButton("+ Sağlayıcı ekle")
        self.add_btn.setProperty("variant", "primary")
        self.add_btn.clicked.connect(lambda _=None: self.add())
        head.addWidget(self.add_btn, 0, Qt.AlignTop)
        v.addLayout(head)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(6)
        v.addLayout(self.rows)
        self.refresh()

    def refresh(self) -> None:
        while self.rows.count():
            w = self.rows.takeAt(0).widget()
            if w is not None:
                w.hide()                        # R-33: eski satır yenisinin üstünde görünmesin
                w.deleteLater()
        self.row_widgets: dict[str, QFrame] = {}
        for c in connections(self.ctx):
            self.rows.addWidget(self._row(c))

    def _row(self, c: Connection) -> QFrame:
        row = QFrame()
        row.setObjectName("ConnRow")
        h = QHBoxLayout(row)
        h.setContentsMargins(10, 8, 10, 8)
        h.setSpacing(10)
        h.addWidget(_badge(c.name))
        col = QVBoxLayout()
        col.setSpacing(1)
        title = QLabel(f"<b>{c.name}</b>")
        col.addWidget(title)
        sub = QLabel(c.detail + (f" · anahtar {c.key_mask}" if c.key_mask else ""))
        sub.setProperty("role", "faint")
        sub.setWordWrap(True)
        col.addWidget(sub)
        status = QLabel("")
        status.setWordWrap(True)
        status.setObjectName("ConnStatus")
        col.addWidget(status)
        h.addLayout(col, 1)
        ok, text = self._status.get(c.id, (None, ""))
        status.setText(text)
        status.setVisible(bool(text))
        if ok is not None:
            theme.style(status, lambda p, r=("success" if ok else "danger"): f"color: {getattr(p, r)};")
        if not c.configured:
            b = QPushButton("Anahtar ekle")
            b.setProperty("variant", "primary")
            b.clicked.connect(lambda _=None, k=c.template: self.add(k))
            h.addWidget(b)
        else:
            test = QPushButton("Dene")
            test.setToolTip("Bağlantıyı dener (model listesi; ücretsiz)")
            test.clicked.connect(lambda _=None, cid=c.id: self.test(cid))
            ed = QPushButton("Düzenle")
            ed.clicked.connect(lambda _=None, cid=c.id: self.edit(cid))
            rm = QPushButton("Sil")
            rm.setProperty("variant", "danger")
            rm.clicked.connect(lambda _=None, cid=c.id: self.remove(cid))
            for b in (test, ed, rm):
                h.addWidget(b)
        row.status_label = status
        self.row_widgets[c.id] = row
        return row

    def _done(self) -> None:
        self.refresh()
        self.changed.emit()                     # model listeleri ve sağlayıcıya özel sayfalar yenilenir

    def add(self, template_key: str | None = None) -> str | None:
        dlg = ConnectionDialog(self.ctx, template_key, parent=self)
        if dlg.exec() != QDialog.Accepted or not dlg.result_id:
            return None
        self._status.pop(dlg.result_id, None)
        self._done()
        return dlg.result_id

    def edit(self, conn_id: str) -> str | None:
        tkey = next((c.template for c in connections(self.ctx) if c.id == conn_id), conn_id)
        dlg = ConnectionDialog(self.ctx, tkey, conn_id=conn_id, parent=self)
        if dlg.exec() != QDialog.Accepted or not dlg.result_id:
            return None
        self._status.pop(conn_id, None)
        self._done()
        return dlg.result_id

    def remove(self, conn_id: str) -> bool:
        c = next((x for x in connections(self.ctx) if x.id == conn_id), None)
        if c is None:
            return False
        warn = (" EVREN anahtarı olmadan EVREN modelleri kullanılamaz." if conn_id == "evren" else "")
        if QMessageBox.question(self, "Sağlayıcıyı kaldır",
                                f"{c.name} ve anahtarı kaldırılsın mı?{warn}") != QMessageBox.Yes:
            return False
        remove_connection(self.ctx, conn_id)
        self._status.pop(conn_id, None)
        self._done()
        return True

    def test(self, conn_id: str) -> None:
        c = next((x for x in connections(self.ctx) if x.id == conn_id), None)
        if c is None:
            return
        g = next((x for x in self.ctx.gateways() if x["id"] == conn_id), {})
        key, base = stored_key(self.ctx, conn_id), g.get("base_url", "")
        self._set_status(conn_id, None, "Bağlanılıyor…")

        def done(ids: list[str]) -> None:
            self._set_status(conn_id, True, "✓ Bağlandı" + (f" · {len(ids)} model" if c.template != "tavily" else ""))

        def fail(exc: BaseException) -> None:
            self._set_status(conn_id, False, "✗ " + describe_error(exc))

        Task(lambda: probe(self.ctx, c.template, key, base), on_done=done, on_error=fail).start()

    def _set_status(self, conn_id: str, ok: bool | None, text: str) -> None:
        self._status[conn_id] = (ok, text)
        row = self.row_widgets.get(conn_id)
        if row is None:
            return
        lab = row.status_label
        lab.setText(text)
        lab.setVisible(bool(text))
        theme.style(lab, lambda p, r=(None if ok is None else ("success" if ok else "danger")):
                    f"color: {getattr(p, r)};" if r else "")
