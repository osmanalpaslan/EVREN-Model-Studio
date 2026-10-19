"""Varsayılan model = auto (yönlendirici); kullanıcı değiştirebilir.

- Yeni kurulumda ve eski varsayılanı (glm-5.3) taşıyan eski config.json'da auto.
- Kullanıcının bilerek seçtiği başka model ve yeni sürüm dosyası korunur.
- auto için kayıttaki 32768/tools:false yerine ölçülen 262k + yerel araç.
"""
from __future__ import annotations

import json
import os
import time

import pytest

from evren_studio.api.client import ModelInfo
from evren_studio.config import SETTINGS_VERSION, ConfigStore, Settings, migrate_raw


def test_yeni_kurulum_varsayilani_auto():
    assert Settings().default_model == "auto"


def test_eski_varsayilan_auto_ya_tasinir(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"default_model": "glm-5.3", "theme": "açık"}),
                                          encoding="utf-8")
    s = ConfigStore(tmp_path).load()
    assert s.default_model == "auto" and s.theme == "açık"
    assert s.settings_version == SETTINGS_VERSION


@pytest.mark.parametrize("raw,expected", [
    ({"default_model": "deepseek-v4-flash"}, "deepseek-v4-flash"),          # bilerek seçilmiş
    ({"default_model": "glm-5.3", "settings_version": 2}, "glm-5.3"),       # yeni sürümde seçilmiş
    ({}, "auto"),
])
def test_kullanici_secimi_korunur(raw, expected):
    assert migrate_raw(dict(raw)).get("default_model", "auto") == expected


def test_kaydet_oku_dongusu_tekrar_tasimaz(tmp_path):
    store = ConfigStore(tmp_path)
    s = store.load()
    s.default_model = "glm-5.3"         # kullanıcı yeni sürümde glm-5.3 seçti
    store.save(s)
    assert ConfigStore(tmp_path).load().default_model == "glm-5.3"


def test_bozuk_veya_liste_config_guvenli(tmp_path):
    (tmp_path / "config.json").write_text("[1, 2]", encoding="utf-8")
    assert ConfigStore(tmp_path).load().default_model == "auto"


def test_auto_olculen_degerler(tmp_path, monkeypatch):
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path))
    from evren_studio.ui.app_context import AppContext

    ctx = AppContext(Settings(data_dir=str(tmp_path)))
    info = ctx.model_info("auto")
    assert info.context_length == 262144 and info.supports_tools
    # canlı listede kayıt değerleri gelse bile ölçülen değer uygulanır
    ctx.set_models([ModelInfo(id="auto", task="chat", modalities=["text"], context_length=32768,
                              default_max_output_tokens=16384, capabilities={"tools": False}),
                    ModelInfo(id="glm-5.3", task="chat", modalities=["text"], context_length=524288,
                              default_max_output_tokens=None, capabilities={"tools": True})])
    info = ctx.model_info("auto")
    assert info.context_length == 262144 and info.supports_tools
    assert ctx.resolve_protocol("auto") == "native"
    ctx.db.close()


@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
    yield app, w
    w.close()


def test_sohbet_ekrani_auto_ile_acilir_ve_degistirilebilir(win):
    app, w = win
    s = w.session
    s.new_session()
    assert s.model == "auto" and s.composer.model() == "auto"
    assert s.mode == "manuel"                                       # onay modu değişmedi
    assert s.composer.model_ids()[:2] == ["auto-pro", "auto"]       # Auto Pro en üstte, EVREN auto hemen altında
    s.composer.set_model("deepseek-v4-flash", emit=True)            # kullanıcı seçiciden değiştirir
    assert s.model == "deepseek-v4-flash" and s.composer.model() == "deepseek-v4-flash"


def test_son_secilen_motor_ve_mod_hatirlanir(win, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)
    app, w = win
    s = w.session
    s.new_session()
    s.composer.set_model("deepseek-v4-flash", emit=True)
    s.composer.set_mode("kabul", emit=True)
    s.new_session()                                                 # yeni oturum son seçimle açılır
    assert s.model == "deepseek-v4-flash" and s.mode == "kabul"
    assert s.composer.model() == "deepseek-v4-flash" and s.composer.mode() == "kabul"
    # uygulama yeniden açılınca da korunur (diskten okunur, R-03)
    loaded = ConfigStore(tmp_path / "data").load()
    assert loaded.default_model == "deepseek-v4-flash" and loaded.agent_mode == "kabul"
    # Ayarlar sayfası da güncel değeri gösterir
    page = w.pages["settings"]
    page.refresh()
    assert page.default_model.currentText() == "deepseek-v4-flash"
    assert page.agent_mode.currentData() == "kabul"
    # /model komutu da hatırlanır
    assert s._command("/model glm-5.3")
    assert ConfigStore(tmp_path / "data").load().default_model == "glm-5.3"


def test_anahtarsiz_ucretli_model_hatirlanmaz(win, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    app, w = win
    s = w.session
    s.new_session()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    s.set_model("gpt-6-luna")                                       # anahtar yok → reddedilir
    assert w.ctx.settings.default_model == "auto"
    assert ConfigStore(tmp_path / "data").load().default_model in ("auto",) or         not (tmp_path / "data" / "config.json").exists()


@pytest.mark.parametrize("raw,expected", [
    ({"settings_version": 2, "agent_max_steps": 40}, 80),     # eski varsayılan taşınır
    ({"settings_version": 2, "agent_max_steps": 25}, 25),     # kullanıcı seçimi korunur
    ({"settings_version": 2}, 80),
    ({"settings_version": 3, "agent_max_steps": 40}, 40),     # yeni sürümde bilerek 40 seçilmiş
])
def test_adim_siniri_tasima(raw, expected):
    assert migrate_raw(dict(raw)).get("agent_max_steps", 80) == expected
