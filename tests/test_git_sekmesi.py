"""Madde 1: Git sekmesi — durum ayrıştırma, yeni/değişen dosya farkı, commit, kimliksiz commit, depo dışı."""
import subprocess
import time

import pytest

from evren_studio.agent import gitview


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "ana")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "ilk")
    return tmp_path


def test_depo_değilse(tmp_path):
    st = gitview.status(tmp_path)
    assert not st.repo and not st.error


def test_durum_ve_fark(repo):
    (repo / "a.py").write_text("print(2)\n", encoding="utf-8")
    (repo / "çğüş klasör").mkdir()
    (repo / "çğüş klasör" / "yeni.txt").write_text("merhaba\n", encoding="utf-8")
    st = gitview.status(repo)
    assert st.repo and st.branch == "ana"
    by = {e.path: e for e in st.entries}
    assert by["a.py"].label == "değişti"
    yeni = by["çğüş klasör/yeni.txt"]
    assert yeni.untracked and yeni.label == "yeni"
    assert "-print(1)" in gitview.file_diff(repo, by["a.py"]) and "+print(2)" in gitview.file_diff(repo, by["a.py"])
    assert "+merhaba" in gitview.file_diff(repo, yeni)
    assert "a.py" in gitview.summary_diff(repo)


def test_commit_kullanıcı_kimliğiyle(repo):
    (repo / "b.py").write_text("x = 1\n", encoding="utf-8")
    ok, info = gitview.commit(repo, "B eklendi")
    assert ok and info
    assert gitview.status(repo).entries == []
    log = subprocess.run(["git", "log", "-1", "--format=%an|%s"], cwd=repo, capture_output=True, text=True).stdout
    assert log.strip() == "Test|B eklendi"


def test_boş_mesaj_commit_etmez(repo):
    (repo / "b.py").write_text("x\n", encoding="utf-8")
    assert gitview.commit(repo, "  ") == (False, "Commit mesajı boş.")
    assert gitview.status(repo).entries


def test_kimlik_yoksa_evren_kimliği(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "yok.gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    _git(tmp_path, "init", "-q")
    (tmp_path / "x.txt").write_text("1", encoding="utf-8")
    ok, _info = gitview.commit(tmp_path, "ilk")
    assert ok
    an = subprocess.run(["git", "log", "-1", "--format=%an"], cwd=tmp_path, capture_output=True, text=True).stdout
    assert an.strip() == "EVREN Studio"


def test_git_sekmesi_listeler_ve_commit_onayı_ister(repo, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox

    from evren_studio.ui import workers
    from evren_studio.ui.side_panel import GitTab

    app = QApplication.instance() or QApplication([])
    # Önceki testte kapanan MainWindow set_accepting(False) bırakır; pencere açmayan bu testte sonuçlar
    # teslim edilmez (tam pakette bulundu, tek başına geçiyordu).
    monkeypatch.setattr(workers, "_ACCEPTING", True)
    (repo / "a.py").write_text("print(3)\n", encoding="utf-8")
    tab = GitTab(ctx=None)
    tab.set_root(str(repo))
    end = time.time() + 10
    while time.time() < end and not tab.entries:
        app.processEvents()
        time.sleep(0.02)
    assert [e.path for e in tab.entries] == ["a.py"]
    assert "Dal: ana" in tab.branch.text()
    tab.message.setPlainText("Üç yazdır")
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(a[2]) or QMessageBox.No)
    tab.commit()
    assert asked and "a.py" in asked[0] and "push" in asked[0]
    assert gitview.status(repo).entries                    # reddedildi → commit yok
    tab.deleteLater()
