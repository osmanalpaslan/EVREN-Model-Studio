"""Uygulama bağlamı: ayarlar, veritabanı, istemci fabrikası, kurtarma.

Tüm sayfalar bu tek nesneyi paylaşır; API anahtarı yalnızca
Windows Credential Manager'dan okunur ve bellekte tutulur.
"""
from __future__ import annotations

from pathlib import Path

from .. import __version__
from ..api.client import EvrenClient, ModelInfo
from ..config import ConfigStore, Settings, default_data_dir
from ..db import Database
from ..recovery import RecoveryEngine
from ..secrets import load_api_key, mask_api_key


def _m(mid: str, ctx: int, tools: bool, vision: bool = False, task: str = "chat") -> ModelInfo:
    return ModelInfo(id=mid, task=task, modalities=["text"] + (["image"] if vision else []),
                     context_length=ctx, default_max_output_tokens=None,
                     capabilities={"tools": tools, "vision": vision})


# Kaynak: docs/knowledge/MODEL_CAPABILITIES.md (canlı liste alınamazsa kullanılır)
FALLBACK_MODELS = [
    _m("glm-5.3", 524288, True),
    _m("deepseek-v4.1-flash", 1048576, True, True),
    _m("deepseek-v4-flash", 1048576, True),
    _m("mimo-v2.6-pro", 1048576, True, True),
    _m("qwen3.8-flash-next", 262144, True, True),
    _m("gemma-4-31b", 262144, True, True),
    _m("qwen3-vl-30b", 262144, True, True, "vision_chat"),
    _m("auto", 32768, False),
]


class AppContext:
    def __init__(self, settings: Settings | None = None):
        # config.json her zaman varsayılan veri klasöründe durur; böylece
        # kullanıcı veri klasörünü değiştirse bile ayarlar bulunabilir.
        self.store = ConfigStore(default_data_dir())
        self.settings = settings or self.store.load()
        self.db = Database(self.settings.resolved_data_dir() / "evren.db")
        self.recovery = RecoveryEngine(self.db, __version__)
        self._cached_key: str | None = None
        # Canlı liste gelene kadar belgelenmiş (2026-10-15) sohbet modelleri
        self.models: list[ModelInfo] = list(FALLBACK_MODELS)
        self.models_live = False
        self._model_listeners: list = []

    # ---- modeller -------------------------------------------------------

    def set_models(self, models: list[ModelInfo]) -> None:
        if not models:
            return
        self.models = list(models)
        self.models_live = True
        for cb in list(self._model_listeners):
            cb()

    def on_models_changed(self, callback) -> None:
        self._model_listeners.append(callback)

    def chat_models(self) -> list[ModelInfo]:
        return [m for m in self.models if m.supports_chat]

    def model_info(self, model_id: str) -> ModelInfo | None:
        for m in self.models:
            if m.id == model_id:
                return m
        return None

    def resolve_protocol(self, model_id: str) -> str:
        """Ayar + model yeteneğine göre araç protokolü: 'native' veya 'text'."""
        pref = self.settings.tool_protocol
        if pref == "yerel":
            return "native"
        if pref == "metin":
            return "text"
        info = self.model_info(model_id)
        if info is not None and not info.supports_tools:
            return "text"
        return "native"

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
