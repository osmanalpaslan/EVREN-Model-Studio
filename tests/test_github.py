"""GitHub bağlantısı ve depo işlemleri (Madde 12d, 2026-11-05). Gerçek ağ/hesap YOK: gh yerine tests/fake_gh.py
(conftest), uzak depo olarak yerel çıplak (bare) git deposu. Gerçek gh çıktı biçimi 2026-11-05'te ölçüldü."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from evren_studio.agent import github as gh

GERCEK_CIKTI = ("! First copy your one-time code: 9F3A-1B7C\n"
                "Open this URL to continue in your web browser: https://github.com/login/device\n")


def _calls() -> list[list[str]]:
    p = Path(os.environ["FAKE_GH_DIR"]) / "calls.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True)


def _repo(tmp_path, name="proje"):
    root = tmp_path / name
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "a.txt").write_text("bir\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "ilk")
    return root


# ---- çekirdek ----------------------------------------------------------------------------------------

def test_cihaz_kodu_gercek_ciktidan_okunur():
    assert gh.parse_device_code(GERCEK_CIKTI) == ("9F3A-1B7C", "https://github.com/login/device")
    assert gh.parse_device_code("henüz bir şey yok") == ("", "")


def test_durum_ayristirma():
    ok = gh.parse_status(0, "github.com\n  ✓ Logged in to github.com account osman (keyring)")
    assert ok.connected and ok.login == "osman" and ok.text() == "Bağlı: osman"
    no = gh.parse_status(1, "You are not logged into any GitHub hosts.")
    assert not no.connected and no.text() == "Bağlı değil"
    missing = gh.parse_status(-1, "GitHub CLI (gh) kurulu değil")
    assert not missing.installed
    # başka sunucuya bağlı olmak github.com sayılmaz (R-22)
    assert not gh.parse_status(0, "  ✓ Logged in to ghe.sirket.com account x (keyring)").connected


def test_github_adi_ve_guvenli_depo_adi():
    assert gh.github_name("https://github.com/osman/EVREN-Model-Studio.git") == "osman/EVREN-Model-Studio"
    assert gh.github_name("git@github.com:osman/blog.git") == "osman/blog"
    assert gh.github_name("https://gitlab.com/a/b.git") == ""
    hedef = Path(os.environ["FAKE_GH_DIR"]) / "hedef"
    assert gh.clone("../../etc; rm -rf /", hedef)[0] is False
    assert not any(c[:2] == ["repo", "clone"] for c in _calls()), "geçersiz adla gh hiç çağrılmamalı"
    assert not hedef.exists() and not hedef.parent.joinpath("etc; rm -rf ").exists()
    assert gh.create_repo(".", "kötü ad!")[0] is False
    import re

    ad = gh.suggest_repo_name(r"C:\işler\Hesap Aracı")
    assert re.fullmatch(r"[A-Za-z0-9_.-]+", ad) and "Hesap" in ad      # GitHub'ın kabul ettiği karakterler


def test_sahte_gh_ile_giris_durum_cikis():
    assert not gh.account().connected
    assert gh.gh_command() is not None
    assert gh.logout("denemeci")[0]
    assert gh.list_repos()[0].full_name == "denemeci/hesap-araci"


def test_gh_kurulu_degilse_anlasilir_sonuc(monkeypatch):
    monkeypatch.delenv("EVREN_GH_CMD")
    monkeypatch.setattr(gh.shutil, "which", lambda _n: None)
    monkeypatch.setattr(gh, "_CANDIDATES", ())
    monkeypatch.setenv("LOCALAPPDATA", str(Path(os.environ["FAKE_GH_DIR"])))
    assert gh.gh_command() is None
    acc = gh.account()
    assert not acc.installed and "kurulu değil" in acc.text()


def test_push_pull_yerel_uzak_depoyla(tmp_path):
    bare = tmp_path / "uzak.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    root = _repo(tmp_path)
    _git(root, "remote", "add", "origin", str(bare))
    assert gh.push(root)[0]
    assert _git(bare, "log", "--oneline", "master").stdout.strip().endswith("ilk")
    # başka bir kopyadan yeni commit → pull ile gelir (yalnız ileri sarma)
    other = tmp_path / "kopya"
    subprocess.run(["git", "clone", "-q", str(bare), str(other)], check=True)
    _git(other, "config", "user.email", "t@example.com")
    _git(other, "config", "user.name", "Test")
    (other / "b.txt").write_text("iki\n", encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-q", "-m", "ikinci")
    _git(other, "push", "-q")
    assert gh.pull(root)[0] and (root / "b.txt").exists()


def test_ileri_sarilamayan_pull_yerel_isi_ezmez(tmp_path):
    bare = tmp_path / "uzak.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    root = _repo(tmp_path)
    _git(root, "remote", "add", "origin", str(bare))
    gh.push(root)
    other = tmp_path / "kopya"
    subprocess.run(["git", "clone", "-q", str(bare), str(other)], check=True)
    for r, f in ((other, "x.txt"), (root, "y.txt")):
        _git(r, "config", "user.email", "t@example.com")
        _git(r, "config", "user.name", "Test")
        (r / f).write_text("z\n", encoding="utf-8")
        _git(r, "add", "-A")
        _git(r, "commit", "-q", "-m", f)
    _git(other, "push", "-q")
    ok, _out = gh.pull(root)
    assert not ok and (root / "y.txt").exists() and not (root / "x.txt").exists()


def test_depo_olustur_gizli_ve_gonderir(tmp_path, monkeypatch):
    bare = tmp_path / "uzak.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    monkeypatch.setenv("FAKE_GH_BARE", str(bare))
    root = _repo(tmp_path)
    ok, out = gh.create_repo(root, "proje", private=True)
    assert ok, out
    call = next(c for c in _calls() if c[:2] == ["repo", "create"])
    assert "--private" in call and "--push" in call and call[call.index("--source") + 1] == str(root)
    assert gh.remote_url(root) == str(bare)


def test_klon_klasore_iner_ve_dolu_klasore_inmez(tmp_path):
    ok, path = gh.clone("denemeci/blog", tmp_path)
    assert ok and Path(path, "README.md").exists()
    ok2, msg = gh.clone("denemeci/blog", tmp_path)
    assert not ok2 and "dolu" in msg


# ---- arayüz ------------------------------------------------------------------------------------------

@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
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


def test_ayarlar_github_menusu_tarayici_akisi_ile_baglanir(win, monkeypatch):
    app, w = win
    from PySide6.QtGui import QDesktopServices, QGuiApplication

    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True)
    page = w.pages["settings"]
    w.show_page("settings")
    page.open_category("github")
    card = page.github_card
    assert _wait(app, lambda: card.status.text() == "Bağlı değil")
    assert card.connect_btn.isVisible() and not card.logout_btn.isVisible()
    dlg = card.connect_account()
    assert _wait(app, lambda: dlg.code == "AB12-CD34")
    assert QGuiApplication.clipboard().text() == "AB12-CD34"          # kod panoya kopyalandı
    assert opened == ["https://github.com/login/device"]               # tarayıcı açıldı
    assert _wait(app, lambda: card.status.text() == "Bağlı: denemeci", 15)
    assert any(c[:2] == ["auth", "setup-git"] for c in _calls())       # git girişi kullanacak
    assert card.logout_btn.isVisible() and card.clone_btn.isVisible() and not card.connect_btn.isVisible()
    card.disconnect_account()
    assert _wait(app, lambda: card.status.text() == "Bağlı değil")


def test_giris_reddedilirse_baglanmaz_ve_neden_yazilir(win, monkeypatch):
    app, w = win
    from PySide6.QtGui import QDesktopServices

    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: True)
    monkeypatch.setenv("FAKE_GH_LOGIN_FAIL", "1")
    page = w.pages["settings"]
    page.open_category("github")
    card = page.github_card
    dlg = card.connect_account()
    assert _wait(app, lambda: "Bağlanamadı" in dlg.state.text())
    assert "denied" in dlg.state.text()
    assert not any(c[:2] == ["auth", "setup-git"] for c in _calls())
    dlg.reject()


def test_vazgecince_gh_sureci_kapanir(win, monkeypatch):
    app, w = win
    from PySide6.QtCore import QProcess
    from PySide6.QtGui import QDesktopServices

    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: True)
    monkeypatch.setenv("FAKE_GH_LOGIN_DELAY", "30")
    card = w.pages["settings"].github_card
    dlg = card.connect_account()
    assert _wait(app, lambda: dlg.code == "AB12-CD34")
    dlg.reject()
    assert dlg.proc.state() == QProcess.NotRunning
    assert not (Path(os.environ["FAKE_GH_DIR"]) / "login.txt").exists()


def test_github_durumu_acilista_degil_menu_acilinca_denetlenir(win):
    app, w = win
    _wait(app, lambda: False, 0.5)
    assert not any(c[:2] == ["auth", "status"] for c in _calls())     # açılışta ağ/gh çağrısı yok (R-22)
    w.pages["settings"].open_category("github")
    assert _wait(app, lambda: any(c[:2] == ["auth", "status"] for c in _calls()))


def test_git_panelinde_gonder_al_ve_depo_olustur(win, tmp_path, monkeypatch):
    app, w = win
    root = _repo(tmp_path, "panelde")
    tab = w.panel.git
    tab.set_root(str(root))
    assert _wait(app, lambda: tab.remote_label.text().startswith("Uzak depo yok"))
    assert tab.create_btn.isVisibleTo(tab) and not tab.push_btn.isVisibleTo(tab)
    bare = tmp_path / "uzak.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    monkeypatch.setenv("FAKE_GH_BARE", str(bare))
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("panelde", True))
    tab.create_remote()
    assert _wait(app, lambda: "Depo oluşturuldu" in tab.note.text(), 15), tab.note.text()
    assert _wait(app, lambda: tab.push_btn.isVisibleTo(tab) and not tab.create_btn.isVisibleTo(tab))
    (root / "c.txt").write_text("üç\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "üçüncü")
    tab.refresh()
    assert _wait(app, lambda: tab.push_btn.text() == "Gönder (1)")
    tab.push()
    assert _wait(app, lambda: "Gönderildi" in tab.note.text(), 15), tab.note.text()
    assert _wait(app, lambda: tab.push_btn.text() == "Gönder")
    assert "üçüncü" in _git(bare, "log", "--oneline", "master").stdout


def test_git_deposu_degilse_github_dugmeleri_gizli(win, tmp_path):
    app, w = win
    plain = tmp_path / "duz"
    plain.mkdir()
    tab = w.panel.git
    tab.set_root(str(plain))
    assert _wait(app, lambda: tab.init_btn.isVisibleTo(tab))
    assert not any(b.isVisibleTo(tab) for b in (tab.push_btn, tab.pull_btn, tab.create_btn))


def test_klonlanan_depo_yeni_oturumda_acilir(win, tmp_path, monkeypatch):
    app, w = win
    card = w.pages["settings"].github_card
    opened = []
    card.open_workspace.connect(opened.append)
    card._clone("denemeci/hesap-araci", str(tmp_path))
    assert _wait(app, lambda: opened, 10)
    assert Path(opened[0]).name == "hesap-araci"
    w.open_workspace(opened[0])
    assert w.session.welcome.workspace == opened[0]
