"""Ayarlar > MCP kartı ve oturumun MCP araç kümesi (sahte sunucu, gerçek ağ/kurulum yok)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from evren_studio.agent import mcp

FAKE = str(Path(__file__).with_name("fake_mcp_server.py"))


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


def _fake_serena_installed(data_dir: Path) -> None:
    b = mcp.serena_bin(data_dir)
    b.mkdir(parents=True, exist_ok=True)
    for n in ("serena.exe", "uvx.exe") if os.name == "nt" else ("serena", "uvx"):
        (b / n).write_text("", encoding="utf-8")
    (mcp.serena_dir(data_dir) / "hazir.txt").write_text("test", encoding="utf-8")


def test_varsayilan_mcp_yok_ve_oturum_arac_kumesi_none(win, tmp_path):
    _app, w = win
    assert w.ctx.settings.mcp_servers == []
    assert w.ctx.mcp_toolset(tmp_path) is None                         # davranış değişmez


def test_serena_kurulu_degilken_etkinlestirilemez(win):
    _app, w = win
    card = w.pages["settings"].mcp_card
    card.load(w.ctx.settings)
    assert card.serena_install.isVisibleTo(card) and not card.serena_toggle.isEnabled()
    assert "Kurulu değil" in card.serena_status.text()


def test_serena_etkinlestirme_kaydedilir_ve_acilista_okunur(win, tmp_path):
    _app, w = win
    data = w.ctx.settings.resolved_data_dir()
    _fake_serena_installed(data)
    card = w.pages["settings"].mcp_card
    card.load(w.ctx.settings)
    assert card.serena_toggle.isEnabled() and not card.serena_install.isVisibleTo(card)
    card.serena_toggle.setChecked(True)
    saved = w.ctx.settings.mcp_servers
    assert saved and saved[0]["name"] == "serena" and saved[0]["enabled"] is True
    assert saved[0]["read_only_tools"] == mcp.SERENA_TOOLS
    # R-03: yeni bir bağlam aynı dosyadan okuyunca ayar gelir
    from evren_studio.config import ConfigStore

    again = ConfigStore(w.ctx.store.data_dir).load()
    assert again.mcp_servers[0]["name"] == "serena" and again.mcp_enabled is True
    # kapatınca araç kümesi yok
    card.serena_toggle.setChecked(False)
    assert w.ctx.mcp_toolset(tmp_path) is None


def test_elle_sunucu_eklenir_oturum_araclari_gercek_surecten_gelir(win, tmp_path, monkeypatch):
    _app, w = win
    card = w.pages["settings"].mcp_card
    from evren_studio.ui import mcp_settings

    class Dlg:
        def __init__(self, *_a):
            pass

        def exec(self):
            return mcp_settings.QDialog.Accepted

        def config(self):
            return mcp.McpServerConfig(name="sahte", command=sys.executable, args=[FAKE],
                                       read_only_tools=["topla"], startup_timeout=20)
    monkeypatch.setattr(mcp_settings, "ServerDialog", Dlg)
    card.add_server()
    assert card.list.count() == 1 and "sahte" in card.list.item(0).text()
    lazy = w.ctx.mcp_toolset(tmp_path)
    assert lazy is not None
    assert "mcp__sahte__topla" in {s.name for s in lazy.specs()}       # ilk kullanımda başlatıldı
    assert lazy.call("mcp__sahte__topla", {"a": 1, "b": 2})[0].startswith("Toplam: 3")
    # ana anahtar kapalı → hiçbir sunucu kullanılmaz
    card.enabled.setChecked(False)
    card._save()
    assert w.ctx.mcp_toolset(tmp_path) is None
    card.enabled.setChecked(True)
    card.list.setCurrentRow(0)
    card.remove_selected()
    assert w.ctx.settings.mcp_servers == []


def test_varsayilanlara_donus_sunuculari_korur(win):
    from evren_studio.ui.settings_page import PRESERVED_ON_RESET

    assert "mcp_servers" in PRESERVED_ON_RESET


def test_sunucu_diyalogu_argumanlari_ayirir(win):
    from evren_studio.ui.mcp_settings import ServerDialog

    d = ServerDialog()
    d.name.setText("play wright")
    d.command.setText("npx")
    d.args.setText('@playwright/mcp@0.0.40 --isolated --output-dir "C:/a b"')
    d.read_only.setText("browser_snapshot, ")
    cfg = d.config()
    assert cfg.name == "play_wright" and cfg.args == ["@playwright/mcp@0.0.40", "--isolated", "--output-dir", "C:/a b"]
    assert cfg.read_only_tools == ["browser_snapshot"]
    d.command.setText("")
    assert d.config() is None


def test_proje_yokken_project_argumani_atlanir(tmp_path):
    argv = mcp.serena_config().argv(None, tmp_path)
    assert "--project" not in argv and "{proje}" not in " ".join(argv)
    env = mcp.serena_config().environment(None, tmp_path)
    assert env["UV_CACHE_DIR"].startswith(str(mcp.serena_dir(tmp_path)))
    assert env["PATH"].startswith(str(mcp.serena_bin(tmp_path)))
