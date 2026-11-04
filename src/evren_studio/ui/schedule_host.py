"""Zamanlanmış görevleri çalıştıran motor (Madde 12c, 2026-11-05).

- Uygulama açıkken dakikada bir denetler (Claude Code yerel görevleri gibi); açılışta kaçırılanlar için son 7 günde
  tek telafi çalıştırması (agent/schedule.due).
- Aynı anda tek çalıştırma; sıradakiler kuyrukta bekler. Aynı görevin önceki çalıştırması sürerken gelen zaman
  "atlandı" diye geçmişe yazılır (Claude Code'daki gibi nedeni görünür).
- Her çalıştırma GÖRÜNMEZ ayrı bir oturum görünümünde (SessionView.unattended) koşar: kullanıcının açık oturumu
  bölünmez; oturum kenar çubuğunda "Zamanlanmış" alt yazısıyla görünür, Geçmiş'ten açılabilir.
- Biten görünüm hemen silinmez (arka plandaki başlık/kapsam işleri ona döner): 5 dk sonra silinir.
"""
from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

from ..agent import schedule as sched
from ..db import utcnow_iso

TICK_MS = 60_000
POLL_MS = 1_000
IDLE_DONE_TICKS = 3                       # tur bitti + 3 sn yeni tur başlamadı (otomatik devam zinciri) → bitti
DISPOSE_MS = 5 * 60_000

STATUS_LABELS = {
    "sirada": "Sırada",
    "calisiyor": "Çalışıyor",
    "kota_bekliyor": "Kota bekleniyor",
    "tamamlandi": "Tamamlandı",
    "yarim": "Yarım kaldı",
    "hata": "Hata",
    "durduruldu": "Durduruldu",
    "atlandi": "Atlandı",
}
STOP_TO_STATUS = {
    "done": ("tamamlandi", ""),
    "cancelled": ("durduruldu", "durduruldu"),
    "loop": ("yarim", "ajan aynı işi tekrarladığı için durdu (döngü)"),
    "max_steps": ("yarim", "tur adım sınırına ulaşıldı"),
    "context_limit": ("yarim", "bağlam sınırı: otomatik özetle devam hakkı bitti"),
    "budget": ("yarim", "aylık bütçe doldu"),
    "error": ("hata", ""),
}


