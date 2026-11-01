"""Auto Pro gerçek kullanım kaydı ve yavaşlama kuralı (Qt'siz).

A1 (2026-10-24): her model çağrısının süresi, ilk parça süresi, çıktı token'ı ve hatası kaydedilir; motorun
"o günkü normal hızı" bu kayıtlardan hesaplanır. Eskiden sağlık bilgisi yalnız Durum İzleme ekranından
yazılıyordu; kullanıcının gerçek veritabanında `model_health` boştu (RAKIP_VE_AUTOPRO_ANALIZI.md §4).

A3 — yavaşlama kuralı (kullanıcı onayı, DECISIONS #88):
1. Yalnız güvenli noktada (iki adım arası) yedeğe geçilir — bunu koşucu sağlar.
2. Motor, o günkü normal hızının (`factor`, normal turda 0,5) altında ART ARDA `SLOW_STREAK` adım kalırsa.
3. Görev başına yavaşlıktan en çok bir değişim (`SlowDetector.used`).
4. Her değişim gerekçesiyle bildirilir (koşucunun durum notu).
5. Proje/Derin görevi içinde eşik ~3 kat yavaşlık (`FACTOR_TASK`); görevler arası geçişi bekleme süresi (A4) yapar.
Yeterli örnek yoksa (`MIN_SAMPLES`) kural ÇALIŞMAZ: bilinmeyen hız yüzünden yanlış geçiş olmasın (R-22).
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from typing import Any, Iterable

MIN_SAMPLES = 6                 # normal hızı hesaplamak için en az başarılı çağrı
MIN_TOKENS_FOR_SPEED = 150      # bundan kısa yanıtta token/sn güvenilmez (yalnız ilk parça bakılır)
FACTOR_TURN = 0.5               # normal tur: normal hızın yarısı (kullanıcının %50 kuralı)
FACTOR_TASK = 1 / 3             # Proje/Derin görevi içinde: ~3 kat yavaşlık
SLOW_STREAK = 2                 # art arda yavaş adım
FIRST_CHUNK_MIN_EXTRA_S = 10.0  # ilk parça için: normalin en az bu kadar üstü (kısa sürelerde gürültü)
WINDOW_HOURS = 6                # "o günkü" hız: son 6 saat; yetmezse son 24 saat
WINDOW_HOURS_FALLBACK = 24
PROBE_ROLE = "yoklama"          # A8 hafif yoklama kayıtlarının rolü

# A5 kalite puanı: koşucunun ve kullanıcının bildirdiği kalite olayları (model_calls.event). Ağırlık = bir
# olayın kaç "kötü çağrı" sayıldığı. Puan yalnız SIRALAMAYI etkiler (router.choose), modeli kapatmaz.
QUALITY_WEIGHTS = {
    "feedback_bad": 3.0,        # kullanıcı yanıtı 👎 ile işaretledi
    "loop": 2.0,                # döngü bekçisi turu durdurdu ya da yedeğe geçirdi
    "test_edit": 2.0,           # istenmeden değiştirilen test dosyası tur sonunda öyle kaldı
    "test_break": 1.0,          # değişiklikten sonra testler düştü (test bekçisi dürttü)
    "plan_stall": 1.0,          # plan bekçisi: açık madde varken ilerlemeden durdu
}
QUALITY_FLOOR = 0.6             # puan bunun altındaysa model sıranın gerisine alınır
QUALITY_MIN_CALLS = MIN_SAMPLES  # puanı hesaplamak için en az çağrı (az örnekle kimse cezalanmaz)
FEEDBACK_BAD_ALONE = 2          # 24 saatte bu kadar 👎 çağrı sayısından bağımsız olarak geri alır
QUALITY_HOURS = 24


def gen_speed(rec: dict[str, Any]) -> float | None:
    """Üretim hızı (token/sn): çıktı token'ı / (süre − ilk parça). Kısa yanıtta None."""
    out = rec.get("out_tokens") or 0
    dur = rec.get("duration_s") or 0
    if out < MIN_TOKENS_FOR_SPEED or dur <= 0:
        return None
    first = rec.get("first_chunk_s") or 0
    gen = dur - first if 0 < first < dur else dur
    return out / max(gen, 0.5)


