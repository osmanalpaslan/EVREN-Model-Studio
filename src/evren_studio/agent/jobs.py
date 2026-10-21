"""Uzun işler: dakikalar/saatler süren komutlar (uzun test takımı, derleme) — Qt'siz.

Neden (kullanıcı 2026-10-21: "başka projemde 90 dakikayı aşan testler var"): run_command en çok 30 dk
bekler ve turu kilitler; servisler tur bitince kapanır. EVREN'in 5 dk penceresi bir HIZ sınırıdır,
süre sınırı değil: uzun test koşarken model çağrılmazsa token harcanmaz.

- start_job: komutu proje klasöründe arka planda başlatır; iş TUR BİTİNCE KAPANMAZ (uygulama
  kapanana ya da stop_job'a kadar). Tüm çıktı veri klasöründe günlük dosyasına yazılır.
- wait_job: iş bitene (veya süre dolana / kullanıcı Esc'ye basana) kadar KODLA bekler — bu sürede
  modele istek gitmez, token harcanmaz. Bitince çıkış kodu ve çıktının sonu döner.
- job_status / stop_job: anlık durum (beklemeden) ve durdurma.
"""
from __future__ import annotations

import collections
import itertools
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from .tools import ToolError, _kill_tree, project_env, shell_argv

MAX_RUNNING = 4
MAX_WAIT_MINUTES = 240             # tek wait_job çağrısında en uzun bekleme
TAIL_LINES = 200


@dataclass
class Job:
    id: str
    command: str
    root: str
    proc: subprocess.Popen
    log_path: Path
    started: float = field(default_factory=time.monotonic)
    started_at: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))
    ended: float | None = None
    stopped: bool = False
    notified: bool = False
    tail: collections.deque = field(default_factory=lambda: collections.deque(maxlen=TAIL_LINES))
    lines: int = 0

    @property
    def running(self) -> bool:
        return self.proc.poll() is None

    @property
    def exit_code(self) -> int | None:
        return self.proc.poll()

    def elapsed(self) -> float:
        return (self.ended or time.monotonic()) - self.started

    def state(self) -> str:
        if self.running:
            return "çalışıyor"
        if self.stopped:
            return "durduruldu"
        return "bitti (başarılı)" if self.exit_code == 0 else f"bitti (çıkış kodu {self.exit_code})"

    def summary(self, tail: int = 40) -> str:
        mins = self.elapsed() / 60
        out = "".join(list(self.tail)[-max(1, tail):]).strip() or "(çıktı yok)"
        return (f"İş {self.id} — {self.state()} · {mins:.1f} dk · komut: {self.command}\n"
                f"Tam çıktı: {self.log_path} ({self.lines} satır)\nSon çıktı:\n{out}")


class JobManager:
    """Uygulama boyunca uzun işler (oturumlar arası; tur bitince kapanmaz)."""

    def __init__(self, log_dir: Path):
        self.log_dir = Path(log_dir)
        self.jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    def start(self, root: Path, command: str, name: str = "") -> Job:
        command = (command or "").strip()
        if not command:
            raise ToolError("Komut boş olamaz.")
        with self._lock:
            if sum(1 for j in self.jobs.values() if j.running) >= MAX_RUNNING:
                raise ToolError(f"En fazla {MAX_RUNNING} uzun iş aynı anda çalışabilir; birini bekle veya durdur.")
            job_id = f"{(name or 'is')[:16]}-{next(self._ids)}".replace(" ", "_")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.log_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{job_id}.log"
        try:
            proc = subprocess.Popen(
                shell_argv(command), cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, env={**project_env(Path(root)), "PYTHONUNBUFFERED": "1"},
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as exc:
            raise ToolError(f"İş başlatılamadı: {exc}") from exc
        job = Job(job_id, command, str(root), proc, log_path)
        with self._lock:
            self.jobs[job_id] = job

        def reader() -> None:
            assert proc.stdout is not None
            with open(log_path, "w", encoding="utf-8", errors="replace") as fh:
                fh.write(f"# {command}\n# başlangıç {job.started_at} · klasör {root}\n")
                for raw in iter(proc.stdout.readline, b""):
                    text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
                    job.tail.append(text)
                    job.lines += 1
                    fh.write(text)
                    fh.flush()
            proc.wait()
            job.ended = time.monotonic()

        threading.Thread(target=reader, daemon=True, name=f"is-{job_id}").start()
        return job

    def get(self, job_id: str = "") -> Job:
        with self._lock:
            if job_id:
                job = self.jobs.get(job_id)
            else:
                running = [j for j in self.jobs.values() if j.running]
                job = running[-1] if len(running) == 1 else (list(self.jobs.values())[-1]
                                                             if len(self.jobs) == 1 else None)
                if job is None and self.jobs:
                    raise ToolError("Birden fazla iş var; id ver: " + ", ".join(self.jobs))
        if job is None:
            raise ToolError(f"'{job_id}' adlı iş yok." if job_id else "Uzun iş yok.")
        return job

    def wait(self, job_id: str = "", max_minutes: float = 60, cancel=None,
             progress: Callable[[str], None] | None = None) -> tuple[Job, str]:
        """İş bitene ya da süre dolana kadar bekler (KOD — model çağrısı yok). (iş, neden)."""
        job = self.get(job_id)
        limit = max(0.01, min(float(max_minutes or 60), MAX_WAIT_MINUTES)) * 60
        start = time.monotonic()
        last_report = start
        while job.running:
            if cancel is not None and getattr(cancel, "cancelled", False):
                return job, "kullanıcı beklemeyi durdurdu (iş arka planda sürüyor)"
            if time.monotonic() - start >= limit:
                return job, f"{int(limit // 60)} dk bekleme süresi doldu (iş sürüyor; tekrar wait_job ile bekleyebilirsin)"
            if progress is not None and time.monotonic() - last_report >= 60:
                last_report = time.monotonic()
                last = next((ln.strip() for ln in reversed(list(job.tail)) if ln.strip()), "")
                progress(f"[{job.elapsed() / 60:.0f} dk] {last[:160]}\n")
            time.sleep(0.5)
        # okuyucu son satırları yazsın
        for _ in range(20):
            if job.ended is not None:
                break
            time.sleep(0.1)
        return job, "bitti"

    def stop(self, job_id: str = "") -> Job:
        job = self.get(job_id)
        if job.running:
            job.stopped = True
            _kill_tree(job.proc)
            job.ended = time.monotonic()
        return job

    def finished_unnotified(self) -> list[Job]:
        with self._lock:
            out = [j for j in self.jobs.values() if not j.running and not j.notified]
            for j in out:
                j.notified = True
        return out

    def running(self) -> list[Job]:
        with self._lock:
            return [j for j in self.jobs.values() if j.running]

    def stop_all(self) -> list[str]:
        names = []
        for j in self.running():
            j.stopped = True
            _kill_tree(j.proc)
            names.append(j.id)
        return names
