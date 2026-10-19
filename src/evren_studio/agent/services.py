"""Arka plan servisleri: ajanın `npm run dev`, `flask run` gibi SÜREKLİ çalışan komutları
başlatıp (start_service) çıktısını okuması (service_logs) ve kapatması (stop_service). Qt'siz.

Neden (2026-10-19, QA hedefi): run_command sonsuza dek çalışan komutu bekleyip zaman aşımına
düşer; ajan gerçek web uygulamasını ayağa kaldırıp tarayıcıda (Playwright) test edemiyordu.

- Komut proje klasöründe, run_command ile AYNI kabuk ve ortamla çalışır (projenin venv'i dahil).
- Port verilirse 127.0.0.1:port açılana kadar beklenir; verilmezse `ready_text` veya kısa süre.
- Çıktı son ~400 satırlık halkada tutulur. Servisler oturuma aittir: arayüz normal tur
  bitince (QA/proje çalışması hariç) ve uygulama kapanınca hepsini kapatır.
"""
from __future__ import annotations

import collections
import re
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .tools import ToolError, _kill_tree, project_env, shell_argv

MAX_SERVICES = 3
LOG_LINES = 400
_PORT_RE = re.compile(r"(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1?\]):(\d{2,5})")


@dataclass
class Service:
    name: str
    command: str
    proc: subprocess.Popen
    port: int | None = None
    started: float = field(default_factory=time.monotonic)
    log: collections.deque = field(default_factory=lambda: collections.deque(maxlen=LOG_LINES))

    @property
    def alive(self) -> bool:
        return self.proc.poll() is None

    def tail(self, n: int = 40) -> str:
        lines = list(self.log)[-max(1, n):]
        return "".join(lines).strip() or "(henüz çıktı yok)"


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class ServiceManager:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.services: dict[str, Service] = {}
        self._lock = threading.Lock()

    def start(self, command: str, name: str = "", port: int | None = None, ready_text: str = "",
              wait_seconds: float = 60.0, cancel=None) -> str:
        command = (command or "").strip()
        if not command:
            raise ToolError("Komut boş olamaz.")
        name = re.sub(r"[^A-Za-z0-9_-]+", "_", name or command.split()[0])[:24] or "servis"
        with self._lock:
            old = self.services.get(name)
            if old is not None and old.alive:
                raise ToolError(f"'{name}' adlı servis zaten çalışıyor; önce stop_service ile kapat "
                                "veya service_logs ile çıktısına bak.")
            if sum(1 for s in self.services.values() if s.alive) >= MAX_SERVICES:
                raise ToolError(f"En fazla {MAX_SERVICES} servis aynı anda çalışabilir; birini kapat.")
        if port and port_open(port):
            raise ToolError(f"Port {port} zaten kullanımda: başka bir program dinliyor. Farklı port seç "
                            "veya o servisi kapat.")
        try:
            proc = subprocess.Popen(
                shell_argv(command), cwd=str(self.root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                # Python sunucuları (http.server, flask, django) boruya tamponlu yazar: çıktı/port
                # satırı geç gelir; günlük canlı okunsun
                env={**project_env(self.root), "PYTHONUNBUFFERED": "1"},
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as exc:
            raise ToolError(f"Servis başlatılamadı: {exc}") from exc
        svc = Service(name, command, proc, port)
        with self._lock:
            self.services[name] = svc

        def reader() -> None:
            assert proc.stdout is not None
            for raw in iter(proc.stdout.readline, b""):
                svc.log.append(raw.decode("utf-8", errors="replace").replace("\r\n", "\n"))

        threading.Thread(target=reader, daemon=True, name=f"servis-{name}").start()
        deadline = time.monotonic() + max(2.0, min(float(wait_seconds or 60), 300.0))
        ready = False
        while time.monotonic() < deadline:
            if cancel is not None and getattr(cancel, "cancelled", False):
                break
            if not svc.alive:
                break
            text = "".join(svc.log)
            if svc.port is None:
                m = _PORT_RE.search(text)
                if m:
                    svc.port = int(m.group(1))
            if svc.port and port_open(svc.port):
                ready = True
                break
            if ready_text and ready_text.lower() in text.lower():
                ready = True
                break
            if not port and not ready_text and time.monotonic() - svc.started > 5:
                ready = True                      # ne port ne işaret: kısa süre ayakta kaldıysa yeter
                break
            time.sleep(0.25)
        if not svc.alive:
            return (f"Servis '{name}' başladıktan hemen sonra kapandı (çıkış kodu {svc.proc.returncode}).\n"
                    f"Son çıktı:\n{svc.tail(30)}")
        url = f"http://127.0.0.1:{svc.port}/" if svc.port else ""
        head = (f"Servis '{name}' çalışıyor" + (f" · {url}" if url else "")
                if ready else f"Servis '{name}' başlatıldı ama {int(wait_seconds)} sn içinde hazır olmadı "
                              "(port açılmadı); service_logs ile çıktıya bak")
        return f"{head}.\nSon çıktı:\n{svc.tail(15)}"

    def logs(self, name: str = "", lines: int = 60) -> str:
        svc = self._get(name)
        state = "çalışıyor" if svc.alive else f"kapandı (çıkış kodu {svc.proc.returncode})"
        return f"Servis '{svc.name}' {state}" + (f" · port {svc.port}" if svc.port else "") + \
            f"\n{svc.tail(max(5, min(int(lines or 60), LOG_LINES)))}"

    def stop(self, name: str = "") -> str:
        svc = self._get(name)
        if svc.alive:
            _kill_tree(svc.proc)
        with self._lock:
            self.services.pop(svc.name, None)
        return f"Servis '{svc.name}' kapatıldı."

    def _get(self, name: str) -> Service:
        with self._lock:
            if name:
                svc = self.services.get(name)
            else:
                alive = [s for s in self.services.values()]
                svc = alive[-1] if len(alive) == 1 else None
                if svc is None and alive:
                    raise ToolError("Birden fazla servis var; name ver: " + ", ".join(self.services))
        if svc is None:
            raise ToolError(f"'{name}' adlı servis yok." if name else "Çalışan servis yok.")
        return svc

    def running(self) -> list[str]:
        with self._lock:
            return [n for n, s in self.services.items() if s.alive]

    def stop_all(self) -> list[str]:
        with self._lock:
            items = list(self.services.values())
            self.services.clear()
        for s in items:
            if s.alive:
                _kill_tree(s.proc)
        return [s.name for s in items]
