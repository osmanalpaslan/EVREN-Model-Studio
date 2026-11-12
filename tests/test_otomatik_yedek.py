"""Günlük otomatik yerel yedek (2026-11-12 analiz bulgusu): tek veritabanındaki oturumlar için geri dönüş noktası."""
from __future__ import annotations

import os
import sqlite3
import time
import zipfile

import pytest

from evren_studio import backup
from evren_studio.db import Database


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "evren.db")
    sid = d.create_session("m", str(tmp_path), "manuel")
    d.add_session_message(sid, "user", "merhaba")
    yield d
    d.close()


def test_gunde_bir_yedek_ve_son_7_kalir(db, tmp_path):
    data = tmp_path
    for day in range(1, 11):
        made = backup.auto_backup(db.path, data, None, today=f"202611{day:02d}")
        assert made is not None and made.name == f"otomatik-202611{day:02d}.zip"
    assert backup.auto_backup(db.path, data, None, today="20261110") is None        # bugünkü var → yeniden alınmaz
    names = sorted(p.name for p in (data / "yedekler").glob("otomatik-*.zip"))
    assert names == [f"otomatik-202611{d:02d}.zip" for d in range(4, 11)]           # en yeni 7
    with zipfile.ZipFile(data / "yedekler" / "otomatik-20261110.zip") as z:
        z.extract("evren.db", tmp_path / "ac")
    con = sqlite3.connect(tmp_path / "ac" / "evren.db")
    assert con.execute("select count(*) from session_messages").fetchone()[0] == 1   # tutarlı, açılabilir kopya
    con.close()


def test_kullanicinin_kendi_dosyalarina_dokunmaz(db, tmp_path):
    folder = tmp_path / "yedekler"
    folder.mkdir()
    mine = folder / "elle-yedek.zip"
    mine.write_bytes(b"x")
    for day in range(1, 10):
        backup.auto_backup(db.path, tmp_path, None, today=f"202611{day:02d}", keep=2)
    assert mine.is_file() and len(list(folder.glob("otomatik-*.zip"))) == 2
    assert not list(folder.glob("*.yaziliyor.zip"))


@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    yield app, w
    w.close()


def _wait(app, cond, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def test_uygulama_acilista_arka_planda_yedek_alir_ayar_kapaliysa_almaz(win, monkeypatch):
    app, w = win
    w._auto_backup()
    app.processEvents()
    assert w.last_auto_backup is None                                     # testlerde kapalı (conftest)
    monkeypatch.delenv("EVREN_STUDIO_NO_AUTO_BACKUP")
    w.ctx.settings.auto_backup = False
    w._auto_backup()
    app.processEvents()
    assert w.last_auto_backup is None and not (w.ctx.data_dir() / "yedekler").exists()
    w.ctx.settings.auto_backup = True
    w._auto_backup()
    assert _wait(app, lambda: w.last_auto_backup is not None)
    assert w.last_auto_backup.parent == w.ctx.data_dir() / "yedekler" and w.last_auto_backup.is_file()
