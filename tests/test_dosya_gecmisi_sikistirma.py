"""Ajanın dosya geçmişi sıkıştırılarak saklanır (2026-11-12, kullanıcı onayı).

Gerçek veritabanının kopyasında ölçüldü: 145 kayıt birebir aynı açıldı, dosya 12,7 → 6,8 MB, 0,36 sn. Okuyan kod aynı
metni görür; eski (TEXT) kayıtlar okunur ve arka planda dönüştürülür; doğrulanamayan kayda dokunulmaz.
"""
from __future__ import annotations

import os
import sqlite3
import threading

import pytest

from evren_studio import db as dbmod
from evren_studio.db import Database

METINLER = [
    "x = 1\n",
    "Türkçe: çğıöşü İĞÜŞÖÇ — “tırnak” ✓ 🌙⭐\r\nikinci satır\r\n",
    "",                                     # boş dosya: NULL DEĞİL (dosya vardı ama boştu)
    "\udcff tek vekil karakter (surrogateescape ile okunmuş bayt)",
    "def f():\n    return 42\n" * 2000,     # büyük ve sıkışır
]


def _legacy(db: Database, sid: int, path: str, before, after) -> int:
    """0.5.0 ve öncesi biçim: düz TEXT."""
    cur = db._exec("INSERT INTO file_changes(session_id, turn_id, path, before_text, after_text, created_at)"
                   " VALUES(?,?,?,?,?, '2026-11-01T00:00:00+00:00')", (sid, None, path, before, after))
    db._commit()
    return int(cur.lastrowid)


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "t.db")
    yield d
    d.close()


def test_yazilan_metin_birebir_geri_okunur_ve_blob_saklanir(db):
    sid = db.create_session("m", None, "auto")
    ids = [db.add_file_change(sid, None, f"d{i}.py", t, METINLER[(i + 1) % len(METINLER)])
           for i, t in enumerate(METINLER)]
    rows = db.list_file_changes(sid)
    for i, r in enumerate(rows):
        assert r["before_text"] == METINLER[i] and r["after_text"] == METINLER[(i + 1) % len(METINLER)]
        g = db.get_file_change(ids[i])
        assert g["before_text"] == METINLER[i] and g["path"] == f"d{i}.py"
    kinds = {r[0] for r in db._exec("SELECT typeof(before_text) FROM file_changes").fetchall()}
    assert kinds == {"blob"}, "yeni kayıt sıkıştırılmış saklanır"
    assert set(rows[0].keys()) == {"id", "session_id", "turn_id", "path", "before_text", "after_text", "reverted",
                                   "created_at"}, "okuyanlar eski sütun adlarını görür"


def test_null_yeni_ve_silinen_dosya_anlamini_korur(db):
    sid = db.create_session("m", None, "auto")
    a = db.add_file_change(sid, None, "yeni.py", None, "içerik\n")
    b = db.add_file_change(sid, None, "silinen.py", "eski\n", None)
    meta = {r["id"]: r for r in db.list_file_change_meta(sid)}
    assert meta[a]["is_new"] == 1 and meta[a]["is_deleted"] == 0
    assert meta[b]["is_new"] == 0 and meta[b]["is_deleted"] == 1
    assert db.get_file_change(a)["before_text"] is None and db.get_file_change(b)["after_text"] is None


def test_sikistirma_gercekten_kucultur(db):
    sid = db.create_session("m", None, "auto")
    big = "satır = 'aynı kalıp'\n" * 20000
    db.add_file_change(sid, None, "b.py", big, big + "x\n")
    stored = db._exec("SELECT length(before_text) FROM file_changes").fetchone()[0]
    assert stored < len(big.encode()) / 10


def test_eski_kayitlar_okunur_donusturulur_ve_ayni_kalir(db):
    sid = db.create_session("m", None, "auto")
    eski = [t for t in METINLER if "\udcff" not in t]     # eski TEXT biçimi tek vekil karakteri hiç saklayamazdı
    old = [_legacy(db, sid, f"e{i}.py", t, None if i == 1 else t + "eklendi\n") for i, t in enumerate(eski)]
    before = {r["id"]: (r["before_text"], r["after_text"]) for r in db.list_file_changes(sid)}
    assert set(before) == set(old), "eski TEXT kayıtlar okunur"
    n = db.pack_file_changes(batch=2)                    # küçük parti: çok parti yolu da sınanır
    assert n == len(old)
    after = {r["id"]: (r["before_text"], r["after_text"]) for r in db.list_file_changes(sid)}
    assert after == before, "dönüştürme içeriği değiştirmez"
    kinds = {r[0] for r in db._exec("SELECT typeof(after_text) FROM file_changes").fetchall()}
    assert kinds <= {"blob", "null"}
    assert db.pack_file_changes() == 0, "ikinci tur: yapılacak iş yok"


