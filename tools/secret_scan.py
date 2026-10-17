"""Commit'e giren değişikliklerde API anahtarı arar (ön-commit kancası çağırır).

İki denetim:
1. Bu bilgisayarın Credential Manager'ındaki GERÇEK anahtarlar (EVREN, OpenAI,
   Anthropic) eklenen satırlarda geçiyor mu?
2. Genel anahtar biçimleri: evren_…, sk-…, sk-ant-… (uzun, rastgele görünen).

Anahtar ekrana YAZDIRILMAZ; yalnız dosya adı ve satır numarası söylenir.
Kullanım: python tools/secret_scan.py [--all]   (--all: tüm izlenen dosyalar)
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    re.compile(r"evren_[A-Za-z0-9_]{30,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{30,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{30,}"),
]
# Testlerdeki bilinçli sahte anahtarlar içinde SAHTE/FAKE geçer; biçim kontrolünden muaftır
# (gerçek anahtar karşılaştırması onlar için de yapılır).
FAKE_MARK = re.compile(r"SAHTE|FAKE", re.I)


def real_keys() -> list[str]:
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from evren_studio.secrets import KEY_NAMES, load_api_key

        keys = [load_api_key(p) for p in KEY_NAMES]
        return [k for k in keys if k and len(k) >= 16]
    except Exception:
        return []


def added_lines(all_files: bool) -> list[tuple[str, int, str]]:
    out: list[tuple[str, int, str]] = []
    if all_files:
        files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8").stdout.split()
        for f in files:
            try:
                text = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            out += [(f, i, line) for i, line in enumerate(text.splitlines(), 1)]
        return out
    diff = subprocess.run(["git", "diff", "--cached", "-U0", "--no-color"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", errors="ignore").stdout
    current, line_no = "?", 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            current = raw[6:] if raw.startswith("+++ b/") else raw[4:]
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            line_no = int(m.group(1)) if m else 0
        elif raw.startswith("+") and not raw.startswith("+++"):
            out.append((current, line_no, raw[1:]))
            line_no += 1
    return out


def main() -> int:
    all_files = "--all" in sys.argv
    keys = real_keys()
    found: list[str] = []
    for path, no, line in added_lines(all_files):
        if any(k in line for k in keys):
            found.append(f"{path}:{no} — bu bilgisayardaki GERÇEK API anahtarı")
        elif any((m := p.search(line)) and not FAKE_MARK.search(m.group(0)) for p in PATTERNS):
            found.append(f"{path}:{no} — API anahtarına benzeyen metin")
    if found:
        print("DURDURULDU: commit'te API anahtarı olabilir (anahtar gösterilmez):")
        for f in found:
            print("  - " + f)
        print("Anahtarı dosyadan çıkarın; anahtarlar yalnız Windows Credential Manager'da tutulur.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
