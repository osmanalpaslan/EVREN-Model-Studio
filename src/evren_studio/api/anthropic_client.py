"""Anthropic (Claude) istemcisi — Messages API (POST /v1/messages).

Kimlik: `x-api-key` + `anthropic-version: 2023-06-01`. OpenAI uyumluluk
katmanı bilerek KULLANILMAZ ("not production-ready"; thinking içeriği yok).

Ajan iç mesajları (OpenAI Chat biçimi) Messages biçimine çevrilir:
- system → üst düzey `system`
- assistant → içerik blokları: text + tool_use{id,name,input}; önceki yanıtın
  ham blokları (`_provider_state.anthropic_content`, thinking + signature
  dahil) varsa AYNEN geri gönderilir (araç turlarında zorunlu).
- tool → bir sonraki user mesajında, EN BAŞTA tool_result{tool_use_id}
  blokları; ardışık araç sonuçları TEK user mesajında toplanır.
- Ardışık aynı rollü mesajlar birleştirilir; boş assistant mesajı atlanır.
- `temperature/top_p/top_k` GÖNDERİLMEZ (4.7+ modellerde 400); prefill yok.

Akış olayları: message_start, content_block_start/delta/stop (text_delta,
input_json_delta, thinking_delta, signature_delta), message_delta
(stop_reason, kümülatif usage), message_stop, ping, error.

DURUM: belgelere göre yazıldı, gerçek istekle DOĞRULANMADI.
"""
from __future__ import annotations

import copy
import json
from typing import Any, Callable

import httpx

from .client import USER_AGENT, CancelToken, ChatResult, EvrenClient, ModelInfo
from .errors import ApiError, ErrorKind, classify_status, parse_retry_after
from .providers import CATALOG, CATALOG_BY_ID, PROVIDERS

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 32_000
_ERROR_KINDS = {
    "authentication_error": ErrorKind.AUTH, "permission_error": ErrorKind.AUTH,
    "not_found_error": ErrorKind.NOT_FOUND, "rate_limit_error": ErrorKind.RATE_LIMIT,
    "overloaded_error": ErrorKind.SERVER_UNAVAILABLE, "api_error": ErrorKind.SERVER_ERROR,
    "timeout_error": ErrorKind.SERVER_ERROR, "billing_error": ErrorKind.QUOTA_EXHAUSTED,
    "invalid_request_error": ErrorKind.VALIDATION, "request_too_large": ErrorKind.REQUEST_TOO_LARGE,
}


