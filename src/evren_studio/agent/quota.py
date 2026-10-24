"""Kota kapısı: EVREN kotasına göre paralelliği ayarlar ve gerekirse kodla bekler (Qt'siz).

EVREN kotası (2026-10-19 ölçümü): 5 dk kayan pencerede 2,5M token (HIZ sınırı, süre değil) ve
günlük 15M token. Paralel alt ajanlar pencereyi hızla doldurabilir; dolunca 429 gelir ve istemci her
ajan için ayrı ayrı bekleyip aynı anda yeniden dener. Kapı bunu önler:
- pencere ≥ %60 → paralellik 1'e iner; ≥ %85 → pencere yenilenene kadar (en çok ~6 dk) bekler;
- günlük kalan alt eşiğin altında → "günlük" duraklama (yenilenme saatinde otomatik sürdürülür).
Kota okunamazsa engel olmaz (bilinmeyen = devam).
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

WINDOW_SLOW = 0.60
WINDOW_WAIT = 0.85
DAILY_MIN_TOKENS = 400_000
CACHE_S = 30.0
MAX_WINDOW_WAIT_S = 360.0


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def seconds_until(iso: str | None, now: datetime | None = None) -> float | None:
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return (t - now).total_seconds()


class QuotaGate:
    def __init__(self, fetch: Callable[[], Any], max_parallel: int = 2, cache_s: float = CACHE_S,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        self.fetch = fetch
        self.max_parallel = max(1, int(max_parallel))
        self.cache_s = cache_s
        self.sleep = sleep
        self.clock = clock
        self._q: Any = None
        self._at = -1e9
        self._lock = threading.Lock()

    def snapshot(self, fresh: bool = False) -> Any:
        with self._lock:
            if fresh or self.clock() - self._at > self.cache_s:
                try:
                    self._q = self.fetch()
                except Exception:
                    self._q = None
                self._at = self.clock()
            return self._q

    def window_ratio(self) -> float | None:
        return _num(getattr(self.snapshot(), "usage_ratio", None))

    def parallel_limit(self) -> int:
        r = self.window_ratio()
        if r is not None and r >= WINDOW_SLOW:
            return 1
        return self.max_parallel

    def daily_low(self) -> tuple[bool, str | None]:
        q = self.snapshot()
        rem = _num(getattr(q, "daily_remaining_tokens", None))
        return (rem is not None and rem < DAILY_MIN_TOKENS), getattr(q, "daily_reset_at", None)

    def before_call(self, cancel=None, status: Callable[[str], None] | None = None,
                    daily_blocks: bool = True) -> str | None:
        """Model çağrısından önce: pencere çok doluysa yenilenene kadar bekler. Dönüş: None → devam,
        "daily" → günlük kota bitti (çağıran duraklatır), "cancelled". `daily_blocks=False` (normal tur, A11):
        günlük kota azlığı durdurmaz — çağıran `daily_low()` ile kullanıcıyı uyarır."""
        low, _reset = self.daily_low()
        if low and daily_blocks:
            return "daily"
        r = self.window_ratio()
        if r is None or r < WINDOW_WAIT:
            return None
        wait = seconds_until(getattr(self._q, "reset_at", None))
        wait = min(max((wait or 60.0) + 3.0, 5.0), MAX_WINDOW_WAIT_S)
        if status:
            status(f"5 dakikalık EVREN kota penceresi %{int(r * 100)} dolu; yenilenmesi bekleniyor (~{int(wait)} sn). "
                   "Bu bekleme token harcamaz.")
        end = self.clock() + wait
        while end - self.clock() > 0.05:     # kayan nokta: kalan ~0'a inip döngü sonsuz dönmesin
            if cancel is not None and getattr(cancel, "cancelled", False):
                return "cancelled"
            self.sleep(min(2.0, end - self.clock()))
        self.snapshot(fresh=True)
        return None


def resume_delay_ms(reset_iso: str | None, extra_s: float = 120.0, fallback_s: float = 3600.0) -> int:
    """Günlük kota yenilenince sürdürmek için QTimer gecikmesi (ms); en az 1 dk, en çok ~24 sa."""
    sec = seconds_until(reset_iso)
    sec = fallback_s if sec is None else sec + extra_s
    return int(min(max(sec, 60.0), 24 * 3600.0) * 1000)
