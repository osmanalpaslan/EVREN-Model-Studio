"""Test bekçisi: ajan turunda dosya değiştiyse, tur bitmeden projenin KENDİ testleri çalışır;
tur başında geçen testler bozulduysa model bir kez uyarılır (Qt'siz).

Neden (2026-10-19): EVREN motorları değişiklikten sonra testleri çalıştırmadan "bitti"
diyebiliyor. Önceden de düşen testler için uyarı verilmez: model ilgisiz bozukluğun peşine
düşüp kapsamı aşmasın (R-20). Test dosyasını değiştirerek geçirme yasaktır (istem + scope.py).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from .tools import find_project_venv, project_env

TEST_TIMEOUT = 180
NUDGE = ("⚠ TEST BEKÇİSİ: Bu turdaki değişikliklerinden sonra projenin testleri DÜŞÜYOR "
         "(`{cmd}`, çıkış {code}). Tur başında geçiyorlardı. Son çıktı:\n{tail}\n\n"
         "Bitti demeden önce nedenini bul ve KODU düzelt. Testi geçirmek için test dosyalarını "
         "değiştirme. İstek ile test gerçekten çelişiyorsa kodu bozmadan bunu kullanıcıya açıkça söyle.")


def _python(root: Path) -> str:
    venv = find_project_venv(root)
    if venv is not None:
        exe = venv / ("python.exe" if os.name == "nt" else "python")
        if exe.exists():
            return str(exe)
    return shutil.which("python") or "python"


def _has_pytest(root: Path) -> bool:
    try:
        r = subprocess.run([_python(root), "-c", "import pytest"], cwd=str(root), capture_output=True,
                           timeout=20, env=project_env(root),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _py_tests(root: Path) -> list[Path]:
    out: list[Path] = []
    for base in (root, root / "tests", root / "test"):
        if base.is_dir():
            out += [p for p in base.glob("test_*.py")] + [p for p in base.glob("*_test.py")]
    return out


def detect_command(root: Path) -> str | None:
    """Projenin test komutu (bulunamazsa None). Yalnız hızlı ve yerel test koşucuları."""
    root = Path(root)
    py = _py_tests(root)
    if py:
        if _has_pytest(root):
            return "python -m pytest -q -x -p no:cacheprovider"
        start = "tests" if (root / "tests").is_dir() and any(p.parent.name == "tests" for p in py) else "."
        return f"python -m unittest discover -s {start} -q"
    pkg = root / "package.json"
    if pkg.exists() and (root / "node_modules").is_dir():
        try:
            script = (json.loads(pkg.read_text(encoding="utf-8")).get("scripts") or {}).get("test", "")
        except (OSError, ValueError, AttributeError):
            script = ""
        if script and "no test specified" not in script:
            return "npm test --silent"
    for csproj in list(root.glob("*.csproj")) + list(root.glob("*/*.csproj")):
        try:
            if "Microsoft.NET.Test.Sdk" in csproj.read_text(encoding="utf-8", errors="replace"):
                return "dotnet test --nologo -v q"
        except OSError:
            continue
    if (root / "go.mod").exists() and shutil.which("go") and any(root.rglob("*_test.go")):
        return "go test ./..."
    return None


def run(toolbox, command: str, timeout: int = TEST_TIMEOUT, cancel=None) -> tuple[str, int | None, str]:
    """(durum, çıkış kodu, çıktı). durum: "gecti" | "dustu" | "yok" (test bulunamadı/çalışmadı)."""
    res = toolbox.run_command(command, timeout_seconds=timeout, cancel=cancel)
    out = res.output or ""
    if res.timed_out or res.cancelled:
        return "yok", res.exit_code, out
    if res.exit_code == 5 or "NO TESTS RAN" in out or "no tests ran" in out:
        return "yok", res.exit_code, out              # pytest/unittest: test yok
    return ("gecti" if res.exit_code == 0 else "dustu"), res.exit_code, out


def tail(text: str, lines: int = 25, chars: int = 2500) -> str:
    t = "\n".join((text or "").strip().splitlines()[-lines:])
    return t[-chars:]
