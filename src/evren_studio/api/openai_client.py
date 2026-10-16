"""OpenAI istemcisi — Responses API (POST /v1/responses).

Neden Responses: OpenAI "Responses is recommended for all new projects" diyor;
GPT-5.4 ve sonrası modellerde Chat Completions, reasoning açıkken araç
çağrısını desteklemiyor (docs/knowledge/PROVIDERS_RESEARCH.md).

Ajan iç mesajları OpenAI Chat biçimindedir (to_api_messages "native"); bu
modül onları Responses `input` öğelerine çevirir:
- system → `instructions`
- user → message(input_text) · assistant → message(output_text) + function_call
- tool → function_call_output(call_id)
- Önceki yanıtın ham çıktı öğeleri (`_provider_state.openai_items`, şifreli
  reasoning dahil) varsa assistant mesajı yerine AYNEN geri gönderilir
  (`store:false` + `include:["reasoning.encrypted_content"]`).

DURUM: belgelere göre yazıldı, gerçek istekle DOĞRULANMADI.
"""
from __future__ import annotations

import json
from typing import Any, Callable

import httpx

from .client import CancelToken, ChatResult, EvrenClient, ModelInfo, strip_internal
from .errors import ApiError, ErrorKind, classify_status, parse_retry_after
from .providers import CATALOG, PROVIDERS

_QUOTA_CODES = {"insufficient_quota", "credit_balance_exhausted", "organization_spend_limit_exceeded",
                "project_spend_limit_exceeded", "organization_usage_limit_exceeded"}


