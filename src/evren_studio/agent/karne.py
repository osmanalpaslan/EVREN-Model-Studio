"""Motor karnesi (Madde 14, kullanıcı 2026-11-06) — Qt'siz, ağ isteği yapmaz.

Kullanıcının fikri: "Motorlar sürekli eğitiliyor, günlük performansları değişebiliyor. Gerçek kalite için birkaç gün
belirleyelim, motorları EN İYİ çalıştıkları günde ölçelim ve her motora puan verelim; bu puanlar gerçek puanlarını
göstersin. Ama günlük hafif yoklamada zayıfsa daha güçlü yedek motora geçilsin; Auto Pro motorlarını ajan yönetsin."

Üç katman:
1. Hafif yoklama (A8, açılışta ve en çok 30 dk'da bir): her motora birkaç tokenlık istek. `weak_models` bugünkü
   son yoklamaya bakar: hata ya da motorun KENDİ normal yoklama süresinin çok üstü → "bugün zayıf" (yönlendirici o
   modeli sağlam adayların arkasına alır, sıradaki en güçlü yedek öne geçer). Yoklama kısa ve gürültülüdür: kaliteyi
   değil yalnız "bugün ayakta ve makul hızda mı"yı söyler.
2. Gerçek puan (karne): belirlenmiş ölçüm günlerinde gerçek görev paketi (tests/e2e_zorluk_real_api.py) motor başına
   koşulur, `score_report` 0-100 puan verir. Ölçüm YALNIZ yoklama o motoru "iyi gün"de bulursa gerçek puan sayılır
   (`day_state`); kötü günün ölçümü kayda "iyi gün değil" diye geçer, puana katılmaz.
3. `best_scores`: her motorun son N gündeki iyi-gün ölçümlerinden EN YÜKSEĞİ — motorun gerçek kapasitesi. Yönlendirici
   bu puanla sıralar; o günkü zayıflığı 1. katman düzeltir.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

PROBE_ROLE = "yoklama"              # modelstats.PROBE_ROLE ile aynı
PROBE_FRESH = timedelta(hours=2)    # "bugünkü" yoklama: son 2 saat (yoklama en çok 30 dk'da bir)
PROBE_MIN_HISTORY = 3               # motorun normal yoklama süresi için en az geçmiş yoklama
PROBE_SLOW_FACTOR = 3.0             # normalinin bu katından yavaşsa zayıf
PROBE_SLOW_MIN_S = 8.0              # ...ama en az bu kadar sürmeli (kısa sürelerde gürültü)
PROBE_VERY_SLOW_S = 30.0            # geçmiş yoksa bile bu süreyi aşan yoklama zayıf
GOOD_DAY_FACTOR = 1.5               # karne ölçümü için: son yoklama normalinin en çok bu katı

# Puan ağırlıkları (toplam 1): doğruluk önce, sonra hız (kullanıcı: "doğruluk bir tık daha önemli")
W_CHECKS, W_TASKS, W_SPEED, W_STABLE = 0.55, 0.25, 0.12, 0.08
REF_TASK_S = 60.0                   # görev başına bu süre ve altı tam hız puanı
SCORE_DAYS = 60                     # gerçek puan: son 60 günün iyi-gün ölçümlerinin en yükseği


def _at(r: dict[str, Any]) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(r.get("at")).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _probes(rows: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if r.get("role") == PROBE_ROLE and not r.get("event") and _at(r) is not None:
            by.setdefault(r["model"], []).append(r)
    for v in by.values():
        v.sort(key=lambda r: _at(r))
    return by


def _normal(history: list[dict[str, Any]]) -> float | None:
    ds = [r["duration_s"] for r in history if r.get("ok") and r.get("duration_s")]
    return statistics.median(ds) if len(ds) >= PROBE_MIN_HISTORY else None


def day_state(rows: Iterable[dict[str, Any]], model: str, now: datetime | None = None) -> tuple[str, str]:
    """("iyi" | "zayif" | "bilinmiyor", gerekçe) — motorun bugünkü son yoklamasına göre."""
    now = now or datetime.now(timezone.utc)
    ps = _probes(rows).get(model) or []
    if not ps or now - _at(ps[-1]) > PROBE_FRESH:
        return "bilinmiyor", "yakın zamanda yoklanmadı"
    last, history = ps[-1], ps[:-1]
    if not last.get("ok"):
        return "zayif", f"yoklamada hata ({last.get('error_kind') or 'bilinmiyor'})"
    d = float(last.get("duration_s") or 0)
    normal = _normal(history)
    if normal is not None:
        if d > max(normal * PROBE_SLOW_FACTOR, PROBE_SLOW_MIN_S):
            return "zayif", f"yoklama {d:.0f} sn, normali ~{normal:.0f} sn"
        if d > max(normal * GOOD_DAY_FACTOR, PROBE_SLOW_MIN_S / 2):
            return "bilinmiyor", f"yoklama {d:.0f} sn, normalinden yavaş (~{normal:.0f} sn)"
        return "iyi", f"yoklama {d:.1f} sn (normali ~{normal:.1f} sn)"
    if d > PROBE_VERY_SLOW_S:
        return "zayif", f"yoklama {d:.0f} sn"
    return "bilinmiyor", "karşılaştırmak için yeterli yoklama geçmişi yok"


def weak_models(rows: Iterable[dict[str, Any]], now: datetime | None = None) -> dict[str, str]:
    """Bugünkü yoklamada zayıf motorlar → gerekçe (yönlendirici bunları sağlam adayların arkasına alır)."""
    rows = list(rows)
    out: dict[str, str] = {}
    for model in _probes(rows):
        state, why = day_state(rows, model, now)
        if state == "zayif":
            out[model] = why
    return out


# ---- gerçek puan -------------------------------------------------------------------------------------------------

def score_report(report: dict[str, Any]) -> dict[str, Any]:
    """Zorluk paketi raporundan (rapor.json) 0-100 puan ve bileşenleri."""
    res = list(report.get("sonuclar") or [])
    if not res:
        return {"score": 0.0, "gorev": 0, "neden": "raporda görev yok"}
    checks = [c for r in res for c in (r.get("kontroller") or [])]
    passed = sum(1 for c in checks if c.get("gecti"))
    check_ratio = passed / len(checks) if checks else 0.0
    full = sum(1 for r in res if r.get("kontroller") and all(c.get("gecti") for c in r["kontroller"]))
    task_ratio = full / len(res)
    times = [float(r.get("sure") or 0) for r in res if r.get("sure")]
    med = statistics.median(times) if times else 0.0
    speed = min(1.0, REF_TASK_S / med) if med > 0 else 0.0
    trouble = sum(int(r.get("hata_karti") or 0) + len(r.get("tekrar_3") or {}) +
                  (0 if r.get("zaman_icinde", True) else 1) for r in res)
    stable = max(0.0, 1.0 - trouble / len(res))
    score = 100.0 * (W_CHECKS * check_ratio + W_TASKS * task_ratio + W_SPEED * speed + W_STABLE * stable)
    return {"score": round(score, 1), "gorev": len(res), "tam_gecen": full, "kontrol": f"{passed}/{len(checks)}",
            "ortanca_sure_sn": round(med, 1), "hiz": round(speed, 2), "kararlilik": round(stable, 2)}


def best_scores(rows: Iterable[dict[str, Any]]) -> dict[str, float]:
    """Model → gerçek puan: iyi-gün ölçümlerinin EN YÜKSEĞİ (kötü günün ölçümü sayılmaz)."""
    out: dict[str, float] = {}
    for r in rows:
        if not r.get("good_day"):
            continue
        m, s = r.get("model"), r.get("score")
        if m and s is not None and float(s) > out.get(m, -1.0):
            out[m] = float(s)
    return out


def card(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ekranda gösterilecek karne: model, gerçek puan, ölçüm sayısı (iyi gün / toplam), son ölçüm."""
    by: dict[str, dict[str, Any]] = {}
    for r in rows:
        s = by.setdefault(r["model"], {"model": r["model"], "puan": None, "iyi": 0, "toplam": 0, "son": ""})
        s["toplam"] += 1
        s["son"] = max(s["son"], str(r.get("at") or ""))
        if r.get("good_day"):
            s["iyi"] += 1
            s["puan"] = max(s["puan"] or 0.0, float(r["score"]))
    return sorted(by.values(), key=lambda s: -(s["puan"] if s["puan"] is not None else -1))