class ScheduleHost(QObject):
    changed = Signal()                    # görev/çalıştırma listesi değişti (sayfa yenilensin)
    sessions_changed = Signal()           # yeni oturum açıldı (kenar çubuğu yenilensin)
    notify = Signal(str, str)             # (başlık, metin) → Windows bildirimi

    def __init__(self, ctx, parent=None, *, view_factory=None, now=None):
        super().__init__(parent)
        self.ctx = ctx
        self._now = now or datetime.now               # testler sahte saat verir (yerel, tz'siz)
        self._view_factory = view_factory or self._make_view
        self.queue: list[int] = []                    # run_id
        self.active: dict | None = None               # {run_id, task_id, view, panel, t0, idle}
        self._parked: list = []                       # silinmeyi bekleyen görünümler
        self.timer = QTimer(self)
        self.timer.setInterval(TICK_MS)
        self.timer.timeout.connect(self.tick)
        self.poll = QTimer(self)
        self.poll.setInterval(POLL_MS)
        self.poll.timeout.connect(self._poll)
        self._awake = False

    # ---- yaşam döngüsü ----

    def start(self) -> None:
        self.timer.start()
        QTimer.singleShot(3000, self, self.tick)       # açılış: kaçırılanlar için telafi denetimi
        self.apply_keep_awake()

    def shutdown(self) -> None:
        self.timer.stop()
        self.poll.stop()
        if self.active is not None:
            try:
                self.active["view"].stop()
            except Exception:
                pass
            self.ctx.db.update_scheduled_run(self.active["run_id"], status="durduruldu",
                                             reason="uygulama kapatıldı", finished_at=utcnow_iso())
            self.active = None
        for rid in self.queue:
            self.ctx.db.update_scheduled_run(rid, status="atlandi", reason="uygulama kapatıldı")
        self.queue.clear()
        self._set_awake(False)

    # ---- zamanlama ----

    def tick(self) -> None:
        """Dakikalık denetim: zamanı gelen (veya kaçırılan) görevleri sıraya koyar."""
        if not self.ctx.settings.schedule_enabled:
            return
        now = self._now()
        for row in self.ctx.db.list_scheduled_tasks():
            if not row["enabled"]:
                continue
            spec = sched.Spec.from_row(row)
            created = sched.to_local(row["created_at"]) or now
            d = sched.due(spec, sched.to_local(row["last_handled_at"]), created, now)
            if d.run_for is None:
                continue
            self.ctx.db.update_scheduled_task(row["id"], last_handled_at=sched.to_utc_iso(d.run_for))
            if d.skipped:
                self.ctx.db.add_scheduled_run(
                    row["id"], "atlandi", scheduled_for=sched.to_utc_iso(d.skipped[-1]),
                    reason=(f"{len(d.skipped)} çalıştırma kaçırıldı (uygulama kapalıydı veya bilgisayar uyuyordu); "
                            "yalnız en yenisi telafi edildi"))
            self.enqueue(row["id"], scheduled_for=d.run_for, catch_up=d.catch_up)
        self.changed.emit()

    def enqueue(self, task_id: int, *, scheduled_for: datetime | None = None, catch_up: bool = False,
                manual: bool = False) -> int | None:
        row = self.ctx.db.get_scheduled_task(task_id)
        if row is None:
            return None
        sf = sched.to_utc_iso(scheduled_for) if scheduled_for else None
        if self.is_busy(task_id):
            self.ctx.db.add_scheduled_run(task_id, "atlandi", scheduled_for=sf, manual=manual,
                                          reason="önceki çalıştırma hâlâ sürüyordu")
            self.changed.emit()
            return None
        rid = self.ctx.db.add_scheduled_run(task_id, "sirada", scheduled_for=sf, catch_up=catch_up, manual=manual)
        self.queue.append(rid)
        if catch_up and self.ctx.settings.schedule_notify:
            self.notify.emit("Zamanlanmış görev — kaçırılan çalıştırma",
                             f"“{row['name']}” kaçırılan zamanı için şimdi çalıştırılıyor.")
        self.changed.emit()
        QTimer.singleShot(0, self, self._pump)
        return rid

    def run_now(self, task_id: int) -> int | None:
        return self.enqueue(task_id, manual=True)

    def is_busy(self, task_id: int) -> bool:
        if self.active is not None and self.active["task_id"] == task_id:
            return True
        return any(self._task_of(rid) == task_id for rid in self.queue)

    def running_task(self) -> int | None:
        return self.active["task_id"] if self.active is not None else None

    def stop_task(self, task_id: int) -> None:
        """Görevin çalışan veya sıradaki çalıştırmasını durdurur."""
        for rid in [r for r in self.queue if self._task_of(r) == task_id]:
            self.queue.remove(rid)
            self.ctx.db.update_scheduled_run(rid, status="durduruldu", reason="kullanıcı durdurdu")
        if self.active is not None and self.active["task_id"] == task_id:
            self.active["stop_reason"] = "kullanıcı durdurdu"
            self.active["view"].stop()
        self.changed.emit()

    def next_run(self, row) -> datetime | None:
        if not row["enabled"] or not self.ctx.settings.schedule_enabled:
            return None
        return sched.Spec.from_row(row).next_after(self._now())

    def _task_of(self, run_id: int) -> int | None:
        r = self.ctx.db._exec("SELECT task_id FROM scheduled_runs WHERE id=?", (run_id,)).fetchone()
        return int(r["task_id"]) if r else None

    # ---- çalıştırma ----

    def _make_view(self):
        from .session_view import SessionView
        from .side_panel import SidePanel

        panel = SidePanel(self.ctx)
        view = SessionView(self.ctx, panel)
        view.unattended = True
        view.hide()
        panel.hide()
        return view, panel

    def _pump(self) -> None:
        if self.active is not None or not self.queue:
            return
        rid = self.queue.pop(0)
        tid = self._task_of(rid)
        row = self.ctx.db.get_scheduled_task(tid) if tid is not None else None
        if row is None:
            self.ctx.db.update_scheduled_run(rid, status="atlandi", reason="görev silindi")
            QTimer.singleShot(0, self, self._pump)
            return
        view, panel = self._view_factory()
        view.sessions_changed.connect(self.sessions_changed.emit)
        title = f"{row['name']} · {self._now().strftime('%d.%m %H:%M')}"
        prompt = row["prompt"]                       # açıklama yalnız listede görünür; modele talimat gider
        self.ctx.db.update_scheduled_run(rid, status="calisiyor", started_at=utcnow_iso())
        sid = view.start_unattended(workspace=row["workspace"] or None, model=row["model"], mode=row["mode"],
                                    title=title, prompt=prompt, task_id=row["id"])
        if sid is None:
            self.ctx.db.update_scheduled_run(rid, status="hata", reason=view.last_error or "başlatılamadı",
                                             finished_at=utcnow_iso())
            self._dispose(view, panel)
            self._report(row["name"], "hata", view.last_error)
            self.changed.emit()
            QTimer.singleShot(0, self, self._pump)
            return
        self.ctx.db.update_scheduled_run(rid, session_id=sid)
        self.active = {"run_id": rid, "task_id": row["id"], "name": row["name"], "view": view, "panel": panel,
                       "t0": time.monotonic(), "idle": 0, "sid": sid, "stop_reason": ""}
        self.sessions_changed.emit()
        self.changed.emit()
        self.poll.start()
        self.apply_keep_awake()

    def _poll(self) -> None:
        a = self.active
        if a is None:
            self.poll.stop()
            return
        view = a["view"]
        limit = max(5, int(self.ctx.settings.schedule_max_minutes or 120)) * 60
        if view.running:
            a["idle"] = 0
            if time.monotonic() - a["t0"] > limit and not a["stop_reason"]:
                a["stop_reason"] = f"süre sınırı ({limit // 60} dk) aşıldı"
                view.stop()
            return
        plan = None
        try:
            plan = view._pending_plan()
        except Exception:
            pass
        if plan is not None and getattr(plan, "session_id", None) == a["sid"]:
            # kota doldu: iş güvenli noktada durdu, kota yenilenince kendiliğinden sürecek
            self.ctx.db.update_scheduled_run(a["run_id"], status="kota_bekliyor",
                                             reason="EVREN kotası doldu; yenilenince kaldığı yerden sürecek")
            a["idle"] = 0
            self.changed.emit()
            return
        a["idle"] += 1
        if a["idle"] >= IDLE_DONE_TICKS:
            self._finish()

    def _finish(self) -> None:
        a, self.active = self.active, None
        self.poll.stop()
        view = a["view"]
        status, reason = STOP_TO_STATUS.get(view.last_stop or "error", ("hata", ""))
        if a["stop_reason"]:
            status, reason = "durduruldu", a["stop_reason"]
        if status == "hata":
            reason = view.last_error or reason or "bilinmeyen hata"
        elif status == "yarim" and view.last_error:
            reason = f"{reason}; {view.last_error}"
        self.ctx.db.update_scheduled_run(a["run_id"], status=status, reason=reason, finished_at=utcnow_iso())
        self._report(a["name"], status, reason)
        self._dispose(view, a["panel"])
        self.changed.emit()
        self.sessions_changed.emit()
        self.apply_keep_awake()
        QTimer.singleShot(0, self, self._pump)

    def _report(self, name: str, status: str, reason: str) -> None:
        if not self.ctx.settings.schedule_notify:
            return
        text = f"“{name}”: {STATUS_LABELS.get(status, status)}" + (f" — {reason}" if reason else "")
        self.notify.emit("Zamanlanmış görev", text[:220])

    def _dispose(self, view, panel) -> None:
        self._parked.append((view, panel))

        def drop():
            if (view, panel) in self._parked:
                self._parked.remove((view, panel))
            for w in (view, panel):
                try:
                    w.deleteLater()
                except RuntimeError:
                    pass
        QTimer.singleShot(DISPOSE_MS, self, drop)

    # ---- bilgisayarı uyanık tut (Claude Code "Keep computer awake") ----

    def apply_keep_awake(self) -> None:
        s = self.ctx.settings
        want = bool(s.schedule_keep_awake and s.schedule_enabled and (
            self.active is not None or any(r["enabled"] and r["kind"] != "manual"
                                           for r in self.ctx.db.list_scheduled_tasks())))
        self._set_awake(want)

    def _set_awake(self, on: bool) -> None:
        if on == self._awake:
            return
        self._awake = on
        try:
            import ctypes

            es_continuous, es_system_required = 0x80000000, 0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(
                es_continuous | (es_system_required if on else 0))
        except (AttributeError, OSError):
            pass                                  # Windows dışı / erişim yok: sessizce geç

    @property
    def keeping_awake(self) -> bool:
        return self._awake
