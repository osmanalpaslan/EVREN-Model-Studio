"""F5 #16 oturum yedeği (Qt'siz): veritabanı (tutarlı kopya, sqlite backup API) + ayarlar + skill'ler → tek .zip.

API anahtarı yedeğe GİRMEZ (Windows Credential Manager'dadır, config.json'da yoktur). Ücretli sağlayıcı anahtarları da
aynı kasada. Yedek kullanıcının seçtiği yere yazılır; uygulama yedeği kendiliğinden bir yere göndermez.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path


def backup(db_path: Path, data_dir: Path, config_path: Path | None, dest: Path) -> dict:
    """Yedeği `dest` (.zip) dosyasına yazar. Dönüş: {"oturum": n, "mesaj": n, "boyut_kb": n, "dosyalar": [...]}."""
    dest = Path(dest)
    if dest.suffix.lower() != ".zip":
        dest = dest.with_suffix(".zip")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        copy = Path(t) / "evren.db"
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(copy)
        try:
            src.backup(dst)                                  # açık bağlantı varken de tutarlı kopya
            n_sess = dst.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            n_msg = dst.execute("SELECT COUNT(*) FROM session_messages").fetchone()[0]
        finally:
            dst.close()
            src.close()
        names = []
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(copy, "evren.db")
            names.append("evren.db")
            if config_path is not None and Path(config_path).is_file():
                z.write(config_path, "config.json")
                names.append("config.json")
            skills = Path(data_dir) / "skills"
            if skills.is_dir():
                for f in sorted(skills.rglob("*")):
                    if f.is_file():
                        z.write(f, "skills/" + f.relative_to(skills).as_posix())
                names.append("skills/")
            z.writestr("YEDEK_BILGI.json", json.dumps({
                "olusturma": datetime.now().isoformat(timespec="seconds"), "oturum": n_sess, "mesaj": n_msg,
                "not": "API anahtarları yedekte yoktur (Windows Credential Manager)."}, ensure_ascii=False, indent=1))
    return {"oturum": n_sess, "mesaj": n_msg, "boyut_kb": max(1, dest.stat().st_size // 1024), "dosyalar": names,
            "yol": str(dest)}
