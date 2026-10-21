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


# Auto Pro: uygulama içi, sağlayıcıya duyarlı yönlendirici (agent/router.py). API'ye ASLA
# bu ad gitmez; her tur başında anahtarı olan sağlayıcıların gerçek bir modeline çevrilir.
AUTO_PRO_INFO = ModelInfo(id="auto-pro", task="chat", modalities=["text", "image"], context_length=1_048_576,
                          default_max_output_tokens=None, capabilities={"tools": True, "vision": True},
                          provider="evren")
AKILLI_INFO = AUTO_PRO_INFO          # eski ad
# Yapay zekâ çağrısında sıradaki modele geçmeyi gerektiren hatalar (kota/yetki hariç)
_AI_FAILOVER = {"sunucu_kullanılamıyor", "sunucu_hatası", "zaman_aşımı", "bulunamadı", "ağ_hatası",
                "geçersiz_istek"}


# `/v1/models` kaydında capabilities.reasoning_effort=true olanlar (2026-10-17, LOOP_ANALYSIS).
# Canlı liste alınamazsa yedek listeye de işlenir: kısa yapay zekâ işlerinde düşünme kapatılır.
REASONING_EFFORT_MODELS = {"deepseek-v4-flash", "deepseek-v4.1-flash", "qwen3.8-flash-next", "glm-5.3",
                           "mimo-v2.6-pro"}


