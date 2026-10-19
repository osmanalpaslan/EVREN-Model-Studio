"""EVREN Akıllı: uygulama içi, ölçüme dayalı model yönlendirici (Qt'siz).

Neden: sunucu tarafı `auto` her istekte modeli kendisi seçer; seçim kuralları
belgelenmemiş, akışlı yanıtta hangi modelin çalıştığı görünmez ve uzun bir
ajan görevinin adımları farklı modellere gidebilir (2026-10-19 ölçümleri,
docs/knowledge/CHALLENGE_RESULTS.md). EVREN Akıllı ise:

- İşin TÜRÜNE (rol) göre modeli seçer: sohbet, kod (ajan araç turu), plan,
  görsel, büyük bağlam, inceleme.
- Seçtiği modeli tur boyunca DEĞİŞTİRMEZ; yalnız sunucu hatası / model bulunamadı
  / döngü durumunda sıradaki yedeğe geçer (AgentRunner.fallback_models).
- Hangi modeli neden seçtiğini söyler (Route.reason) — arayüz gösterir.

Rol → model tablosu `ROUTES` ölçümle doldurulur; model listesi veya EVREN
davranışı değişince `tests/e2e_zorluk_real_api.py` ile yeniden ölç (R-21).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

AKILLI_ID = "akilli"
AKILLI_LABEL = "EVREN Akıllı"

ROLE_LABELS = {
    "sohbet": "sohbet",
    "kod": "kod / araç",
    "plan": "plan",
    "gorsel": "görsel",
    "buyuk_baglam": "büyük bağlam",
    "inceleme": "inceleme",
}

# Rol → sıralı model listesi (ilk: birincil, sonrakiler: yedek). Kaynak:
# docs/knowledge/CHALLENGE_RESULTS.md "Yönlendirme tablosu" (ölçüm tarihiyle).
#
# 2026-10-19 ölçümü (12 görev, gerçek API; ayrıntı CHALLENGE_RESULTS.md "8 motor"):
#   deepseek-v4-flash 12/12 · 5 dk (en tutarlı, maratonda da en hızlı) → kod/sohbet birincil
#   qwen3.8-flash-next 12/12 · 9 dk (maratonda A/B/C tam) → kod yedek, inceleme birincil
#   gemma-4-31b 12/12 · 3 dk, görsel okur → görsel birincil; kodda 3. sıra (LOOP_ANALYSIS #1:
#     çelişkili testte hile görüldü)
#   deepseek-v4.1-flash 12/12 · 10 dk, plan 44 sn → plan birincil
#   qwen3-vl-30b 9/12 (çelişkide test değiştirdi, oluşturma isteğinde soru sordu) → görselde son
#   glm-5.3 ve mimo-v2.6-pro: mini projede 6 dk sınırını aştı (glm tek adımda ~6 dk) → kodda YOK
ROUTES: dict[str, list[str]] = {
    "sohbet": ["deepseek-v4-flash", "qwen3.8-flash-next", "gemma-4-31b"],
    "kod": ["deepseek-v4-flash", "qwen3.8-flash-next", "gemma-4-31b"],
    "plan": ["deepseek-v4.1-flash", "qwen3.8-flash-next", "deepseek-v4-flash"],
    "gorsel": ["gemma-4-31b", "qwen3.8-flash-next", "qwen3-vl-30b"],
    "buyuk_baglam": ["deepseek-v4-flash", "deepseek-v4.1-flash", "mimo-v2.6-pro"],
    "inceleme": ["qwen3.8-flash-next", "deepseek-v4.1-flash", "gemma-4-31b"],
}
ROUTES_MEASURED = "2026-10-19"

# Görsel kabul ETMEYEN modeller (gerçek API: 400 feature_not_enabled, 2026-10-19)
TEXT_ONLY = {"glm-5.3", "deepseek-v4-flash"}
# Bu orandan büyük tahmini bağlamda "büyük bağlam" rolüne geçilir (birincilin bağlamına göre)
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
        return f"{AKILLI_LABEL} → {self.model} ({ROLE_LABELS.get(self.role, self.role)})"


def classify(*, agentic: bool, mode: str = "", has_images: bool = False,
             est_tokens: int = 0, context_of: dict[str, int] | None = None) -> tuple[str, str]:
    """(rol, gerekçe). Öncelik: görsel > büyük bağlam > plan > kod > sohbet."""
    if has_images:
        return "gorsel", "mesajda görsel var"
    if est_tokens and context_of:
        base = ROUTES["kod" if agentic else "sohbet"][0]
        limit = context_of.get(base) or 0
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
    """Rol için birincil model + yedekler. Listede olmayan modeller atlanır; son 30 dk'da
    sağlıksız ölçülenler sona alınır (tamamen atılmaz: hepsi sağlıksızsa yine dene)."""
    now = now or datetime.now(timezone.utc)
    chain = list(ROUTES.get(role) or ROUTES["sohbet"])
    if available:
        chain = [m for m in chain if m in available] or chain
    chain.sort(key=lambda m: _unhealthy(health, m, now))           # sağlıklılar önde (kararlı sıralama)
    if role == "gorsel":
        chain = [m for m in chain if m not in TEXT_ONLY] or chain
    note = reason
    if chain and _unhealthy(health, chain[0], now):
        note += " · tüm adaylar yakın zamanda sorunlu ölçüldü"
    return Route(model=chain[0], role=role, reason=note, fallbacks=chain[1:])


def route(*, agentic: bool, mode: str = "", has_images: bool = False, est_tokens: int = 0,
          context_of: dict[str, int] | None = None, available: set[str] | None = None,
          health: dict[str, dict] | None = None) -> Route:
    role, reason = classify(agentic=agentic, mode=mode, has_images=has_images,
                            est_tokens=est_tokens, context_of=context_of)
    return choose(role, available=available, health=health, reason=reason)


def is_akilli(model_id: str | None) -> bool:
    return model_id == AKILLI_ID
