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
    # F2 (A6/A7, 2026-10-24)
    "kod_kolay": "kolay kod işi",
    "veri": "veri / rapor",
    "oyun": "oyun",
    "web": "web",
    "metin": "Türkçe metin",
    "qa": "QA testi",
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
#   2026-10-21 akşam yeniden ölçüm (12 görev, CHALLENGE_RESULTS.md "Kod motoru sırası"): üçü de 12/12;
#   gemma-4-31b 3,1 dk · deepseek-v4.1-flash 7,0 dk (19 Ekim'de 10 dk) · qwen3.8-flash-next 8,9 dk (en çok
#   adım). Kullanıcı kararı: kod = deepseek-v4.1-flash → qwen3.8-flash-next → gemma-4-31b (gemma uzun işte
#   döngüye girmişti; maratonla ölçülmeden öne alınmaz). v4-flash listeye dönerse yeniden ölçülmeli.
#   2026-11-01 kullanıcı kararı: UYARLANABİLİR sıra — bu tablo varsayılandır; öndeki model son 3 saatte
#   zincirdeki sağlıklı yedeğinden 2 kattan fazla yavaşsa o gün yedek öne alınır (choose(speeds=...),
#   modelstats.effective_speeds). O gün deepseek-v4.1-flash 14,4, qwen3.8-flash-next 3,7 sn/100 token ölçüldü.
EVREN_ROUTES: dict[str, list[str]] = {
    "sohbet": ["deepseek-v4-flash", "qwen3.8-flash-next", "deepseek-v4.1-flash", "gemma-4-31b"],
    # 2026-11-11 kullanıcı yetkisiyle ("yetki sende"): karne ölçümü (2026-11-06: qwen 95,5 · ortanca görev 29 sn;
    # deepseek 91,7 · 55 sn) sabit tabloya işlendi — 2026-10-21 kararının (deepseek önde) yerine. Bu sıra yalnız auto'nun
    # güvenlik ağı ve iç işler (Derin/Proje kod aşaması) içindir; kullanıcı turlarını auto (sunucu) seçer.
    "kod": ["qwen3.8-flash-next", "deepseek-v4.1-flash", "gemma-4-31b"],
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
    # F2 — A6 zorluk: kısa, tek dosyalık iş → hızlı model (gemma 12 görev 3,1 dk; uzun işte döngüye girdiği
    # için YALNIZ bu rolde önde). A7 iş türü rolleri: tests/e2e_rol_paketi_real_api.py, 2026-10-24, paket başına
    # 2 görev × 1 koşu (küçük örnek; CHALLENGE_RESULTS.md "Rol paketleri"): qwen3.8-flash-next 8/8 ve her pakette
    # en hızlı (toplam ~3,6 dk) · gemma-4-31b 7/8 (~4,6 dk; formda `required` eksik) · deepseek-v4.1-flash 7/8
    # (~16 dk; JSON'u PowerShell ile BOM'lu yazdı). Sıra: doğruluk, sonra süre.
    "kod_kolay": ["gemma-4-31b", "deepseek-v4.1-flash", "qwen3.8-flash-next"],
    "veri": ["qwen3.8-flash-next", "gemma-4-31b", "deepseek-v4.1-flash"],
    "oyun": ["qwen3.8-flash-next", "deepseek-v4.1-flash", "gemma-4-31b"],
    "web": ["qwen3.8-flash-next", "deepseek-v4.1-flash", "gemma-4-31b"],
    "metin": ["qwen3.8-flash-next", "gemma-4-31b", "deepseek-v4.1-flash"],
    # Madde 14 (2026-11-06): QA testi. 2026-11-05 gerçek masaüstü QA'da süre %84 model beklemesiydi; QA "kod" rolünü
    # kullanıyordu ve sağlık/hız bilgisi olmadan hep deepseek-v4.1-flash seçiliyordu (~43 sn/çağrı). Rol paketlerinde
    # (2026-10-24) qwen3.8-flash-next hem en doğru hem en hızlıydı → önde. gemma QA kararında yok: zor işte hile yazdı.
    "qa": ["qwen3.8-flash-next", "deepseek-v4.1-flash"],
}
ROUTES = EVREN_ROUTES               # eski ad
ROUTES_MEASURED = "2026-10-21"

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
    "kod_kolay": ["claude-haiku-5-5", "gpt-6-luna", "claude-sonnet-5-5"],
    "veri": ["claude-sonnet-5-5", "gpt-6.1-sol", "claude-haiku-5-5"],
    "oyun": ["claude-sonnet-5-5", "gpt-5.3-codex", "gpt-6.1-sol"],
    "web": ["claude-sonnet-5-5", "gpt-5.3-codex", "gpt-6.1-sol"],
    "metin": ["claude-sonnet-5-5", "gpt-6.1-sol", "claude-haiku-5-5"],
    "qa": ["claude-sonnet-5-5", "gpt-6.1-sol", "claude-haiku-5-5"],
}
PAID_ROUTES_VERIFIED = False
# Dengeli politika: bu rollerde (az token, yüksek değer) ücretli güçlü model önce gelir
PAID_FIRST_ROLES = {"plan", "inceleme", "gorsel"}

