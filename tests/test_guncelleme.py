"""Güncelleme denetimi (Madde 20 C2, 2026-11-12): GitHub Releases'teki son sürüm yeniyse yalnız bildirilir."""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

import pytest

from evren_studio import updates

REL = {"tag_name": "v0.5.0", "draft": False, "prerelease": False,
       "html_url": "https://github.com/osmanalpaslan/EVREN-Model-Studio/releases/tag/v0.5.0",
       "body": "Paralel görevler\nayrıntı",
       "assets": [{"name": "EVREN-Studio-0.5.0.zip", "browser_download_url":
                   "https://github.com/osmanalpaslan/EVREN-Model-Studio/releases/download/v0.5.0/x.zip"},
                  {"name": "EVREN-Studio-Kurulum-0.5.0.exe", "browser_download_url":
                   "https://github.com/osmanalpaslan/EVREN-Model-Studio/releases/download/v0.5.0/EVREN-Studio-Kurulum-0.5.0.exe"}]}


@pytest.mark.parametrize("latest,current,expected", [
    ("v0.5.0", "0.4.2", True), ("0.4.10", "0.4.9", True), ("v1.0", "0.9.9", True), ("0.4.2", "0.4.2", False),
    ("0.4.1", "0.4.2", False), ("v0.4.2.0", "0.4.2", False), ("bozuk", "0.4.2", False), ("", "0.4.2", False),
])
def test_surum_karsilastirma(latest, current, expected):
    assert updates.newer(latest, current) is expected


def test_yeni_surum_kurulum_dosyasi_ve_notlar():
    info = updates.check("0.4.2", fetch=lambda: REL)
    assert info.version == "0.5.0" and info.asset_url.endswith("Kurulum-0.5.0.exe")
    assert info.url == REL["html_url"] and info.notes.startswith("Paralel")


@pytest.mark.parametrize("change", [{"draft": True}, {"prerelease": True}, {"tag_name": "v0.4.2"}])
def test_taslak_on_surum_ve_ayni_surum_onerilmez(change):
    assert updates.check("0.4.2", fetch=lambda: {**REL, **change}) is None


def test_atlanan_surum_gosterilmez_daha_yenisi_gosterilir():
    assert updates.check("0.4.2", fetch=lambda: REL, skipped="0.5.0") is None
    assert updates.check("0.4.2", fetch=lambda: {**REL, "tag_name": "v0.5.1"}, skipped="0.5.0").version == "0.5.1"


def test_ag_hatasi_ve_bozuk_yanit_sessiz():
    def boom():
        raise OSError("ağ yok")
    assert updates.check("0.4.2", fetch=boom) is None
    assert updates.check("0.4.2", fetch=lambda: ["liste"]) is None


def test_yabanci_adres_acilmaz():
    bad = {**REL, "html_url": "https://kotu.example/indir",
           "assets": [{"name": "EVREN-Studio-Kurulum-0.5.0.exe", "browser_download_url": "https://kotu.example/x.exe"}]}
    info = updates.check("0.4.2", fetch=lambda: bad)
    assert info.url == updates.PAGE and info.asset_url == ""


def test_gunde_bir_kez():
    now = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
    assert updates.due("", now)
    assert not updates.due((now - timedelta(hours=3)).isoformat(), now)
    assert updates.due((now - timedelta(hours=25)).isoformat(), now)
    assert updates.due((now + timedelta(days=2)).isoformat(), now)          # saat geri alındı → yine denetle
    assert updates.due("bozuk", now)


# ---- arayüz ----

@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show_notification = lambda title, text: None
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


def _update_cards(w):
    from PySide6.QtWidgets import QLabel, QPushButton

    from evren_studio.ui.transcript import ActionCard

    out = []
    for c in w.session.findChildren(ActionCard):
        texts = " ".join(lb.text() for lb in c.findChildren(QLabel))
        if "yayınlandı" in texts:
            out.append((c, texts, {b.text(): b for b in c.findChildren(QPushButton)}))
    return out


def test_arayuz_yeni_surum_karti_ve_atla(win, monkeypatch):
    app, w = win
    calls = []
    monkeypatch.setattr(updates, "check", lambda cur, skipped="", fetch=None: (calls.append((cur, skipped)),
                                                                             updates.UpdateInfo("0.5.0", REL["html_url"],
                                                                                                "https://x/k.exe", "not"))[1])
    w.check_updates()
    assert _wait(app, lambda: w.update_info is not None)
    assert calls and w.ctx.settings.update_last_check
    cards = _update_cards(w)
    assert len(cards) == 1 and "0.5.0" in cards[0][1]
    buttons = cards[0][2]
    assert {"İndir", "Sürüm notları", "Bu sürümü atla"} <= set(buttons)
    buttons["Bu sürümü atla"].click()
    assert w.ctx.settings.update_skipped == "0.5.0"
    w.check_updates()                                                    # 24 saat dolmadı → yeniden sorulmaz
    app.processEvents()
    assert len(calls) == 1
    w.ctx.settings.update_check = False
    w.check_updates(force=True)
    app.processEvents()
    assert len(calls) == 1                                                # ayar kapalı → hiç


def test_otomatik_denetim_test_ortaminda_kapali(win, monkeypatch):
    app, w = win
    calls = []
    monkeypatch.setattr(w, "check_updates", lambda force=False: calls.append(force))
    w._auto_update_check()
    assert calls == []                                                    # conftest: EVREN_STUDIO_NO_UPDATE_CHECK
    monkeypatch.delenv("EVREN_STUDIO_NO_UPDATE_CHECK")
    w._auto_update_check()
    assert calls == [False]


def test_yardim_sayfasindan_elle_denetim(win, monkeypatch):
    from evren_studio.ui.help_page import HelpPage

    app, w = win
    page = w.findChild(HelpPage)
    assert page is not None
    monkeypatch.setattr(updates, "check", lambda cur, skipped="", fetch=None: None)
    page.check_updates()
    assert _wait(app, lambda: "Güncelsiniz" in page.update_label.text())
    info = updates.UpdateInfo("9.9.9", REL["html_url"], "", "")
    monkeypatch.setattr(updates, "check", lambda cur, skipped="", fetch=None: info)
    page.check_updates()
    assert _wait(app, lambda: "9.9.9" in page.update_label.text()) and w.update_info is info