# Uyarlanabilir sıra (kullanıcı kararı 2026-11-01): öndeki model yedeğinden bu kat yavaşsa o gün yedek öne alınır.
# Ölçüm 2026-11-01: deepseek-v4.1-flash 14,4 sn/100 token, qwen3.8-flash-next 3,7 (21 Ekim'de tersiydi → sabit
# sıra yerine son saatlerin gerçek hızı).
SPEED_HOURS = 3.0
SPEED_FACTOR = 2.0


def effective_speeds(rows: Iterable[dict[str, Any]], min_samples: int = MIN_SAMPLES) -> dict[str, float]:
    """Model → etkili hız (token/sn; ilk parça DAHİL: kullanıcının beklediği gerçek süre). Ortanca; yetersiz
    örnekli (az veya kısa yanıtlı) model dönmez. Yoklama kayıtları sayılmaz."""
    by: dict[str, list[float]] = {}
    for r in rows:
        if not r.get("ok") or r.get("event") or r.get("role") == PROBE_ROLE:
            continue
        out, dur = r.get("out_tokens") or 0, r.get("duration_s") or 0
        if out >= MIN_TOKENS_FOR_SPEED and dur > 0:
            by.setdefault(r["model"], []).append(out / dur)
    return {m: statistics.median(v) for m, v in by.items() if len(v) >= min_samples}


@dataclass
class Baseline:
    model: str
    tps: float | None            # ortanca üretim hızı
    first_chunk_s: float | None  # ortanca ilk parça süresi
    samples: int


def baselines(rows: Iterable[dict[str, Any]]) -> dict[str, Baseline]:
    """Başarılı çağrılardan model başına normal hız. Yetersiz örnekli model dönmez. Yoklama (A8) kısa ve
    bağlamsızdır: ilk parça süresi gerçek işten kısa çıkar, normal hızı çarpıtmasın diye sayılmaz."""
    by: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("ok") and not r.get("event") and r.get("role") != PROBE_ROLE:
            by.setdefault(r["model"], []).append(r)
    out: dict[str, Baseline] = {}
    for model, rs in by.items():
        if len(rs) < MIN_SAMPLES:
            continue
        speeds = [s for s in (gen_speed(r) for r in rs) if s]
        firsts = [r["first_chunk_s"] for r in rs if r.get("first_chunk_s")]
        out[model] = Baseline(model, statistics.median(speeds) if len(speeds) >= 3 else None,
                              statistics.median(firsts) if len(firsts) >= 3 else None, len(rs))
    return out


def slow_reason(rec: dict[str, Any], base: Baseline | None, factor: float) -> str:
    """Bu adım normalin `factor` katından yavaş mı? Gerekçe metni ("" → yavaş değil)."""
    if base is None or not rec.get("ok"):
        return ""
    sp = gen_speed(rec)
    if sp is not None and base.tps and sp < base.tps * factor:
        return f"üretim hızı {sp:.0f} token/sn, bugünkü normali ~{base.tps:.0f}"
    first = rec.get("first_chunk_s")
    if first and base.first_chunk_s and first > max(base.first_chunk_s / factor,
                                                    base.first_chunk_s + FIRST_CHUNK_MIN_EXTRA_S):
        return f"ilk yanıt {first:.0f} sn, bugünkü normali ~{base.first_chunk_s:.0f} sn"
    return ""


class SlowDetector:
    """Art arda yavaş adım sayar; görev başına en çok bir yavaşlık değişimi önerir."""

    def __init__(self, base: dict[str, Baseline] | None, factor: float = FACTOR_TURN):
        self.base = base or {}
        self.factor = factor
        self.streak = 0
        self.used = False
        self.last_reason = ""

    def observe(self, model: str, rec: dict[str, Any]) -> str:
        """Adım sonucu → değiştirme gerekçesi ("" → değiştirme)."""
        if self.used:
            return ""
        why = slow_reason(rec, self.base.get(model), self.factor)
        if not why:
            self.streak = 0
            return ""
        self.streak += 1
        self.last_reason = why
        if self.streak >= SLOW_STREAK:
            return f"art arda {self.streak} adım yavaş ({why})"
        return ""

    def reset(self) -> None:
        """Model değişince sayaç sıfırlanır (yeni modelin normaliyle başlar)."""
        self.streak = 0