# Görsel kabul ETMEYEN modeller (gerçek API: 400 feature_not_enabled, 2026-10-19)
TEXT_ONLY = {"glm-5.3", "deepseek-v4-flash"}
BIG_CONTEXT_RATIO = 0.6
HEALTH_FRESH = timedelta(minutes=30)
# Motor karnesi puanı (Madde 14) yalnız karnenin ölçtüğü işlerde sırayı etkiler: zorluk paketi ajan/kod görevleri
# ölçer; görsel, özet, başlık gibi işlerde bu puan anlamsızdır.
SCORE_ROLES = {"kod", "kod_kolay", "plan", "veri", "web", "oyun", "inceleme", "qa"}

# A10 tutarlılık (2026-10-24 ölçümü, tests/e2e_tutarlilik_real_api.py, aynı istem 3 kez): temperature=0 +
# seed=42 YALNIZ gemma-4-31b'de yanıtı sabitledi (3/3 aynı); deepseek-v4.1-flash ve qwen3.8-flash-next her
# seferinde farklı metin yazdı (sayılar 18/18 aynıydı). Bu yüzden seed yalnız onu dinleyen modelde gönderilir;
# veri işlerinde tutarlılığı asıl sağlayan "hesabı betikle yap" talimatıdır (ROLE_HINTS["veri"]).
SEED_HONORED = {"gemma-4-31b"}
CONSISTENT_BODY = {"temperature": 0, "seed": 42}
CONSISTENT_ROLES = {"veri"}
ROLE_HINTS = {
    "veri": ("# Veri / rapor işi (Auto Pro)\n"
             "Sayıları, toplamları ve tabloları elle sayma veya tahmin etme: bir Python betiğiyle (csv, openpyxl "
             "kuruluysa o) hesapla, betiği projeye kaydet ve sonucu betiğin çıktısından al. Aynı veri aynı "
             "betikle her seferinde aynı raporu vermeli."),
}


def consistent_body(role: str, model: str) -> dict | None:
    """A10: tutarlılık rolünde, seed'i gerçekten dinleyen modele gönderilecek alanlar (yoksa None)."""
    return dict(CONSISTENT_BODY) if role in CONSISTENT_ROLES and model in SEED_HONORED else None


@dataclass
class Route:
    model: str
    role: str
    reason: str
    fallbacks: list[str] = field(default_factory=list)
    level: str = ""                 # A6 zorluk ("kolay" | "normal" | "zor" | "")

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
             available: set[str] | None = None, level: str = "", level_reason: str = "",
             kind: str = "", kind_reason: str = "") -> tuple[str, str]:
    """(rol, gerekçe). Öncelik: görsel > büyük bağlam > plan > iş türü (A7) > kolay iş (A6) > kod > sohbet.
    `level`/`kind`: modelstats.difficulty / task_kind sonucu (boş → eski davranış)."""
    if has_images:
        return "gorsel", "mesajda görsel var"
    if est_tokens and context_of:
        base_chain = chain_for("kod" if agentic else "sohbet", available)
        limit = context_of.get(base_chain[0]) if base_chain else 0
        if limit and est_tokens > limit * BIG_CONTEXT_RATIO:
            return "buyuk_baglam", f"bağlam ~{est_tokens // 1000}k token"
    if agentic and mode == "plan":
        return "plan", "Plan modu"
    if kind and kind in EVREN_ROUTES and (agentic or kind == "metin"):
        return kind, kind_reason or ROLE_LABELS.get(kind, kind)
    if agentic and level == "kolay":
        return "kod_kolay", level_reason or "kısa iş"
    if agentic:
        if level == "zor":
            return "kod", "zor iş" + (f": {level_reason}" if level_reason else "")
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
           reason: str = "", now: datetime | None = None, penalties: dict[str, str] | None = None,
           speeds: dict[str, float] | None = None, speed_factor: float = 2.0,
           scores: dict[str, float] | None = None, weak: dict[str, str] | None = None) -> Route:
    """Rol için birincil model + yedekler. Son 30 dk'da sağlıksız ölçülenler en sona, kalite puanı düşenler
    (A5, `penalties`: model → gerekçe) sağlamların arkasına alınır; hiçbiri zincirden ÇIKARILMAZ.

    Madde 14 (kullanıcı 2026-11-06): `scores` (motor karnesi: modelin EN İYİ ölçüm günündeki gerçek puanı, 0-100)
    en az iki aday puanlıysa puanlı adayları kendi yerlerinde puana göre dizer (puansızın yeri değişmez); `weak`
    (bugünkü hafif yoklamada hatalı/aşırı yavaş: model → gerekçe) o modeli sağlam adayların arkasına alır — sıradaki
    en güçlü yedek öne geçer. Zayıf rolde (modelstats.SLOW_SWITCH_EXCLUDE, ör. kodda gemma) zayıflık yüzünden öne
    GEÇİLMEZ: yavaş ama güçlü model zayıf modelden iyidir."""
    from . import modelstats

    now = now or datetime.now(timezone.utc)
    pen = penalties or {}
    wk = weak or {}
    sc = (scores or {}) if role in SCORE_ROLES else {}
    chain = chain_for(role, available)
    note = reason
    slots = [i for i, m in enumerate(chain) if m in sc]
    if len(slots) >= 2:
        before = [chain[i] for i in slots]
        ranked = sorted(before, key=lambda m: -sc[m])             # eşit puanda tablo sırası korunur
        for i, m in zip(slots, ranked):
            chain[i] = m
        if ranked != before:
            note += " · gerçek puana göre: " + ", ".join(f"{m} {sc[m]:.0f}" for m in ranked)
    first = chain[0] if chain else ""
    excl = modelstats.SLOW_SWITCH_EXCLUDE.get(role, set())
    any_weak = any(m in wk for m in chain)
    chain.sort(key=lambda m: (_unhealthy(health, m, now), m in wk or (any_weak and m in excl), m in pen))
    if role == "gorsel":
        chain = [m for m in chain if m not in TEXT_ONLY] or chain
    if first in wk and chain and chain[0] != first:
        note += f" · {first} bugün zayıf ({wk[first]}) → {chain[0]}"
    if first in pen and chain and chain[0] != first:
        note += f" · {first} geri alındı: {pen[first]}"
    if chain and _unhealthy(health, chain[0], now):
        note += " · tüm adaylar yakın zamanda sorunlu ölçüldü"
    # Uyarlanabilir sıra (kullanıcı kararı 2026-11-01): öndeki model, zincirdeki sağlıklı ve cezasız bir
    # yedekten son saatlerde `speed_factor` kattan fazla yavaşsa o yedek öne alınır (sıra varsayılan kalır).
    sp = speeds or {}
    if len(chain) > 1 and sp.get(chain[0]):
        fast = [m for m in chain[1:] if sp.get(m) and sp[m] >= sp[chain[0]] * speed_factor
                and not _unhealthy(health, m, now) and m not in pen and m not in wk]
        if fast:
            best = max(fast, key=lambda m: sp[m])
            note += (f" · {chain[0]} bugün yavaş ({sp[chain[0]]:.0f} token/sn) → {best} öne alındı "
                     f"({sp[best]:.0f} token/sn)")
            chain.remove(best)
            chain.insert(0, best)
    if not chain:
        return Route(model="", role=role, reason="kullanılabilir model yok (API anahtarı girin)")
    return Route(model=chain[0], role=role, reason=note, fallbacks=chain[1:])


