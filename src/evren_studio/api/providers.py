"""Sağlayıcı kaydı ve ücretli sağlayıcıların tarihli model/fiyat kataloğu.

Kaynak: docs/knowledge/PROVIDERS_RESEARCH.md (resmî belgeler, 2026-10-16).
OpenAI ve Anthropic entegrasyonu belgelere göre yazıldı, GERÇEK İSTEKLE
DOĞRULANMADI (`verified=False`); anahtarı olan biri
`tests/e2e_providers_real_api.py` ile doğrulayınca güncelleyin.

Fiyatlar USD / 1M token'dır ve DEĞİŞİR. `PRICES_AS_OF` tarihinden eski
fiyatları kullanmadan önce kaynak sayfadan doğrulayın (bkz. R-17).
"""
from __future__ import annotations

from dataclasses import dataclass, field

PRICES_AS_OF = "2026-10-16"


@dataclass(frozen=True)
class ProviderInfo:
    id: str
    name: str
    base_url: str
    paid: bool
    verified: bool               # gerçek istekle doğrulandı mı
    key_prefix: str              # yalnız bilgi amaçlı (doğrulama yapılmaz)
    keys_url: str
    billing_url: str
    usage_url: str
    docs_url: str
    steps: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


PROVIDERS: dict[str, ProviderInfo] = {
    "evren": ProviderInfo(
        "evren", "EVREN", "https://evren-llmapi.ssyz.org.tr/v1", paid=False, verified=True,
        key_prefix="evren_llm_", keys_url="https://evren.ssyz.org.tr/",
        billing_url="https://evren.ssyz.org.tr/pricing", usage_url="https://evren.ssyz.org.tr/",
        docs_url="https://evren-llmapi.ssyz.org.tr/openapi.json",
    ),
    "openai": ProviderInfo(
        "openai", "OpenAI", "https://api.openai.com/v1", paid=True, verified=False,
        key_prefix="sk-",
        keys_url="https://platform.openai.com/settings/organization/api-keys",
        # Faturalama sayfasının adresi araştırmada doğrulanamadı; doğrulanan
        # Limits sayfası kullanılır (harcama sınırı ve kredi bağlantıları orada).
        billing_url="https://platform.openai.com/settings/organization/limits",
        usage_url="https://platform.openai.com/settings/organization/usage",
        docs_url="https://developers.openai.com/api/docs",
        steps=(
            "platform.openai.com'da hesap açın veya giriş yapın.",
            "Settings > API keys sayfasında “Create new secret key” ile anahtar oluşturun "
            "(anahtar yalnızca bir kez gösterilir).",
            "Billing sayfasından kredi yükleyin (ilk ücretli kademe $5 alımla açılır).",
            "İsterseniz Limits sayfasından aylık harcama sınırı koyun.",
        ),
        notes=(
            "Ön ödemeli kredi; kredi bitince istekler 429 'insufficient_quota' ile durur.",
            "API verisi açık izin olmadan eğitimde kullanılmaz; kötüye kullanım kayıtları ≤30 gün.",
            "Kalan kredi uygulamadan okunamaz: kullanımı paneldeki Usage sayfasından izleyin.",
        ),
    ),
    "anthropic": ProviderInfo(
        "anthropic", "Anthropic", "https://api.anthropic.com/v1", paid=True, verified=False,
        key_prefix="sk-ant-",
        keys_url="https://platform.claude.com/settings/keys",
        billing_url="https://platform.claude.com/settings/billing",
        usage_url="https://platform.claude.com/usage",
        docs_url="https://platform.claude.com/docs/en/api/overview",
        steps=(
            "platform.claude.com'da hesap açın veya giriş yapın (Claude Pro/Max aboneliği "
            "API'yi KARŞILAMAZ).",
            "Settings > API keys > “Create key” ile anahtar oluşturun (sk-ant- ile başlar, "
            "yalnızca bir kez gösterilir).",
            "Settings > Billing > “Buy credits” ile kredi yükleyin (USD, kart).",
        ),
        notes=(
            "Ön ödemeli kredi (1 yıl geçerli); kredi bitince istekler durur.",
            "Veri varsayılan olarak 30 günde silinir; açık izin olmadan eğitimde kullanılmaz.",
            "Kalan kredi uygulamadan okunamaz: Usage/Cost sayfalarından izleyin.",
        ),
    ),
}


# ---- ağ geçitleri (Madde 9, 2026-11-04): tek anahtarla çok model, OpenAI uyumlu Chat Completions ----
# Adresler sağlayıcı belgelerine göre; GERÇEK ANAHTARLA DOĞRULANMADI (R-17, ücretli istek yapılmadı).
GATEWAY_KINDS: dict[str, dict] = {
    "openrouter": {"name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "key_prefix": "sk-or-",
                   "keys_url": "https://openrouter.ai/settings/keys", "docs_url": "https://openrouter.ai/docs",
                   "billing_url": "https://openrouter.ai/settings/credits",
                   "note": "Tek anahtarla OpenAI, Anthropic, Google, DeepSeek… modelleri (model adı: sağlayıcı/model)."},
    "kilo": {"name": "Kilo Gateway", "base_url": "https://api.kilo.ai/api/gateway", "key_prefix": "",
             "keys_url": "https://app.kilo.ai", "docs_url": "https://kilo.ai/docs",
             "billing_url": "https://app.kilo.ai",
             "note": "Kilo hesabının anahtarıyla çok sayıda model (model adı: sağlayıcı/model)."},
    "openai_uyumlu": {"name": "OpenAI uyumlu sunucu", "base_url": "", "key_prefix": "",
                      "keys_url": "", "docs_url": "", "billing_url": "",
                      "note": "Chat Completions destekleyen herhangi bir sunucu (yerel LM Studio/Ollama, kurum içi…)."},
}


