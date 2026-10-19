"""OpenAI (Responses) ve Anthropic (Messages) entegrasyonu — sahte HTTP ile.

Gerçek anahtar yoktur; istek gövdeleri, başlıklar, akış ayrıştırma, hata
eşlemesi, ajan araç döngüsü, maliyet tahmini, bütçe koruması ve arayüz
(gruplu model seçici, Ayarlar > Sağlayıcılar) bu dosyada sınanır. Gerçek
API ile doğrulama: tests/e2e_providers_real_api.py (anahtar gerekir).
"""
from __future__ import annotations

import json
import os
import time

import httpx
import pytest

from evren_studio import secrets
from evren_studio.agent.runner import AgentEvents, AgentRunner
from evren_studio.agent.tools import Workspace
from evren_studio.api.anthropic_client import AnthropicClient, to_anthropic
from evren_studio.api.client import ChatResult, normalize_usage
from evren_studio.api.errors import ApiError, ErrorKind
from evren_studio.api.openai_client import OpenAIClient, to_responses_input
from evren_studio.api.providers import CATALOG_BY_ID, estimate_cost, provider_of_model
from evren_studio.budget import BudgetState, current_state
from evren_studio.db import Database

OAI_KEY = "sk-proj-SAHTEANAHTAR1234567890abcdef"
ANT_KEY = "sk-ant-api03-SAHTEANAHTAR1234567890abcdef"


def sse(events: list[dict]) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n"
                   for e in events).encode("utf-8")


