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


def gen_speed(rec: dict[str, Any]) -> float | None:
    """Üretim hızı (token/sn): çıktı token'ı / (süre − ilk parça). Kısa yanıtta None."""
    out = rec.get("out_tokens") or 0
    dur = rec.get("duration_s") or 0
    if out < MIN_TOKENS_FOR_SPEED or dur <= 0:
        return None
    first = rec.get("first_chunk_s") or 0
    gen = dur - first if 0 < first < dur else dur
    return out / max(gen, 0.5)


@dataclass
class Baseline:
    model: str
    tps: float | None            # ortanca üretim hızı
    first_chunk_s: float | None  # ortanca ilk parça süresi
    samples: int


def baselines(rows: Iterable[dict[str, Any]]) -> dict[str, Baseline]:
    """Başarılı çağrılardan model başına normal hız. Yetersiz örnekli model dönmez."""
    by: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("ok") and not r.get("event"):
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