def summary(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Model başına özet (A12): çağrı, hata oranı, ortanca hız ve ilk yanıt, değişim sayısı."""
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        s = out.setdefault(r["model"], {"calls": 0, "errors": 0, "switches": 0, "_sp": [], "_fc": []})
        if r.get("event") == "switch":
            s["switches"] += 1
            continue
        if r.get("event"):                 # kalite olayı (A5): çağrı değildir
            continue
        s["calls"] += 1
        if not r.get("ok"):
            s["errors"] += 1
        sp = gen_speed(r)
        if sp:
            s["_sp"].append(sp)
        if r.get("first_chunk_s"):
            s["_fc"].append(r["first_chunk_s"])
    for s in out.values():
        sp, fc = s.pop("_sp"), s.pop("_fc")
        s["tps"] = round(statistics.median(sp)) if sp else None
        s["first_chunk_s"] = round(statistics.median(fc), 1) if fc else None
        s["error_rate"] = round(s["errors"] / s["calls"], 2) if s["calls"] else 0.0
    return out


# ---- A5: kalite puanı -------------------------------------------------------------------------

def quality(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Model başına kalite: çağrı sayısı, olay sayıları, puan (1 = temiz; 0 = her çağrı kötü)."""
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        s = out.setdefault(r["model"], {"calls": 0, "events": {}})
        ev = r.get("event")
        if ev in QUALITY_WEIGHTS:
            s["events"][ev] = s["events"].get(ev, 0) + 1
        elif not ev and r.get("role") != PROBE_ROLE:
            s["calls"] += 1
    for s in out.values():
        bad = sum(QUALITY_WEIGHTS[k] * n for k, n in s["events"].items())
        s["score"] = round(max(0.0, 1.0 - bad / s["calls"]), 2) if s["calls"] else None
    return out


def penalized(rows: Iterable[dict[str, Any]]) -> dict[str, str]:
    """Sıranın gerisine alınacak modeller → gerekçe. Az örnekte yalnız açık kullanıcı işareti sayılır."""
    out: dict[str, str] = {}
    for model, s in quality(rows).items():
        bad_marks = s["events"].get("feedback_bad", 0)
        if bad_marks >= FEEDBACK_BAD_ALONE:
            out[model] = f"son {QUALITY_HOURS} saatte {bad_marks} yanıtı kötü işaretlendi"
        elif s["calls"] >= QUALITY_MIN_CALLS and s["score"] is not None and s["score"] < QUALITY_FLOOR:
            olay = ", ".join(f"{k} {n}" for k, n in sorted(s["events"].items()))
            out[model] = f"kalite puanı {s['score']:.2f} ({olay})"
    return out


# ---- A6: zorluk, A7: iş türü --------------------------------------------------------------------
# Yalnız mesaj metnine ve proje dosya adlarına bakan, açıklanabilir kurallar (model çağrısı yok). Yanlış
# "kolay" sınıflaması en pahalı hatadır (hızlı model uzun işte döngüye girebilir): şüphede "normal".

_FILE_RE = re.compile(r"[\w\-./\\]+\.(?:py|js|ts|tsx|jsx|html?|css|json|ya?ml|toml|md|txt|csv|xlsx?|sql|"
                      r"gd|tscn|cs|java|go|rs|cpp|c|h|ini|cfg|log|bat|ps1|sh)\b", re.I)
_HARD_RE = re.compile(r"baştan|sıfırdan|tüm proje|bütün proje|projenin tamam|mimari|refactor|yeniden yapılandır|"
                      r"uygulama (?:yap|geliştir|oluştur)|sistem(?:i)? (?:yap|kur|geliştir)|uçtan uca|"
                      r"entegrasyon|veritabanı (?:tasarla|kur)|birden (?:çok|fazla) dosya|her dosya", re.I)
_NOT_EASY_RE = re.compile(r"\btest|her yer|tüm |bütün |hata(?:yı|ları)? (?:bul|ayıkla)|neden çalışmıyor|debug(?:la|ging)|"
                          r"\bbug|proje|ekle(?:yip|yerek)? .* ve |performans|güvenlik|kur(?:ulum)?\b|"
                          # program çalıştırmak yargı ister (girdi bekleyen komut, yan etki): 2026-10-24 zorluk
                          # paketinde "oyun.py'yi çalıştır" kolay sayılıp gemma'ya gitti, girdiyi kendisi uydurdu
                          r"çalıştır|\bbaşlat|\bkomut", re.I)
_COMPLAINT_RE = re.compile(r"\b(?:olmadı|hala|hâlâ|yine|düzelmedi|çalışmıyor|çalışmadı|yanlış|bozuldu|"
                           r"eksik kaldı|tamamlanmadı)\b", re.I)
EASY_MAX_CHARS = 180
HARD_MIN_CHARS = 700


def difficulty(text: str, *, project_task: bool = False) -> tuple[str, str]:
    """("kolay" | "normal" | "zor", gerekçe). Proje/Derin görevi her zaman "zor"dur."""
    t = (text or "").strip()
    if project_task:
        return "zor", "proje görevi"
    files = {m.group(0).lower() for m in _FILE_RE.finditer(t)}
    if len(t) >= HARD_MIN_CHARS:
        return "zor", f"uzun istek (~{len(t)} karakter)"
    if len(files) >= 3:
        return "zor", f"{len(files)} dosya anılıyor"
    m = _HARD_RE.search(t)
    if m:
        return "zor", f"\"{m.group(0)}\""
    if len(t) <= EASY_MAX_CHARS and len(files) <= 1 and not _NOT_EASY_RE.search(t):
        return "kolay", "kısa, tek dosyalık istek"
    return "normal", ""


def is_complaint(text: str) -> bool:
    """Kullanıcı önceki turun işe yaramadığını söylüyor mu (A6 yükseltme)."""
    t = (text or "").strip()
    return len(t) <= 300 and bool(_COMPLAINT_RE.search(t))


_KIND_RES = {
    "veri": re.compile(r"\b(?:excel|xlsx|xls|csv|pivot|rapor(?:u|la|lar)?|veri seti|dataset|hesap kapama|"
                       r"özet tablo|tablo(?:yu|da|dan|ya)?)\b", re.I),
    # "oyun.py" bir dosya adıdır, iş türü değil → nokta + uzantı izliyorsa sayılmaz
    "oyun": re.compile(r"(?<![\w/\\])(?:oyun(?:u|un|da|lar|cu)?|game|godot|pygame|phaser|sprite|"
                       r"platform oyunu)(?!\.\w)", re.I),
    "web": re.compile(r"(?<![\w.])(?:html|css|web sayfa\w*|web sitesi|site(?:si|yi)?|react|vue|frontend|"
                      r"tarayıcı|playwright|pwa|landing page|javascript)(?![\w.])", re.I),
}
_KIND_FILES = {
    "veri": (".xlsx", ".xls", ".csv"),
    "oyun": ("project.godot",),
    "web": ("index.html", "package.json"),
}
_CODE_EXT = (".py", ".js", ".ts", ".tsx", ".jsx", ".cs", ".java", ".go", ".rs", ".cpp", ".c", ".gd", ".php", ".rb")
_TEXT_RE = re.compile(r"e-?posta|\bmail\b|dilekçe|mektup|makale|blog yazısı|paragraf|şiir|metn(?:i|ini) "
                      r"(?:düzelt|yaz|özetle|çevir)|(?:yazım|imla) (?:hata|kontrol)|(?:yazım|imla) ve noktalama|noktalama hata|türkçeye çevir|"
                      r"ingilizceye çevir|resmi yazı|duyuru metni", re.I)


def task_kind(text: str, *, agentic: bool, files: Iterable[str] = ()) -> tuple[str, str]:
    """("veri" | "oyun" | "web" | "metin" | "", gerekçe). Mesaj önce; proje dosyaları yalnız yardımcı."""
    t = text or ""
    if not agentic:
        return ("metin", "Türkçe metin işi") if _TEXT_RE.search(t) else ("", "")
    hits = [(k, m.group(0)) for k, rx in _KIND_RES.items() if (m := rx.search(t))]
    if len(hits) == 1:
        return hits[0][0], f"istekte \"{hits[0][1]}\""
    if len(hits) > 1:
        return "", ""                       # karışık iş (ör. web + veri) → genel kod rolü
    names = [str(f).replace("\\", "/").rsplit("/", 1)[-1].lower() for f in files]
    found = [k for k, sfx in _KIND_FILES.items() if any(n.endswith(sfx) for n in names)]
    # Kod projesindeki örnek/test .csv dosyası her işi "veri" yapmasın (R-22): veri rolü yalnız kodsuz klasörde
    if "veri" in found and any(n.endswith(_CODE_EXT) for n in names):
        found.remove("veri")
    if len(found) == 1:
        return found[0], "proje dosyaları"
    return "", ""
