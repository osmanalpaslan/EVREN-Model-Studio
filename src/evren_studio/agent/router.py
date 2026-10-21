"""Auto Pro: uygulama içi, sağlayıcıya duyarlı model yönlendirici (Qt'siz).

Neden: EVREN'in sunucu tarafı `auto`'su her istekte modeli kendisi seçer; seçim
kuralları belgelenmemiş, akışta hangi modelin çalıştığı görünmez (2026-10-19,
docs/knowledge/CHALLENGE_RESULTS.md). Auto Pro ise:

- İşin TÜRÜNE (rol) göre model seçer. Sohbet rolleri: sohbet, kod, plan, görsel,
  büyük bağlam. Uygulamanın kendi yapay zekâ işleri: inceleme, özet, başlık,
  commit mesajı, hata açıklaması.
- YALNIZ anahtarı girilmiş sağlayıcıların modellerini kullanır (kullanıcı kararı
  2026-10-19): yalnız EVREN → EVREN tablosu; yalnız OpenAI/Anthropic → onların
  tablosu; birden fazla → "dengeli" birleştirme.
- Dengeli: çok token harcayan roller (kod, sohbet, özet, başlık, commit, büyük
  bağlam, hata) önce ücretsiz EVREN'de; az token ama yüksek değerli roller (plan,
  inceleme, görsel) önce güçlü ücretli modelde. Aylık bütçe koruması ayrıca geçerli.
- Seçtiği modeli tur boyunca DEĞİŞTİRMEZ; yalnız sunucu hatası / model bulunamadı
  / döngü / görsel reddinde sıradaki yedeğe geçer (AgentRunner.fallback_models).

EVREN tablosu gerçek API ile ölçüldü (R-21). OpenAI/Anthropic tablosu sağlayıcı
belgelerine dayanır ve DOĞRULANMADI (anahtar yok; R-07, R-17).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

AUTO_PRO_ID = "auto-pro"
AUTO_PRO_LABEL = "Auto Pro"
LEGACY_IDS = {"akilli"}             # 2026-10-19'da kısa süre "EVREN Akıllı" adıyla kullanıldı
# Eski adlar (geriye uyumluluk)
AKILLI_ID = AUTO_PRO_ID
AKILLI_LABEL = AUTO_PRO_LABEL

ROLE_LABELS = {
    "sohbet": "sohbet",
    "kod": "kod / araç",
    "plan": "plan",
    "gorsel": "görsel",
    "buyuk_baglam": "büyük bağlam",
    "inceleme": "inceleme",
    "ozet": "özet",
    "baslik": "başlık",
    "commit": "commit mesajı",
    "hata": "hata açıklaması",
}

# EVREN: 2026-10-19 ölçümü (12 görev, gerçek API; CHALLENGE_RESULTS.md "8 motor"):
#   deepseek-v4-flash 12/12 · 5 dk (en tutarlı, maratonda da en hızlı) → kod/sohbet birincil
#   qwen3.8-flash-next 12/12 · 9 dk (maratonda A/B/C tam) → kod yedek, inceleme birincil
#   gemma-4-31b 12/12 · 3 dk, görsel okur → görsel birincil; kodda 3. sıra (LOOP_ANALYSIS #1)
#   deepseek-v4.1-flash 12/12 · 10 dk, plan 44 sn → plan birincil
#   qwen3-vl-30b 9/12 → görselde son · glm-5.3, mimo-v2.6-pro: mini projede 6 dk aşıldı → kodda YOK
#   2026-10-21: deepseek-v4-flash EVREN /v1/models listesinden KALKTI (gerçek istekle görüldü); kod/sohbet
#   zinciri yalnız qwen → gemma'ya düşüyordu. deepseek-v4.1-flash (12/12) ikinci sıraya alındı; v4-flash geri
#   gelirse yine birincil olur (chain_for listede olmayanı atlar).
EVREN_ROUTES: dict[str, list[str]] = {
    "sohbet": ["deepseek-v4-flash", "qwen3.8-flash-next", "deepseek-v4.1-flash", "gemma-4-31b"],
    "kod": ["deepseek-v4-flash", "qwen3.8-flash-next", "deepseek-v4.1-flash", "gemma-4-31b"],
    "plan": ["deepseek-v4.1-flash", "qwen3.8-flash-next", "deepseek-v4-flash"],
    "gorsel": ["gemma-4-31b", "qwen3.8-flash-next", "qwen3-vl-30b"],
    "buyuk_baglam": ["deepseek-v4-flash", "deepseek-v4.1-flash", "mimo-v2.6-pro"],
    "inceleme": ["qwen3.8-flash-next", "deepseek-v4.1-flash", "gemma-4-31b"],
    # uygulamanın kendi işleri: kısa ve sık → hızlı modeller (özet ölçümü: deepseek-v4-flash 41 sn,
    # glm-5.3 153 sn — MODEL_CAPABILITIES.md "Özet gerçek testi")
    "ozet": ["deepseek-v4-flash", "qwen3.8-flash-next", "gemma-4-31b"],
    # gemma-4-31b kısa başlık isteğinde iki kez boş yanıt verdi (2026-10-19) → yedekte
    "baslik": ["deepseek-v4-flash", "qwen3.8-flash-next", "gemma-4-31b"],
    "commit": ["deepseek-v4-flash", "gemma-4-31b", "qwen3.8-flash-next"],
    "hata": ["deepseek-v4-flash", "qwen3.8-flash-next", "gemma-4-31b"],
}
ROUTES = EVREN_ROUTES               # eski ad
ROUTES_MEASURED = "2026-10-19"

# OpenAI + Anthropic: sağlayıcı belgelerindeki konumlandırmaya göre (api/providers.py
# kataloğu, PRICES_AS_OF) — DOĞRULANMADI. Pahalı amiral modeller yalnız plan rolünde önde.
PAID_ROUTES: dict[str, list[str]] = {
    "sohbet": ["claude-sonnet-5-5", "gpt-6.1-sol", "claude-haiku-5-5", "gpt-6-luna"],
    "kod": ["claude-sonnet-5-5", "gpt-5.3-codex", "gpt-6.1-sol", "claude-opus-5-5"],
    "plan": ["claude-opus-5-5", "gpt-6-astra", "claude-sonnet-5-5", "gpt-6.1-sol"],
    "gorsel": ["claude-sonnet-5-5", "gpt-6.1-sol", "claude-haiku-5-5"],
    "buyuk_baglam": ["gpt-6.1-sol", "claude-sonnet-5-5", "gpt-6-luna"],
    "inceleme": ["claude-sonnet-5-5", "gpt-6.1-sol", "claude-haiku-5-5"],
    "ozet": ["claude-haiku-5-5", "gpt-6-luna", "claude-sonnet-5-5"],
    "baslik": ["gpt-6-luna", "claude-haiku-5-5"],
    "commit": ["claude-haiku-5-5", "gpt-6-luna"],
    "hata": ["claude-haiku-5-5", "gpt-6-luna", "claude-sonnet-5-5"],
}
PAID_ROUTES_VERIFIED = False
# Dengeli politika: bu rollerde (az token, yüksek değer) ücretli güçlü model önce gelir
PAID_FIRST_ROLES = {"plan", "inceleme", "gorsel"}

# Görsel kabul ETMEYEN modeller (gerçek API: 400 feature_not_enabled, 2026-10-19)
TEXT_ONLY = {"glm-5.3", "deepseek-v4-flash"}
BIG_CONTEXT_RATIO = 0.6
HEALTH_FRESH = timedelta(minutes=30)


@dataclass
class Route:
    model: str
    role: str
    reason: str
    fallbacks: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{AUTO_PRO_LABEL} → {self.model} ({ROLE_LABELS.get(self.role, self.role)})"


def chain_for(role: str, available: set[str] | None = None) -> list[str]:
    """Rol için sıralı model zinciri. `available`: anahtarı olan sağlayıcıların model
    kimlikleri; None → yalnız EVREN tablosu (geriye uyumluluk / testler)."""
    evren = list(EVREN_ROUTES.get(role) or EVREN_ROUTES["sohbet"])
    paid = list(PAID_ROUTES.get(role) or PAID_ROUTES["sohbet"])
    if available is None:
        return evren
    ev = [m for m in evren if m in available]
    pd = [m for m in paid if m in available]
    if not ev and not pd:
        # tabloda olmayan ama erişilebilir bir model varsa (ör. yeni EVREN modeli) onu kullan
        return sorted(available)[:1]
    if not ev:
        return pd
    if not pd:
        return ev
    return pd + ev if role in PAID_FIRST_ROLES else ev + pd


def classify(*, agentic: bool, mode: str = "", has_images: bool = False,
             est_tokens: int = 0, context_of: dict[str, int] | None = None,
             available: set[str] | None = None) -> tuple[str, str]:
    """(rol, gerekçe). Öncelik: görsel > büyük bağlam > plan > kod > sohbet."""
    if has_images:
        return "gorsel", "mesajda görsel var"
    if est_tokens and context_of:
        base_chain = chain_for("kod" if agentic else "sohbet", available)
        limit = context_of.get(base_chain[0]) if base_chain else 0
        if limit and est_tokens > limit * BIG_CONTEXT_RATIO:
            return "buyuk_baglam", f"bağlam ~{est_tokens // 1000}k token"
    if agentic and mode == "plan":
        return "plan", "Plan modu"
    if agentic:
        return "kod", "proje klasöründe ajan görevi"
    return "sohbet", "klasörsüz sohbet"


def _unhealthy(health: dict[str, dict] | None, model: str, now: datetime) -> bool:
    h = (health or {}).get(model)
    if not h or h.get("healthy") in (None, 1, True):
        return False
    try:
        at = datetime.fromisoformat(str(h.get("last_test_at")).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return now - at <= HEALTH_FRESH


def choose(role: str, *, available: set[str] | None = None, health: dict[str, dict] | None = None,
           reason: str = "", now: datetime | None = None) -> Route:
    """Rol için birincil model + yedekler. Son 30 dk'da sağlıksız ölçülenler sona alınır."""
    now = now or datetime.now(timezone.utc)
    chain = chain_for(role, available)
    chain.sort(key=lambda m: _unhealthy(health, m, now))           # kararlı sıralama
    if role == "gorsel":
        chain = [m for m in chain if m not in TEXT_ONLY] or chain
    note = reason
    if chain and _unhealthy(health, chain[0], now):
        note += " · tüm adaylar yakın zamanda sorunlu ölçüldü"
    if not chain:
        return Route(model="", role=role, reason="kullanılabilir model yok (API anahtarı girin)")
    return Route(model=chain[0], role=role, reason=note, fallbacks=chain[1:])


