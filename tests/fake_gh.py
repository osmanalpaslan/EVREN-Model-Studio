"""Sahte GitHub CLI (gh) — testler için (Madde 12d). Gerçek ağ/hesap YOK.

Durum: FAKE_GH_DIR klasörü (login.txt = bağlı kullanıcı, calls.jsonl = çağrılar).
Davranış: FAKE_GH_LOGIN_FAIL=1 → giriş başarısız; FAKE_GH_LOGIN_DELAY (sn, varsayılan 0.3);
FAKE_GH_BARE → `repo create --push` bu yerel çıplak depoyu origin yapıp gönderir.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")       # gerçek gh de UTF-8 yazar ("✓"); cp1254'te yazılamıyordu
d = Path(os.environ.get("FAKE_GH_DIR") or ".")
d.mkdir(parents=True, exist_ok=True)
args = sys.argv[1:]
with (d / "calls.jsonl").open("a", encoding="utf-8") as f:
    f.write(json.dumps(args, ensure_ascii=False) + "\n")
login_file = d / "login.txt"


def out(text, code=0):
    sys.stdout.write(text + "\n")
    sys.stdout.flush()
    sys.exit(code)


if args[:2] == ["auth", "status"]:
    if login_file.exists():
        out(f"github.com\n  ✓ Logged in to github.com account {login_file.read_text(encoding='utf-8').strip()} "
            "(keyring)\n  - Active account: true")
    out("You are not logged into any GitHub hosts. To log in, run: gh auth login", 1)
if args[:2] == ["auth", "login"]:
    sys.stdout.write("! First copy your one-time code: AB12-CD34\n"
                     "Open this URL to continue in your web browser: https://github.com/login/device\n")
    sys.stdout.flush()
    time.sleep(float(os.environ.get("FAKE_GH_LOGIN_DELAY", "0.3")))
    if os.environ.get("FAKE_GH_LOGIN_FAIL"):
        out("error: authorization was denied", 1)
    login_file.write_text("denemeci", encoding="utf-8")
    out("✓ Authentication complete.\n✓ Logged in as denemeci")
if args[:2] == ["auth", "setup-git"]:
    out("")
if args[:2] == ["auth", "logout"]:
    login_file.unlink(missing_ok=True)
    out("✓ Logged out of github.com account denemeci")
if args[:2] == ["repo", "list"]:
    out(json.dumps([{"nameWithOwner": "denemeci/hesap-araci", "description": "Hesap aracı", "isPrivate": True,
                     "updatedAt": "2026-11-01T10:00:00Z"},
                    {"nameWithOwner": "denemeci/blog", "description": "", "isPrivate": False,
                     "updatedAt": "2026-10-01T10:00:00Z"}]))
if args[:2] == ["repo", "clone"]:
    dest = Path(args[3])
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "README.md").write_text(f"# {args[2]}\n", encoding="utf-8")
    out(f"Cloning into '{dest}'...")
if args[:2] == ["repo", "create"]:
    src = args[args.index("--source") + 1]
    bare = os.environ.get("FAKE_GH_BARE")
    if bare:
        subprocess.run(["git", "remote", "add", "origin", bare], cwd=src, check=True, capture_output=True)
        r = subprocess.run(["git", "push", "-u", "origin", "HEAD"], cwd=src, capture_output=True, text=True)
        if r.returncode:
            out(r.stderr, 1)
    out(f"✓ Created repository denemeci/{args[2]} on GitHub")
out(f"bilinmeyen sahte gh komutu: {args}", 2)
