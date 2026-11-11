"""Gerçek (etkileşimli) terminal çekirdeği — Madde 20 C4 (2026-11-12; Qt'siz).

Neden: Terminal sekmesi her komutu ayrı süreçte çalıştırıyordu: `cd` kalmıyor, değişkenler kayboluyor, soru soran
komutlara (Read-Host, "Devam? [E/H]", npm init, git'in düzenleyicisi) yanıt verilemiyordu. Burada proje klasöründe
SÜREKLİ bir PowerShell, Windows sözde terminali (ConPTY, pywinpty — MIT) içinde çalışır; çıktı bir ekran
öykünücüsüne (pyte — LGPL-3.0, değiştirilebilir ayrı paket) beslenir, arayüz ekranı çizer ve tuşları gönderir.
Ajanın komutları bu kabukta ÇALIŞMAZ (ajan kendi yalıtılmış komutlarını kullanmaya devam eder); bu kabuk yalnız kullanıcı
içindir. Projenin sanal ortamı (varsa) PATH'in başına eklenir (ajanla aynı ortam: tools.project_env).
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable

HISTORY = 3000

# Uygulama nasıl kapanırsa kapansın (pencere, çökme dışı çıkış) açık kabuk süreçleri arkada KALMASIN
import atexit  # noqa: E402
import weakref  # noqa: E402

_LIVE: "weakref.WeakSet[PtyShell]" = weakref.WeakSet()


def close_all() -> None:
    for sh in list(_LIVE):
        sh.close()


atexit.register(close_all)

# Qt tuşu adı → terminal dizisi (Windows Terminal / xterm ile aynı)
KEYS = {
    "Return": "\r", "Enter": "\r", "Backspace": "\x7f", "Tab": "\t", "Escape": "\x1b",
    "Up": "\x1b[A", "Down": "\x1b[B", "Right": "\x1b[C", "Left": "\x1b[D",
    "Home": "\x1b[H", "End": "\x1b[F", "Delete": "\x1b[3~", "Insert": "\x1b[2~",
    "PageUp": "\x1b[5~", "PageDown": "\x1b[6~",
}


def ctrl_key(ch: str) -> str:
    """Ctrl+harf → denetim karakteri (Ctrl+C = \\x03)."""
    c = (ch or "").upper()
    if len(c) == 1 and "@" <= c <= "_":
        return chr(ord(c) - 64)
    return ""


def _backends() -> list[tuple[str, object]]:
    try:
        from winpty import Backend

        return [("WinPTY", Backend.WinPTY), ("ConPTY", Backend.ConPTY)]
    except Exception:                                      # eski pywinpty: arka uç seçimi yok
        return [("varsayılan", None)]


def available() -> bool:
    try:
        import pyte  # noqa: F401
        import winpty  # noqa: F401
    except Exception:
        return False
    return os.name == "nt"


class PtyShell:
    def __init__(self, root: str | Path, cols: int = 120, rows: int = 32,
                 on_output: Callable[[], None] | None = None, argv: list[str] | None = None):
        self.root = str(root)
        self.cols, self.rows = max(20, int(cols)), max(5, int(rows))
        self.on_output = on_output or (lambda: None)
        self.argv = argv or ["powershell.exe", "-NoLogo"]
        self._proc = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        import pyte

        self.screen = pyte.HistoryScreen(self.cols, self.rows, history=HISTORY)
        self.stream = pyte.Stream(self.screen)
        self.exit_note = ""
        self.backend = ""

    # -- yaşam döngüsü --
    def start(self) -> None:
        from winpty import PtyProcess

        from .tools import project_env

        env = project_env(Path(self.root))
        env.pop("PYTHONIOENCODING", None)
        # Ölçüldü (2026-11-12): pywinpty'nin varsayılan ConPTY arka ucunda yazılan Ctrl+C (\x03) uzun komutu KESMİYOR
        # (ping sürdü, sonraki komut kuyrukta kaldı); WinPTY arka ucunda kesiyor → önce WinPTY, açılamazsa ConPTY.
        last: Exception | None = None
        for name, backend in _backends():
            try:
                self._proc = PtyProcess.spawn(self.argv, cwd=self.root, env=env, dimensions=(self.rows, self.cols),
                                              backend=backend)
                self.backend = name
                break
            except Exception as exc:                       # noqa: BLE001 — sıradaki arka uç denenir
                last = exc
        if self._proc is None:
            raise last or RuntimeError("kabuk başlatılamadı")
        _LIVE.add(self)
        self._thread = threading.Thread(target=self._reader, name="pty-okuyucu", daemon=True)
        self._thread.start()

    def _reader(self) -> None:
        proc = self._proc
        while not self._stop.is_set():
            try:
                data = proc.read(4096)
            except EOFError:
                break
            except Exception:
                if not proc.isalive():
                    break
                continue
            if data:
                with self._lock:
                    try:
                        self.stream.feed(data)
                    except Exception:            # öykünücüde beklenmeyen dizi ekranı bozmasın
                        pass
                self.on_output()
        self.exit_note = "[kabuk kapandı]"
        self.on_output()

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.isalive()

    def write(self, text: str) -> None:
        if self.alive and text:
            self._proc.write(text)

    def resize(self, cols: int, rows: int) -> None:
        cols, rows = max(20, int(cols)), max(5, int(rows))
        if (cols, rows) == (self.cols, self.rows):
            return
        self.cols, self.rows = cols, rows
        with self._lock:
            self.screen.resize(rows, cols)
        if self.alive:
            try:
                self._proc.setwinsize(rows, cols)
            except Exception:
                pass

    def close(self) -> None:
        self._stop.set()
        proc, self._proc = self._proc, None
        if proc is not None:
            try:
                if proc.isalive():
                    proc.terminate(force=True)
            except Exception:
                pass
            try:
                proc.close()
            except Exception:
                pass

    # -- ekran --
    def _line(self, row) -> str:
        return "".join(row[x].data for x in range(self.cols)).rstrip()

    def lines(self) -> list[str]:
        """Geçmiş + görünen ekran (sondaki boş satırlar atılır)."""
        with self._lock:
            hist = [self._line(r) for r in self.screen.history.top]
            disp = [ln.rstrip() for ln in self.screen.display]
        out = hist + disp
        while out and not out[-1]:
            out.pop()
        if self.exit_note:
            out.append(self.exit_note)
        return out

    def cursor(self) -> tuple[int, int]:
        """(geçmiş dahil satır, sütun)."""
        with self._lock:
            return len(self.screen.history.top) + self.screen.cursor.y, self.screen.cursor.x

    def text(self) -> str:
        return "\n".join(self.lines())
