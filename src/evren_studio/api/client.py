"""EVREN LLM API istemcisi.

Doğrulanmış uç noktalar (bkz. docs/knowledge/API_COMPATIBILITY.md):
- GET  /healthz, /readyz            (kimlik doğrulamasız)
- GET  /v1/models                   (anahtar gerekli)
- POST /v1/chat/completions         (stream=true → text/event-stream)
- GET  /v1/quota
- GET  /v1/requests/{id}            (belirsiz sonuç sorgusu)
- GET  /v1/terms/status | /text     (şart metni)

Davranış kuralları:
- 429/5xx: Retry-After varsa uyulur (≤300 sn); yoksa 5/10/20 sn artan bekleme.
  Varsayılan en fazla 3 otomatik tekrar.
- Zaman aşımı (istek gönderildikten sonra) ve akış kopması: otomatik tekrar
  YOK — sonuç belirsizdir, kullanıcıya durum sorgusu sunulur.
- Tüm hata gövdeleri anahtar maskelenerek işlenir.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from .. import __version__
from ..secrets import mask_secret
from .errors import (
    RETRYABLE_KINDS,
    ApiError,
    ErrorKind,
    backoff_seconds,
    classify_status,
    error_from_httpx,
    parse_retry_after,
)
from .images import expand_chat_images

USER_AGENT = f"EVREN-Model-Studio/{__version__}"

# Retry-After bu süreden uzunsa bekleme yerine kullanıcıya bildirilir.
MAX_RETRY_AFTER_SLEEP = 300.0


@dataclass
class ChatResult:
    content: str = ""
    reasoning: str = ""
    model: str = ""
    request_id: str | None = None
    routed_model: str | None = None
    finish_reason: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    # Yerel araç çağrıları: [{"id", "name", "arguments" (JSON metni)}]
    tool_calls: list[dict[str, str]] = field(default_factory=list)
    # Sağlayıcıya özel, sonraki istekte AYNEN geri gönderilmesi gereken durum
    # (OpenAI şifreli reasoning öğeleri, Anthropic thinking blokları). Ajan
    # bunu mesaj meta'sında saklar; to_api_messages "_provider_state" olarak taşır.
    provider_state: dict[str, Any] = field(default_factory=dict)
    # Akışta isteğin gönderilmesinden ilk parçaya (içerik, düşünme veya araç) kadar geçen süre (sn).
    # Auto Pro gerçek kullanım kaydı (A1) için; akışsız istekte None.
    first_chunk_s: float | None = None

    def token_usage(self) -> dict[str, int]:
        return normalize_usage(self.usage)


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, int]:
    """Sağlayıcıdan bağımsız kullanım: input_tokens, output_tokens, cached_tokens.

    Chat Completions (prompt_tokens/completion_tokens), Responses
    (input_tokens/output_tokens, input_tokens_details.cached_tokens) ve
    Anthropic (input_tokens/output_tokens/cache_read_input_tokens) biçimlerini tanır.
    """
    u = usage or {}
    inp = u.get("input_tokens", u.get("prompt_tokens")) or 0
    out = u.get("output_tokens", u.get("completion_tokens")) or 0
    details = u.get("input_tokens_details") or u.get("prompt_tokens_details") or {}
    cached = details.get("cached_tokens") or u.get("cache_read_input_tokens") or 0
    # Anthropic'te input_tokens önbellekli/yazılan kısmı İÇERMEZ; toplam girdiye ekle
    if "cache_read_input_tokens" in u or "cache_creation_input_tokens" in u:
        inp = inp + (u.get("cache_read_input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
    return {"input_tokens": int(inp), "output_tokens": int(out), "cached_tokens": int(cached)}


def strip_internal(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """'_' ile başlayan iç alanları (ör. _provider_state) API'ye göndermeden siler."""
    return [{k: v for k, v in m.items() if not k.startswith("_")} for m in messages]


@dataclass
class ModelInfo:
    id: str
    task: str
    modalities: list[str]
    context_length: int | None
    default_max_output_tokens: int | None
    capabilities: dict[str, Any]
    free_until: str | None = None
    prompt_token_price: float | None = None
    completion_token_price: float | None = None
    provider: str = "evren"

    @property
    def supports_chat(self) -> bool:
        return self.task in ("chat", "vision_chat")

    @property
    def supports_stream(self) -> bool:
        return self.supports_chat

    @property
    def supports_tools(self) -> bool:
        return bool(self.capabilities.get("tools"))

    @property
    def supports_vision(self) -> bool:
        return bool(self.capabilities.get("vision")) or "image" in self.modalities


