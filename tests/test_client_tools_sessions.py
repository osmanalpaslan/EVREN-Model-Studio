"""İstemcide araç çağrısı ayrıştırma ve oturum veritabanı testleri."""
from __future__ import annotations

import json
import sqlite3

import httpx

from evren_studio.api.client import EvrenClient
from evren_studio.db import Database

BASE = "https://test.example/v1"
KEY = "evren_llm_TESTKEY"


def sse(*chunks) -> bytes:
    lines = [f"data: {json.dumps(c)}\n\n" for c in chunks] + ["data: [DONE]\n\n"]
    return "".join(lines).encode("utf-8")


def test_akista_arac_cagrisi_parcalari_birlestirilir():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        body = sse(
            {"id": "x", "choices": [{"delta": {"content": "Bakıyorum"}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_1", "type": "function",
                                                     "function": {"name": "read_file", "arguments": "{\"pa"}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "th\": \"a.py\"}"}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 1, "id": "call_2",
                                                     "function": {"name": "list_files", "arguments": "{}"}}]}}]},
            {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
        )
        return httpx.Response(200, content=body, headers={"Content-Type": "text/event-stream"})

    client = EvrenClient(BASE, KEY, transport=httpx.MockTransport(handler))
    tools = [{"type": "function", "function": {"name": "read_file", "parameters": {}}}]
    res = client.chat("glm-5.3", [{"role": "user", "content": "x"}], stream=True, tools=tools)
    assert seen["body"]["tools"] == tools and seen["body"]["tool_choice"] == "auto"
    assert res.content == "Bakıyorum" and res.finish_reason == "tool_calls"
    assert res.tool_calls == [
        {"id": "call_1", "name": "read_file", "arguments": '{"path": "a.py"}'},
        {"id": "call_2", "name": "list_files", "arguments": "{}"},
    ]


def test_akissiz_arac_cagrisi():
    def handler(request):
        assert "tools" not in json.loads(request.content)
        return httpx.Response(200, json={
            "id": "req-1", "model": "glm-5.3",
            "choices": [{"finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": None,
                "tool_calls": [{"id": "t1", "type": "function",
                                "function": {"name": "run_command", "arguments": {"command": "dir"}}}]}}],
        })

    client = EvrenClient(BASE, KEY, transport=httpx.MockTransport(handler))
    res = client.chat("glm-5.3", [{"role": "user", "content": "x"}])
    assert res.content == ""
    assert res.tool_calls[0]["name"] == "run_command"
    assert json.loads(res.tool_calls[0]["arguments"]) == {"command": "dir"}


# ---- oturum veritabanı ---------------------------------------------------------------


def test_oturum_ve_mesajlar(tmp_path):
    db = Database(tmp_path / "s.db")
    sid = db.create_session("glm-5.3", "C:/proje", "plan", title="Deneme")
    db.add_session_message(sid, "user", "merhaba dünya")
    db.add_session_message(sid, "assistant", "", tool_calls=[{"id": "a", "name": "read_file", "arguments": "{}"}])
    db.add_session_message(sid, "tool", "çıktı", tool_call_id="a", name="read_file", meta={"summary": "Okundu"})
    msgs = db.get_session_messages(sid)
    assert msgs[1]["tool_calls"][0]["name"] == "read_file"
    assert msgs[2]["meta"]["summary"] == "Okundu"
    assert len(db.list_sessions("dünya")) == 1, "mesaj içeriğinde arama"
    assert len(db.list_sessions("proje")) == 1, "klasör adında arama"
    db.update_session(sid, pinned=1, mode="otomatik")
    assert db.get_session(sid)["mode"] == "otomatik"
    db.delete_session_messages_from(sid, msgs[1]["id"])
    assert len(db.get_session_messages(sid)) == 1
    cid = db.add_file_change(sid, None, "a.py", None, "x\n")
    db.mark_change_reverted(cid)
    assert db.list_file_changes(sid)[0]["reverted"] == 1
    assert "Deneme" in db.export_session_markdown(sid)
    db.delete_session(sid)
    assert db.get_session_messages(sid) == [] and db.list_file_changes(sid) == []
    db.close()


def test_v1_sohbetleri_oturuma_tasinir(tmp_path):
    path = tmp_path / "eski.db"
    db = Database(path)
    cid = db.create_chat("glm-5.3", "Eski sohbet")
    db.add_message(cid, "user", "eski soru")
    db.add_message(cid, "assistant", "eski yanıt")
    db._exec("DELETE FROM sessions")
    db._exec("UPDATE meta SET value='1' WHERE key='schema_version'")
    db._commit()
    db.close()

    db2 = Database(path)
    sessions = db2.list_sessions()
    assert len(sessions) == 1 and sessions[0]["title"] == "Eski sohbet"
    assert sessions[0]["workspace"] is None
    assert [m["content"] for m in db2.get_session_messages(sessions[0]["id"])] == ["eski soru", "eski yanıt"]
    db2.close()
    # ikinci açılışta tekrar taşınmaz
    db3 = Database(path)
    assert len(db3.list_sessions()) == 1
    version = db3._exec("SELECT value FROM meta WHERE key='schema_version'").fetchone()["value"]
    assert version == "3"
    assert db3.list_sessions()[0]["provider"] == "evren", "eski oturumlar EVREN sayılmalı"
    db3.close()
    assert sqlite3.connect(path).execute("SELECT COUNT(*) FROM chats").fetchone()[0] == 1, \
        "eski tablo silinmemeli"
