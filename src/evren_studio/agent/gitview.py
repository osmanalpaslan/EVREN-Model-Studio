"""Git sekmesi için Qt'siz yardımcılar: durum, dosya farkı, commit (madde 1, 2026-10-24).

Yalnız okuma + kullanıcının onayladığı commit. push/reset/checkout YOK (geri döndürülemez işlem kullanıcıya
kalır). Commit kullanıcının kendi git kimliğiyle yapılır; kimlik tanımlı değilse "EVREN Studio" kimliğine düşer.
Arayüz iş parçacığında ÇAĞRILMAZ (R-04).
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

DIFF_LIMIT = 200_000
NEW_FILE_LIMIT = 40_000
STATUS_TEXT = {"M": "değişti", "A": "eklendi", "D": "silindi", "R": "taşındı", "C": "kopyalandı", "U": "çakışma",
               "?": "yeni"}


@dataclass
class Entry:
    path: str
    code: str                     # porcelain XY (ör. " M", "??", "A ")

    @property
    def label(self) -> str:
        c = self.code.strip()[:1] or "M"
        return STATUS_TEXT.get(c, c)

    @property
    def untracked(self) -> bool:
        return self.code == "??"


@dataclass
class Status:
    repo: bool
    branch: str = ""
    ahead: int = 0
    behind: int = 0
    entries: list[Entry] = field(default_factory=list)
    error: str = ""


def _run(root: Path, *args: str, env: dict | None = None, timeout: int = 30) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=root, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           env=env or {**os.environ, "GIT_TERMINAL_PROMPT": "0"},
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode, (r.stdout if r.returncode == 0 else (r.stderr or r.stdout)).rstrip("\n")
    except FileNotFoundError:
        return -1, "git bulunamadı (Git for Windows kurulu değil)"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, type(exc).__name__


def status(root: str | Path) -> Status:
    root = Path(root)
    c, o = _run(root, "status", "--porcelain=v1", "--branch", "--untracked-files=all")
    if c != 0:
        if "not a git repository" in o.lower():
            return Status(False)
        return Status(False, error=o[:300])
    st = Status(True)
    for line in o.splitlines():
        if line.startswith("## "):
            head = line[3:]
            st.branch = head.split("...")[0].replace("No commits yet on ", "")
            if "[" in head:
                info = head[head.index("[") + 1:head.rindex("]")]
                for part in info.split(","):
                    k, _, n = part.strip().partition(" ")
                    if k == "ahead":
                        st.ahead = int(n or 0)
                    elif k == "behind":
                        st.behind = int(n or 0)
            continue
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        st.entries.append(Entry(path.strip('"'), line[:2]))
    return st


def file_diff(root: str | Path, entry: Entry) -> str:
    root = Path(root)
    if entry.untracked:
        try:
            body = (root / entry.path).read_bytes()[:NEW_FILE_LIMIT]
        except OSError as exc:
            return f"(okunamadı: {exc})"
        if b"\0" in body:
            return "(ikili dosya)"
        lines = body.decode("utf-8", errors="replace").splitlines()
        return f"@@ yeni dosya: {entry.path} @@\n" + "\n".join("+" + ln for ln in lines)
    c, o = _run(root, "diff", "HEAD", "--", entry.path)
    if c != 0:                                       # henüz commit yok: aşamalı içerik
        c, o = _run(root, "diff", "--cached", "--", entry.path)
    return o[:DIFF_LIMIT] if o else "(metin farkı yok — izin/ikili değişiklik olabilir)"


def summary_diff(root: str | Path, limit: int = 6000) -> str:
    """Commit mesajı önerisi için kısaltılmış toplam fark."""
    st = status(root)
    parts = ["Değişen dosyalar: " + ", ".join(f"{e.path} ({e.label})" for e in st.entries[:40])]
    for e in st.entries:
        if sum(len(p) for p in parts) > limit:
            break
        parts.append(file_diff(root, e)[:2000])
    return "\n".join(parts)[:limit]


def _has_identity(root: Path) -> bool:
    return _run(root, "config", "user.email")[0] == 0 and _run(root, "config", "user.name")[0] == 0


def commit(root: str | Path, message: str, paths: list[str] | None = None) -> tuple[bool, str]:
    """Seçilen (yoksa tüm) değişiklikleri aşamalar ve commit'ler. Dönüş: (başarılı, kısa kimlik/hata)."""
    root = Path(root)
    message = (message or "").strip()
    if not message:
        return False, "Commit mesajı boş."
    c, o = _run(root, "add", "-A", "--", *(paths or ["."]))
    if c != 0:
        return False, o[:300]
    env = None
    if not _has_identity(root):
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_AUTHOR_NAME": "EVREN Studio",
               "GIT_AUTHOR_EMAIL": "evren-studio@localhost", "GIT_COMMITTER_NAME": "EVREN Studio",
               "GIT_COMMITTER_EMAIL": "evren-studio@localhost"}
    c, o = _run(root, "commit", "-q", "-m", message, env=env, timeout=120)
    if c != 0:
        return False, o[:400] or "commit başarısız"
    return True, _run(root, "rev-parse", "--short", "HEAD")[1]


def init(root: str | Path) -> tuple[bool, str]:
    c, o = _run(Path(root), "init", "-q")
    return c == 0, o