class Recorder:
    """İstekleri kaydeder, sıradaki hazır yanıtı döndürür."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        r = self.responses.pop(0) if self.responses else httpx.Response(500)
        return r

    def body(self, i: int) -> dict:
        return json.loads(self.requests[i].content)


def stream_resp(events):
    return httpx.Response(200, content=sse(events), headers={"content-type": "text/event-stream"})


def oai(rec, **kw):
    return OpenAIClient(OAI_KEY, transport=httpx.MockTransport(rec), **kw)


def ant(rec, **kw):
    return AnthropicClient(ANT_KEY, transport=httpx.MockTransport(rec), **kw)


TOOLS = [{"type": "function", "function": {
    "name": "read_file", "description": "dosya oku",
    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}]


# ---- OpenAI ------------------------------------------------------------------------


def test_openai_govde_ve_basliklar():
    rec = Recorder([httpx.Response(200, json={
        "id": "resp_1", "status": "completed", "model": "gpt-6-luna",
        "output": [{"type": "message", "role": "assistant",
                    "content": [{"type": "output_text", "text": "Merhaba"}]}],
        "usage": {"input_tokens": 12, "output_tokens": 3}})])
    msgs = [{"role": "system", "content": "Sen yardımcısın."},
            {"role": "user", "content": "selam"},
            {"role": "assistant", "content": "", "_provider_state": {"openai_items": [
                {"type": "reasoning", "id": "rs_0", "encrypted_content": "ENC0", "summary": []}]}},
            {"role": "tool", "tool_call_id": "call_0", "content": "çıktı"},
            {"role": "user", "content": "devam", "_meta": {"x": 1}}]
    r = oai(rec).chat("gpt-6-luna", msgs, tools=TOOLS)
    req = rec.requests[0]
    assert req.url.path == "/v1/responses"
    assert req.headers["authorization"] == f"Bearer {OAI_KEY}"
    b = rec.body(0)
    assert b["instructions"] == "Sen yardımcısın."
    assert b["store"] is False and b["include"] == ["reasoning.encrypted_content"]
    assert b["tools"] == [{"type": "function", "name": "read_file", "description": "dosya oku",
                           "parameters": TOOLS[0]["function"]["parameters"]}]
    types = [it["type"] for it in b["input"]]
    assert types == ["message", "reasoning", "function_call_output", "message"]
    assert b["input"][1]["encrypted_content"] == "ENC0"      # ham öğe aynen geri gider
    assert "_provider_state" not in json.dumps(b) and "_meta" not in json.dumps(b)
    assert r.content == "Merhaba" and r.finish_reason == "stop"
    assert r.token_usage() == {"input_tokens": 12, "output_tokens": 3, "cached_tokens": 0}


def test_openai_arac_cagrisi_donusumu():
    _, items = to_responses_input([
        {"role": "user", "content": "oku"},
        {"role": "assistant", "content": "bakıyorum",
         "tool_calls": [{"id": "call_9", "type": "function",
                         "function": {"name": "read_file", "arguments": '{"path": "a.py"}'}}]},
        {"role": "tool", "tool_call_id": "call_9", "content": "x = 1"},
    ])
    assert items[1] == {"type": "message", "role": "assistant",
                        "content": [{"type": "output_text", "text": "bakıyorum"}]}
    assert items[2] == {"type": "function_call", "call_id": "call_9", "name": "read_file",
                        "arguments": '{"path": "a.py"}'}
    assert items[3] == {"type": "function_call_output", "call_id": "call_9", "output": "x = 1"}


def test_openai_akis_ayristirma():
    deltas = []
    rec = Recorder([stream_resp([
        {"type": "response.created", "response": {"id": "resp_7"}},
        {"type": "response.output_text.delta", "delta": "Mer"},
        {"type": "response.output_text.delta", "delta": "haba"},
        {"type": "response.output_item.done", "item": {
            "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Merhaba"}]}},
        {"type": "response.output_item.done", "item": {
            "type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "read_file",
            "arguments": '{"path": "app.py"}'}},
        {"type": "response.completed", "response": {
            "id": "resp_7", "status": "completed",
            "usage": {"input_tokens": 200, "output_tokens": 30,
                      "input_tokens_details": {"cached_tokens": 100}}}},
    ])])
    r = oai(rec).chat("gpt-6-luna", [{"role": "user", "content": "x"}], stream=True,
                      on_delta=lambda t, _: deltas.append(t), tools=TOOLS)
    assert rec.requests[0].headers["accept"] == "text/event-stream"
    assert "".join(deltas) == "Merhaba" and r.content == "Merhaba"
    assert r.tool_calls == [{"id": "call_1", "name": "read_file", "arguments": '{"path": "app.py"}'}]
    assert r.finish_reason == "tool_calls" and r.request_id == "resp_7"
    assert r.token_usage() == {"input_tokens": 200, "output_tokens": 30, "cached_tokens": 100}
    assert len(r.provider_state["openai_items"]) == 2


@pytest.mark.parametrize("code", ["insufficient_quota", "organization_spend_limit_exceeded"])
def test_openai_kredi_bitti_tekrar_denenmez(code):
    rec = Recorder([httpx.Response(429, json={"error": {"message": "quota", "type": code, "code": code}})] * 3)
    with pytest.raises(ApiError) as e:
        oai(rec, max_retries=2).chat("gpt-6-luna", [{"role": "user", "content": "x"}])
    assert e.value.kind == ErrorKind.QUOTA_EXHAUSTED
    assert len(rec.requests) == 1


def test_openai_hiz_siniri_ve_yetki():
    rec = Recorder([httpx.Response(429, json={"error": {"type": "requests", "code": "rate_limit_exceeded"}})])
    with pytest.raises(ApiError) as e:
        oai(rec, max_retries=0).chat("gpt-6-luna", [{"role": "user", "content": "x"}])
    assert e.value.kind == ErrorKind.RATE_LIMIT
    rec = Recorder([httpx.Response(401, json={"error": {"message": f"bad key {OAI_KEY}"}})])
    with pytest.raises(ApiError) as e:
        oai(rec, max_retries=0).chat("gpt-6-luna", [{"role": "user", "content": "x"}])
    assert e.value.kind == ErrorKind.AUTH
    assert OAI_KEY not in e.value.message                      # anahtar maskelenir


def test_openai_akista_hata_olayi():
    rec = Recorder([stream_resp([{"type": "response.failed", "response": {
        "error": {"code": "insufficient_quota", "message": "no credit"}}}])])
    with pytest.raises(ApiError) as e:
        oai(rec).chat("gpt-6-luna", [{"role": "user", "content": "x"}], stream=True)
    assert e.value.kind == ErrorKind.QUOTA_EXHAUSTED


def test_openai_model_listesi_katalog_kesisimi():
    rec = Recorder([httpx.Response(200, json={"data": [{"id": "gpt-6-luna"}, {"id": "dall-e-9"},
                                                       {"id": "gpt-5.3-codex"}]})])
    ids = [m.id for m in oai(rec).list_models()]
    assert ids == ["gpt-6-luna", "gpt-5.3-codex"]


# ---- Anthropic ---------------------------------------------------------------------


def test_anthropic_govde_ve_basliklar():
    rec = Recorder([httpx.Response(200, json={
        "id": "msg_1", "model": "claude-haiku-5-5", "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "Merhaba"}],
        "usage": {"input_tokens": 10, "output_tokens": 2, "cache_read_input_tokens": 90}})])
    msgs = [{"role": "system", "content": "Kurallar."},
            {"role": "user", "content": "oku"},
            {"role": "assistant", "content": "",
             "tool_calls": [{"id": "toolu_1", "function": {"name": "read_file", "arguments": '{"path": "a"}'}},
                            {"id": "toolu_2", "function": {"name": "read_file", "arguments": '{"path": "b"}'}}]},
            {"role": "tool", "tool_call_id": "toolu_1", "content": "A"},
            {"role": "tool", "tool_call_id": "toolu_2", "content": "B"},
            {"role": "user", "content": "özetle"}]
    r = ant(rec).chat("claude-haiku-5-5", msgs, tools=TOOLS, max_tokens=999_999)
    req = rec.requests[0]
    assert req.url.path == "/v1/messages"
    assert req.headers["x-api-key"] == ANT_KEY and req.headers["anthropic-version"] == "2023-06-01"
    assert "authorization" not in req.headers
    b = rec.body(0)
    assert b["system"] == "Kurallar."
    assert b["max_tokens"] == CATALOG_BY_ID["claude-haiku-5-5"].max_output   # üst sınıra kırpılır
    assert not {"temperature", "top_p", "top_k"} & set(b)
    assert b["tools"][0]["input_schema"]["required"] == ["path"]
    roles = [m["role"] for m in b["messages"]]
    assert roles == ["user", "assistant", "user"]                        # ardışık user birleşir
    last = b["messages"][2]["content"]
    assert [c["type"] for c in last] == ["tool_result", "tool_result", "text"]   # sonuçlar başta
    assert last[0]["tool_use_id"] == "toolu_1" and last[2]["text"] == "özetle"
    assert b["messages"][1]["content"][0]["input"] == {"path": "a"}
    assert r.content == "Merhaba" and r.finish_reason == "stop"
    assert r.token_usage() == {"input_tokens": 100, "output_tokens": 2, "cached_tokens": 90}


def test_anthropic_ham_bloklar_aynen_geri_gider():
    raw = [{"type": "thinking", "thinking": "düşün", "signature": "SIG"},
           {"type": "text", "text": ""},
           {"type": "tool_use", "id": "toolu_1", "name": "read_file", "input": {"path": "a"}}]
    _, msgs = to_anthropic([{"role": "user", "content": "x"},
                            {"role": "assistant", "content": "", "_provider_state": {"anthropic_content": raw}},
                            {"role": "tool", "tool_call_id": "toolu_1", "content": "A"}])
    assert msgs[1]["content"] == [raw[0], raw[2]]                    # boş metin bloğu atılır
    assert msgs[2]["content"][0]["type"] == "tool_result"


def test_anthropic_akis_thinking_ve_arac():
    reasoning, deltas = [], []
    rec = Recorder([stream_resp([
        {"type": "message_start", "message": {"id": "msg_5", "usage": {"input_tokens": 100, "output_tokens": 1}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": "", "signature": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "plan "}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "SIG"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "ping"},
        {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Bakıyorum"}},
        {"type": "content_block_stop", "index": 1},
        {"type": "content_block_start", "index": 2, "content_block": {"type": "tool_use", "id": "toolu_1",
                                                                       "name": "read_file", "input": {}}},
        {"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": '{"pa'}},
        {"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": 'th": "app.py"}'}},
        {"type": "content_block_stop", "index": 2},
        {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 50}},
        {"type": "message_stop"},
    ])])
    r = ant(rec).chat("claude-haiku-5-5", [{"role": "user", "content": "x"}], stream=True, tools=TOOLS,
                      on_delta=lambda t, _: deltas.append(t), on_reasoning=reasoning.append)
    assert "".join(reasoning) == "plan " and r.reasoning == "plan "
    assert "".join(deltas) == "Bakıyorum" and r.content == "Bakıyorum"
    assert r.finish_reason == "tool_calls"
    assert json.loads(r.tool_calls[0]["arguments"]) == {"path": "app.py"}
    blocks = r.provider_state["anthropic_content"]
    assert blocks[0] == {"type": "thinking", "thinking": "plan ", "signature": "SIG"}
    assert blocks[2]["input"] == {"path": "app.py"}
    assert r.token_usage() == {"input_tokens": 100, "output_tokens": 50, "cached_tokens": 0}


@pytest.mark.parametrize("status,body,kind", [
    (402, {"type": "error", "error": {"type": "billing_error", "message": "kredi yok"}}, ErrorKind.QUOTA_EXHAUSTED),
    (429, {"type": "error", "error": {"type": "rate_limit_error", "message": "tavan",
                                      "details": {"error_code": "enforced_spend_limit_reached"}}},
     ErrorKind.QUOTA_EXHAUSTED),
    (401, {"type": "error", "error": {"type": "authentication_error", "message": "x"}}, ErrorKind.AUTH),
])
def test_anthropic_hata_esleme_tekrarsiz(status, body, kind):
    rec = Recorder([httpx.Response(status, json=body)] * 3)
    with pytest.raises(ApiError) as e:
        ant(rec, max_retries=2).chat("claude-haiku-5-5", [{"role": "user", "content": "x"}])
    assert e.value.kind == kind
    assert len(rec.requests) == 1


def test_anthropic_529_asiri_yuk_tekrar_edilebilir():
    rec = Recorder([httpx.Response(529, json={"type": "error", "error": {"type": "overloaded_error"}})])
    with pytest.raises(ApiError) as e:
        ant(rec, max_retries=0).chat("claude-haiku-5-5", [{"role": "user", "content": "x"}])
    assert e.value.kind == ErrorKind.SERVER_UNAVAILABLE and e.value.retryable


def test_anthropic_model_listesi():
    rec = Recorder([httpx.Response(200, json={"data": [
        {"id": "claude-haiku-5-5", "max_input_tokens": 200_000, "max_tokens": 64_000},
        {"id": "claude-eski-1"}]})])
    models = ant(rec).list_models()
    assert [m.id for m in models] == ["claude-haiku-5-5"]
    assert models[0].context_length == 200_000 and models[0].provider == "anthropic"
    assert rec.requests[0].headers["x-api-key"] == ANT_KEY


# ---- ajan döngüsü uçtan uca (sahte HTTP) ------------------------------------------


class Events(AgentEvents):
    def approval_needed(self, request):
        request.resolve("allow", "")


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "t.db")
    yield d
    d.close()


def _run(db, tmp_path, client, model):
    proj = tmp_path / "proje"
    proj.mkdir()
    (proj / "app.py").write_text("x = 1\n", encoding="utf-8")
    sid = db.create_session(model, str(proj), provider=provider_of_model(model))
    db.add_session_message(sid, "user", "app.py'yi oku")
    history = db.get_session_messages(sid)
    out = AgentRunner(client, model, session_id=sid, store=db, events=Events(),
                      workspace=Workspace(proj), protocol="native", stream=True).run(history)
    return out, db.get_session_messages(sid)


def test_ajan_openai_arac_dongusu(db, tmp_path):
    rec = Recorder([
        stream_resp([
            {"type": "response.output_item.done", "item": {"type": "reasoning", "id": "rs_1",
                                                           "encrypted_content": "ENC", "summary": []}},
            {"type": "response.output_item.done", "item": {"type": "function_call", "id": "fc_1",
                                                           "call_id": "call_1", "name": "read_file",
                                                           "arguments": '{"path": "app.py"}'}},
            {"type": "response.completed", "response": {"id": "r1", "status": "completed",
                                                        "usage": {"input_tokens": 300, "output_tokens": 20}}}]),
        stream_resp([
            {"type": "response.output_text.delta", "delta": "Dosyada x = 1 var."},
            {"type": "response.completed", "response": {"id": "r2", "status": "completed",
                                                        "usage": {"input_tokens": 400, "output_tokens": 10}}}]),
    ])
    out, saved = _run(db, tmp_path, oai(rec), "gpt-6-luna")
    assert out.stopped == "done" and out.protocol == "native"
    second = rec.body(1)
    kinds = [it["type"] for it in second["input"]]
    assert kinds == ["message", "reasoning", "function_call", "function_call_output"]
    assert second["input"][1]["encrypted_content"] == "ENC"
    assert "x = 1" in second["input"][3]["output"] and second["input"][3]["call_id"] == "call_1"
    assert second["instructions"]                                   # sistem istemi gider
    metas = [m.get("meta") or {} for m in saved if m["role"] == "assistant"]
    assert metas[0]["usage"] == {"input_tokens": 300, "output_tokens": 20, "cached_tokens": 0}
    assert metas[0]["provider_state"]["openai_items"][0]["type"] == "reasoning"


def test_ajan_anthropic_arac_dongusu(db, tmp_path):
    rec = Recorder([
        stream_resp([
            {"type": "message_start", "message": {"id": "m1", "usage": {"input_tokens": 500, "output_tokens": 1}}},
            {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": "", "signature": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "okuyayım"}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "SIG1"}},
            {"type": "content_block_stop", "index": 0},
            {"type": "content_block_start", "index": 1, "content_block": {"type": "tool_use", "id": "toolu_1",
                                                                           "name": "read_file", "input": {}}},
            {"type": "content_block_delta", "index": 1,
             "delta": {"type": "input_json_delta", "partial_json": '{"path": "app.py"}'}},
            {"type": "content_block_stop", "index": 1},
            {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 40}},
            {"type": "message_stop"}]),
        stream_resp([
            {"type": "message_start", "message": {"id": "m2", "usage": {"input_tokens": 600}}},
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "x = 1"}},
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 5}},
            {"type": "message_stop"}]),
    ])
    out, saved = _run(db, tmp_path, ant(rec), "claude-haiku-5-5")
    assert out.stopped == "done"
    msgs = rec.body(1)["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[1]["content"][0] == {"type": "thinking", "thinking": "okuyayım", "signature": "SIG1"}
    assert msgs[1]["content"][1]["type"] == "tool_use" and msgs[1]["content"][1]["input"] == {"path": "app.py"}
    res = msgs[2]["content"][0]
    assert res["type"] == "tool_result" and res["tool_use_id"] == "toolu_1" and "x = 1" in res["content"]
    assert rec.body(1)["system"]
    assert saved[-1]["content"] == "x = 1"


def test_before_model_call_butce_durdurur(db, tmp_path):
    rec = Recorder([])
    sid = db.create_session("claude-haiku-5-5", None, provider="anthropic")
    db.add_session_message(sid, "user", "x")
    out = AgentRunner(ant(rec), "claude-haiku-5-5", session_id=sid, store=db, events=Events(),
                      stream=False, before_model_call=lambda step: "budget").run(db.get_session_messages(sid))
    assert out.stopped == "budget" and rec.requests == []


# ---- maliyet, bütçe, veritabanı, anahtarlar -----------------------------------------


def test_maliyet_tahmini_ve_kullanim():
    m = CATALOG_BY_ID["claude-haiku-5-5"]
    full = estimate_cost("claude-haiku-5-5", {"input_tokens": 1_000_000, "output_tokens": 1_000_000})
    assert full == pytest.approx(m.price_in + m.price_out)
    cached = estimate_cost("claude-haiku-5-5", {"input_tokens": 1_000_000, "cached_tokens": 500_000})
    assert cached == pytest.approx(0.5 * m.price_in + 0.5 * m.price_cached)
    assert estimate_cost("glm-5.3", {"input_tokens": 10**6}) == 0.0           # EVREN ücretsiz
    assert normalize_usage({"prompt_tokens": 5, "completion_tokens": 2}) == \
        {"input_tokens": 5, "output_tokens": 2, "cached_tokens": 0}
    assert provider_of_model("gpt-6-luna") == "openai"
    assert provider_of_model("claude-opus-5-5") == "anthropic"
    assert provider_of_model("glm-5.3") == "evren"


def test_butce_durumu():
    assert BudgetState(4.0, 5.0, True).warn and not BudgetState(4.0, 5.0, True).exceeded
    assert BudgetState(5.0, 5.0, True).exceeded
    assert not BudgetState(9.0, 5.0, False).exceeded                     # zorlama kapalı
    assert not BudgetState(9.0, 0.0, True).exceeded                      # 0 = sınırsız
    assert not BudgetState(3.0, 5.0, True).warn
    assert "5,00" in BudgetState(1.0, 5.0, True).text()


def test_aylik_harcama_veritabani(db):
    db.add_usage_cost("openai", "gpt-6-luna", {"input_tokens": 10, "output_tokens": 5}, 0.25)
    db.add_usage_cost("anthropic", "claude-haiku-5-5", {"input_tokens": 1}, 1.5)
    db.add_usage_cost("anthropic", "claude-haiku-5-5", {"input_tokens": 1}, 0.5)
    assert db.month_spend() == {"openai": 0.25, "anthropic": 2.0}
    assert db.month_spend("1999-01") == {}
    assert current_state(db, 5.0).spent == pytest.approx(2.25)
    db.wipe_user_data()
    assert db.month_spend() == {}


def test_saglayici_anahtarlari_ayri_saklanir(fake_keyring):
    secrets.save_api_key("evren_llm_TEST123456789", "evren")
    secrets.save_api_key(OAI_KEY, "openai")
    secrets.save_api_key(ANT_KEY, "anthropic")
    assert secrets.load_api_key() == "evren_llm_TEST123456789"
    assert secrets.load_api_key("openai") == OAI_KEY
    assert secrets.load_api_key("anthropic") == ANT_KEY
    secrets.delete_api_key("openai")
    assert secrets.load_api_key("openai") is None and secrets.load_api_key("anthropic") == ANT_KEY


def test_saglayici_anahtarlari_maskelenir():
    text = f"Authorization: Bearer {OAI_KEY}\nx-api-key: {ANT_KEY}\nhata {ANT_KEY} ve {OAI_KEY}"
    masked = secrets.mask_secret(text)
    assert OAI_KEY not in masked and ANT_KEY not in masked
    assert "SAHTEANAHTAR" not in masked


# ---- arayüz ----------------------------------------------------------------------------


@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
    yield app, w
    w.close()


def _wait(app, cond, timeout=6.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def _popup_texts(comp):
    comp._show_models()
    return [(comp.popup.item(i).text(), comp.popup.item(i).flags()) for i in range(comp.popup.count())]


def test_gruplu_model_secici_ve_anahtar_kapisi(win, monkeypatch):
    """Yalnız anahtarı girilmiş sağlayıcıların modelleri listelenir (kullanıcı kararı 2026-10-19)."""
    from PySide6.QtCore import Qt

    app, w = win
    s = w.session
    s.refresh_models()
    rows = _popup_texts(s.composer)
    heads = [t for t, f in rows if f == Qt.NoItemFlags]
    assert "Otomatik yönlendirme" in heads and "EVREN · ücretsiz" in heads
    assert not any("gpt-6-luna" in t for t, _ in rows)              # anahtar yok → görünmez
    assert not any(h.startswith("OpenAI") for h in heads)
    # anahtar girilince grup ve fiyat ipucu görünür
    w.ctx._provider_keys["openai"] = OAI_KEY
    s.refresh_models()
    rows = _popup_texts(s.composer)
    heads = [t for t, f in rows if f == Qt.NoItemFlags]
    assert "OpenAI · ücretli · doğrulanmadı" in heads
    luna = next(t for t, _ in rows if "gpt-6-luna" in t)
    assert "$" in luna
    s.set_model("gpt-6-luna")
    assert s.model == "gpt-6-luna"

def test_ayarlar_saglayici_anahtari_ve_butce(win, monkeypatch, fake_keyring):
    from PySide6.QtWidgets import QMessageBox

    app, w = win
    page = w.pages["settings"]
    page.refresh()
    assert page.budget.value() == 5.0 and page.budget_enforce.isChecked()   # varsayılan $5/ay
    assert "Bu ayki tahmini harcama" in page.spend_label.text()
    p = page._prov["anthropic"]
    assert p["key_label"].text() == "yok"
    p["input"].setText(ANT_KEY)
    page.save_provider_key("anthropic")
    assert secrets.load_api_key("anthropic") == ANT_KEY
    assert w.ctx.has_provider_key("anthropic")
    assert ANT_KEY not in p["key_label"].text() and "sk-ant-a" in p["key_label"].text()
    assert p["input"].text() == ""
    # bütçe kaydı
    page.budget.setValue(12.5)
    page._collect(w.ctx.settings)
    assert w.ctx.settings.monthly_budget_usd == 12.5
    # silme
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    page.delete_provider_key("anthropic")
    assert secrets.load_api_key("anthropic") is None and not w.ctx.has_provider_key("anthropic")


def test_ayarlar_baglanti_dogrulama(win):
    app, w = win
    page = w.pages["settings"]
    w.ctx._provider_keys["anthropic"] = ANT_KEY
    rec = Recorder([httpx.Response(200, json={"data": [{"id": "claude-haiku-5-5"}]})])
    w.ctx.make_client_for = lambda provider, log_sink=None: ant(rec)
    page.verify_provider("anthropic")
    st = page._prov["anthropic"]["status"]
    assert _wait(app, lambda: "Bağlantı başarılı" in st.text() or "başarısız" in st.text())
    assert "claude-haiku-5-5" in st.text()


def _haiku_text_stream(text="Merhaba!"):
    return stream_resp([
        {"type": "message_start", "message": {"id": "m", "usage": {"input_tokens": 1000}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 200}},
        {"type": "message_stop"}])


def test_oturum_anthropic_maliyet_ve_butce_onayi(win, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    app, w = win
    s = w.session
    w.ctx._provider_keys["anthropic"] = ANT_KEY
    rec = Recorder([_haiku_text_stream(), _haiku_text_stream("İkinci")])
    w.ctx.make_client_for = lambda provider, log_sink=None: ant(rec)
    s.welcome._choose(None)
    s.set_model("claude-haiku-5-5")
    s.send("merhaba")
    assert _wait(app, lambda: not s.running)
    assert len(rec.requests) == 1
    assert w.ctx.db.get_session(s.session_id)["provider"] == "anthropic"
    spent = w.ctx.db.month_spend()["anthropic"]
    assert spent == pytest.approx(estimate_cost("claude-haiku-5-5",
                                                {"input_tokens": 1000, "output_tokens": 200}))
    # bütçe aşıldı → onay; Hayır derse istek gitmez, metin geri gelir
    w.ctx.db.add_usage_cost("anthropic", "claude-haiku-5-5", {}, 10.0)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    s.send("ikinci soru")
    assert len(rec.requests) == 1 and s.composer.edit.toPlainText() == "ikinci soru"
    # Evet derse bu ay için serbest
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    s.composer.edit.clear()
    s.send("ikinci soru")
    assert _wait(app, lambda: not s.running)
    assert len(rec.requests) == 2
