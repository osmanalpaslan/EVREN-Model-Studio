"""Kaynak hijyeni: bozuk Türkçe (mojibake), BOM ve git'in dışladığı kaynak dosyası.

Kayıtlar: docs/ai-memory/incidents/2026-10-15-cift-kodlanmis-turkce-metinler-mojibake.md,
2026-10-15-gitignore-secrets-kalibi-kaynak-modulu-disladi.md (kurallar R-01, R-02, R-10).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("src", "tests", "tools", "docs")
SCAN_FILES = ("README.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md", "pyproject.toml")
SUFFIXES = {".py", ".md", ".toml", ".txt", ".mdc", ".bat"}
# UTF-8 Türkçe metnin cp1252 ile yanlış okunmasıyla oluşan diziler (Ã§, Ä±, ÅŸ, â€¦ vb.)
MOJIBAKE = re.compile(
    "[ÃÄÅ][\u0080-¿ŒœŠšŸŽž"
    "–—‘-„†-•…‰‹›€™]"
    "|â€"
)
EXEMPT_MARK = "kodlama-ornegi"   # bilerek örnek gösteren satırlar bu işareti taşır


def _files():
    for d in SCAN_DIRS:
        for p in (ROOT / d).rglob("*"):
            if p.is_file() and p.suffix in SUFFIXES and "__pycache__" not in p.parts:
                yield p
    for name in SCAN_FILES:
        if (ROOT / name).exists():
            yield ROOT / name


def test_bozuk_turkce_metin_yok():
    problems = []
    for p in _files():
        if p == Path(__file__).resolve():
            continue
        text = p.read_bytes().decode("utf-8", errors="replace")
        for no, line in enumerate(text.splitlines(), 1):
            if MOJIBAKE.search(line) and EXEMPT_MARK not in line:
                problems.append(f"{p.relative_to(ROOT)}:{no}: {line.strip()[:80]}")
    assert not problems, (
        "Çift kodlanmış (mojibake) Türkçe metin bulundu — dosyayı PowerShell 5.1 ile "
        "yazmayın (R-01):\n" + "\n".join(problems[:30]))


def test_python_dosyalarinda_bom_yok_ve_utf8():
    problems = []
    for p in _files():
        raw = p.read_bytes()
        if p.suffix == ".py" and raw.startswith(b"\xef\xbb\xbf"):
            problems.append(f"{p.relative_to(ROOT)}: BOM var")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            problems.append(f"{p.relative_to(ROOT)}: geçerli UTF-8 değil")
    assert not problems, "\n".join(problems)


@pytest.mark.skipif(shutil.which("git") is None or not (ROOT / ".git").exists(),
                    reason="git deposu gerekir")
def test_git_kaynak_dosyasini_yok_saymiyor():
    out = subprocess.run(
        ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "src", "tests", "tools"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
    ).stdout.splitlines()
    ignored_src = [f for f in out if f.endswith(".py") and "__pycache__" not in f
                   and ".egg-info" not in f]
    assert not ignored_src, (
        ".gitignore bu kaynak dosyalarını dışlıyor; depoya girmezler (R-02):\n"
        + "\n".join(ignored_src))