def _args_to_input(arguments: Any) -> dict:
    if isinstance(arguments, dict):
        return arguments
    try:
        v = json.loads(arguments) if arguments else {}
        return v if isinstance(v, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def to_anthropic(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    system: list[str] = []
    out: list[dict[str, Any]] = []

    def push(role: str, blocks: list[dict[str, Any]], results_first: bool = False) -> None:
        if not blocks:
            return
        if out and out[-1]["role"] == role:
            if results_first:
                # tool_result blokları mesajın başında olmalı
                prev = out[-1]["content"]
                n = sum(1 for b in prev if b.get("type") == "tool_result")
                out[-1]["content"] = prev[:n] + blocks + prev[n:]
            else:
                out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": list(blocks)})

    for m in messages:
        role = m.get("role")
        content = m.get("content") or ""
        if role in ("system", "developer"):
            if content:
                system.append(content)
        elif role == "user":
            if content:
                push("user", [{"type": "text", "text": content}])
        elif role == "tool":
            push("user", [{"type": "tool_result", "tool_use_id": m.get("tool_call_id") or "",
                           "content": content or "(boş çıktı)"}], results_first=True)
        elif role == "assistant":
            raw = (m.get("_provider_state") or {}).get("anthropic_content")
            if raw:
                # thinking/tool_use blokları değiştirilmeden; boş metin blokları atılır
                push("assistant", [copy.deepcopy(b) for b in raw
                                   if not (b.get("type") == "text" and not b.get("text"))])
                continue
            blocks: list[dict[str, Any]] = []
            if content:
                blocks.append({"type": "text", "text": content})
            for c in m.get("tool_calls") or []:
                fn = c.get("function") or {}
                blocks.append({"type": "tool_use", "id": c.get("id"),
                               "name": fn.get("name", c.get("name", "")),
                               "input": _args_to_input(fn.get("arguments", c.get("arguments")))})
            push("assistant", blocks)
    # Messages API ilk mesajın user olmasını bekler
    if out and out[0]["role"] != "user":
        out.insert(0, {"role": "user", "content": [{"type": "text", "text": "(önceki bağlam)"}]})
    return "\n\n".join(system), out


def to_anthropic_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    out = []
    for t in tools:
        fn = t.get("function", t)
        out.append({"name": fn["name"], "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}})})
    return out


class AnthropicClient(EvrenClient):
    provider = "anthropic"

    def __init__(self, api_key: str, base_url: str | None = None, timeout: float = 300.0,
                 max_retries: int = 3, log_sink: Callable[[str], None] | None = None,
                 transport: httpx.BaseTransport | None = None):
        super().__init__(base_url or PROVIDERS["anthropic"].base_url, api_key, timeout=timeout,
                         max_retries=max_retries, log_sink=log_sink, transport=transport)

    def _headers(self, auth: bool) -> dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json",
             "User-Agent": USER_AGENT, "anthropic-version": ANTHROPIC_VERSION}
        if auth:
            h["x-api-key"] = self.api_key
        return h

    def _to_api_error(self, resp: httpx.Response, operation: str, model: str | None) -> ApiError:
        try:
            if not resp.is_stream_consumed and not resp.is_closed:
                resp.read()
            body = resp.json()
        except Exception:
            body = {}
        err = body.get("error") if isinstance(body, dict) else None
        err = err if isinstance(err, dict) else {}
        etype = err.get("type") or ""
        kind = _ERROR_KINDS.get(etype, classify_status(resp.status_code))
        details = err.get("details") if isinstance(err.get("details"), dict) else {}
        code = details.get("error_code") or etype or None
        if code == "enforced_spend_limit_reached":
            kind = ErrorKind.QUOTA_EXHAUSTED      # aylık tavan: retry-after yok, tekrar denenmez
        message = self._mask(str(err.get("message") or resp.text or ""))[:500] or "(boş hata gövdesi)"
        return ApiError(kind=kind, message=message, status=resp.status_code, code=code,
                        request_id=resp.headers.get("request-id") or body.get("request_id"),
                        retry_after_seconds=parse_retry_after(resp.headers.get("retry-after")),
                        operation=operation, model=model,
                        api_path=resp.request.url.path if resp.request is not None else "")

    def get_quota(self):  # pragma: no cover
        raise ApiError(kind=ErrorKind.NOT_FOUND, message="Anthropic kota ucu yok; Console'dan izleyin.",
                       operation="get_quota")

    def resolve_unknown_request(self, request_id: str | None) -> dict[str, Any]:
        return {"execution_terminal": "unknown",
                "note": "Anthropic'te istek durumu sorgusu yok; Console Usage sayfasından kontrol edin."}

    def list_models(self) -> list[ModelInfo]:
        resp = self._request("GET", "/v1/models?limit=1000", operation="list_models")
        try:
            data = resp.json().get("data") or []
        finally:
            resp.close()
        live = {m.get("id"): m for m in data}
        out = []
        for c in CATALOG:
            if c.provider != "anthropic" or (live and c.id not in live):
                continue
            m = live.get(c.id) or {}
            out.append(ModelInfo(id=c.id, task="chat", modalities=["text", "image"],
                                 context_length=m.get("max_input_tokens") or c.context,
                                 default_max_output_tokens=m.get("max_tokens") or c.max_output,
                                 capabilities={"tools": True, "vision": c.vision,
                                               **(m.get("capabilities") or {})},
                                 prompt_token_price=c.price_in, completion_token_price=c.price_out,
                                 provider="anthropic"))
        return out

    def build_body(self, model: str, messages: list[dict[str, Any]], stream: bool,
                   tools: list[dict[str, Any]] | None, max_tokens: int | None) -> dict[str, Any]:
        system, msgs = to_anthropic(messages)
        cap = CATALOG_BY_ID[model].max_output if model in CATALOG_BY_ID else DEFAULT_MAX_TOKENS
        body: dict[str, Any] = {"model": model, "max_tokens": min(max_tokens or DEFAULT_MAX_TOKENS, cap),
                                "messages": msgs, "stream": bool(stream)}
        if system:
            body["system"] = system
        atools = to_anthropic_tools(tools)
        if atools:
            body["tools"] = atools
            body["tool_choice"] = {"type": "auto"}
        return body

    def chat(self, model: str, messages: list[dict[str, Any]], max_tokens: int | None = None,
             stream: bool = False, cancel: CancelToken | None = None,
             on_delta: Callable[[str, str], None] | None = None,
             on_reasoning: Callable[[str], None] | None = None,
             tools: list[dict[str, Any]] | None = None, tool_choice: str | None = None,
             extra_body: dict[str, Any] | None = None) -> ChatResult:
        # extra_body EVREN'e özgüdür (reasoning_effort vb.); burada yok sayılır.
        if cancel is not None and cancel.cancelled:
            return ChatResult(model=model, finish_reason="cancelled_by_user")
        body = self.build_body(model, messages, stream, tools, max_tokens)
        extra = {"Accept": "text/event-stream"} if stream else None
        resp = self._request("POST", "/v1/messages", json_body=body, operation="messages",
                             model=model, stream=stream, extra_headers=extra)
        if stream:
            return self._consume_messages_stream(resp, model, cancel, on_delta, on_reasoning)
        try:
            data = resp.json()
        finally:
            resp.close()
        return self._result(data.get("content") or [], data.get("model") or model,
                            data.get("usage") or {}, data.get("id"), data.get("stop_reason"))

    def _result(self, blocks: list[dict], model: str, usage: dict, rid: str | None,
                stop_reason: str | None, cancelled: bool = False) -> ChatResult:
        text = "".join(b.get("text") or "" for b in blocks if b.get("type") == "text")
        thinking = "".join(b.get("thinking") or "" for b in blocks if b.get("type") == "thinking")
        calls = [{"id": b.get("id") or "", "name": b.get("name") or "",
                  "arguments": json.dumps(b.get("input") or {}, ensure_ascii=False)}
                 for b in blocks if b.get("type") == "tool_use"]
        finish = {"tool_use": "tool_calls", "end_turn": "stop", "stop_sequence": "stop",
                  "max_tokens": "length", "refusal": "refusal", "pause_turn": "stop"}.get(stop_reason or "", stop_reason)
        if cancelled:
            finish = "cancelled_by_user"
        elif calls and not finish:
            finish = "tool_calls"
        return ChatResult(content=text, reasoning=thinking, model=model, request_id=rid,
                          finish_reason=finish, usage=usage, tool_calls=calls,
                          provider_state={"anthropic_content": blocks} if blocks else {})

    def _consume_messages_stream(self, resp: httpx.Response, model: str, cancel: CancelToken | None,
                                 on_delta, on_reasoning) -> ChatResult:
        blocks: dict[int, dict] = {}
        partial_json: dict[int, list[str]] = {}
        usage: dict = {}
        rid = None
        stop_reason = None

        def ordered() -> list[dict]:
            out = []
            for i in sorted(blocks):
                b = blocks[i]
                if b.get("type") == "tool_use" and i in partial_json:
                    raw = "".join(partial_json[i])
                    b["input"] = _args_to_input(raw) if raw else (b.get("input") or {})
                out.append(b)
            return out

        try:
            for line in resp.iter_lines():
                if cancel is not None and cancel.cancelled:
                    return self._result(ordered(), model, usage, rid, stop_reason, cancelled=True)
                if not line or not line.startswith("data:"):
                    continue
                try:
                    ev = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                et = ev.get("type")
                if et == "message_start":
                    msg = ev.get("message") or {}
                    rid = msg.get("id")
                    usage.update(msg.get("usage") or {})
                elif et == "content_block_start":
                    i = int(ev.get("index", len(blocks)))
                    b = dict(ev.get("content_block") or {})
                    if b.get("type") == "tool_use":
                        b.setdefault("input", {})
                        partial_json[i] = []
                    blocks[i] = b
                elif et == "content_block_delta":
                    i = int(ev.get("index", 0))
                    d = ev.get("delta") or {}
                    b = blocks.setdefault(i, {"type": "text", "text": ""})
                    dt = d.get("type")
                    if dt == "text_delta":
                        b["text"] = (b.get("text") or "") + (d.get("text") or "")
                        if on_delta and d.get("text"):
                            on_delta(d["text"], "")
                    elif dt == "input_json_delta":
                        partial_json.setdefault(i, []).append(d.get("partial_json") or "")
                    elif dt == "thinking_delta":
                        b["thinking"] = (b.get("thinking") or "") + (d.get("thinking") or "")
                        if on_reasoning and d.get("thinking"):
                            on_reasoning(d["thinking"])
                    elif dt == "signature_delta":
                        b["signature"] = (b.get("signature") or "") + (d.get("signature") or "")
                elif et == "message_delta":
                    stop_reason = (ev.get("delta") or {}).get("stop_reason") or stop_reason
                    usage.update(ev.get("usage") or {})
                elif et == "message_stop":
                    break
                elif et == "error":
                    err = ev.get("error") or {}
                    raise ApiError(kind=_ERROR_KINDS.get(err.get("type") or "", ErrorKind.SERVER_ERROR),
                                   message=self._mask(str(err.get("message") or "akış hatası"))[:500],
                                   code=err.get("type"), request_id=rid, operation="messages_stream",
                                   model=model, api_path="/v1/messages")
        except httpx.HTTPError as exc:
            raise ApiError(kind=ErrorKind.UNKNOWN_RESULT, message=f"Akış kesildi: {type(exc).__name__}.",
                           operation="messages_stream", model=model, api_path="/v1/messages")
        finally:
            resp.close()
        return self._result(ordered(), model, usage, rid, stop_reason)
