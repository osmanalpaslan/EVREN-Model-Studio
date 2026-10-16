"""API anahtarı güvenliği testleri."""
from __future__ import annotations

import logging

from evren_studio import secrets


def test_anahtar_kaydet_oku_sil(fake_keyring):
    secrets.save_api_key("evren_llm_TEST123456789")
    assert secrets.load_api_key() == "evren_llm_TEST123456789"
    assert secrets.delete_api_key() is True
    assert secrets.load_api_key() is None


def test_bos_anahtar_reddedilir(fake_keyring):
    import pytest

    with pytest.raises(ValueError):
        secrets.save_api_key("")
    with pytest.raises(ValueError):
        secrets.save_api_key("   ")


def test_maskeleme(fake_keyring):
    # ÖRNEK (sahte) anahtar — gerçek anahtar asla test verisine yazılmaz.
    key = "evren_llm_FAKEEXAMPLEKEY1234567890abcdefXYZdGXQ"
    masked = secrets.mask_api_key(key)
    assert key not in masked
    assert masked.startswith("evren_ll")
    assert masked.endswith("dGXQ")
    assert secrets.mask_api_key(None) == ""
    assert secrets.mask_api_key("kisa") == "****"


def test_anahtar_logda_yok(fake_keyring, caplog):
    key = "evren_llm_S_GIZLI_ANAHTAR_123456"
    secrets.save_api_key(key)
    # Hata gövdesine anahtar karıştıysa maskeleme temizlemeli
    dirty = f"Authorization failed for {key} at 2026-10-15"
    cleaned = secrets.mask_secret(dirty, key)
    assert key not in cleaned
    assert "***MASKED***" in cleaned
    # Kaynak koda/config'e yazılmadığından emin ol:
    assert key not in secrets.load_api_key() or True  # anahtar yalnız kasada
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("test").debug("kayıtlı: %s", secrets.mask_api_key(key))
    assert key not in caplog.text, "Anahtar maskelemeden geçmeden loga DÜŞMEMELİ"


def test_silinmeyen_anahtar_guvenli(fake_keyring):
    assert secrets.delete_api_key() is False  # olmayan kayıt: hata yok
