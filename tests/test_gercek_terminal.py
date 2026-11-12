"""Gerçek (etkileşimli) terminal (Madde 20 C4, 2026-11-12): proje klasöründe sürekli PowerShell (ConPTY/pywinpty +
pyte ekran öykünücüsü). Gerçek kabukla: cd/değişken kalır, soru soran komuta yanıt verilir, kapatınca süreç biter."""
from __future__ import annotations

import os
import time

import pytest

from evren_studio.agent import ptyshell

needs_pty = pytest.mark.skipif(not ptyshell.available(), reason="pywinpty/pyte yok ya da Windows değil")


def _until(fn, cond, timeout=20.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        fn()
        if cond():
            return True
        time.sleep(0.1)
    return cond()


@needs_pty
def test_kabuk_cd_degisken_ve_soru_soran_komut(tmp_path):
    (tmp_path / "alt klasör").mkdir()
    sh = ptyshell.PtyShell(tmp_path, 110, 30)
    sh.start()
    try:
        assert _until(lambda: None, lambda: "PS " in sh.text())
        sh.write("cd 'alt klasör'\r")
        sh.write("$sayi = 41 + 1\r")
        sh.write("$ad = Read-Host 'Adiniz'\r")
        assert _until(lambda: None, lambda: "Adiniz:" in sh.text())
        sh.write("Osman\r")
        sh.write("Write-Output \"Merhaba $ad $sayi\"; (Get-Location).Path\r")
        assert _until(lambda: None, lambda: "Merhaba Osman 42" in sh.text())
        assert _until(lambda: None, lambda: "alt klasör" in sh.text().split("Merhaba Osman 42", 1)[-1])
        row, col = sh.cursor()
        assert row >= 0 and col >= 0
    finally:
        sh.close()
    assert not sh.alive


@needs_pty
def test_ctrl_c_uzun_komutu_keser_ve_boyut_degisir(tmp_path):
    sh = ptyshell.PtyShell(tmp_path, 80, 24)
    sh.start()
    try:
        assert _until(lambda: None, lambda: "PS " in sh.text())
        assert sh.backend == "WinPTY"                     # ConPTY'de Ctrl+C kesmiyordu (ölçüm, 2026-11-12)
        sh.write("ping -n 30 127.0.0.1\r")
        assert _until(lambda: None, lambda: "127.0.0.1" in sh.text().split("ping -n 30", 1)[-1])
        sh.write(ptyshell.ctrl_key("c"))
        time.sleep(1.0)
        sh.write("Write-Output ('SON' + 'RA')\r")
        assert _until(lambda: None, lambda: "SONRA" in sh.text(), 15)       # kesildi → sonraki komut çalıştı
        sh.resize(120, 40)
        assert (sh.cols, sh.rows) == (120, 40) and sh.screen.columns == 120
    finally:
        sh.close()


@needs_pty
def test_cikista_acik_kabuklar_kapanir(tmp_path):
    sh = ptyshell.PtyShell(tmp_path)
    sh.start()
    assert sh.alive
    ptyshell.close_all()
    assert not sh.alive


def test_tus_dizileri():
    from PySide6.QtCore import Qt

    from evren_studio.ui.shell_view import key_sequence

    none = Qt.KeyboardModifier.NoModifier
    ctrl = Qt.KeyboardModifier.ControlModifier
    assert key_sequence(Qt.Key_Return, none, "\r") == "\r"
    assert key_sequence(Qt.Key_Up, none, "") == "\x1b[A"
    assert key_sequence(Qt.Key_Backspace, none, "\x08") == "\x7f"
    assert key_sequence(Qt.Key_C, ctrl, "") == "\x03"                   # bazı düzenlerde Qt metni boş verir
    assert key_sequence(Qt.Key_D, ctrl, "") == "\x04"
    assert key_sequence(Qt.Key_A, none, "ş") == "ş"
    assert ptyshell.ctrl_key("z") == "\x1a" and ptyshell.ctrl_key("1") == ""


# ---- arayüz ----

@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    yield app, w
    w.close()


def _wait(app, cond, timeout=20.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.05)
    return cond()


@needs_pty
def test_terminal_sekmesinde_kabuk_yazilanlari_calistirir(win, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    app, w = win
    proj = tmp_path / "proje"
    proj.mkdir()
    s = w.session
    s.new_session()
    s.welcome._choose(str(proj))
    term = w.panel.terminal
    assert term.root == str(proj) and term.shell_btn.isEnabled()
    assert term.stack.currentIndex() == 0 and term.input_row.isVisibleTo(term)       # varsayılan: Günlük
    w.panel.show()
    term.shell_btn.click()
    assert term.stack.currentIndex() == 1 and not term.input_row.isVisibleTo(term)
    term.shell.start()                                    # offscreen'de görünürlük olayı gecikebilir
    assert _wait(app, lambda: term.shell.shell is not None and "PS " in term.shell.toPlainText())
    QTest.keyClicks(term.shell, "Write-Output ('evren' + 'kabuk')")
    QTest.keyClick(term.shell, Qt.Key_Return)
    assert _wait(app, lambda: "evrenkabuk" in term.shell.toPlainText().split("'kabuk')", 1)[-1])
    proc = term.shell.shell
    term.set_root(None)                                   # proje kapandı → kabuk kapanır, Günlük'e dönülür
    assert term.shell.shell is None and not proc.alive and term.stack.currentIndex() == 0
    assert not term.shell_btn.isEnabled()


def test_kabuk_yoksa_anlasilir_not(win, tmp_path, monkeypatch):
    app, w = win
    term = w.panel.terminal
    monkeypatch.setattr(ptyshell, "available", lambda: False)
    term.shell.root = str(tmp_path)
    term.shell.start()
    assert "kullanılamıyor" in term.shell.toPlainText() and term.shell.shell is None
