"""Önbellek (prefix cache) raporu: bir EVREN Studio veritabanında ajan adımlarının ne kadarı sunucu önbelleğinden geldi.

Neden (2026-11-13 ölçümü, Madde 22 A): EVREN istemin değişmeyen başını önbelleğe alıyor — aynı başla gelen istek 4-7 kat
hızlı (deepseek 13,6 → 2 sn) ve önbellekten okunan token GÜNLÜK KOTADAN DÜŞMÜYOR (52.824 gönderilen, 35.072 önbellek,
kotadan 18.806 düştü). Bu rapor değişikliklerin önbelleği bozup bozmadığını sayıyla gösterir. SALT OKUNUR.

Kullanım:
    .venv\\Scripts\\python.exe tools\\onbellek_raporu.py <evren.db> [--adim]
Ölçüler: tüm adımlar · oturumun 2.+ adımları · TUR BAŞI adımları (yeni kullanıcı mesajından sonraki ilk adım: önceki
turların geçmişi önbellekte mi? — sistem istemi turlar arasında değişirse burası düşer).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


def rapor(db: Path, adim: bool = False) -> dict:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    top = {"adim": 0, "girdi": 0, "onbellek": 0, "sonraki_girdi": 0, "sonraki_onbellek": 0,
           "tur_basi_girdi": 0, "tur_basi_onbellek": 0, "tur_basi_adim": 0}
    for (sid,) in c.execute("SELECT id FROM sessions ORDER BY id"):
        k = 0
        yeni_tur = False
        for role, meta in c.execute("SELECT role, meta FROM session_messages WHERE session_id=? ORDER BY id", (sid,)):
            if role == "user":
                yeni_tur = True
                continue
            if role != "assistant":
                continue
            u = (json.loads(meta) if meta else {}).get("usage") or {}
            i, ca = int(u.get("input_tokens") or 0), int(u.get("cached_tokens") or 0)
            if not i:
                continue
            top["adim"] += 1
            top["girdi"] += i
            top["onbellek"] += ca
            if k:
                top["sonraki_girdi"] += i
                top["sonraki_onbellek"] += ca
                if yeni_tur:
                    top["tur_basi_adim"] += 1
                    top["tur_basi_girdi"] += i
                    top["tur_basi_onbellek"] += ca
            if adim:
                print(f"  oturum {sid} adım {k + 1}{' (tur başı)' if yeni_tur and k else ''}: girdi {i} önbellek {ca}")
            yeni_tur = False
            k += 1
    c.close()
    return top


def oran(a: int, b: int) -> str:
    return f"%{round(100 * a / b)}" if b else "-"


def main(argv: list[str]) -> int:
    dbs = [Path(a) for a in argv if not a.startswith("--")]
    if not dbs:
        print(__doc__)
        return 2
    for db in dbs:
        t = rapor(db, "--adim" in argv)
        print(f"{db}: {t['adim']} adım · önbellek {oran(t['onbellek'], t['girdi'])} "
              f"(2.+ adımlar {oran(t['sonraki_onbellek'], t['sonraki_girdi'])}, "
              f"tur başı {oran(t['tur_basi_onbellek'], t['tur_basi_girdi'])} / {t['tur_basi_adim']} adım) · "
              f"kotadan düşmeyen {t['onbellek']} token")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
