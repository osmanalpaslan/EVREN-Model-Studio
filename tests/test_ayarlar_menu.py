"""Ayarlar Claude Code tarzı menülere bölündü (kullanıcı isteği 2026-11-04, Madde 12a).

Korunan değişmezler: hiçbir ayar kaybolmadı (her alan bir menüde), ilgili ayar ilgili menüde, arama Türkçe
karakterden bağımsız bulur ve bulamayınca söyler, kaydedilen değer yeni açılışta okunur (R-03).
"""
from __future__ import annotations

import os

import pytest

# load_values/_collect'in kullandığı tüm alanlar → beklenen menü
BEKLENEN = {
    "default_model": "genel", "agent_mode": "genel", "send_enter": "genel", "ai_titles": "genel",
    "theme": "gorunum", "font_size": "gorunum", "compact_view": "gorunum", "simple_view": "gorunum",
    "show_reasoning": "gorunum",
    "key_input": "saglayicilar", "budget": "saglayicilar", "budget_enforce": "saglayicilar",
    "gateways": "saglayicilar",
    "plan_first": "ajan", "scope_check": "ajan", "project_map": "ajan", "learnings_suggest": "ajan",
    "suggest_project": "ajan", "auto_test_tools": "ajan", "edit_diag": "ajan", "test_check": "ajan", "plan_guard": "ajan",
    "tool_protocol": "ajan", "max_steps": "ajan", "cmd_timeout": "ajan", "output_limit": "ajan",
    "autopro_smart": "autopro", "autopro_probe": "autopro", "autopro_architect": "autopro",
    "auto_switch": "autopro", "quota_guard_turns": "autopro", "auto_resume": "autopro",
    "auto_compact": "baglam", "compact_percent": "baglam", "compact_max": "baglam", "compact_model": "baglam",
    "tavily_input": "web", "web_tools_chat": "web",
    "mcp_card": "baglayicilar",
    "install_mode": "bilgisayar", "data_dir": "bilgisayar", "game_card": "bilgisayar",
    "untrusted_list": "bilgisayar",
    "base_url": "ag", "announcement_url": "ag", "timeout": "ag", "stall": "ag", "retries": "ag",
    "streaming": "ag",
    "retention": "gizlilik", "gozlem_card": "gizlilik", "desktop_blocked": "bilgisayar",
}


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
    w.show_page("settings")
    yield app, w
    w.close()


def _kategori(page, widget) -> str:
    """Bileşenin bulunduğu menü sayfası."""
    for key, idx in page._page_index.items():
        sayfa = page.stack.widget(idx)
        if widget is sayfa or sayfa.isAncestorOf(widget):
            return key
    return ""


def test_her_ayar_bir_menude_ve_dogru_menude(win):
    _app, w = win
    page = w.pages["settings"]
    for attr, beklenen in BEKLENEN.items():
        assert _kategori(page, getattr(page, attr)) == beklenen, attr


def test_load_ve_collectteki_hicbir_alan_disarida_kalmadi(win):
    """Yeni bir ayar eklenip menüye konmazsa (sayfada kaybolursa) bu test yakalar."""
    import inspect
    import re

    _app, w = win
    page = w.pages["settings"]
    kaynak = inspect.getsource(type(page).load_values) + inspect.getsource(type(page)._collect)
    alanlar = set(re.findall(r"self\.([a-z_]+)\.(?:set|is|value|text|current|enabled|load|collect)", kaynak))
    alanlar -= {"ctx"}
    assert len(alanlar) >= 40
    eksik = [a for a in sorted(alanlar) if not _kategori(page, getattr(page, a))]
    assert not eksik, f"menüsüz ayar: {eksik}"


def test_menu_secince_yalniz_o_sayfa_gorunur(win):
    _app, w = win
    page = w.pages["settings"]
    page.open_category("web")
    assert page.current_category() == "web"
    assert page.tavily_input.isVisible() and not page.theme.isVisible()
    page.open_category("gorunum")
    assert page.theme.isVisible() and not page.tavily_input.isVisible()


def test_bos_menuler_gizli_dolu_menuler_gorunur(win):
    _app, w = win
    page = w.pages["settings"]
    for i, (key, *_r) in enumerate(page.CATEGORIES):
        dolu = page._page_cols[key].count() > 3
        assert page.nav.item(i).isHidden() == (not dolu), key


@pytest.mark.parametrize("sorgu, menu", [
    ("tema", "gorunum"), ("TEMA", "gorunum"), ("özet", "baglam"), ("ozet", "baglam"),
    ("tavily", "web"), ("İnternet", "web"), ("zaman aşımı", "ag"), ("güvenilmeyen", "bilgisayar"),
    ("bütçe", "saglayicilar"), ("bekçi", "ajan"),
])
def test_arama_ilgili_menuyu_bulur_ve_acar(win, sorgu, menu):
    _app, w = win
    page = w.pages["settings"]
    page.search.setText(sorgu)
    gorunen = [k for i, (k, *_r) in enumerate(page.CATEGORIES) if not page.nav.item(i).isHidden()]
    assert menu in gorunen
    assert page.current_category() in gorunen          # seçili menü sonuçlardan biri
    assert not page.no_match.isVisible()


def test_arama_bulamazsa_soyler_temizleyince_hepsi_doner(win):
    _app, w = win
    page = w.pages["settings"]
    page.search.setText("qqqzzz-yok")
    assert page.no_match.isVisible()
    assert all(page.nav.item(i).isHidden() for i in range(page.nav.count()))
    page.search.clear()
    assert not page.no_match.isVisible()
    dolu = [k for k, *_r in page.CATEGORIES if page._page_cols[k].count() > 3]
    gorunen = [k for i, (k, *_r) in enumerate(page.CATEGORIES) if not page.nav.item(i).isHidden()]
    assert gorunen == dolu


def test_menuden_kaydedilen_ayar_yeni_acilista_okunur(win):
    """R-03: başka menüdeki ayar da 'Kaydet' ile kaydedilir ve diskten okununca gelir."""
    _app, w = win
    page = w.pages["settings"]
    page.open_category("baglam")
    page.compact_percent.setValue(60)
    page.open_category("gorunum")                       # başka menüdeyken kaydet
    page.font_size.setValue(12)
    page.save_all()
    from evren_studio.config import ConfigStore

    again = ConfigStore(w.ctx.store.data_dir).load()
    assert again.auto_compact_percent == 60 and again.font_size == 12
