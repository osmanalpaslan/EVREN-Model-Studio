"""Ajan döngüsü testleri — sahte model istemcisiyle (gerçek ağ yok)."""
from __future__ import annotations

import copy
import json

import pytest

from evren_studio.agent.permissions import SessionPermissions
from evren_studio.agent.runner import (
    TRIMMED_NOTE,
    AgentEvents,
    AgentRunner,
    ApprovalRequest,
    to_api_messages,
    trim_for_context,
)
from evren_studio.agent.tools import Workspace
from evren_studio.api.client import CancelToken, ChatResult
from evren_studio.api.errors import ApiError, ErrorKind
from evren_studio.db import Database


def call(name, cid="c1", **args):
    return {"id": cid, "name": name, "arguments": json.dumps(args, ensure_ascii=False)}


class FakeClient:
    """Sırayla önceden yazılmış yanıtları döndürür; gelen istekleri kaydeder."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None,
             on_reasoning=None, tools=None, **kw):
        self.calls.append({"messages": copy.deepcopy(messages), "tools": tools})
        if not self.responses:
            return ChatResult(content="(bitti)", model=model, finish_reason="stop")
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        if callable(r):
            r = r(tools)
        if on_delta and r.content:
            on_delta(r.content, "")
        return r


class Recorder(AgentEvents):
    def __init__(self, decision="allow", feedback="", cancel=None):
        self.decision = decision
        self.feedback = feedback
        self.cancel = cancel
        self.approvals = []
        self.protocols = []
        self.todos = []
        self.files = []
        self.text = ""

    def text_delta(self, text):
        self.text += text

    def approval_needed(self, request: ApprovalRequest):
        self.approvals.append(request)
        if self.cancel is not None:
            self.cancel.cancel()
            return  # karar verilmez; iptal beklemeyi sonlandırmalı
        request.resolve(self.decision, self.feedback)

    def protocol_changed(self, protocol, reason):
        self.protocols.append(protocol)

    def todos_changed(self, todos):
        self.todos.append(todos)

    def file_changed(self, change_id, change):
        self.files.append((change_id, change.rel_path))


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    yield d
    d.close()


@pytest.fixture()
def proj(tmp_path):
    root = tmp_path / "proje"
    root.mkdir()
    (root / "app.py").write_text("x = 1\n", encoding="utf-8")
    return root


def make_runner(db, client, proj=None, events=None, **kw):
    sid = db.create_session("glm-5.3", str(proj) if proj else None)
    db.add_session_message(sid, "user", "görev")
    history = db.get_session_messages(sid)
    runner = AgentRunner(client, "glm-5.3", session_id=sid, store=db, events=events or Recorder(),
                         workspace=Workspace(proj) if proj else None, stream=False, **kw)
    return runner, history, sid


def test_sohbet_modu_arac_gondermez(db):
    client = FakeClient([ChatResult(content="Merhaba!", model="glm-5.3", finish_reason="stop")])
    runner, history, sid = make_runner(db, client)
    out = runner.run(history)
    assert out.stopped == "done" and out.steps == 1
    assert client.calls[0]["tools"] is None
    roles = [m["role"] for m in db.get_session_messages(sid)]
    assert roles == ["user", "assistant"]


def test_yerel_arac_dongusu(db, proj):
    client = FakeClient([
        ChatResult(content="Okuyorum.", tool_calls=[call("read_file", path="app.py")]),
        ChatResult(content="x değişkeni 1.", finish_reason="stop"),
    ])
    runner, history, sid = make_runner(db, client, proj)
    out = runner.run(history)
    assert out.stopped == "done" and out.steps == 2
    tool_names = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert {"read_file", "edit_file", "run_command"} <= tool_names
    second = client.calls[1]["messages"]
    tool_msg = [m for m in second if m["role"] == "tool"][0]
    assert tool_msg["tool_call_id"] == "c1" and "x = 1" in tool_msg["content"]
    asst = [m for m in second if m["role"] == "assistant"][0]
    assert asst["tool_calls"][0]["function"]["name"] == "read_file"
    saved = db.get_session_messages(sid)
    assert [m["role"] for m in saved] == ["user", "assistant", "tool", "assistant"]
    assert saved[2]["meta"]["summary"].startswith("Okundu")


def test_duzenleme_onaylanirsa_uygulanir_ve_kaydedilir(db, proj):
    ev = Recorder("allow")
    client = FakeClient([
        ChatResult(tool_calls=[call("edit_file", path="app.py", old_string="x = 1", new_string="x = 2")]),
        ChatResult(content="Tamam", finish_reason="stop"),
    ])
    runner, history, sid = make_runner(db, client, proj, ev)
    runner.run(history)
    assert len(ev.approvals) == 1 and "-x = 1" in ev.approvals[0].detail
    assert (proj / "app.py").read_text(encoding="utf-8") == "x = 2\n"
    changes = db.list_file_changes(sid)
    assert len(changes) == 1 and changes[0]["before_text"] == "x = 1\n"
    assert ev.files and ev.files[0][1] == "app.py"


def test_reddedilen_duzenleme_uygulanmaz_ve_not_iletilir(db, proj):
    ev = Recorder("deny", feedback="önce test yaz")
    client = FakeClient([
        ChatResult(tool_calls=[call("write_file", path="yeni.py", content="print(1)\n")]),
        ChatResult(content="Anladım", finish_reason="stop"),
    ])
    runner, history, sid = make_runner(db, client, proj, ev)
    runner.run(history)
    assert not (proj / "yeni.py").exists()
    tool = [m for m in client.calls[1]["messages"] if m["role"] == "tool"][0]
    assert "reddetti" in tool["content"] and "önce test yaz" in tool["content"]
    assert db.list_file_changes(sid) == []


def test_oturumda_hep_izin_ver(db, proj):
    ev = Recorder("allow_session")
    perms = SessionPermissions()
    client = FakeClient([
        ChatResult(tool_calls=[call("write_file", "a", path="a.txt", content="1\n")]),
        ChatResult(tool_calls=[call("write_file", "b", path="b.txt", content="2\n")]),
        ChatResult(content="bitti", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, proj, ev, permissions=perms)
    runner.run(history)
    assert len(ev.approvals) == 1, "İkinci yazma için tekrar sorulmamalı"
    assert perms.allow_all_writes
    assert (proj / "b.txt").exists()


def test_plan_modu_yazmayi_engeller(db, proj):
    ev = Recorder("allow")
    client = FakeClient([
        ChatResult(tool_calls=[call("write_file", path="a.txt", content="1")]),
        ChatResult(content="Plan: ...", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, proj, ev, mode="plan")
    runner.run(history)
    names = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert "write_file" not in names and "run_command" not in names
    assert not ev.approvals and not (proj / "a.txt").exists()
    tool = [m for m in client.calls[1]["messages"] if m["role"] == "tool"][0]
    assert "Plan modunda" in tool["content"]


def test_otomatik_mod_dosyayi_onaysiz_yazar_komutu_sorar(db, proj):
    ev = Recorder("deny")
    client = FakeClient([
        ChatResult(tool_calls=[call("write_file", "a", path="a.txt", content="1\n"),
                               call("run_command", "b", command="Write-Output hi")]),
        ChatResult(content="tamam", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, proj, ev, mode="otomatik")
    runner.run(history)
    assert (proj / "a.txt").exists()
    assert len(ev.approvals) == 1 and ev.approvals[0].kind == "exec"


def test_metin_protokolu(db, proj):
    text = ('Bakıyorum.\n<arac_cagrisi>\n{"name": "read_file", "arguments": {"path": "app.py"}}\n'
            "</arac_cagrisi>")
    client = FakeClient([
        ChatResult(content=text),
        ChatResult(content="Dosyada x = 1 var.", finish_reason="stop"),
    ])
    runner, history, sid = make_runner(db, client, proj, protocol="text")
    runner.run(history)
    assert client.calls[0]["tools"] is None
    assert "<arac_cagrisi>" in client.calls[0]["messages"][0]["content"], "sistem istemi protokolü anlatmalı"
    second = client.calls[1]["messages"]
    assert all(m["role"] != "tool" for m in second)
    assert "<arac_sonucu" in second[-1]["content"] and "x = 1" in second[-1]["content"]
    saved = db.get_session_messages(sid)
    assert saved[1]["content"] == "Bakıyorum."      # blok görünür metinden çıkarıldı


def test_yerel_arac_reddedilirse_metne_gecer(db, proj):
    ev = Recorder()
    err = ApiError(kind=ErrorKind.VALIDATION, message="tools not supported", status=422,
                   operation="chat_completions", model="glm-5.3")
    client = FakeClient([err, ChatResult(content="Merhaba", finish_reason="stop")])
    runner, history, _ = make_runner(db, client, proj, ev)
    out = runner.run(history)
    assert ev.protocols == ["text"] and out.protocol == "text"
    assert client.calls[1]["tools"] is None


def test_adim_siniri(db, proj):
    # Farklı parametreler: aynı çağrı tekrarı döngü bekçisine takılır (test_loop_guard.py)
    responses = [ChatResult(tool_calls=[call("list_files", f"c{i}", depth=i + 1)]) for i in range(10)]
    client = FakeClient(responses)
    runner, history, _ = make_runner(db, client, proj, max_steps=3)
    out = runner.run(history)
    assert out.stopped == "max_steps" and len(client.calls) == 3


def test_onay_beklerken_iptal(db, proj):
    token = CancelToken()
    ev = Recorder(cancel=token)
    client = FakeClient([
        ChatResult(tool_calls=[call("run_command", command="Write-Output x")]),
        ChatResult(content="olmamalı"),
    ])
    runner, history, _ = make_runner(db, client, proj, ev, cancel=token)
    out = runner.run(history)
    assert out.stopped == "cancelled" and len(client.calls) == 1


def test_bilinmeyen_arac_ve_bozuk_parametre(db, proj):
    client = FakeClient([
        ChatResult(tool_calls=[{"id": "u", "name": "format_disk", "arguments": "{}"},
                               {"id": "v", "name": "read_file", "arguments": "{bozuk"}]),
        ChatResult(content="tamam", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, proj)
    runner.run(history)
    tools = [m for m in client.calls[1]["messages"] if m["role"] == "tool"]
    assert "Bilinmeyen araç" in tools[0]["content"]
    assert "JSON" in tools[1]["content"]


def test_gorev_listesi_kaydedilir(db, proj):
    ev = Recorder()
    client = FakeClient([
        ChatResult(tool_calls=[{"id": "t", "name": "update_todos", "arguments": json.dumps(
            {"todos": [{"content": "İncele", "status": "in_progress"}]})}]),
        ChatResult(content="tamam", finish_reason="stop"),
    ])
    runner, history, sid = make_runner(db, client, proj, ev)
    runner.run(history)
    assert db.get_session_todos(sid)[0]["content"] == "İncele"
    assert ev.todos


def test_ozetten_sonrasi_gonderilir():
    hist = [
        {"role": "user", "content": "eski"},
        {"role": "assistant", "content": "eski yanıt"},
        {"role": "summary", "content": "ÖZET"},
        {"role": "user", "content": "yeni"},
    ]
    msgs = to_api_messages("sys", hist, "native")
    joined = " ".join(m["content"] for m in msgs)
    assert "eski yanıt" not in joined and "ÖZET" in joined and msgs[-1]["content"] == "yeni"


def test_baglam_siniri_eski_cikti_kisaltir():
    hist = [{"role": "user", "content": "x"}]
    for i in range(12):
        hist.append({"role": "assistant", "content": "", "tool_calls": [{"id": str(i), "name": "read_file", "arguments": "{}"}]})
        hist.append({"role": "tool", "tool_call_id": str(i), "content": "a" * 5000})
    trimmed = trim_for_context(hist, context_tokens=10_000)
    assert trimmed[2]["content"] == TRIMMED_NOTE
    assert trimmed[-1]["content"] == "a" * 5000, "son mesajlar korunmalı"
    assert hist[2]["content"] == "a" * 5000, "kalıcı geçmiş değişmemeli"
