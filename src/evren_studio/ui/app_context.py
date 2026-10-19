"""Uygulama bağlamı: ayarlar, veritabanı, istemci fabrikası, kurtarma.

Tüm sayfalar bu tek nesneyi paylaşır; API anahtarı yalnızca
Windows Credential Manager'dan okunur ve bellekte tutulur.
"""
from __future__ import annotations

from pathlib import Path

from .. import __version__
from ..api.client import EvrenClient, ModelInfo
from ..api.providers import CATALOG, PROVIDERS, provider_of_model
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
    _m("auto", 262144, True, True),
]

# Kayıttaki değeri gerçek ölçümle çelişen EVREN modelleri (R-07):
# auto kaydı 32768 bağlam ve tools:false diyor; ancak 2026-10-16'da 108k token'lık
# istek kabul edildi (gemma-4-31b / qwen3.8-flash-next'e, ikisi de 262k, yönlendirdi)
# ve yerel araç çağrısı iki protokolde de çalıştı. docs/knowledge/MODEL_CAPABILITIES.md
MEASURED_OVERRIDES: dict[str, dict] = {
    # 2026-10-19: görselli istekte auto qwen3-vl-30b / gemma-4-31b'ye yönlendirdi ve doğru okudu
    "auto": {"context_length": 262144, "tools": True, "vision": True},
}


def apply_measured(m: ModelInfo) -> ModelInfo:
    o = MEASURED_OVERRIDES.get(m.id)
    if o and m.provider == "evren":
        if o.get("context_length"):
            m.context_length = o["context_length"]
        for cap in ("tools", "vision"):
            if cap in o:
                m.capabilities = {**(m.capabilities or {}), cap: o[cap]}
    return m


class AppContext:
    def __init__(self, settings: Settings | None = None):
        # config.json her zaman varsayılan veri klasöründe durur; böylece
        # kullanıcı veri klasörünü değiştirse bile ayarlar bulunabilir.
        self.store = ConfigStore(default_data_dir())
        self.settings = settings or self.store.load()
        # Eski mod anahtarları (onayli/otomatik) güvenli eşdeğerine çevrilir
        from ..agent.permissions import normalize_mode

        self.settings.agent_mode = normalize_mode(self.settings.agent_mode)
        self.db = Database(self.settings.resolved_data_dir() / "evren.db")
        self.recovery = RecoveryEngine(self.db, __version__)
        self._cached_key: str | None = None
        # Canlı liste gelene kadar belgelenmiş (2026-10-15) sohbet modelleri
        self.models: list[ModelInfo] = [apply_measured(m) for m in FALLBACK_MODELS]
        self.models_live = False
        self._model_listeners: list = []
        # Ücretli sağlayıcı modelleri: tarihli katalogdan (api/providers.py)
        self.paid_models: list[ModelInfo] = [
            ModelInfo(id=c.id, task="chat", modalities=["text", "image"], context_length=c.context,
                      default_max_output_tokens=c.max_output, capabilities={"tools": c.tools, "vision": c.vision},
                      prompt_token_price=c.price_in, completion_token_price=c.price_out, provider=c.provider)
            for c in CATALOG
        ]
        self._provider_keys: dict[str, str | None] = {}

    # ---- modeller -------------------------------------------------------

    def set_models(self, models: list[ModelInfo]) -> None:
        if not models:
            return
        self.models = [apply_measured(m) for m in models]
        self.models_live = True
        for cb in list(self._model_listeners):
            cb()

    def on_models_changed(self, callback) -> None:
        self._model_listeners.append(callback)

    def chat_models(self) -> list[ModelInfo]:
        """EVREN (canlı/yedek) + OpenAI + Anthropic sohbet modelleri."""
        return [m for m in self.models if m.supports_chat] + list(self.paid_models)

    def evren_chat_models(self) -> list[ModelInfo]:
        return [m for m in self.models if m.supports_chat]

    def model_info(self, model_id: str) -> ModelInfo | None:
        for m in list(self.models) + list(self.paid_models):
            if m.id == model_id:
                return m
        return None

    def provider_of(self, model_id: str) -> str:
        info = self.model_info(model_id)
        return info.provider if info is not None else provider_of_model(model_id)

    def resolve_protocol(self, model_id: str) -> str:
        """Ayar + model yeteneğine göre araç protokolü: 'native' veya 'text'."""
        pref = self.settings.tool_protocol
        if pref == "yerel":
            return "native"
        if pref == "metin":
            return "text"
        info = self.model_info(model_id)
        if info is not None and info.provider != "evren":
            return "native"     # OpenAI/Anthropic istemcileri yerel araç çağrısı kullanır
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

    # ---- ücretli sağlayıcılar ----------------------------------------------

    def provider_key(self, provider: str, refresh: bool = False) -> str | None:
        if provider == "evren":
            return self.api_key(refresh)
        if refresh or provider not in self._provider_keys:
            try:
                self._provider_keys[provider] = load_api_key(provider)
            except Exception:
                self._provider_keys[provider] = None
        return self._provider_keys[provider]

    def has_provider_key(self, provider: str) -> bool:
        return bool(self.provider_key(provider))

    def make_client_for(self, provider: str, log_sink=None):
        """Sağlayıcının istemcisi. EVREN için make_client (testler bunu değiştirir)."""
        if provider == "evren":
            return self.make_client(log_sink=log_sink)
        key = self.provider_key(provider)
        if not key:
            name = PROVIDERS[provider].name if provider in PROVIDERS else provider
            raise RuntimeError(f"{name} API anahtarı tanımlı değil. Ayarlar > Sağlayıcılar bölümünden girin.")
        timeout = max(self.settings.timeout_seconds, 180.0)
        if provider == "openai":
            from ..api.openai_client import OpenAIClient

            return OpenAIClient(key, timeout=timeout, max_retries=self.settings.max_retries, log_sink=log_sink)
        if provider == "anthropic":
            from ..api.anthropic_client import AnthropicClient

            return AnthropicClient(key, timeout=max(timeout, 300.0), max_retries=self.settings.max_retries,
                                   log_sink=log_sink)
        raise RuntimeError(f"Bilinmeyen sağlayıcı: {provider}")

    # ---- veri konumu ---------------------------------------------------------

    def data_dir(self) -> Path:
        return self.settings.resolved_data_dir()

    def save_settings(self) -> None:
        self.store.save(self.settings)

    def close(self) -> None:
        self.db.close()
