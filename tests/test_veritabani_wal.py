"""SQLite WAL kipi (2026-11-13, analiz önerisi; kullanıcı "önerilerinle sonuna kadar git").

Ölçüm (200 mesaj yazmanın ortancası): eski kip 3,42 ms → WAL 0,96 ms. Riskler ayrı ayrı sınanır: kapanınca veri ve
-wal temizliği, açıkken alınan yedeğin -wal'daki son yazıyı içermesi (okuma yolu, R-03), eski kipteki veritabanının
dönüşümü, ağ sürücüsünde WAL'a GEÇİLMEMESİ (tetiklenmeyen, R-22), VACUUM sonrası -wal'ın sıfırlanması.
"""
from __future__ import annotations

import json
import os
import sqlite3
import zipfile
from pathlib import Path

import pytest

from evren_studio import db as db_mod
from evren_studio.backup import backup
from evren_studio.db import Database


def _wal(path: Path) -> Path:
    return path.with_name(path.name + "-wal")


def _mesaj_sayisi(path: Path) -> int:
    c = sqlite3.connect(path)
    try:
        return c.execute("SELECT COUNT(*) FROM session_messages").fetchone()[0]
    finally:
        c.close()


def test_yeni_veritabani_wal_kipinde_ve_kip_kalici(tmp_path):
    path = tmp_path / "evren.db"
    db = Database(path)
    assert db.journal_mode == "wal"
    db.close()
    c = sqlite3.connect(path)
    assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"      # kip dosyada saklanır
    c.close()


def test_kapanip_acilinca_veri_kalir_ve_wal_dosyasi_temizlenir(tmp_path):
    path = tmp_path / "evren.db"
    db = Database(path)
    sid = db.create_session("m", None, "auto")
    db.add_session_message(sid, "user", "merhaba")
    assert _wal(path).is_file()                       # yazılan veri önce -wal'da
    db.close()
    assert not _wal(path).exists() or _wal(path).stat().st_size == 0
    db2 = Database(path)
    assert [m["content"] for m in db2.get_session_messages(sid)] == ["merhaba"]
    db2.close()


def test_acikken_alinan_yedek_wal_daki_son_yaziyi_icerir(tmp_path):
    data = tmp_path / "veri"
    db = Database(data / "evren.db")
    sid = db.create_session("m", None, "auto")
    for i in range(3):
        db.add_session_message(sid, "user", f"mesaj {i}")
    assert _wal(db.path).stat().st_size > 0            # son yazılar henüz ana dosyada değil
    info = backup(db.path, data, None, tmp_path / "yedek.zip")
    assert info["mesaj"] == 3
    with zipfile.ZipFile(tmp_path / "yedek.zip") as z:
        z.extract("evren.db", tmp_path / "acilan")
        bilgi = json.loads(z.read("YEDEK_BILGI.json"))
    assert _mesaj_sayisi(tmp_path / "acilan" / "evren.db") == 3
    assert "evren.db-wal" in bilgi["geri_yukleme"] and "kapatın" in bilgi["geri_yukleme"]
    db.close()


def test_ikinci_baglanti_acik_veritabaninda_yazilani_gorur(tmp_path):
    path = tmp_path / "evren.db"
    db = Database(path)
    sid = db.create_session("m", None, "auto")
    db.add_session_message(sid, "assistant", "yanıt")
    assert _mesaj_sayisi(path) == 1                   # ayrı bağlantı (araçlar, yedek) WAL'daki işlenmiş yazıyı okur
    db.close()


def test_eski_kipteki_veritabani_donusturulur_veri_korunur(tmp_path):
    path = tmp_path / "evren.db"
    db = Database(path)
    sid = db.create_session("m", None, "auto")
    db.add_session_message(sid, "user", "eski kipte yazıldı")
    db.conn.execute("PRAGMA journal_mode=DELETE")
    db.close()
    c = sqlite3.connect(path)
    assert c.execute("PRAGMA journal_mode").fetchone()[0] == "delete"   # 0.5.0'ın bıraktığı hâl
    c.close()
    db2 = Database(path)
    assert db2.journal_mode == "wal"
    assert [m["content"] for m in db2.get_session_messages(sid)] == ["eski kipte yazıldı"]
    db2.close()


def test_ag_surucusunde_wal_a_gecilmez_ve_wal_daki_veritabani_geri_doner(tmp_path, monkeypatch):
    path = tmp_path / "evren.db"
    db = Database(path)                               # önce yerelde WAL'a geçmiş veritabanı
    sid = db.create_session("m", None, "auto")
    db.add_session_message(sid, "user", "taşındı")
    db.close()
    monkeypatch.setattr(db_mod, "_is_network_path", lambda p: True)    # veri klasörü ağ sürücüsüne taşındı
    db2 = Database(path)
    assert db2.journal_mode == "delete"
    db2.add_session_message(sid, "user", "ağda yazıldı")
    assert not _wal(path).exists()
    assert len(db2.get_session_messages(sid)) == 2
    db2.close()


def test_ag_yolu_tanima(tmp_path):
    assert db_mod._is_network_path(Path(r"\\sunucu\paylasim\evren.db"))
    assert db_mod._is_network_path(Path("//sunucu/paylasim/evren.db"))
    assert not db_mod._is_network_path(tmp_path / "evren.db")


@pytest.mark.skipif(os.name != "nt", reason="sürücü türü yalnız Windows'ta sorulur")
def test_eslenmis_ag_surucusu_tanınır(monkeypatch):
    import ctypes
    turler = {"Z:\\": 4, "C:\\": 3}                     # 4 = DRIVE_REMOTE, 3 = DRIVE_FIXED
    monkeypatch.setattr(ctypes.windll.kernel32, "GetDriveTypeW", lambda d: turler.get(d, 0))
    assert db_mod._is_network_path(Path("Z:/veri/evren.db"))
    assert not db_mod._is_network_path(Path("C:/veri/evren.db"))


def test_kucultme_sonrasi_wal_sifirlanir_ve_dosya_kuculur(tmp_path):
    path = tmp_path / "evren.db"
    db = Database(path)
    sid = db.create_session("m", None, "auto")
    for i in range(400):
        db.add_session_message(sid, "user", f"{i} " + "x" * 2000)
    db.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    buyuk = path.stat().st_size
    db.conn.execute("DELETE FROM session_messages")
    db.conn.commit()
    assert db.compact_if_worthwhile() is True
    assert _wal(path).stat().st_size == 0               # -wal veritabanı boyunda kalmaz
    assert path.stat().st_size < buyuk * 0.5, (buyuk, path.stat().st_size)
    db.close()