def gateway_id(kind: str, existing: set[str]) -> str:
    """Yeni ağ geçidi için benzersiz kimlik: gw-openrouter, gw-openrouter-2…"""
    base = f"gw-{kind.replace('_', '-')}"
    pid, n = base, 2
    while pid in existing:
        pid, n = f"{base}-{n}", n + 1
    return pid


def register_gateway(pid: str, kind: str, name: str = "", base_url: str = "") -> ProviderInfo:
    """Kullanıcının eklediği ağ geçidini çalışma anında PROVIDERS'a kaydeder (ad, faturalama bağlantısı vb.
    mevcut ekranlarda değişiklik gerektirmeden görünsün). Ücretli sayılır; doğrulanmamış."""
    k = GATEWAY_KINDS.get(kind, GATEWAY_KINDS["openai_uyumlu"])
    info = ProviderInfo(pid, name or k["name"], base_url or k["base_url"], paid=(kind != "openai_uyumlu"),
                        verified=False, key_prefix=k["key_prefix"], keys_url=k["keys_url"],
                        billing_url=k["billing_url"], usage_url=k["billing_url"], docs_url=k["docs_url"],
                        notes=(k["note"], "Harcama uygulamada tahmin edilemez: sağlayıcı panelinden izleyin."))
    PROVIDERS[pid] = info
    return info


def unregister_gateways(keep: set[str]) -> None:
    for pid in [p for p in PROVIDERS if p.startswith("gw-") and p not in keep]:
        PROVIDERS.pop(pid, None)


@dataclass(frozen=True)
class CatalogModel:
    id: str
    provider: str
    label: str                   # kısa açıklama (model seçicide)
    context: int
    max_output: int
    price_in: float              # USD / 1M girdi token
    price_out: float             # USD / 1M çıktı token
    price_cached: float          # USD / 1M önbellekten okunan girdi
    tools: bool = True
    vision: bool = True
    tags: tuple[str, ...] = field(default_factory=tuple)


CATALOG: list[CatalogModel] = [
    # OpenAI — developers.openai.com/api/docs/pricing (Standard, ≤272K girdi)
    CatalogModel("gpt-6-astra", "openai", "amiral gemisi", 1_050_000, 128_000, 10.0, 50.0, 1.0),
    CatalogModel("gpt-6.1-sol", "openai", "dengeli", 1_050_000, 128_000, 2.0, 10.0, 0.10),
    CatalogModel("gpt-6-luna", "openai", "hızlı · ucuz", 1_050_000, 128_000, 0.10, 0.50, 0.01),
    CatalogModel("gpt-5.6-terra", "openai", "genel", 1_050_000, 128_000, 2.0, 12.0, 0.20),
    CatalogModel("gpt-5.3-codex", "openai", "kodlama", 400_000, 128_000, 1.75, 14.0, 0.175,
                 tags=("kodlama",)),
    # Anthropic — platform.claude.com/docs/en/about-claude/pricing
    CatalogModel("claude-opus-5-5", "anthropic", "ajan kodlama (önerilen)", 1_000_000, 128_000,
                 4.0, 20.0, 0.20, tags=("kodlama",)),
    CatalogModel("claude-sonnet-5-5", "anthropic", "hız-zekâ dengesi", 1_000_000, 128_000,
                 2.0, 10.0, 0.10),
    CatalogModel("claude-haiku-5-5", "anthropic", "en hızlı · ucuz", 1_000_000, 128_000,
                 0.10, 0.50, 0.01),
    CatalogModel("claude-fable-5-1", "anthropic", "en güçlü · yavaş", 1_000_000, 128_000,
                 10.0, 50.0, 0.25),
]
CATALOG_BY_ID = {m.id: m for m in CATALOG}


def provider_of_model(model_id: str) -> str:
    if "::" in (model_id or ""):
        return model_id.split("::", 1)[0]          # ağ geçidi modeli: gw-…::sağlayıcı/model
    m = CATALOG_BY_ID.get(model_id)
    if m:
        return m.provider
    if model_id.startswith(("gpt-", "o1", "o3", "o4", "chatgpt-")):
        return "openai"
    if model_id.startswith("claude-"):
        return "anthropic"
    return "evren"


def estimate_cost(model_id: str, usage: dict | None) -> float:
    """Tahmini maliyet (USD). usage: input_tokens, output_tokens, cached_tokens.

    Önbellekten okunan girdi ayrı fiyatlanır; katalogda olmayan model → 0.
    Uzun bağlam (OpenAI >272K, Haiku >100K) üst fiyat kademeleri dikkate
    alınmaz: tahmin eksik kalabilir.
    """
    m = CATALOG_BY_ID.get(model_id)
    if m is None or not usage:
        return 0.0
    inp = int(usage.get("input_tokens") or 0)
    out = int(usage.get("output_tokens") or 0)
    cached = min(int(usage.get("cached_tokens") or 0), inp)
    return ((inp - cached) * m.price_in + cached * m.price_cached + out * m.price_out) / 1_000_000


def price_hint(model_id: str) -> str:
    m = CATALOG_BY_ID.get(model_id)
    if m is None:
        return ""
    def f(x: float) -> str:
        return (f"{x:.2f}" if x < 10 else f"{x:.0f}").replace(".", ",")
    return f"${f(m.price_in)} girdi / ${f(m.price_out)} çıktı (1M token)"
