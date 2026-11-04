"""Zamanlanmış görevler: zaman hesabı (Qt'siz, test edilebilir).

Claude Code masaüstündeki yerel "Scheduled tasks" yapısı örnek alındı (kullanıcı isteği 2026-11-04, Madde 12c;
başvuru: code.claude.com/docs/en/desktop-scheduled-tasks):
- Sıklık: Saatlik · Günlük (saat) · Hafta içi (saat) · Haftalık (gün + saat) · Elle (yalnız "Şimdi çalıştır") ·
  Özel (cron, yerel saat; saatte birden sık olamaz). Cron'da gün ve ay SAYI ile yazılır, Pazar 0'dır (7 değil).
- Uygulama açıkken dakikada bir denetlenir. Uygulama kapalıyken / bilgisayar uyurken kaçırılan çalıştırmalardan
  son 7 gün içindeki EN YENİSİ için tek bir telafi çalıştırması yapılır; daha eskiler atlanmış sayılır.
Zamanlar: görev saati yerel duvar saatidir; kayıtlarda zaman damgası UTC ISO (db.utcnow_iso) tutulur.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

KINDS = ("hourly", "daily", "weekdays", "weekly", "manual", "custom")
KIND_LABELS = {
    "hourly": "Saatlik",
    "daily": "Günlük",
    "weekdays": "Hafta içi",
    "weekly": "Haftalık",
    "manual": "Elle",
    "custom": "Özel (cron)",
}
WEEKDAYS_TR = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")   # Python: Pzt=0
CATCH_UP_DAYS = 7
DEFAULT_TIME = "09:00"


# ---- cron (5 alan: dakika saat ayın-günü ay haftanın-günü) ---------------------------------------

_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
_NAMES = ("dakika", "saat", "ayın günü", "ay", "haftanın günü")


class CronError(ValueError):
    pass


def _field(text: str, lo: int, hi: int, name: str) -> frozenset[int]:
    out: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            raise CronError(f"{name}: boş değer")
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            if not s.isdigit() or int(s) < 1:
                raise CronError(f"{name}: adım geçersiz ({s})")
            step = int(s)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            x, y = part.split("-", 1)
            if not (x.isdigit() and y.isdigit()):
                raise CronError(f"{name}: aralık sayı olmalı ({part}); gün/ay adları kabul edilmez")
            a, b = int(x), int(y)
        elif part.isdigit():
            a = b = int(part)
            if step != 1:
                b = hi
        else:
            raise CronError(f"{name}: '{part}' anlaşılmadı; gün ve ay adları değil sayılar kullanılır")
        if a < lo or b > hi or a > b:
            hint = " (Pazar 0'dır, 7 değil)" if name == "haftanın günü" and b == 7 else ""
            raise CronError(f"{name}: {lo}-{hi} aralığı dışında{hint}")
        out.update(range(a, b + 1, step))
    return frozenset(out)


@dataclass(frozen=True)
class Cron:
    minutes: frozenset[int]
    hours: frozenset[int]
    days: frozenset[int]
    months: frozenset[int]
    weekdays: frozenset[int]          # 0 = Pazar (cron)
    dom_any: bool
    dow_any: bool

    def matches(self, dt: datetime) -> bool:
        if dt.minute not in self.minutes or dt.hour not in self.hours or dt.month not in self.months:
            return False
        dow = (dt.weekday() + 1) % 7      # Python Pzt=0 → cron Pzt=1, Paz=0
        dom_ok, dow_ok = dt.day in self.days, dow in self.weekdays
        if self.dom_any or self.dow_any:  # biri '*' ise diğeri belirler
            return dom_ok and dow_ok
        return dom_ok or dow_ok           # ikisi de kısıtlıysa standart cron: VEYA


def parse_cron(expr: str) -> Cron:
    parts = (expr or "").split()
    if len(parts) != 5:
        raise CronError("5 alan gerekir: dakika saat ayın-günü ay haftanın-günü (ör. 0 9 * * 1-5)")
    vals = [_field(p, lo, hi, n) for p, (lo, hi), n in zip(parts, _RANGES, _NAMES)]
    return Cron(*vals, dom_any=parts[2] == "*", dow_any=parts[4] == "*")


def validate_cron(expr: str) -> str:
    """Hata metni ("" → geçerli). Saatte birden sık çalışan ifade reddedilir (Claude Code formu gibi)."""
    try:
        c = parse_cron(expr)
    except CronError as exc:
        return str(exc)
    if len(c.minutes) != 1:
        return "Saatte birden sık çalışamaz: dakika alanı tek bir sayı olmalı (ör. 0 veya 30)"
    if next_cron(c, datetime(2026, 1, 1), limit_days=366 * 5) is None:
        return "Bu ifade hiçbir zaman çalışmaz (ör. 31 Şubat)"
    return ""


def next_cron(c: Cron, after: datetime, limit_days: int = 400) -> datetime | None:
    """`after`dan SONRAKİ ilk eşleşen dakika (saniyesiz)."""
    t = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    end = t + timedelta(days=limit_days)
    minute = min(c.minutes)
    while t <= end:
        if t.month not in c.months:
            t = (t.replace(day=1, hour=0, minute=0) + timedelta(days=32)).replace(day=1)
            continue
        dow = (t.weekday() + 1) % 7
        day_ok = (t.day in c.days and dow in c.weekdays) if (c.dom_any or c.dow_any) else \
            (t.day in c.days or dow in c.weekdays)
        if not day_ok:
            t = t.replace(hour=0, minute=0) + timedelta(days=1)
            continue
        if t.hour not in c.hours:
            t = t.replace(minute=0) + timedelta(hours=1)
            continue
        cand = t.replace(minute=minute)
        if cand >= t and c.matches(cand):
            return cand
        t = t.replace(minute=0) + timedelta(hours=1)
    return None


# ---- görev zamanlaması -----------------------------------------------------------------------------

@dataclass
class Spec:
    kind: str = "daily"
    time_hm: str = DEFAULT_TIME       # "SS:DD" (günlük/hafta içi/haftalık; saatlik için yalnız dakika)
    weekday: int = 0                  # Python: Pazartesi=0 (haftalık)
    cron: str = ""

    @classmethod
    def from_row(cls, row) -> "Spec":
        g = (lambda k, d=None: row[k] if k in row.keys() else d) if hasattr(row, "keys") else \
            (lambda k, d=None: row.get(k, d))
        return cls(kind=g("kind") or "daily", time_hm=g("time_hm") or DEFAULT_TIME,
                   weekday=int(g("weekday") or 0), cron=g("cron") or "")

    def hm(self) -> tuple[int, int]:
        try:
            h, m = (int(x) for x in (self.time_hm or DEFAULT_TIME).split(":", 1))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return h, m
        except ValueError:
            pass
        return 9, 0

    def validate(self) -> str:
        if self.kind not in KINDS:
            return f"Bilinmeyen sıklık: {self.kind}"
        if self.kind == "custom":
            return validate_cron(self.cron)
        if self.kind in ("daily", "weekdays", "weekly", "hourly"):
            try:
                h, m = (int(x) for x in (self.time_hm or "").split(":", 1))
            except ValueError:
                return "Saat SS:DD biçiminde olmalı (ör. 09:00)"
            if not (0 <= h <= 23 and 0 <= m <= 59):
                return "Saat 00:00 ile 23:59 arasında olmalı"
        if self.kind == "weekly" and not 0 <= self.weekday <= 6:
            return "Haftanın günü seçilmeli"
        return ""

    def describe(self) -> str:
        h, m = self.hm()
        hm = f"{h:02d}:{m:02d}"
        if self.kind == "hourly":
            return f"Her saat :{m:02d}'de"
        if self.kind == "daily":
            return f"Her gün {hm}"
        if self.kind == "weekdays":
            return f"Hafta içi her gün {hm}"
        if self.kind == "weekly":
            return f"Her {WEEKDAYS_TR[self.weekday % 7]} {hm}"
        if self.kind == "manual":
            return "Elle (yalnız “Şimdi çalıştır”)"
        return f"Özel: {self.cron}"

    def next_after(self, after: datetime) -> datetime | None:
        """`after`dan sonraki ilk çalıştırma zamanı (yerel, saniyesiz); elle → None."""
        if self.kind == "manual":
            return None
        if self.kind == "custom":
            try:
                return next_cron(parse_cron(self.cron), after)
            except CronError:
                return None
        h, m = self.hm()
        base = after.replace(second=0, microsecond=0)
        if self.kind == "hourly":
            cand = base.replace(minute=m)
            return cand if cand > after else cand + timedelta(hours=1)
        cand = base.replace(hour=h, minute=m)
        if cand <= after:
            cand += timedelta(days=1)
        for _ in range(8):
            if self.kind == "daily":
                return cand
            if self.kind == "weekdays" and cand.weekday() < 5:
                return cand
            if self.kind == "weekly" and cand.weekday() == self.weekday % 7:
                return cand
            cand += timedelta(days=1)
        return None

    def occurrences(self, start: datetime, end: datetime, limit: int = 10_000) -> list[datetime]:
        """(start, end] aralığındaki çalıştırma zamanları."""
        out: list[datetime] = []
        t = start
        while len(out) < limit:
            n = self.next_after(t)
            if n is None or n > end:
                break
            out.append(n)
            t = n
        return out


@dataclass
class Due:
    """Bir denetimde görev için karar: çalıştırılacak zaman (yoksa None) ve atlanan eski zamanlar."""
    run_for: datetime | None
    skipped: list[datetime]
    catch_up: bool                     # zamanından belirgin geç (uygulama kapalıydı / uyuyordu)


LATE_TOLERANCE = timedelta(minutes=3)


def due(spec: Spec, last_handled: datetime | None, created: datetime, now: datetime) -> Due:
    """Son ele alınan zamandan bu yana gelen çalıştırmalar → en yenisi çalışır, eskiler atlanır.
    7 günden eski kaçırılanlar hiç sayılmaz (Claude Code ile aynı)."""
    since = max(last_handled or created, created, now - timedelta(days=CATCH_UP_DAYS))
    occ = spec.occurrences(since, now)
    if not occ:
        return Due(None, [], False)
    latest = occ[-1]
    return Due(latest, occ[:-1], now - latest > LATE_TOLERANCE)


def to_local(iso: str | None) -> datetime | None:
    """UTC ISO kaydı → yerel saat (tz'siz, görev saatleriyle karşılaştırmak için)."""
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def to_utc_iso(local: datetime) -> str:
    """Yerel (tz'siz) zaman → UTC ISO (kayıt için)."""
    from datetime import timezone

    return local.astimezone(timezone.utc).isoformat(timespec="seconds")


def slug(name: str) -> str:
    """Görev adı → küçük harfli, tireli kimlik (Claude Code adı kebab-case yapar; ad benzersiz olmalı)."""
    import re

    t = (name or "").replace("İ", "i").replace("I", "ı").lower()
    t = t.translate(str.maketrans("çğıöşüâîû", "cgiosuaiu"))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")