@dataclass
class QuotaInfo:
    used_tokens: int | None
    cap: int | None
    window_minutes: int | None
    reset_at: str | None
    usage_ratio: float | None
    level: str
    held_cr: str
    remaining_cr: str
    daily_used_tokens: int | None
    daily_limit_tokens: int | None
    daily_remaining_tokens: int | None
    daily_reset_at: str | None


class CancelToken:
    """Kullanıcı iptali için basit işaret bayrağı (thread-safe)."""

    def __init__(self):
        import threading

        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()


class EvrenClient:
    """Senkron EVREN API istemcisi (arayüzde QThread içinden çağrılır).

    Akış yanıtlarının okunabilmesi için httpx.Client istek başına değil,
    istemci yaşam boyunca tutulur; close() ile kapatılır.
    """

    def __init__(self, base_url: str, api_key: str, timeout: float = 120.0,
                 max_retries: int = 3, log_sink: Callable[[str], None] | None = None,
                 transport: httpx.BaseTransport | None = None,
                 stream_idle_timeout: float | None = None):
        # Kullanıcı "/v1" ile biten adres verebilir; yollar resmî OpenAPI
        # şemasındaki gibi "/v1/models" biçimindedir. Kök adresi normalize et.
        root = base_url.rstrip("/")
        if root.endswith("/v1"):
            root = root[: -len("/v1")]
        self.base_url = root
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self._log = log_sink or (lambda msg: None)
        self._client: httpx.Client | None = None
        self._transport = transport  # birim testler için MockTransport enjeksiyonu
        # Akışlı istekte ilk parça gelmezse veya akış bu kadar saniye susarsa model "yanıt vermiyor"
        # sayılır ve TIMEOUT yükselir → ajan yedek modele geçer (Auto Pro A2, 2026-10-24). None → yalnız
        # genel zaman aşımı (eskiden sessiz akış 120 sn sonra UNKNOWN_RESULT ile turu bitiriyordu).
        self.stream_idle_timeout = stream_idle_timeout

    # ---- yaşam döngüsü --------------------------------------------------

    def _http(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=self.timeout, verify=True, follow_redirects=True,
                transport=self._transport,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            self._client.close()

    # ---- düşük seviye ------------------------------------------------------

    def _headers(self, auth: bool) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        if auth:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _mask(self, text: str) -> str:
        return mask_secret(text, self.api_key)

    def _to_api_error(self, resp: httpx.Response, operation: str,
                      model: str | None) -> ApiError:
        """Hata yanıtını (gövdesi okunarak) ApiError'a çevirir."""
        path = ""
        if resp.request is not None and resp.request.url is not None:
            path = resp.request.url.path
        try:
            if not resp.is_stream_consumed and not resp.is_closed:
                resp.read()
            body_text = resp.text
        except Exception:
            body_text = ""
        try:
            body = json.loads(body_text) if body_text else {}
        except json.JSONDecodeError:
            body = {}
        if not isinstance(body, dict):
            body = {}

        err_detail = body.get("detail")
        message = ""
        if isinstance(err_detail, str):
            message = err_detail
        elif isinstance(err_detail, list):
            parts = []
            for d in err_detail:
                if isinstance(d, dict):
                    parts.append(str(d.get("msg", "")))
            message = "; ".join(p for p in parts if p)
        if not message:
            message = str(body.get("error") or body.get("message") or body_text or "")
        message = self._mask(message)[:500] or "(boş hata gövdesi)"

        request_id = resp.headers.get("X-Request-Id") or body.get("request_id")

        return ApiError(
            kind=classify_status(resp.status_code),
            message=message,
            status=resp.status_code,
            code=str(body.get("error_code") or "") or None,
            request_id=request_id,
            retry_after_seconds=parse_retry_after(resp.headers.get("Retry-After")),
            operation=operation,
            model=model,
            api_path=path,
        )

    def _request(self, method: str, path: str, *, json_body: dict | None = None,
                 operation: str, model: str | None = None,
                 stream: bool = False, extra_headers: dict | None = None,
                 auth: bool = True, timeout: httpx.Timeout | None = None) -> httpx.Response:
        """Yeniden deneme politikalı HTTP isteği.

        Başarılıysa yanıtı döndürür; hatalıysa (tekrarlar tükendiyse)
        ApiError fırlatır. Zaman aşımı/akış kopması UNKNOWN_RESULT olarak
        hemen yükselir — otomatik tekrar yapılmaz.
        """
        headers = self._headers(auth)
        if extra_headers:
            headers.update(extra_headers)
        url = f"{self.base_url}{path}"
        client = self._http()
        attempt = 0

        while True:
            attempt += 1
            try:
                if stream:
                    req = client.build_request(
                        method, url, headers=headers,
                        json=json_body if json_body is not None else None,
                        **({"timeout": timeout} if timeout is not None else {}),
                    )
                    resp = client.send(req, stream=True)
                else:
                    resp = client.request(
                        method, url, headers=headers,
                        json=json_body if json_body is not None else None,
                    )
            except httpx.HTTPError as exc:
                if stream and timeout is not None and isinstance(exc, httpx.ReadTimeout):
                    raise ApiError(
                        kind=ErrorKind.TIMEOUT,
                        message=f"Model {timeout.read:.0f} sn içinde yanıt vermeye başlamadı.",
                        operation=operation, model=model, api_path=path,
                    ) from exc
                err = error_from_httpx(exc, operation, model, path)
                if err.kind == ErrorKind.UNKNOWN_RESULT:
                    raise err
                if err.kind != ErrorKind.NETWORK or attempt > self.max_retries:
                    raise err
                wait = backoff_seconds(attempt)
                self._log(
                    f"{operation}: ağ hatası ({err.message[:80]}), "
                    f"{wait:.0f} sn sonra tekrar denenecek "
                    f"({attempt}/{self.max_retries})"
                )
                time.sleep(wait)
                continue

            if resp.status_code < 400:
                return resp

            api_err = self._to_api_error(resp, operation, model)
            # Yeniden denenebilir mi? (429/5xx/408; Retry-After'a uy)
            if api_err.kind in RETRYABLE_KINDS and attempt <= self.max_retries:
                if api_err.retry_after_seconds is None:
                    wait = backoff_seconds(attempt)
                elif api_err.retry_after_seconds > MAX_RETRY_AFTER_SLEEP:
                    # Çok uzun bekleme isteniyorsa kullanıcıya bırak.
                    api_err.message += (
                        f" | Sunucu {int(api_err.retry_after_seconds)} sn "
                        "bekleme öneriyor; otomatik bekleme yapılmadı."
                    )
                    resp.close()
                    raise api_err
                else:
                    wait = api_err.retry_after_seconds
                self._log(
                    f"{operation}: HTTP {api_err.status}, {wait:.0f} sn sonra "
                    f"tekrar denenecek ({attempt}/{self.max_retries})"
                )
                resp.close()
                time.sleep(wait)
                continue
            resp.close()
            raise api_err

    # ---- sağlık (kimlik doğrulamasız, maliyetsiz) --------------------------

    def healthz(self) -> dict[str, Any]:
        resp = self._request("GET", "/healthz", operation="healthz", auth=False)
        try:
            return resp.json()
        finally:
            resp.close()

    def readyz(self) -> dict[str, Any]:
        resp = self._request("GET", "/readyz", operation="readyz", auth=False)
        try:
            return resp.json()
        finally:
            resp.close()

    # ---- modeller ------------------------------------------------------------

    def list_models(self) -> list[ModelInfo]:
        resp = self._request("GET", "/v1/models", operation="list_models")
        try:
            data = resp.json().get("data", [])
        finally:
            resp.close()
        models = []
        for m in data:
            pricing = m.get("pricing") or {}
            models.append(ModelInfo(
                id=m["id"],
                task=m.get("task", "chat"),
                modalities=m.get("modalities", []),
                context_length=m.get("context_length"),
                default_max_output_tokens=m.get("default_max_output_tokens"),
                capabilities=m.get("capabilities") or {},
                free_until=pricing.get("free_until"),
                prompt_token_price=pricing.get("prompt_token_price"),
                completion_token_price=pricing.get("completion_token_price"),
            ))
        return models

    # ---- kota ------------------------------------------------------------------

    def get_quota(self) -> QuotaInfo:
        resp = self._request("GET", "/v1/quota", operation="get_quota")
        try:
            d = resp.json()
        finally:
            resp.close()
        return QuotaInfo(
            used_tokens=d.get("used_tokens"),
            cap=d.get("cap"),
            window_minutes=d.get("window_minutes"),
            reset_at=d.get("reset_at"),
            usage_ratio=d.get("usage_ratio"),
            level=d.get("level", "unknown"),
            held_cr=d.get("held_cr", "?"),
            remaining_cr=d.get("remaining_cr", "?"),
            daily_used_tokens=d.get("daily_used_tokens"),
            daily_limit_tokens=d.get("daily_limit_tokens"),
            daily_remaining_tokens=d.get("daily_remaining_tokens"),
            daily_reset_at=d.get("daily_reset_at"),
        )

    # ---- şartlar ------------------------------------------------------------------

    def terms_status(self) -> dict[str, Any]:
        resp = self._request("GET", "/v1/terms/status", operation="terms_status")
        try:
            return resp.json()
        finally:
            resp.close()

    # ---- belirsiz sonuç sorgusu ------------------------------------------------------

    def get_request_status(self, request_id: str) -> dict[str, Any]:
        """GET /v1/requests/{id} — execution_unknown kurtarma adımı."""
        resp = self._request("GET", f"/v1/requests/{request_id}",
                             operation="get_request_status")
        try:
            return resp.json()
        finally:
            resp.close()

    def resolve_unknown_request(self, request_id: str | None) -> dict[str, Any]:
        """Belirsiz isteğin durumunu sorgular; kayıt yoksa bilinmeyen döner."""
        if not request_id:
            return {"execution_terminal": "unknown",
                    "note": "İstek kimliği yok (akış kimliği sunucu kaydıyla "
                            "eşleşmeyebilir)."}
        try:
            return self.get_request_status(request_id)
        except ApiError as exc:
            if exc.kind == ErrorKind.NOT_FOUND:
                return {"execution_terminal": "unknown",
                        "note": "İstek sunucu kayıtlarında bulunamadı."}
            raise

    # ---- sohbet ------------------------------------------------------------------------

    def chat(self, model: str, messages: list[dict[str, Any]],
             max_tokens: int | None = None, stream: bool = False,
             cancel: CancelToken | None = None,
             on_delta: Callable[[str, str], None] | None = None,
             on_reasoning: Callable[[str], None] | None = None,
             tools: list[dict[str, Any]] | None = None,
             tool_choice: str | None = None,
             extra_body: dict[str, Any] | None = None) -> ChatResult:
        """Chat Completion; stream=True ise SSE parçaları geri çağrıyla iletilir.

        İptal: cancel bayrağı gönderim öncesi ve her akış parçasında denetlenir.
        tools verilirse OpenAI uyumlu function calling istenir; araç çağrıları
        ChatResult.tool_calls içinde döner (akışta parçalar birleştirilir).
        extra_body gövdeye eklenir (ör. {"reasoning_effort": "none"} — EVREN'de
        düşünmeyi kapatır, 2026-10-17 gerçek istekle ölçüldü).
        """
        if cancel is not None and cancel.cancelled:
            return ChatResult(model=model, finish_reason="cancelled_by_user")

        body: dict[str, Any] = {"model": model, "messages": strip_internal(expand_chat_images(messages)),
                                "stream": bool(stream)}
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice or "auto"
        if extra_body:
            body.update(extra_body)

        extra = {"Accept": "text/event-stream"} if stream else None
        idle = self.stream_idle_timeout if stream else None
        tmo = httpx.Timeout(self.timeout, read=idle) if idle else None
        t0 = time.monotonic()
        resp = self._request("POST", "/v1/chat/completions", json_body=body,
                             operation="chat_completions", model=model,
                             stream=stream, extra_headers=extra, timeout=tmo)
        if stream:
            return self._consume_stream(resp, model, cancel, on_delta, on_reasoning, t0=t0, idle=idle)
        try:
            data = resp.json()
        finally:
            resp.close()
        return self._parse_chat_response(data)

    def _parse_chat_response(self, data: dict[str, Any]) -> ChatResult:
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        usage = data.get("usage") or {}
        evren_usage = usage.get("evren") or {}
        calls = []
        for i, tc in enumerate(msg.get("tool_calls") or []):
            fn = tc.get("function") or {}
            args = fn.get("arguments")
            if isinstance(args, dict):
                args = json.dumps(args, ensure_ascii=False)
            calls.append({"id": tc.get("id") or f"call_{i}",
                          "name": fn.get("name") or "",
                          "arguments": args or ""})
        return ChatResult(
            content=msg.get("content") or "",
            reasoning=msg.get("reasoning") or msg.get("reasoning_content") or "",
            model=data.get("model", ""),
            request_id=data.get("id"),
            routed_model=evren_usage.get("routed_model"),
            finish_reason=choice.get("finish_reason"),
            usage=usage,
            tool_calls=calls,
        )

    def _consume_stream(self, resp: httpx.Response, model: str,
                        cancel: CancelToken | None,
                        on_delta: Callable[[str, str], None] | None,
                        on_reasoning: Callable[[str], None] | None,
                        t0: float | None = None, idle: float | None = None) -> ChatResult:
        """SSE akışını tüketir; kopma durumunda belirsiz sonuç (UNKNOWN_RESULT)
        olarak yükseltir — otomatik tekrar yapılmaz."""
        result = ChatResult(model=model)
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        # index → {"id", "name", "arguments"(parçalar)}
        call_parts: dict[int, dict[str, Any]] = {}

        def collect_calls() -> list[dict[str, str]]:
            out = []
            for idx in sorted(call_parts):
                c = call_parts[idx]
                out.append({"id": c["id"] or f"call_{idx}", "name": c["name"],
                            "arguments": "".join(c["arguments"])})
            return out

        try:
            for line in resp.iter_lines():
                if cancel is not None and cancel.cancelled:
                    result.content = "".join(content_parts)
                    result.reasoning = "".join(reasoning_parts)
                    result.tool_calls = collect_calls()
                    result.finish_reason = "cancelled_by_user"
                    return result
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if not isinstance(chunk, dict):
                    continue
                if chunk.get("id") and not result.request_id:
                    result.request_id = str(chunk["id"])
                if chunk.get("usage"):
                    result.usage = chunk["usage"]
                choices = chunk.get("choices") or []
                if not choices:
                    if chunk.get("usage"):
                        result.usage = chunk["usage"]
                    continue
                delta = choices[0].get("delta") or {}
                if result.first_chunk_s is None and t0 is not None and (
                        delta.get("content") or delta.get("reasoning") or delta.get("reasoning_content")
                        or delta.get("tool_calls")):
                    result.first_chunk_s = round(time.monotonic() - t0, 2)
                for tc in delta.get("tool_calls") or []:
                    idx = tc.get("index", len(call_parts))
                    slot = call_parts.setdefault(idx, {"id": "", "name": "", "arguments": []})
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["name"] += fn["name"]
                    if fn.get("arguments"):
                        args = fn["arguments"]
                        slot["arguments"].append(
                            args if isinstance(args, str) else json.dumps(args, ensure_ascii=False))
                r_text = delta.get("reasoning") or delta.get("reasoning_content")
                if r_text:
                    reasoning_parts.append(r_text)
                    if on_reasoning:
                        on_reasoning(r_text)
                c_text = delta.get("content")
                if c_text:
                    content_parts.append(c_text)
                    if on_delta:
                        on_delta(c_text, choices[0].get("finish_reason") or "")
                if choices[0].get("finish_reason"):
                    result.finish_reason = choices[0]["finish_reason"]
        except httpx.HTTPError as exc:
            partial = "".join(content_parts)
            if idle and isinstance(exc, httpx.ReadTimeout):
                raise ApiError(
                    kind=ErrorKind.TIMEOUT,
                    message=f"Model {idle:.0f} sn boyunca yanıt vermedi (akış durdu; kısmi yanıt "
                            f"{len(partial)} karakter).",
                    operation="chat_completions_stream", model=model,
                    api_path="/v1/chat/completions",
                ) from exc
            raise ApiError(
                kind=ErrorKind.UNKNOWN_RESULT,
                message=f"Akış kesildi: {type(exc).__name__}. Kısmi yanıt "
                        f"{len(partial)} karakterde kaldı.",
                operation="chat_completions_stream", model=model,
                api_path="/v1/chat/completions",
            )
        finally:
            resp.close()
        result.content = "".join(content_parts)
        result.reasoning = "".join(reasoning_parts)
        result.tool_calls = collect_calls()
        evren_usage = (result.usage or {}).get("evren") or {}
        if evren_usage.get("routed_model"):
            result.routed_model = evren_usage["routed_model"]
        return result