def route(*, agentic: bool, mode: str = "", has_images: bool = False, est_tokens: int = 0,
          context_of: dict[str, int] | None = None, available: set[str] | None = None,
          health: dict[str, dict] | None = None, level: str = "", level_reason: str = "",
          kind: str = "", kind_reason: str = "", penalties: dict[str, str] | None = None,
          speeds: dict[str, float] | None = None, scores: dict[str, float] | None = None,
          weak: dict[str, str] | None = None) -> Route:
    role, reason = classify(agentic=agentic, mode=mode, has_images=has_images,
                            est_tokens=est_tokens, context_of=context_of, available=available,
                            level=level, level_reason=level_reason, kind=kind, kind_reason=kind_reason)
    r = choose(role, available=available, health=health, reason=reason, penalties=penalties, speeds=speeds,
               scores=scores, weak=weak)
    r.level = level
    return r


def same_provider(models: list[str], model: str, provider_of) -> list[str]:
    """Yedekleri birincil modelin sağlayıcısıyla sınırlar: istemci tur boyunca aynıdır, EVREN
    turu ücretli modele (veya tersi) geçemez; MCP'nin ücretli modele ulaşmaması da bununla
    garanti (kullanıcı kararı 2026-10-19)."""
    p = provider_of(model)
    return [m for m in models if provider_of(m) == p]


def is_auto_pro(model_id: str | None) -> bool:
    return model_id == AUTO_PRO_ID or model_id in LEGACY_IDS


is_akilli = is_auto_pro             # eski ad


# Madde 19 (kullanıcı 2026-11-07: "auto'dan daha iyi iş yapamayacaksak Auto Pro'yu silelim"): aynı gün zorluk paketi
# auto 12/12 1319 sn · Auto Pro 11/12 1182 sn, sohbette aynı motor → Auto Pro artık SEÇİLEBİLİR motor değil; oturum,
# ayar ve zamanlanmış görevdeki eski "auto-pro"/"akilli" kaydı "auto"ya taşınır. Auto Pro'nun yararlı parçası
# (karneye göre sıralı yedek motorlar) auto'nun GÜVENLİK AĞI olur (session_view: auto hata verir/takılırsa yedek);
# uygulamanın iç işleri (özet, inceleme, QA, Derin/Proje rolleri) yönlendiriciyi (ai_route) kullanmaya devam eder.
USER_DEFAULT_ID = "auto"


def normalize_model_id(model_id: str | None) -> str | None:
    """Kullanıcının seçebileceği motor: eski "auto-pro"/"akilli" → "auto"."""
    return USER_DEFAULT_ID if is_auto_pro(model_id) else model_id
