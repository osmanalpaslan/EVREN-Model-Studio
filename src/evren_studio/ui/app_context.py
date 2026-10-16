"""Uygulama bağlamı: ayarlar, veritabanı, istemci fabrikası, kurtarma.

Tüm sayfalar bu tek nesneyi paylaşır; API anahtarı yalnızca
Windows Credential Manager'dan okunur ve bellekte tutulur.
"""
from __future__ import annotations

from pathlib import Path

from .. import __version__
from ..api.client import EvrenClient
from ..config import ConfigStore, Settings
from ..db import Database
from ..recovery import RecoveryEngine
from ..secrets import load_api_key, mask_api_key


class AppContext:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.store = ConfigStore(self.settings.resolved_data_dir())
        self.db = Database(self.settings.resolved_data_dir() / "evren.db")
        self.recovery = RecoveryEngine(self.db, __version__)
        self._cached_key: str | None = None

    # ---- API anahtarı ---------------------------------------------------

    def api_key(self, refresh: bool = False) -> str | None:
        if self._cached_key is None or refresh:
            self._cached_key = load_api_key()
        return self._cached_key

    def masked_key(self) -> str:
        return mask_api_key(self.api_key())

    # ---- istemci -----------------------------------------------------------

    def make_client(self, log_sink=None) -> EvrenClient:
        key = self.api_key()
        if not key:
            raise RuntimeError(
                "API anahtarı tanımlı değil. Ayarlar > API Anahtarı bölümünden "
                "girin. Anahtar Windows Credential Manager'da saklanır."
            )
        return EvrenClient(
            base_url=self.settings.base_url,
            api_key=key,
            timeout=self.settings.timeout_seconds,
            max_retries=self.settings.max_retries,
            log_sink=log_sink,
        )

    def has_api_key(self) -> bool:
        return bool(self.api_key())

    # ---- veri konumu ---------------------------------------------------------

    def data_dir(self) -> Path:
        return self.settings.resolved_data_dir()

    def save_settings(self) -> None:
        self.store.save(self.settings)

    def close(self) -> None:
        self.db.close()
