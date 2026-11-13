"""OpenAI uyumlu (Chat Completions) ağ geçidi istemcisi: OpenRouter, Kilo, yerel/özel sunucular.

Neden (kullanıcı, 2026-11-01): "bütün motor girişlerini veya bir apide kilo gibi birden fazla motor var ise
ekleyeceğimiz daha minimal bir api anahtarı tasarımı". EVREN istemcisi zaten OpenAI uyumlu; burada yalnız
farklar ele alınır:
- Adres `/v1` ile bitmeyebilir (Kilo: `https://api.kilo.ai/api/gateway`); yollar buna göre kurulur.
- Uygulama içinde model kimliği `<sağlayıcı>::<model>` (ör. `gw-openrouter::anthropic/claude-sonnet-5.5`);
  istekte ön ek kaldırılır. Böylece iki ağ geçidindeki aynı model adı karışmaz.
- EVREN'e özgü uçlar (kota, şartlar) yoktur.
Gerçek anahtarla DOĞRULANMADI (R-17): arayüz "doğrulanmadı" der; ücretli istek testte yapılmaz.
"""
from __future__ import annotations

from typing import Any

from .client import ChatResult, EvrenClient, ModelInfo
from .errors import ApiError, ErrorKind

SEP = "::"


def split_model(model_id: str) -> tuple[str, str]:
    """`gw-x::vendor/model` → ("gw-x", "vendor/model"); ön eksiz → ("", model_id)."""
    if SEP in (model_id or ""):
        pid, _, real = model_id.partition(SEP)
        return pid, real
    return "", model_id


def join_model(provider_id: str, model: str) -> str:
    return f"{provider_id}{SEP}{model}"


class CompatClient(EvrenClient):
    def __init__(self, base_url: str, api_key: str, provider_id: str, **kw: Any):
        raw = (base_url or "").rstrip("/")
        self._has_v1 = raw.endswith("/v1")
        super().__init__(raw, api_key, **kw)
        if not self._has_v1:
            self.base_url = raw            # yollar "/chat/completions" olarak eklenecek
        self.provider_id = provider_id

    def _request(self, method: str, path: str, **kw: Any):
        if not self._has_v1 and path.startswith("/v1/"):
            path = path[3:]
        return super()._request(method, path, **kw)

    def _headers(self, auth: bool) -> dict[str, str]:
        # Anahtarsız (yerel Ollama/LM Studio, herkese açık liste) istekte kimlik başlığı GÖNDERİLMEZ: eskiden
        # "Bearer yok" gidiyordu; Vercel AI Gateway bunu reddetti (2026-11-12 gerçek deneme), başlıksız istek 200.
        return super()._headers(auth and bool((self.api_key or "").strip()))

    def list_models(self) -> list[ModelInfo]:
        out = []
        for m in super().list_models():
            m.id = join_model(self.provider_id, m.id)
            m.provider = self.provider_id
            m.task = m.task or "chat"
            out.append(m)
        return out

    def chat(self, model: str, messages: list[dict[str, Any]], **kw: Any) -> ChatResult:
        _pid, real = split_model(model)
        res = super().chat(real, messages, **kw)
        res.model = model
        return res

    def get_quota(self):
        raise ApiError(ErrorKind.NOT_FOUND, "Bu sağlayıcıda kota ucu yok (yalnız EVREN).", status=404)
