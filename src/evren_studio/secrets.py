"""API anahtarı güvenli saklama ve maskeleme.

Anahtar yalnızca Windows Credential Manager'da (keyring) tutulur.
Kayıt adı: ``EVREN-Model-Studio`` / ``evren_api_key`` (bkz. docs/SECURITY.md).
Kasa kullanılamazsa düz metne SESSİZCE GEÇİLMEZ; hata yukarı iletilir.
"""
from __future__ import annotations

import re
from typing import Any

SERVICE_NAME = "EVREN-Model-Studio"
KEY_NAME = "evren_api_key"
# Sağlayıcı başına Credential Manager kayıt adı (hepsi aynı SERVICE_NAME altında)
KEY_NAMES = {
    "evren": KEY_NAME,
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "tavily": "tavily_api_key",          # web araması (agent/websearch.py); model sağlayıcısı değil
}
MASK_TOKEN = "***MASKED***"

# Metin içinde geçebilecek EVREN anahtarları ve Bearer başlıkları
_KEY_PATTERN = re.compile(
    r"evren_llm_[A-Za-z0-9_\-]{6,}"          # EVREN
    r"|sk-ant-[A-Za-z0-9_\-]{8,}"            # Anthropic (sk-ant-api03-…, sk-ant-admin01-…)
    r"|sk-(?:proj-|admin-|svcacct-)?[A-Za-z0-9_\-]{16,}"  # OpenAI
    r"|tvly-[A-Za-z0-9_\-]{8,}"              # Tavily
)
_HEADER_PATTERN = re.compile(r"(x-api-key[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9_\-\.]{6,}", re.IGNORECASE)
_BEARER_PATTERN = re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{6,}", re.IGNORECASE)

# Testlerde sahte kasa enjekte etmek için; None → gerçek keyring
_backend: Any = None


def _set_backend(backend: Any) -> None:
    """Keyring arka ucunu değiştirir (yalnızca testler için)."""
    global _backend
    _backend = backend


def _kr() -> Any:
    if _backend is not None:
        return _backend
    import keyring

    return keyring


def _key_name(provider: str) -> str:
    if provider not in KEY_NAMES:
        raise ValueError(f"Bilinmeyen sağlayıcı: {provider}")
    return KEY_NAMES[provider]


def save_api_key(key: str, provider: str = "evren") -> None:
    """Anahtarı Credential Manager'a yazar. Boş anahtar reddedilir."""
    key = (key or "").strip()
    if not key:
        raise ValueError("API anahtarı boş olamaz.")
    _kr().set_password(SERVICE_NAME, _key_name(provider), key)


def load_api_key(provider: str = "evren") -> str | None:
    """Kayıtlı anahtarı döndürür; yoksa None."""
    value = _kr().get_password(SERVICE_NAME, _key_name(provider))
    return value or None


def delete_api_key(provider: str = "evren") -> bool:
    """Anahtarı siler. Kayıt yoksa False döner, hata fırlatmaz."""
    import keyring.errors

    try:
        _kr().delete_password(SERVICE_NAME, _key_name(provider))
    except keyring.errors.PasswordDeleteError:
        return False
    return True


def mask_api_key(key: str | None) -> str:
    """Ekranda gösterim için maskeler: ``evren_ll...dGXQ``."""
    if not key:
        return ""
    if len(key) < 16:
        return "****"
    return f"{key[:8]}...{key[-4:]}"


def mask_secret(text: str, key: str | None = None) -> str:
    """Metindeki anahtar/token izlerini ``***MASKED***`` ile değiştirir."""
    if not text:
        return text
    if key:
        text = text.replace(key, MASK_TOKEN)
    text = _KEY_PATTERN.sub(MASK_TOKEN, text)
    text = _HEADER_PATTERN.sub(lambda m: m.group(1) + MASK_TOKEN, text)
    text = _BEARER_PATTERN.sub(lambda m: m.group(1) + MASK_TOKEN, text)
    return text