def route(*, agentic: bool, mode: str = "", has_images: bool = False, est_tokens: int = 0,
          context_of: dict[str, int] | None = None, available: set[str] | None = None,
          health: dict[str, dict] | None = None) -> Route:
    role, reason = classify(agentic=agentic, mode=mode, has_images=has_images,
                            est_tokens=est_tokens, context_of=context_of, available=available)
    return choose(role, available=available, health=health, reason=reason)


def same_provider(models: list[str], model: str, provider_of) -> list[str]:
    """Yedekleri birincil modelin sağlayıcısıyla sınırlar: istemci tur boyunca aynıdır, EVREN
    turu ücretli modele (veya tersi) geçemez; MCP'nin ücretli modele ulaşmaması da bununla
    garanti (kullanıcı kararı 2026-10-19)."""
    p = provider_of(model)
    return [m for m in models if provider_of(m) == p]


def is_auto_pro(model_id: str | None) -> bool:
    return model_id == AUTO_PRO_ID or model_id in LEGACY_IDS


is_akilli = is_auto_pro             # eski ad


def normalize_model_id(model_id: str | None) -> str | None:
    """Eski "akilli" kaydını "auto-pro"ya çevirir."""
    return AUTO_PRO_ID if model_id in LEGACY_IDS else model_id
