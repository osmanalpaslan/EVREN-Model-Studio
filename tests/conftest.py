"""Test ortak yardımcıları."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class FakeKeyring:
    """Bellek içi sahte keyring (Windows Credential Manager taklidi)."""

    def __init__(self):
        self.store: dict[tuple[str, str], str] = {}

    def set_password(self, service, key, value):
        self.store[(service, key)] = value

    def get_password(self, service, key):
        return self.store.get((service, key))

    def delete_password(self, service, key):
        if (service, key) not in self.store:
            import keyring.errors

            raise keyring.errors.PasswordDeleteError("olmayan kayıt")
        self.store.pop((service, key))


@pytest.fixture(autouse=True)
def _gercek_program_kurulumu_yok(monkeypatch):
    """Testler bilgisayara ASLA gerçek program kurmaz (ortam denetimi, winget/npm).

    Kurulumu deneyen test kendi sahte install'ını verir; verilmezse bu kilit
    başarısız sonuç döndürür.
    """
    from evren_studio.agent import environment

    def _blocked(key, *a, **k):
        return environment.InstallResult(key, False, "", "testte gerçek kurulum kapalı")

    monkeypatch.setattr(environment, "install", _blocked)
    yield


@pytest.fixture(autouse=True)
def _token_kalibrasyonu_temiz():
    """runner._CALIB süreç geneli; bir testin sahte `usage` değeri diğerinin bağlam hesabını değiştirmesin."""
    from evren_studio.agent import runner

    runner._CALIB.clear()
    yield
    runner._CALIB.clear()


@pytest.fixture(autouse=True)
def _yapay_zeka_basligi_kapali(monkeypatch):
    """Otomatik oturum başlığı ilk yanıttan sonra EK bir model çağrısı yapar; sahte istemcilerin
    sıralı yanıtlarını kaydırmasın. Özelliğin kendisi test_auto_pro.py'de açıkça sınanır."""
    monkeypatch.setenv("EVREN_STUDIO_NO_AI_TITLE", "1")


@pytest.fixture(autouse=True)
def _yoklama_kapali(monkeypatch):
    """A8 hafif yoklama gerçek EVREN'e istek atar; testlerde otomatik tetiklenmesin (anahtar bu bilgisayarda
    kayıtlı olabilir). Yoklamanın kendisi test_autopro_akilli.py'de sahte istemciyle `force=True` sınanır."""
    monkeypatch.setenv("EVREN_STUDIO_NO_PROBE", "1")
    # E6 ders önerisi de ek model çağrısı yapar (yalnız sinyal varsa); learnings testleri açıkça sınar
    monkeypatch.setenv("EVREN_STUDIO_NO_LEARNINGS", "1")


@pytest.fixture(autouse=True)
def _qt_pencere_temizligi():
    """Her testten sonra açık kalan Qt pencerelerini gerçekten yok eder.

    Kapatılan ama silinmeyen pencereler (zamanlayıcılar, dosya izleyicileri)
    tam test paketinde birikip her yeni pencerenin açılışını yavaşlatıyordu.
    """
    yield
    try:
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return
    app = QApplication.instance()
    if app is None:
        return
    for w in app.topLevelWidgets():
        w.close()
        w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


@pytest.fixture()
def fake_keyring():
    from evren_studio import secrets

    fake = FakeKeyring()
    secrets._set_backend(fake)
    yield fake
    secrets._set_backend(None)