def to_responses_input(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    instructions: list[str] = []
    items: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content") or ""
        if role in ("system", "developer"):
            if content:
                instructions.append(content)
            continue
        if role == "user":
            items.append({"type": "message", "role": "user",
                          "content": [{"type": "input_text", "text": content}]})
        elif role == "assistant":
            raw = (m.get("_provider_state") or {}).get("openai_items")
            if raw:
                items.extend(raw)
                continue
            if content:
                items.append({"type": "message", "role": "assistant",
                              "content": [{"type": "output_text", "text": content}]})
            for c in m.get("tool_calls") or []:
                fn = c.get("function") or {}
                items.append({"type": "function_call", "call_id": c.get("id"),
                              "name": fn.get("name", c.get("name", "")),
                              "arguments": fn.get("arguments", c.get("arguments", "")) or "{}"})
        elif role == "tool":
            items.append({"type": "function_call_output", "call_id": m.get("tool_call_id"),
                          "output": content})
    return "\n\n".join(instructions), items


def to_responses_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    out = []
    for t in tools:
        fn = t.get("function", t)
        out.append({"type": "function", "name": fn["name"], "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {"type": "object", "properties": {}})})
    return out


class OpenAIClient(EvrenClient):
    provider = "openai"

    def __init__(self, api_key: str, base_url: str | None = None, timeout: float = 180.0,
                 max_retries: int = 3, log_sink: Callable[[str], None] | None = None,
                 transport: httpx.BaseTransport | None = None):
        super().__init__(base_url or PROVIDERS["openai"].base_url, api_key, timeout=timeout,
                         max_retries=max_retries, log_sink=log_sink, transport=transport)

    def _to_api_error(self, resp: httpx.Response, operation: str, model: str | None) -> ApiError:
        try:
            if not resp.is_stream_consumed and not resp.is_closed:
                resp.read()
            body = resp.json()
        except Exception:
            body = {}
        err = body.get("error") if isinstance(body, dict) else None
        err = err if isinstance(err, dict) else {}
        etype, code = err.get("type") or "", err.get("code") or ""
        kind = classify_status(resp.status_code)
        if resp.status_code == 429 and (etype in _QUOTA_CODES or code in _QUOTA_CODES):
            kind = ErrorKind.QUOTA_EXHAUSTED
        message = self._mask(str(err.get("message") or resp.text or ""))[:500] or "(boş hata gövdesi)"
        return ApiError(kind=kind, message=message, status=resp.status_code, code=code or etype or None,
                        request_id=resp.headers.get("x-request-id"),
                        retry_after_seconds=parse_retry_after(resp.headers.get("Retry-After")),
                        operation=operation, model=model,
                        api_path=resp.request.url.path if resp.request is not None else "")

    # EVREN'e özgü uçlar OpenAI'de yok
    def get_quota(self):  # pragma: no cover - arayüz bu sağlayıcıda çağırmaz
        raise ApiError(kind=ErrorKind.NOT_FOUND, message="OpenAI kota ucu yok; panelden izleyin.",
                       operation="get_quota")

    def resolve_unknown_request(self, request_id: str | None) -> dict[str, Any]:
        return {"execution_terminal": "unknown",
                "note": "OpenAI'de istek durumu sorgusu kullanılmıyor (store:false)."}

    def list_models(self) -> list[ModelInfo]:
        resp = self._request("GET", "/v1/models", operation="list_models")
        try:
            ids = {m.get("id") for m in (resp.json().get("data") or [])}
        finally:
            resp.close()
        known = [c for c in CATALOG if c.provider == "openai" and (c.id in ids or not ids)]
        return [ModelInfo(id=c.id, task="chat", modalities=["text", "image"], context_length=c.context,
                          default_max_output_tokens=c.max_output,
                          capabilities={"tools": c.tools, "vision": c.vision},
                          prompt_token_price=c.price_in, completion_token_price=c.price_out,
                          provider="openai") for c in known]

    def build_body(self, model: str, messages: list[dict[str, Any]], stream: bool,
                   tools: list[dict[str, Any]] | None, max_tokens: int | None) -> dict[str, Any]:
        instructions, items = to_responses_input(messages)
        body: dict[str, Any] = {"model": model, "input": items, "stream": bool(stream),
                                "store": False, "include": ["reasoning.encrypted_content"]}
        if instructions:
            body["instructions"] = instructions
        rtools = to_responses_tools(tools)
        if rtools:
            body["tools"] = rtools
            body["tool_choice"] = "auto"
        if max_tokens:
            body["max_output_tokens"] = max_tokens
        return body

    def chat(self, model: str, messages: list[dict[str, Any]], max_tokens: int | None = None,
             stream: bool = False, cancel: CancelToken | None = None,
             on_delta: Callable[[str, str], None] | None = None,
             on_reasoning: Callable[[str], None] | None = None,
             tools: list[dict[str, Any]] | None = None, tool_choice: str | None = None) -> ChatResult:
        if cancel is not None and cancel.cancelled:
            return ChatResult(model=model, finish_reason="cancelled_by_user")
        body = self.build_body(model, strip_internal_keep_state(messages), stream, tools, max_tokens)
        extra = {"Accept": "text/event-stream"} if stream else None
        resp = self._request("POST", "/v1/responses", json_body=body, operation="responses",
                             model=model, stream=stream, extra_headers=extra)
        if stream:
            return self._consume_responses_stream(resp, model, cancel, on_delta, on_reasoning)
        try:
            data = resp.json()
        finally:
            resp.close()
        return self._parse_response(data, model)

    # -- yanıt ayrıştırma -------------------------------------------------------

    def _result_from_items(self, items: list[dict], model: str, usage: dict, rid: str | None,
                           status: str | None, text: str | None = None) -> ChatResult:
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        calls: list[dict[str, str]] = []
        for it in items:
            t = it.get("type")
            if t == "message":
                for c in it.get("content") or []:
                    if c.get("type") in ("output_text", "text"):
                        content_parts.append(c.get("text") or "")
            elif t == "function_call":
                calls.append({"id": it.get("call_id") or it.get("id") or "", "name": it.get("name") or "",
                              "arguments": it.get("arguments") or ""})
            elif t == "reasoning":
                for s in it.get("summary") or []:
                    if s.get("text"):
                        reasoning_parts.append(s["text"])
        finish = "tool_calls" if calls else ("length" if status == "incomplete" else "stop")
        return ChatResult(content=text if text is not None else "".join(content_parts),
                          reasoning="\n".join(reasoning_parts), model=model, request_id=rid,
                          finish_reason=finish, usage=usage or {}, tool_calls=calls,
                          provider_state={"openai_items": items} if items else {})

    def _parse_response(self, data: dict[str, Any], model: str) -> ChatResult:
        return self._result_from_items(data.get("output") or [], data.get("model") or model,
                                       data.get("usage") or {}, data.get("id"), data.get("status"))

    def _consume_responses_stream(self, resp: httpx.Response, model: str, cancel: CancelToken | None,
                                  on_delta, on_reasoning) -> ChatResult:
        items: list[dict] = []
        text_parts: list[str] = []
        usage: dict = {}
        rid = None
        status = None
        try:
            for line in resp.iter_lines():
                if cancel is not None and cancel.cancelled:
                    r = self._result_from_items(items, model, usage, rid, status, "".join(text_parts))
                    r.finish_reason = "cancelled_by_user"
                    return r
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    ev = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                et = ev.get("type", "")
                if et == "response.output_text.delta":
                    delta = ev.get("delta") or ""
                    text_parts.append(delta)
                    if on_delta and delta:
                        on_delta(delta, "")
                elif et in ("response.reasoning_summary_text.delta", "response.reasoning_text.delta"):
                    if on_reasoning and ev.get("delta"):
                        on_reasoning(ev["delta"])
                elif et == "response.output_item.done":
                    item = ev.get("item")
                    if isinstance(item, dict):
                        items.append(item)
                elif et in ("response.created", "response.in_progress"):
                    rid = (ev.get("response") or {}).get("id") or rid
                elif et in ("response.completed", "response.incomplete"):
                    r = ev.get("response") or {}
                    usage = r.get("usage") or usage
                    rid = r.get("id") or rid
                    status = r.get("status") or ("incomplete" if et.endswith("incomplete") else "completed")
                    if not items and r.get("output"):
                        items = list(r["output"])
                elif et in ("response.failed", "error"):
                    err = ev.get("error") or (ev.get("response") or {}).get("error") or {}
                    code = err.get("code") or err.get("type") or ""
                    kind = ErrorKind.QUOTA_EXHAUSTED if code in _QUOTA_CODES else ErrorKind.SERVER_ERROR
                    raise ApiError(kind=kind, message=self._mask(str(err.get("message") or et))[:500],
                                   code=code or None, request_id=rid, operation="responses_stream",
                                   model=model, api_path="/v1/responses")
        except httpx.HTTPError as exc:
            raise ApiError(kind=ErrorKind.UNKNOWN_RESULT,
                           message=f"Akış kesildi: {type(exc).__name__}.", operation="responses_stream",
                           model=model, api_path="/v1/responses")
        finally:
            resp.close()
        return self._result_from_items(items, model, usage, rid, status, "".join(text_parts))


def strip_internal_keep_state(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """_provider_state dışındaki iç alanları siler (dönüştürücü state'i kullanır)."""
    out = []
    for m in messages:
        d = {k: v for k, v in m.items() if not k.startswith("_") or k == "_provider_state"}
        out.append(d)
    return out


__all__ = ["OpenAIClient", "to_responses_input", "to_responses_tools", "strip_internal"]
