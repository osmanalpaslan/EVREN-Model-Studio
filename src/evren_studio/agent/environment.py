"""Ortam denetimi: projenin ihtiyaç duyduğu programları bulur, kurulu mu bakar, kurar.

Kullanıcı kararı (2026-10-17): eksik program tespit edilince
- Ayarlar > "Program kurulumu: Otomatik" → sorulmadan kurulur,
- "Manuel" → "X programı gerekli, kurulsun mu?" bildirimi, onayla kurulur.
Bu ayar ajanın çalışma modundan (Manuel/Otomatik) BAĞIMSIZDIR.

Kurulum yalnız aşağıdaki BİLİNEN listeden ve yalnız resmi kaynaklardan yapılır
(Windows Paket Yöneticisi `winget`; pnpm/yarn için Node'un kendi `npm`'i).
Listede olmayan program kurulmaz; ajan kullanıcıya söyler.

Bu modül Qt kullanmaz; ağır işler (sürüm sorgusu, kurulum) arayüzde arka plan
iş parçacığında çağrılmalıdır (R-04). `quick_status` yalnız PATH'e bakar (hızlı).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

INSTALL_MODES = {"otomatik": "Otomatik (sormadan kur)", "manuel": "Manuel (kurmadan önce sor)"}
DEFAULT_INSTALL_MODE = "otomatik"
INSTALL_TIMEOUT = 15 * 60
# Ajan ve arayüz aynı anda kurmaya kalkarsa sıraya girer (ikincisi "zaten kurulu" görür).
_INSTALL_LOCK = threading.RLock()


@dataclass(frozen=True)
class KnownTool:
    key: str
    title: str
    exes: tuple[str, ...]                 # PATH'te aranacak adlar (ilk bulunan)
    version_args: tuple[str, ...] = ("--version",)
    winget_id: str | None = None
    winget_user_scope: bool = False       # yönetici izni istemeden kurulabilir
    npm_package: str | None = None        # Node varsa npm -g ile kurulur (yönetici gerekmez)
    requires: str | None = None           # önce kurulması gereken araç
    note: str = ""


KNOWN_TOOLS: dict[str, KnownTool] = {t.key: t for t in [
    KnownTool("git", "Git", ("git",), winget_id="Git.Git"),
    KnownTool("python", "Python 3.12", ("python", "py"), winget_id="Python.Python.3.12",
              winget_user_scope=True),
    KnownTool("uv", "uv (Python paket yöneticisi)", ("uv",), winget_id="astral-sh.uv",
              winget_user_scope=True),
    KnownTool("node", "Node.js LTS (npm dahil)", ("node",), winget_id="OpenJS.NodeJS.LTS"),
    KnownTool("pnpm", "pnpm", ("pnpm",), npm_package="pnpm", winget_id="pnpm.pnpm",
              winget_user_scope=True, requires="node"),
    KnownTool("yarn", "Yarn", ("yarn",), npm_package="yarn", requires="node"),
    KnownTool("go", "Go", ("go",), version_args=("version",), winget_id="GoLang.Go"),
    KnownTool("rust", "Rust (rustup + cargo)", ("cargo",), winget_id="Rustlang.Rustup",
              winget_user_scope=True),
    KnownTool("dotnet", ".NET SDK 10", ("dotnet",), winget_id="Microsoft.DotNet.SDK.10"),
    KnownTool("java", "Java JDK 21 (Temurin)", ("java",), version_args=("-version",),
              winget_id="EclipseAdoptium.Temurin.21.JDK"),
]}
# npm Node ile gelir: ayrı kurulmaz, Node'a yönlendirilir
ALIASES = {"npm": "node", "nodejs": "node", "cargo": "rust", "rustup": "rust", "py": "python",
           "python3": "python", ".net": "dotnet", "jdk": "java"}


def normalize_tool(name: str) -> str | None:
    n = (name or "").strip().lower()
    n = ALIASES.get(n, n)
    return n if n in KNOWN_TOOLS else None


# ---- proje türü → gereken araçlar ------------------------------------------------------


def detect_requirements(root: Path) -> dict[str, str]:
    """Proje dosyalarından gereken araçlar: {anahtar: gerekçe}. Boş klasörde boş döner."""
    root = Path(root)
    req: dict[str, str] = {}

    def has(*names: str) -> str | None:
        for n in names:
            if any(root.glob(n)):
                return n
        return None

    if (root / "package.json").is_file():
        req["node"] = "package.json"
        manager = ""
        try:
            manager = str(json.loads((root / "package.json").read_text(encoding="utf-8",
                                                                       errors="ignore")).get("packageManager") or "")
        except (OSError, ValueError, AttributeError):
            pass
        if (root / "pnpm-lock.yaml").is_file() or manager.startswith("pnpm"):
            req["pnpm"] = "pnpm-lock.yaml" if (root / "pnpm-lock.yaml").is_file() else "packageManager: pnpm"
        if (root / "yarn.lock").is_file() or manager.startswith("yarn"):
            req["yarn"] = "yarn.lock" if (root / "yarn.lock").is_file() else "packageManager: yarn"
    hit = has("pyproject.toml", "requirements*.txt", "setup.py", "*.py")
    if hit:
        req["python"] = hit
    if (root / "uv.lock").is_file():
        req["uv"] = "uv.lock"
    if (root / "go.mod").is_file():
        req["go"] = "go.mod"
    if (root / "Cargo.toml").is_file():
        req["rust"] = "Cargo.toml"
    hit = has("*.sln", "*.csproj", "*.fsproj", "global.json")
    if hit:
        req["dotnet"] = hit
    hit = has("pom.xml", "build.gradle", "build.gradle.kts")
    if hit:
        req["java"] = hit
    if (root / ".git").exists():
        req["git"] = ".git"
    return req


# ---- kurulu mu? ----------------------------------------------------------------------------


@dataclass
class ToolStatus:
    key: str
    title: str
    reason: str
    path: str | None
    version: str = ""

    @property
    def installed(self) -> bool:
        return self.path is not None


def find_exe(tool: KnownTool) -> str | None:
    for exe in tool.exes:
        p = shutil.which(exe)
        if p:
            return p
    return None


def tool_version(tool: KnownTool, exe: str, timeout: float = 15) -> str:
    try:
        p = subprocess.run([exe, *tool.version_args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    out = (p.stdout or "") + (p.stderr or "")
    m = re.search(r"\d+\.\d+(?:\.\d+)?", out)
    return m.group(0) if m else ""


def check(root: Path, with_versions: bool = True, extra: list[str] | None = None) -> list[ToolStatus]:
    """Projenin gereken araçlarının durumu (with_versions=False → yalnız PATH, hızlı)."""
    req = detect_requirements(root)
    for name in extra or []:
        key = normalize_tool(name)
        if key and key not in req:
            req[key] = "istendi"
    out: list[ToolStatus] = []
    for key, reason in req.items():
        tool = KNOWN_TOOLS[key]
        exe = find_exe(tool)
        ver = tool_version(tool, exe) if (exe and with_versions) else ""
        out.append(ToolStatus(key, tool.title, reason, exe, ver))
    return out


def quick_status(root: Path) -> list[ToolStatus]:
    return check(root, with_versions=False)


def status_line(statuses: list[ToolStatus]) -> str:
    parts = []
    for s in statuses:
        if s.installed:
            parts.append(f"{s.key} ✓{(' ' + s.version) if s.version else ''}")
        else:
            parts.append(f"{s.key} ✗ eksik")
    return ", ".join(parts)


def prompt_section(statuses: list[ToolStatus], install_mode: str) -> str:
    """Sistem istemine eklenen ortam bölümü."""
    known = ", ".join(sorted(KNOWN_TOOLS))
    lines = ["# Ortam denetimi"]
    if statuses:
        lines.append("- Projenin gerektirdiği programlar: " + status_line(statuses))
    else:
        lines.append("- Proje dosyalarından gereken program belirlenemedi (klasör boş olabilir).")
    how = ("sorulmadan kurulur" if install_mode == "otomatik"
           else "kullanıcıya sorulur, onaylarsa kurulur")
    lines.append(
        f"- Eksik bir program gerekirse install_program aracını kullan ({how}); komutla "
        f"(winget, npm -g) kendin kurmaya çalışma. Kurulabilenler: {known}. "
        "Listede olmayan bir program gerekiyorsa kullanıcıya söyle.")
    lines.append(
        "- npm ile kurulan araçları (pnpm, yarn, tsc, npx …) PowerShell'de `.cmd` uzantısıyla "
        "çağır: `pnpm.cmd install`, `yarn.cmd --version`. Bu bilgisayarın betik politikası "
        "`.ps1` kabuklarını engelleyebilir (\"running scripts is disabled\").")
    return "\n".join(lines) + "\n"


# ---- kurulum ---------------------------------------------------------------------------------


@dataclass
class InstallResult:
    key: str
    ok: bool
    command: str
    output: str = ""
    version: str = ""
    path: str | None = None
    needs_restart: bool = False
    steps: list[str] = field(default_factory=list)


def refresh_path() -> None:
    """Kurulumdan sonra kayıt defterindeki güncel PATH'i bu sürece al (Windows).

    winget yeni programı PATH'e ekler ama çalışan uygulamanın ortamı eski kalır;
    yenilenmezse ajanın komutları programı bulamaz.
    """
    if os.name != "nt":
        return
    try:
        import winreg
    except ImportError:  # pragma: no cover
        return
    found: list[str] = []
    for hive, sub in ((winreg.HKEY_LOCAL_MACHINE,
                       r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                      (winreg.HKEY_CURRENT_USER, r"Environment")):
        try:
            with winreg.OpenKey(hive, sub) as k:
                val, _ = winreg.QueryValueEx(k, "Path")
                found += [os.path.expandvars(p) for p in str(val).split(";") if p.strip()]
        except OSError:
            continue
    current = os.environ.get("PATH", "").split(os.pathsep)
    seen = {p.lower().rstrip("\\") for p in current if p}
    added = [p for p in found if p.lower().rstrip("\\") not in seen]
    if added:
        os.environ["PATH"] = os.pathsep.join(current + added)


def install_plan(key: str) -> list[list[str]]:
    """Kurulum komutları (sırayla denenir; ilki başarılı olursa diğerleri çalışmaz)."""
    tool = KNOWN_TOOLS[key]
    plans: list[list[str]] = []
    npm = shutil.which("npm")
    if tool.npm_package and npm:
        plans.append([npm, "install", "-g", tool.npm_package])
    winget = shutil.which("winget")
    if tool.winget_id and winget:
        cmd = [winget, "install", "--id", tool.winget_id, "-e", "--silent",
               "--accept-source-agreements", "--accept-package-agreements",
               "--disable-interactivity"]
        if tool.winget_user_scope:
            cmd += ["--scope", "user"]
        plans.append(cmd)
    return plans


def describe_plan(key: str) -> str:
    plans = install_plan(key)
    if not plans:
        return "(bu bilgisayarda uygun kurulum yolu yok: winget/npm bulunamadı)"
    return " ".join([Path(plans[0][0]).stem] + plans[0][1:])


def short_plan(key: str) -> str:
    """Kart için kısa kurulum açıklaması: 'npm install -g pnpm' / 'winget install GoLang.Go'."""
    plans = install_plan(key)
    if not plans:
        return "uygun kurulum yolu yok (winget/npm bulunamadı)"
    cmd = plans[0]
    tool = Path(cmd[0]).stem
    if tool.lower() == "winget" and "--id" in cmd:
        return f"winget install {cmd[cmd.index('--id') + 1]}"
    return " ".join([tool] + cmd[1:])


def install(key: str, on_output: Callable[[str], None] | None = None,
            timeout: int = INSTALL_TIMEOUT, cancel=None) -> InstallResult:
    """Aracı kurar (önce gereksinimi). Arka plan iş parçacığında çağrılmalı."""
    with _INSTALL_LOCK:
        return _install(key, on_output, timeout, cancel)


def _install(key: str, on_output: Callable[[str], None] | None, timeout: int, cancel) -> InstallResult:
    key = normalize_tool(key) or key
    if key not in KNOWN_TOOLS:
        return InstallResult(key, False, "", f"'{key}' bilinen kurulum listesinde yok.")
    tool = KNOWN_TOOLS[key]
    steps: list[str] = []
    if find_exe(tool):
        exe = find_exe(tool)
        return InstallResult(key, True, "", "Zaten kurulu.", tool_version(tool, exe), exe)
    if tool.requires and not find_exe(KNOWN_TOOLS[tool.requires]):
        dep = _install(tool.requires, on_output, timeout, cancel)
        steps.append(f"{tool.requires}: {'kuruldu' if dep.ok else 'kurulamadı'}")
        if not dep.ok:
            return InstallResult(key, False, dep.command,
                                 f"Önce {KNOWN_TOOLS[tool.requires].title} gerekiyordu ve kurulamadı.\n"
                                 + dep.output, steps=steps)
    plans = install_plan(key)
    if not plans:
        return InstallResult(key, False, "", "Kurulum için winget veya npm bulunamadı.", steps=steps)
    last = InstallResult(key, False, "", "", steps=steps)
    for cmd in plans:
        if cancel is not None and getattr(cancel, "cancelled", False):
            last.output += "\nİptal edildi."
            return last
        shown = " ".join([Path(cmd[0]).stem] + cmd[1:])
        if on_output:
            on_output(f"$ {shown}\n")
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
            out = ((p.stdout or "") + (p.stderr or "")).strip()
            code = p.returncode
        except subprocess.TimeoutExpired:
            out, code = f"Zaman aşımı ({timeout} sn).", -1
        except OSError as exc:
            out, code = f"Başlatılamadı: {exc}", -1
        out = _clean_progress(out)
        if on_output and out:
            on_output(out[-2000:] + "\n")
        refresh_path()
        exe = find_exe(tool)
        last = InstallResult(key, exe is not None, shown, out[-4000:], steps=steps)
        if exe:
            last.path, last.version = exe, tool_version(tool, exe)
            return last
        if code == 0:
            # Kuruldu ama PATH bu süreçte görünmüyor (nadiren yeniden başlatma gerekir)
            last.ok, last.needs_restart = True, True
            return last
    return last


def _clean_progress(text: str) -> str:
    """winget ilerleme çubuklarını ve dönen karakterleri ayıklar."""
    lines = []
    for line in text.replace("\r", "\n").splitlines():
        s = line.strip()
        if not s or set(s) <= set("-\\|/ █▒░") or re.fullmatch(r"[\s█▒░\d.%KMGBkb/]+", s):
            continue
        lines.append(s)
    return "\n".join(lines)