def apply_measured(m: ModelInfo) -> ModelInfo:
    o = MEASURED_OVERRIDES.get(m.id)
    if o and m.provider == "evren":
        if o.get("context_length"):
            m.context_length = o["context_length"]
        for cap in ("tools", "vision"):
            if cap in o:
                m.capabilities = {**(m.capabilities or {}), cap: o[cap]}
    if m.provider == "evren" and m.id in REASONING_EFFORT_MODELS and "reasoning_effort" not in (m.capabilities or {}):
        m.capabilities = {**(m.capabilities or {}), "reasoning_effort": True}
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

    # ---- sağlayıcıya duyarlı model listesi (kullanıcı kararı 2026-10-19) ----
    # Yalnız anahtarı girilmiş sağlayıcıların modelleri görünür: yalnız OpenAI/Anthropic
    # girildiyse EVREN motorları (ve EVREN auto) görünmez. Hiç anahtar yoksa EVREN listesi
    # gösterilir (kullanıcı ücretsiz EVREN anahtarı girmeye yönlendirilir).

    def available_providers(self) -> set[str]:
        out = set()
        if self.has_api_key():
            out.add("evren")
        for p in ("openai", "anthropic"):
            if self.has_provider_key(p):
                out.add(p)
        return out

    def chat_models(self) -> list[ModelInfo]:
        """Auto Pro + anahtarı olan sağlayıcıların sohbet modelleri."""
        provs = self.available_providers()
        evren = [m for m in self.models if m.supports_chat] if ("evren" in provs or not provs) else []
        paid = [m for m in self.paid_models if m.provider in provs]
        return [AUTO_PRO_INFO] + evren + paid

    def evren_chat_models(self) -> list[ModelInfo]:
        """Gerçek EVREN sohbet modelleri (anahtar durumundan bağımsız)."""
        return [m for m in self.models if m.supports_chat]

    def available_model_ids(self) -> set[str]:
        """Auto Pro'nun seçebileceği gerçek modeller (anahtarı olan sağlayıcılar)."""
        provs = self.available_providers()
        ids = {m.id for m in self.models if m.supports_chat} if "evren" in provs else set()
        ids |= {m.id for m in self.paid_models if m.provider in provs}
        return ids

    def ai_route(self, role: str, reason: str = ""):
        """Uygulamanın kendi yapay zekâ işi veya Auto Pro turu için rota (router.choose)."""
        from ..agent import router

        health = {}
        try:
            health = {r["model"]: dict(r) for r in self.db.all_model_health()}
        except Exception:
            pass
        return router.choose(role, available=self.available_model_ids() or None, health=health, reason=reason)

    def ai_chat(self, role: str, messages: list[dict], max_tokens: int = 800,
                session_id: int | None = None, evren_only: bool = False) -> tuple[str, str]:
        """Uygulamanın kendi yapay zekâ işleri (özet hariç: özet akışlıdır) için tek giriş:
        rol → bağlı sağlayıcının uygun modeli; sunucu hatasında sıradaki yedek; ücretli
        modelde aylık bütçe dolduysa o model atlanır; ücretli maliyet kaydedilir.
        (içerik, kullanılan model) döndürür. Arka plan iş parçacığında çağrılır (R-04)."""
        from ..api.errors import ApiError
        from ..api.providers import estimate_cost
        from ..budget import current_state

        r = self.ai_route(role)
        chain = [m for m in [r.model] + r.fallbacks if m]
        if evren_only:                      # QA/MCP işleri: ücretli sağlayıcıya ASLA (kullanıcı kararı)
            chain = [m for m in chain if self.provider_of(m) == "evren"]
        if not chain:
            raise RuntimeError("Yapay zekâ işi için API anahtarı yok (Ayarlar)."
                               if not evren_only else "Bu iş yalnız EVREN ile yapılır: EVREN anahtarı gerekli.")
        last: Exception | None = None
        for model in chain:
            provider = self.provider_of(model)
            if provider != "evren":
                st = current_state(self.db, self.settings.monthly_budget_usd, self.settings.budget_enforce)
                if st.exceeded:
                    last = RuntimeError("aylık bütçe doldu")
                    continue
            try:
                client = self.make_client_for(provider)
            except RuntimeError as exc:
                last = exc
                continue
            # Kısa işlerde düşünmeyi kapat: EVREN düşünen modelleri küçük max_tokens bütçesini
            # tamamen düşünmeye harcayıp BOŞ içerik döndürüyordu (2026-10-19 gerçek ölçüm: başlık,
            # hata açıklaması ve commit mesajı üçü de boş). `reasoning_effort: none` deepseek'te
            # düşünmeyi 0'a indiriyor (LOOP_ANALYSIS "EVREN düşünme ayarı").
            kwargs = {}
            info = self.model_info(model)
            if provider == "evren" and info is not None and (info.capabilities or {}).get("reasoning_effort"):
                kwargs["extra_body"] = {"reasoning_effort": "none"}
            try:
                result = client.chat(model, messages, stream=False, max_tokens=max_tokens, **kwargs)
            except ApiError as exc:
                last = exc
                if exc.kind.value in _AI_FAILOVER:
                    continue
                raise
            finally:
                close = getattr(client, "close", None)
                if close:
                    close()
            if provider != "evren":
                usage = result.token_usage() if hasattr(result, "token_usage") else {}
                try:
                    self.db.add_usage_cost(provider, model, usage, estimate_cost(model, usage), session_id)
                except Exception:
                    pass
            text = (result.content or "").strip()
            if not text:                     # yine boşsa (düşünme bütçesi) sıradaki model
                last = RuntimeError(f"{model} boş yanıt verdi")
                continue
            return text, model
        raise last or RuntimeError("yapay zekâ işi yapılamadı")

    def model_info(self, model_id: str) -> ModelInfo | None:
        from ..agent import router

        if router.is_auto_pro(model_id):
            return AUTO_PRO_INFO
        for m in list(self.models) + list(self.paid_models):
            if m.id == model_id:
                return m
        return None

    def provider_of(self, model_id: str) -> str:
        from ..agent import router

        if router.is_auto_pro(model_id):
            # Auto Pro'nun "sağlayıcısı": anahtar denetimi için EVREN varsa EVREN, yoksa ilk ücretli
            provs = self.available_providers()
            return "evren" if ("evren" in provs or not provs) else sorted(provs)[0]
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

    # ---- uzun işler (agent/jobs.py) ----------------------------------------------------

    @property
    def jobs(self):
        """Uygulama boyunca tek uzun iş yöneticisi (işler oturum/tur bitince kapanmaz)."""
        if getattr(self, "_jobs", None) is None:
            from ..agent.jobs import JobManager

            self._jobs = JobManager(self.settings.resolved_data_dir() / "jobs")
        return self._jobs

    # ---- MCP sunucuları (agent/mcp.py) ----------------------------------------------

    @property
    def mcp(self):
        """Uygulama boyunca tek MCP yöneticisi (sunucu süreçleri proje başına tutulur)."""
        if getattr(self, "_mcp", None) is None:
            from ..agent.mcp import McpManager

            self._mcp = McpManager(self.settings.resolved_data_dir())
        return self._mcp

    def mcp_configs(self) -> list:
        from ..agent.mcp import configs_from_settings

        if not self.settings.mcp_enabled:
            return []
        return [c for c in configs_from_settings(self.settings.mcp_servers) if c.enabled]

    def mcp_toolset(self, project_root, message: str = "", provider: str = "evren", status=None):
        """Ajan turu için tembel araç kümesi; gerekmiyorsa None (davranış değişmez).

        - Yalnız EVREN modellerinde (kullanıcı kararı 2026-10-19: uygulamanın amacı ücretsiz
          hizmet; ücretli sağlayıcıyla MCP KESİNLİKLE çalışmaz).
        - Sunucu yalnız gerektiği projede/görevde sunulur (McpServerConfig.when) ve ilk araç
          çağrısında, ajanın ARKA PLAN iş parçacığında açılır (R-04)."""
        if provider != "evren":
            return None
        configs = self.mcp_configs()
        if not configs or project_root is None:
            return None
        from ..agent.mcp import LazyToolset

        return LazyToolset(lambda: self.mcp.toolset(configs, Path(project_root), message, status))

    def close(self) -> None:
        if getattr(self, "_jobs", None) is not None:
            self._jobs.stop_all()
        if getattr(self, "_mcp", None) is not None:
            self._mcp.close_all()
        self.db.close()
