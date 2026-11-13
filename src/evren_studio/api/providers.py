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
    # ---- Tek ekran (2026-11-12, kullanıcı: "kilo code gibi bütün api anahtarları ve motorlar için genel bir alan").
    # Hepsi OpenAI uyumlu Chat Completions sunar. Model listesi uçları 2026-11-12'de ANAHTARSIZ yoklandı (kişisel veri
    # yok): 401/403/400 "anahtar gerekli" = uç var · 200 = açık liste. Gemini anahtarsız 404 döndü, sahte anahtarla
    # "Please pass a valid API key" (400) → uç doğru. Cerebras bot korumasına (429) takıldı → eklenmedi.
    # Gerçek (ücretli) anahtarla DOĞRULANMADI (R-17).
    "gemini": {"name": "Google Gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
               "key_prefix": "AIza", "keys_url": "https://aistudio.google.com/apikey",
               "docs_url": "https://ai.google.dev/gemini-api/docs/openai",
               "billing_url": "https://aistudio.google.com/usage",
               "note": "Google'ın Gemini modelleri (ücretsiz kullanım kotası olan hesaplar var)."},
    "deepseek": {"name": "DeepSeek", "base_url": "https://api.deepseek.com", "key_prefix": "sk-",
                 "keys_url": "https://platform.deepseek.com/api_keys", "docs_url": "https://api-docs.deepseek.com",
                 "billing_url": "https://platform.deepseek.com/usage",
                 "note": "DeepSeek'in kendi modelleri (sohbet ve akıl yürütme)."},
    "mistral": {"name": "Mistral AI", "base_url": "https://api.mistral.ai/v1", "key_prefix": "",
                "keys_url": "https://console.mistral.ai/api-keys", "docs_url": "https://docs.mistral.ai",
                "billing_url": "https://console.mistral.ai/usage",
                "note": "Mistral modelleri (Codestral kodlama modeli dahil)."},
    "groq": {"name": "Groq", "base_url": "https://api.groq.com/openai/v1", "key_prefix": "gsk_",
             "keys_url": "https://console.groq.com/keys", "docs_url": "https://console.groq.com/docs",
             "billing_url": "https://console.groq.com/settings/billing",
             "note": "Çok hızlı çıkarım yapan açık modeller."},
    "xai": {"name": "xAI (Grok)", "base_url": "https://api.x.ai/v1", "key_prefix": "xai-",
            "keys_url": "https://console.x.ai", "docs_url": "https://docs.x.ai",
            "billing_url": "https://console.x.ai", "note": "xAI'ın Grok modelleri."},
    "together": {"name": "Together AI", "base_url": "https://api.together.xyz/v1", "key_prefix": "",
                 "keys_url": "https://api.together.ai/settings/api-keys", "docs_url": "https://docs.together.ai",
                 "billing_url": "https://api.together.ai/settings/billing",
                 "note": "Çok sayıda açık model (Llama, Qwen, DeepSeek…)."},
    "fireworks": {"name": "Fireworks AI", "base_url": "https://api.fireworks.ai/inference/v1", "key_prefix": "fw_",
                  "keys_url": "https://fireworks.ai/account/api-keys", "docs_url": "https://docs.fireworks.ai",
                  "billing_url": "https://fireworks.ai/account/billing", "note": "Hızlı açık modeller."},
    "moonshot": {"name": "Moonshot (Kimi)", "base_url": "https://api.moonshot.ai/v1", "key_prefix": "sk-",
                 "keys_url": "https://platform.moonshot.ai/console/api-keys",
                 "docs_url": "https://platform.moonshot.ai/docs", "billing_url": "https://platform.moonshot.ai/console",
                 "note": "Moonshot'ın Kimi modelleri."},
    "huggingface": {"name": "Hugging Face", "base_url": "https://router.huggingface.co/v1", "key_prefix": "hf_",
                    "keys_url": "https://huggingface.co/settings/tokens",
                    "docs_url": "https://huggingface.co/docs/inference-providers",
                    "billing_url": "https://huggingface.co/settings/billing",
                    "note": "Hugging Face çıkarım sağlayıcıları üzerinden açık modeller."},
    "vercel": {"name": "Vercel AI Gateway", "base_url": "https://ai-gateway.vercel.sh/v1", "key_prefix": "",
               "keys_url": "https://vercel.com/docs/ai-gateway", "docs_url": "https://vercel.com/docs/ai-gateway",
               "billing_url": "https://vercel.com/docs/ai-gateway",
               "note": "Tek anahtarla birçok sağlayıcının modelleri (model adı: sağlayıcı/model)."},
    "ollama": {"name": "Ollama (bu bilgisayarda)", "base_url": "http://localhost:11434/v1", "key_prefix": "",
               "keys_url": "", "docs_url": "https://ollama.com", "billing_url": "",
               "note": "Bilgisayarınızda çalışan ücretsiz modeller; anahtar gerekmez (Ollama açık olmalı)."},
    "lmstudio": {"name": "LM Studio (bu bilgisayarda)", "base_url": "http://localhost:1234/v1", "key_prefix": "",
                 "keys_url": "", "docs_url": "https://lmstudio.ai", "billing_url": "",
                 "note": "Bilgisayarınızda çalışan ücretsiz modeller; anahtar gerekmez (LM Studio sunucusu açık olmalı)."},
}
# Anahtar istemeyen (yerel/özel) türler: ücretsiz sayılır, anahtar alanı isteğe bağlı
KEYLESS_KINDS = frozenset({"openai_uyumlu", "ollama", "lmstudio"})


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
    info = ProviderInfo(pid, name or k["name"], base_url or k["base_url"], paid=(kind not in KEYLESS_KINDS),
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