def test_dogrulanamayan_kayda_dokunulmaz_ve_tarama_takilmaz(db, monkeypatch):
    sid = db.create_session("m", None, "auto")
    bad = _legacy(db, sid, "bozuk.py", "BOZULACAK METİN\n", "x\n")
    good = _legacy(db, sid, "iyi.py", "iyi\n", "iyi2\n")
    real = dbmod.pack_text
    monkeypatch.setattr(dbmod, "pack_text",
                        lambda t: dbmod.PACK_MAGIC + b"\x00bozuk" if t == "BOZULACAK METİN\n" else real(t))
    assert db.pack_file_changes(batch=1) == 1             # yalnız doğrulanan satır
    types = dict(db._exec("SELECT id, typeof(before_text) FROM file_changes").fetchall())
    assert types[bad] == "text" and types[good] == "blob"
    assert db.get_file_change(bad)["before_text"] == "BOZULACAK METİN\n", "bozuk sıkıştırma yazılmadı"


def test_bakim_bir_kez_calisir_ve_dosyayi_kucultur(tmp_path):
    path = tmp_path / "b.db"
    d = Database(path)
    sid = d.create_session("m", None, "auto")
    for i in range(30):
        text = f"# dosya {i}\n" + ("def islem(x):\n    return x * 2\n" * 3000)
        _legacy(d, sid, f"f{i}.py", text, text + "# son\n")
    size0 = path.stat().st_size
    info = d.maintain_file_history()
    assert info["sikistirilan"] == 30 and info["kuculdu"] and not info["zaten"]
    assert path.stat().st_size < size0 * 0.5, (size0, path.stat().st_size)
    assert d.get_meta(dbmod.PACK_DONE_KEY) == "1"
    assert d.maintain_file_history()["zaten"], "işaret varsa tekrar taramaz"
    rows = d.list_file_changes(sid)
    assert rows[5]["before_text"].startswith("# dosya 5\n") and rows[5]["after_text"].endswith("# son\n")
    d.close()


def test_kucultme_bos_sayfa_azken_yapilmaz(db):
    """Tetiklenmeyen durum: boş sayfa oranı düşükse VACUUM çalışmaz (gereksiz kilit yok)."""
    sid = db.create_session("m", None, "auto")
    db.add_file_change(sid, None, "a.py", "a\n", "b\n")
    assert db.compact_if_worthwhile() is False


def test_donusturme_sirasinda_okuma_tutarli(db):
    """Dönüştürme arka plan iş parçacığında koşarken arayüz okuması hep aynı metni görür."""
    sid = db.create_session("m", None, "auto")
    for i in range(60):
        _legacy(db, sid, f"p{i}.py", f"önce {i}\n" * 50, f"sonra {i}\n" * 50)
    expected = {r["id"]: (r["before_text"], r["after_text"]) for r in db.list_file_changes(sid)}
    errors = []
    th = threading.Thread(target=lambda: db.pack_file_changes(batch=5))
    th.start()
    while th.is_alive():
        try:
            got = {r["id"]: (r["before_text"], r["after_text"]) for r in db.list_file_changes(sid)}
            if got != expected:
                errors.append("tutarsız")
        except sqlite3.Error as exc:                     # pragma: no cover - hata olursa test düşer
            errors.append(str(exc))
    th.join()
    assert not errors and db.pack_file_changes() == 0


def test_pencere_bakimi_arka_planda_yapar_ve_testte_kapali(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    import time

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from evren_studio.ui import workers
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    try:
        d = w.ctx.db
        sid = d.create_session("m", None, "auto")
        rid = _legacy(d, sid, "eski.py", "eski metin\n", "yeni metin\n")
        started = []
        real_start = workers.Task.start
        monkeypatch.setattr(workers.Task, "start", lambda self: started.append(self) or real_start(self))
        w._maintain_history()                                # conftest: EVREN_STUDIO_NO_DB_MAINT=1 → kapalı
        assert started == [] and w.last_history_maintenance is None
        monkeypatch.delenv("EVREN_STUDIO_NO_DB_MAINT")
        w._maintain_history()
        assert len(started) == 1
        end = time.monotonic() + 10
        while w.last_history_maintenance is None and time.monotonic() < end:
            app.processEvents()
            time.sleep(0.01)
        assert w.last_history_maintenance["sikistirilan"] == 1
        assert d._exec("SELECT typeof(before_text) FROM file_changes WHERE id=?", (rid,)).fetchone()[0] == "blob"
        assert d.get_file_change(rid)["after_text"] == "yeni metin\n"
        w._maintain_history()                                # işaret yazıldı: bir daha başlamaz
        assert len(started) == 1
    finally:
        w.close()
