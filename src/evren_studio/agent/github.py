"""GitHub bağlantısı ve depo işlemleri (Madde 12d, 2026-11-05) — Qt'siz.

Ücretsiz ve tarayıcı yönlendirmeli: GitHub'ın resmî komut satırı aracı `gh` kullanılır (`gh auth login --web`).
gh, tek kullanımlık bir cihaz kodu yazar ve https://github.com/login/device adresinde onay bekler; kullanıcı
tarayıcıda kodu girip "Authorize" deyince giriş tamamlanır. Belirteç (token) gh tarafından Windows Credential
Manager'da saklanır; uygulama belirteci hiç görmez ve dosyaya yazmaz. `gh auth setup-git` ile git de bu girişi
kullanır (push/pull için ayrıca parola sorulmaz).
Gerçek ölçüm 2026-11-05: etkileşimsiz çalıştırmada (stdin kapalı) gh kodu ve adresi yazıp onayı bekliyor.

Testler `EVREN_GH_CMD` ortam değişkeniyle (JSON liste, ör. ["python", "sahte_gh.py"]) sahte gh verir.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

HOST = "github.com"
DEVICE_URL = "https://github.com/login/device"
WINGET_ID = "GitHub.cli"
_CODE_RE = re.compile(r"\b([A-Z0-9]{4}-[A-Z0-9]{4})\b")
_URL_RE = re.compile(r"https://github\.com/login/device\S*")
_ACCOUNT_RE = re.compile(r"Logged in to (\S+) account (\S+)")
_CANDIDATES = (r"C:\Program Files\GitHub CLI\gh.exe", r"C:\Program Files (x86)\GitHub CLI\gh.exe")
_NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def gh_command() -> list[str] | None:
    """gh'yi çalıştıracak komut başı; kurulu değilse None. Yeni kurulduysa PATH yenilenmemiş olabilir → bilinen yol."""
    env = os.environ.get("EVREN_GH_CMD")
    if env:
        try:
            cmd = json.loads(env)
            if isinstance(cmd, list) and cmd:
                return [str(c) for c in cmd]
        except ValueError:
            pass
    found = shutil.which("gh")
    if found:
        return [found]
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "GitHub CLI" / "gh.exe"
    for c in (*_CANDIDATES, str(local)):
        if Path(c).is_file():
            return [c]
    return None


