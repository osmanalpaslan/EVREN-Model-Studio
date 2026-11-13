"""tools/onbellek_raporu.py (Madde 22 A): önbellek oranları — tüm adımlar, 2.+ adımlar, TUR BAŞI adımları.

Tur başı ölçüsü Faz B'nin kanıtıdır: sistem istemi turlar arasında değişirse önceki turların geçmişi önbellekten
düşer ve bu oran düşer.
"""
from __future__ import annotations

import sys
from pathlib import Path

from evren_studio.db import Database

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import onbellek_raporu as rap  # noqa: E402


def _u(db, sid, i, c):
    db.add_session_message(sid, "assistant", "x", meta={"usage": {"input_tokens": i, "output_tokens": 5,
                                                                  "cached_tokens": c}})


def test_oranlar_ve_tur_basi(tmp_path, capsys):
    db = Database(tmp_path / "e.db")
    sid = db.create_session("m", None, "auto")
    db.add_session_message(sid, "user", "1. tur")
    _u(db, sid, 5000, 0)            # oturumun ilk adımı (önbellek boş)
    _u(db, sid, 6000, 4800)         # aynı tur, 2. adım
    db.add_session_message(sid, "user", "2. tur")
    _u(db, sid, 8000, 1600)         # TUR BAŞI: önceki geçmiş önbellekte değil (istem değişmiş)
    db.add_session_message(sid, "tool", "araç çıktısı")
    _u(db, sid, 9000, 7600)
    sid2 = db.create_session("m", None, "auto")
    db.add_session_message(sid2, "assistant", "kullanımsız")    # usage yok → sayılmaz
    db.close()
    t = rap.rapor(tmp_path / "e.db")
    assert (t["adim"], t["girdi"], t["onbellek"]) == (4, 28000, 14000)
    assert (t["sonraki_girdi"], t["sonraki_onbellek"]) == (23000, 14000)
    assert (t["tur_basi_adim"], t["tur_basi_girdi"], t["tur_basi_onbellek"]) == (1, 8000, 1600)
    assert rap.main([str(tmp_path / "e.db")]) == 0
    out = capsys.readouterr().out
    assert "önbellek %50" in out and "tur başı %20 / 1 adım" in out and "kotadan düşmeyen 14000" in out
    assert rap.main([]) == 2
