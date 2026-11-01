"""Kota bitince otomatik devam (Qt'siz): ne zaman sürdürüleceği, kotanın yeterli olup olmadığı ve kalıcı kayıt.

Neden (kullanıcı, 2026-11-01): "token bittiğinde proje çalışması yarıda kalıyor". Normal ajan turunda günlük
kota azalınca yalnız uyarılıyor, ardından 429 ile tur hata veriyordu; Proje/QA/Derin'deki otomatik sürdürme
yalnız uygulama açıkken çalışıyordu. Burada: tur güvenli noktada durur (model çağrısından önce — araç
sonuçları kayıtlı, yarım düzenleme yok), devam kaydı veritabanına yazılır (uygulama kapanıp açılsa da kalır),
saatinde önce kota yoklanır (token harcamaz), yeterliyse aynı oturumda kaldığı yerden devam edilir.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass

from .quota import DAILY_MIN_TOKENS, WINDOW_WAIT, _num, seconds_until

META_KEY = "pending_resume"
DAILY_EXTRA_S = 120.0          # yenilenme saatinden sonra pay (sunucu saati farkı)
WINDOW_EXTRA_S = 20.0
DAILY_FALLBACK_S = 3600.0      # yenilenme saati okunamazsa
WINDOW_FALLBACK_S = 360.0      # 5 dk kayan pencere + pay
PROBE_RETRY_S = 600.0          # yoklama başarısız / kota hâlâ yetersiz ve saat bilinmiyor
MAX_DELAY_S = 26 * 3600.0


@dataclass
class ResumePlan:
    session_id: int
    kind: str                  # "gunluk" | "pencere"
    resume_at: float           # epoch saniye
    reason: str = ""
    created: float = 0.0
    attempts: int = 0
    flow: str = "sohbet"       # "sohbet" | "proje" | "qa" | "derin" — devamda hangi akış sürdürülür

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str | None) -> "ResumePlan | None":
        try:
            d = json.loads(text or "")
            return cls(int(d["session_id"]), str(d["kind"]), float(d["resume_at"]), str(d.get("reason") or ""),
                       float(d.get("created") or 0.0), int(d.get("attempts") or 0), str(d.get("flow") or "sohbet"))
        except (ValueError, KeyError, TypeError):
            return None

    def seconds_left(self, now: float | None = None) -> float:
        return max(0.0, self.resume_at - (time.time() if now is None else now))


def resume_after(kind: str, quota) -> float:
    """Kotanın yenilenmesine kalan saniye (+ pay); saat bilinmiyorsa temkinli varsayılan."""
    if kind == "gunluk":
        sec = seconds_until(getattr(quota, "daily_reset_at", None))
        sec = DAILY_FALLBACK_S if sec is None else sec + DAILY_EXTRA_S
    else:
        sec = seconds_until(getattr(quota, "reset_at", None))
        sec = WINDOW_FALLBACK_S if sec is None else sec + WINDOW_EXTRA_S
    return min(max(sec, 30.0), MAX_DELAY_S)


def make_plan(session_id: int, kind: str, quota, reason: str = "", now: float | None = None,
              flow: str = "sohbet") -> ResumePlan:
    now = time.time() if now is None else now
    return ResumePlan(session_id, kind, now + resume_after(kind, quota), reason, now, flow=flow)


def kind_from_reason(reason: str) -> str | None:
    """Proje/QA/Derin duraklatma nedeninden kota türü; kota dışı neden (soru, karar, hata) → None."""
    low = (reason or "").lower()
    if "günlük" in low:
        return "gunluk"
    if "kota" in low or "pencere" in low or "rate" in low or "429" in low:
        return "pencere"
    return None


def kind_for(quota) -> str:
    """Kotanın hangi sınırı dolu: günlük kalan azsa "gunluk", değilse "pencere" (5 dk hız sınırı)."""
    rem = _num(getattr(quota, "daily_remaining_tokens", None))
    return "gunluk" if rem is not None and rem < DAILY_MIN_TOKENS else "pencere"


def quota_ok(quota) -> bool:
    """Devam etmek için yeterli mi? Okunamayan değer engel sayılmaz (kota kapısıyla aynı ilke)."""
    if quota is None:
        return True
    rem = _num(getattr(quota, "daily_remaining_tokens", None))
    if rem is not None and rem < DAILY_MIN_TOKENS:
        return False
    ratio = _num(getattr(quota, "usage_ratio", None))
    return ratio is None or ratio < WINDOW_WAIT


def after_probe(plan: ResumePlan, quota, now: float | None = None) -> ResumePlan:
    """Yoklama kota yetersiz dedi: yeni saat (sunucunun söylediği yenilenme ya da PROBE_RETRY_S sonra)."""
    now = time.time() if now is None else now
    kind = kind_for(quota) if quota is not None else plan.kind
    sec = resume_after(kind, quota) if quota is not None else PROBE_RETRY_S
    return ResumePlan(plan.session_id, kind, now + max(sec, 60.0), plan.reason, plan.created, plan.attempts + 1,
                      plan.flow)


def describe(plan: ResumePlan, now: float | None = None) -> str:
    """"01.11 23:59 (yaklaşık 4 sa 39 dk sonra)" biçimi."""
    from datetime import datetime

    left = int(plan.seconds_left(now))
    when = datetime.fromtimestamp(plan.resume_at).strftime("%d.%m %H:%M")
    if left <= 0:
        return f"{when} (şimdi yoklanıyor)"
    h, m = divmod((left + 59) // 60, 60)
    span = f"{h} sa {m} dk" if h else f"{m} dk"
    return f"{when} (yaklaşık {span} sonra)"
