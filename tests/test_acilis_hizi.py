"""Açılış hızı (2026-11-12 ölçümü: MainWindow() 1,10 → 0,19 sn; pencere görünene kadar ~1,7 → ~0,7 sn).

1. Sayfalar ilk açıldıklarında kurulur (görünmeyen Ayarlar/Yardım/... açılışta stillendirilmez). Modeller sayfası
   kurulurken model listesini ağdan çekiyordu — açılışta app.py zaten çekiyor: pencere kurulumu ağ isteği yapmaz.
2. Anahtar kasası Qt yüklenirken arka planda bir kez okunur (secrets.preload_keys); AppContext sonucu bir kez alır.
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.app_context import AppContext

    calls = []
    real = AppContext.make_client
    monkeypatch.setattr(AppContext, "make_client", lambda self, log_sink=None: calls.append(1) or real(self, log_sink))
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    app.processEvents()
    yield app, w, calls
    w.close()


def test_sayfalar_ilk_acilista_kurulur(win):
    from evren_studio.ui.settings_page import SettingsPage

    app, w, _calls = win
    assert len(w.page_keys) == 10 and "settings" in w.page_keys
    assert len(w.pages) == 0, "açılışta hiçbir sayfa kurulmaz"
    assert w.pages.get("monitor") is None                 # .get kurmaz (kapanış yolu)
    for key in w.page_keys:                               # tüm sayfaların düğmesi/menüsü yine kayıtlı
        if key in w.sidebar.nav_buttons:
            assert not w.sidebar.nav_buttons[key].isHidden(), key
    w.show_page("settings")
    page = w.pages["settings"]
    assert isinstance(page, SettingsPage) and w.center.currentWidget() is page
    assert list(w.pages) == ["settings"], "yalnız açılan sayfa kurulur"
    assert w.pages["settings"] is page, "ikinci kez kurulmaz"
    assert w.center.indexOf(page) >= 0 and w.center.count() == 2          # oturum + ayarlar
    w.show_page("yok-boyle-sayfa")                        # bilinmeyen anahtar sessizce yok sayılır
    with pytest.raises(KeyError):
        w.pages["yok-boyle-sayfa"]


def test_ayarlar_sinyalleri_gec_kurulumda_da_bagli(win):
    app, w, _calls = win
    seen = []
    w._settings_saved = lambda: seen.append("kaydet")      # örnek bağlantı: kurulumda bağlanır
    page = w.pages["settings"]
    page.settings_saved.emit()
    assert seen == ["kaydet"]


def test_pencere_kurulumu_ag_istegi_yapmaz(win):
    """Modeller sayfası kurulurken listeyi çeker; artık yalnız sayfa açılınca (açılışta app.py zaten çekiyor)."""
    app, w, calls = win
    assert calls == []
    w.show_page("models")
    assert len(calls) == 1


def test_kapanista_kurulmamis_izleme_sayfasi_sorun_cikarmaz(win):
    app, w, _calls = win
    w.close()
    assert w.pages.get("monitor") is None


def test_anahtar_onokuma_bir_kez_ve_dogru(fake_keyring):
    from evren_studio import secrets

    secrets.save_api_key("evren_llm_ONOKUMA_12345678")
    secrets.save_api_key("sk-ant-ONOKUMA-123456", "anthropic")
    assert secrets.take_preloaded() == {}, "başlatılmadıysa beklemeden boş döner"
    secrets.preload_keys()
    got = secrets.take_preloaded()
    assert got["evren"] == "evren_llm_ONOKUMA_12345678" and got["anthropic"] == "sk-ant-ONOKUMA-123456"
    assert got["openai"] is None
    assert secrets.take_preloaded() == {}, "sonuç bir kez alınır; modülde anahtar kalmaz"
    assert secrets._preload == {}


def test_appcontext_onokunan_anahtari_kullanir(tmp_path, monkeypatch, fake_keyring):
    from evren_studio import secrets
    from evren_studio.ui.app_context import AppContext

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    secrets.save_api_key("evren_llm_ONOKUMA_12345678")
    secrets.preload_keys()
    reads = []
    real = fake_keyring.get_password
    monkeypatch.setattr(fake_keyring, "get_password", lambda s, k: reads.append(k) or real(s, k))
    ctx = AppContext()
    try:
        assert ctx.api_key() == "evren_llm_ONOKUMA_12345678" and not ctx.has_provider_key("openai")
        assert reads == [], "önceden okunan anahtarlar kasadan yeniden okunmaz"
        ctx.has_provider_key("gw-ornek")                   # önceden okunmayan sağlayıcı normal yoldan okunur
        assert reads == ["gw-ornek_api_key"]
    finally:
        ctx.close()


def test_appcontext_onokumasiz_ve_anahtarsiz(tmp_path, monkeypatch, fake_keyring):
    """Tetiklenmeyen durum: önceden okuma yoksa (testler/araçlar) eski yol; kayıtlı anahtar yoksa '' (yok) kalır."""
    from evren_studio import secrets
    from evren_studio.ui.app_context import AppContext

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    ctx = AppContext()
    try:
        assert ctx._cached_key is None and not ctx.has_api_key()
    finally:
        ctx.close()
    secrets.preload_keys()                               # kasada anahtar yok
    ctx = AppContext()
    try:
        assert ctx._cached_key == "" and not ctx.has_api_key()
        secrets.save_api_key("evren_llm_YENI_123456789")  # Ayarlar'dan girildi → yenile ile görünür
        assert ctx.api_key(refresh=True) == "evren_llm_YENI_123456789"
    finally:
        ctx.close()


def test_uygulama_onokumayi_qt_yuklenmeden_baslatir():
    """app.main anahtar okumayı Qt ve arayüz modülleri yüklenmeden ÖNCE başlatır (aksi halde kazanç olmaz)."""
    import inspect

    from evren_studio import app as appmod

    src = inspect.getsource(appmod.main)
    assert "preload_keys()" in src
    assert src.index("preload_keys()") < src.index("from PySide6.QtWidgets import QApplication")
    assert src.index("preload_keys()") < src.index("from .ui.main_window import MainWindow")