def run_gh(*args: str, cwd: str | Path | None = None, timeout: int = 60) -> tuple[int, str]:
    cmd = gh_command()
    if cmd is None:
        return -1, "GitHub CLI (gh) kurulu değil"
    try:
        r = subprocess.run([*cmd, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, stdin=subprocess.DEVNULL,
                           env={**os.environ, "GH_PROMPT_DISABLED": "1", "GIT_TERMINAL_PROMPT": "0",
                                "NO_COLOR": "1"},
                           creationflags=_NOWIN)
        out = (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")
        return r.returncode, out.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, f"{type(exc).__name__}: {exc}"


def login_args() -> list[str]:
    """Tarayıcıyla giriş: HTTPS (SSH anahtarı yaratılmaz), yalnız github.com."""
    return ["auth", "login", "--web", "--hostname", HOST, "--git-protocol", "https", "--skip-ssh-key"]


def parse_device_code(text: str) -> tuple[str, str]:
    """gh çıktısından (tek kullanımlık kod, adres); bulunamazsa ("", "")."""
    code = _CODE_RE.search(text or "")
    url = _URL_RE.search(text or "")
    return (code.group(1) if code else ""), (url.group(0) if url else (DEVICE_URL if code else ""))


@dataclass
class Account:
    connected: bool
    login: str = ""
    installed: bool = True
    error: str = ""

    def text(self) -> str:
        if not self.installed:
            return "GitHub CLI (gh) kurulu değil"
        if self.connected:
            return f"Bağlı: {self.login}"
        return "Bağlı değil" + (f" ({self.error})" if self.error else "")


def parse_status(code: int, out: str) -> Account:
    """`gh auth status --hostname github.com` çıktısı → hesap."""
    if code == -1 and "kurulu değil" in out:
        return Account(False, installed=False)
    m = next((m for m in _ACCOUNT_RE.finditer(out or "") if m.group(1) == HOST), None)
    if m and code == 0:
        return Account(True, m.group(2))
    text = (out or "").strip()
    if not text or "not logged" in text.lower():
        return Account(False)
    return Account(False, error=text.splitlines()[-1][:160])


def account() -> Account:
    return parse_status(*run_gh("auth", "status", "--hostname", HOST, timeout=20))


def setup_git() -> tuple[bool, str]:
    c, o = run_gh("auth", "setup-git", "--hostname", HOST, timeout=30)
    return c == 0, o


def logout(login: str) -> tuple[bool, str]:
    args = ["auth", "logout", "--hostname", HOST] + (["--user", login] if login else [])
    c, o = run_gh(*args, timeout=30)
    return c == 0, o


@dataclass
class Repo:
    full_name: str
    description: str = ""
    private: bool = False
    updated: str = ""


def list_repos(limit: int = 200) -> list[Repo]:
    c, o = run_gh("repo", "list", "--limit", str(limit), "--json",
                  "nameWithOwner,description,isPrivate,updatedAt", timeout=60)
    if c != 0:
        raise RuntimeError(o or "depolar alınamadı")
    data = json.loads(_json_part(o) or "[]")
    return [Repo(d.get("nameWithOwner", ""), d.get("description") or "", bool(d.get("isPrivate")),
                 d.get("updatedAt") or "") for d in data]


def _json_part(text: str) -> str:
    i = min([p for p in (text.find("["), text.find("{")) if p >= 0], default=-1)
    return text[i:] if i >= 0 else ""


_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def clone(full_name: str, parent: str | Path) -> tuple[bool, str]:
    """Depoyu `parent/<ad>` klasörüne klonlar. Dönüş: (başarı, klasör yolu veya hata)."""
    if not _SAFE_NAME.match(full_name or ""):
        return False, f"geçersiz depo adı: {full_name}"
    dest = Path(parent) / full_name.split("/", 1)[1]
    if dest.exists() and any(dest.iterdir()):
        return False, f"hedef klasör dolu: {dest}"
    c, o = run_gh("repo", "clone", full_name, str(dest), timeout=600)
    return (c == 0, str(dest) if c == 0 else o)


def suggest_repo_name(root: str | Path) -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "-", Path(root).name).strip("-.") or "proje"
    return name[:90]


def create_repo(root: str | Path, name: str, private: bool = True) -> tuple[bool, str]:
    """Klasörden GitHub deposu oluşturur, `origin` ekler ve gönderir (en az bir commit gerekir)."""
    if not re.match(r"^[A-Za-z0-9_.-]+$", name or ""):
        return False, "Depo adında yalnız harf, rakam, - _ . kullanılabilir"
    args = ["repo", "create", name, "--private" if private else "--public", "--source", str(root),
            "--remote", "origin", "--push"]
    c, o = run_gh(*args, cwd=root, timeout=300)
    return c == 0, o


# ---- git uzak depo işlemleri (gh setup-git sonrası parolasız) ----

def _git(root: str | Path, *args: str, timeout: int = 300) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, stdin=subprocess.DEVNULL,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}, creationflags=_NOWIN)
        return r.returncode, ((r.stdout or "") + ("\n" + r.stderr if r.stderr else "")).strip()
    except FileNotFoundError:
        return -1, "git bulunamadı"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, f"{type(exc).__name__}: {exc}"


def remote_url(root: str | Path) -> str:
    c, o = _git(root, "remote", "get-url", "origin", timeout=15)
    return o.strip() if c == 0 else ""


def github_name(url: str) -> str:
    """https://github.com/a/b(.git) veya git@github.com:a/b(.git) → "a/b"; GitHub değilse ""."""
    m = re.search(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?/?$", url or "")
    return m.group(1) if m else ""


def push(root: str | Path) -> tuple[bool, str]:
    """Geçerli dalı origin'e gönderir; ilk kez ise yukarı akışı (upstream) kurar. Zorla gönderme YOK."""
    c, o = _git(root, "push", "-u", "origin", "HEAD")
    return c == 0, o


def pull(root: str | Path) -> tuple[bool, str]:
    """Yalnız ileri sarma (fast-forward): yerel değişiklikleri ezmez, birleştirme commit'i yaratmaz."""
    c, o = _git(root, "pull", "--ff-only")
    return c == 0, o


def install_command() -> list[str]:
    return ["winget", "install", "--id", WINGET_ID, "-e", "--accept-source-agreements",
            "--accept-package-agreements", "--silent"]
