"""Döngü bekçisi: tekrar eden araç çağrısı, ileri-geri düzenleme, boş yanıt ve
"inceleyeyim" deyip durma (2026-10-17 gerçek API döngü analizinden)."""
from __future__ import annotations

import json

import pytest

from evren_studio.agent.runner import (
    NUDGE_EMPTY,
    NUDGE_INTENT,
    AgentEvents,
    AgentRunner,
    looks_like_unfinished_intent,
)
from evren_studio.agent.tools import Workspace
from evren_studio.api.client import ChatResult
from evren_studio.db import Database


def tc(name, cid, **args):
    return ChatResult(tool_calls=[{"id": cid, "name": name,
                                   "arguments": json.dumps(args, ensure_ascii=False)}],
                      finish_reason="tool_calls")


class Fake:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None,
             on_reasoning=None, tools=None, **kw):
        self.requests.append({"messages": messages, "kw": kw})
        if not self.responses:
            return ChatResult(content="Bitti, özet: değişiklik yapıldı.", finish_reason="stop")
        return self.responses.pop(0)


class Ev(AgentEvents):
    def __init__(self):
        self.statuses = []

    def status(self, text):
        self.statuses.append(text)


@pytest.fixture()
def env(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    (root / "a.py").write_text("KDV = 0.20\n", encoding="utf-8")
    db = Database(tmp_path / "t.db")
    yield root, db
    db.close()


def run(env, responses, **kw):
    root, db = env
    sid = db.create_session("m", str(root), "kabul")
    db.add_session_message(sid, "user", "görev")
    client, ev = Fake(responses), Ev()
    r = AgentRunner(client, "m", session_id=sid, store=db, events=ev, workspace=Workspace(root),
                    mode="kabul", stream=False, **kw)
    out = r.run(db.get_session_messages(sid))
    return out, client, ev, db.get_session_messages(sid)


def test_ayni_okuma_ikinci_kez_uyari_ucuncu_kez_durur(env):
    out, client, ev, msgs = run(env, [tc("read_file", f"c{i}", path="a.py") for i in range(5)])
    tools = [m for m in msgs if m["role"] == "tool"]
    assert "[Döngü uyarısı]" not in tools[0]["content"]
    assert "[Döngü uyarısı]" in tools[1]["content"]
    assert out.stopped == "loop" and len(tools) == 3
    assert any("Döngü algılandı" in s for s in ev.statuses)


def test_yazma_sonrasi_tekrar_sayaci_sifirlanir(env):
    seq = [tc("read_file", "c1", path="a.py"),
           tc("edit_file", "c2", path="a.py", old_string="0.20", new_string="0.18"),
           tc("read_file", "c3", path="a.py"),
           tc("edit_file", "c4", path="a.py", old_string="0.18", new_string="0.19"),
           tc("read_file", "c5", path="a.py")]
    out, *_ = run(env, seq)
    assert out.stopped == "done"


def test_ileri_geri_duzenleme_algilanir(env):
    seq = [tc("edit_file", "c1", path="a.py", old_string="0.20", new_string="0.18"),
           tc("edit_file", "c2", path="a.py", old_string="0.18", new_string="0.20"),   # geri döndü
           tc("edit_file", "c3", path="a.py", old_string="0.20", new_string="0.18"),   # yine
           tc("edit_file", "c4", path="a.py", old_string="0.18", new_string="0.20")]
    out, client, ev, msgs = run(env, seq)
    tools = [m for m in msgs if m["role"] == "tool"]
    assert "ileri-geri" in tools[1]["content"]
    assert out.stopped == "loop"


def test_bos_yanit_bir_kez_durtulur_ve_dusunme_kapatilir(env):
    seq = [ChatResult(content="", reasoning="uzun düşünce...", finish_reason="length"),
           ChatResult(content="Tamamlandı: a.py incelendi.", finish_reason="stop")]
    out, client, ev, msgs = run(env, seq, stall_retry_body={"reasoning_effort": "none"})
    assert out.stopped == "done" and out.steps == 2
    second = client.requests[1]
    assert second["messages"][-1]["content"] == NUDGE_EMPTY
    assert second["kw"].get("extra_body") == {"reasoning_effort": "none"}
    # hatırlatma kayda yazılmaz
    assert not any(m["content"] == NUDGE_EMPTY for m in msgs)
    assert "extra_body" not in client.requests[0]["kw"]


def test_bos_yanit_ikinci_kez_gelirse_kullaniciya_soylenir(env):
    seq = [ChatResult(content="", finish_reason="length"), ChatResult(content="", finish_reason="length")]
    out, client, ev, msgs = run(env, seq)
    assert out.stopped == "done" and out.steps == 2
    assert any("boş yanıt" in s for s in ev.statuses)


def test_soz_verip_durma_durtulur(env):
    seq = [ChatResult(content="Önce projeyi inceleyeyim.", finish_reason="stop"),
           tc("read_file", "c1", path="a.py"),
           ChatResult(content="a.py içinde KDV = 0.20 tanımlı; değişiklik gerekmedi.", finish_reason="stop")]
    out, client, ev, msgs = run(env, seq)
    assert out.stopped == "done"
    assert client.requests[1]["messages"][-1]["content"] == NUDGE_INTENT
    assert any(m["role"] == "tool" for m in msgs)


@pytest.mark.parametrize("text,expected", [
    ("Önce projeyi inceleyeyim.", True),
    ("Şimdi testleri çalıştıracağım:", True),
    ("Dosyayı okuyorum…", True),
    ("Let me check the tests.", True),
    ("Tüm testler geçti. stok.py'de iki hata düzelttim.", False),
    ("", False),
    ("x" * 400 + " inceleyeyim", False),
])
def test_niyet_algilama(text, expected):
    assert looks_like_unfinished_intent(text) is expected


def test_tek_yanitta_dongu_algilaninca_kalan_cagrilar_calismaz(env):
    # glm-5.3 gözlemi: tek yanıtta aynı dosyayı defalarca okuyan çok sayıda çağrı
    calls = [{"id": f"c{i}", "name": "read_file", "arguments": json.dumps({"path": "a.py"})}
             for i in range(8)]
    out, client, ev, msgs = run(env, [ChatResult(tool_calls=calls, finish_reason="tool_calls")])
    tools = [m for m in msgs if m["role"] == "tool"]
    assert out.stopped == "loop" and len(tools) == 8          # her çağrıya yanıt yazılır
    assert sum("çalıştırılmadı" in t["content"] for t in tools) == 5


def test_tek_yanitta_cagri_siniri(env):
    root, _ = env
    for i in range(15):
        (root / f"f{i}.py").write_text("x\n", encoding="utf-8")
    calls = [{"id": f"c{i}", "name": "read_file", "arguments": json.dumps({"path": f"f{i}.py"})}
             for i in range(15)]
    out, client, ev, msgs = run(env, [ChatResult(tool_calls=calls, finish_reason="tool_calls")])
    tools = [m for m in msgs if m["role"] == "tool"]
    assert len(tools) == 15 and sum("atlandı" in t["content"] for t in tools) == 3


# ---- metin içi tekrar (auto, 2026-10-17 maraton) ---------------------------------------

DEJENERE = ("README.md dosyası oluşturuldu. " + "Testlerin çalışması için harcama.py dosyasının doğru "
            "olduğunu doğrulayayım. harcama.py dosyasını okuyayım. Testleri çalıştıracağım. " * 6)


def test_metin_tekrari_kisaltilir_ve_durtulur(env):
    from evren_studio.agent.runner import NUDGE_REPEAT, REPEAT_COLLAPSED

    seq = [ChatResult(content=DEJENERE, finish_reason="stop"),
           tc("read_file", "c1", path="a.py"),
           ChatResult(content="Bitti: a.py okundu, değişiklik gerekmedi.", finish_reason="stop")]
    out, client, ev, msgs = run(env, seq)
    first = [m for m in msgs if m["role"] == "assistant"][0]["content"]
    assert first.endswith(REPEAT_COLLAPSED) and first.count("okuyayım") == 1
    assert client.requests[1]["messages"][-1]["content"] == NUDGE_REPEAT
    assert out.stopped == "done"


def test_normal_ozet_tekrar_sayilmaz():
    from evren_studio.agent.runner import collapse_repetition

    ozet = ("Testler geçti. stok.py'de ekle düzeltildi. fiyat.py'de indirim düzeltildi. "
            "README güncellendi. Testler geçti. Komut: python -m unittest -v")
    assert collapse_repetition(ozet) == (ozet, False)


def test_akista_tekrar_istegi_keser(env):
    class Streaming(Fake):
        def chat(self, model, messages, stream=False, cancel=None, on_delta=None, **kw):
            self.requests.append({"messages": messages, "kw": kw})
            if len(self.requests) > 1:
                return ChatResult(content="Tamam, iş bitti ve özetlendi burada.", finish_reason="stop")
            sent = []
            for i in range(2000):
                if cancel is not None and cancel.cancelled:
                    return ChatResult(content="".join(sent), finish_reason="cancelled_by_user")
                piece = "harcama.py dosyasını okuyayım. " if i % 2 else "Testleri çalıştıracağım. "
                sent.append(piece)
                on_delta(piece, "")
            return ChatResult(content="".join(sent), finish_reason="stop")

    root, db = env
    sid = db.create_session("m", str(root), "kabul")
    db.add_session_message(sid, "user", "görev")
    client = Streaming([])
    r = AgentRunner(client, "m", session_id=sid, store=db, events=Ev(), workspace=Workspace(root),
                    mode="kabul", stream=True)
    out = r.run(db.get_session_messages(sid))
    msgs = db.get_session_messages(sid)
    first = [m for m in msgs if m["role"] == "assistant"][0]
    assert first["meta"]["finish_reason"] == "repetition"
    assert out.stopped == "done" and len(client.requests) == 2      # dürtüldü, kullanıcı iptali sayılmadı


def test_sunucu_model_json_400_ayni_adimi_yeniden_dener(env):
    """EVREN, modelin bozuk araç JSON'unu okuyamayınca 400 dönüyor; yerel protokol bırakılmamalı."""
    from evren_studio.api.errors import ApiError, ErrorKind

    class Flaky(Fake):
        def chat(self, model, messages, **kw):
            self.requests.append({"messages": messages, "kw": kw})
            if len(self.requests) == 1:
                raise ApiError(kind=ErrorKind.VALIDATION, status=400,
                               message="{'message': \"Expecting ',' delimiter: line 1 column 2371\"}")
            return ChatResult(content="Tamam, iş bitti.", finish_reason="stop")

    root, db = env
    sid = db.create_session("m", str(root), "kabul")
    db.add_session_message(sid, "user", "görev")
    client, ev = Flaky([]), Ev()
    r = AgentRunner(client, "m", session_id=sid, store=db, events=ev, workspace=Workspace(root),
                    mode="kabul", stream=False)
    out = r.run(db.get_session_messages(sid))
    assert out.stopped == "done" and out.protocol == "native" and len(client.requests) == 2
    assert any("yeniden deneniyor" in s for s in ev.statuses)


def test_gercek_400_metin_protokolune_gecer(env):
    from evren_studio.api.errors import ApiError, ErrorKind

    class Rejects(Fake):
        def chat(self, model, messages, tools=None, **kw):
            self.requests.append({"messages": messages, "kw": kw})
            if tools:
                raise ApiError(kind=ErrorKind.VALIDATION, status=400, message="tools not supported")
            return ChatResult(content="Tamam, iş bitti.", finish_reason="stop")

    out, client, ev, msgs = run(env, [])
    root, db = env
    sid = db.create_session("m", str(root), "kabul")
    db.add_session_message(sid, "user", "görev")
    c2 = Rejects([])
    r = AgentRunner(c2, "m", session_id=sid, store=db, events=Ev(), workspace=Workspace(root),
                    mode="kabul", stream=False)
    assert r.run(db.get_session_messages(sid)).protocol == "text"


def test_plan_modunda_niyet_cumlesi_durtulmez(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    db = Database(tmp_path / "t.db")
    sid = db.create_session("m", str(root), "plan")
    db.add_session_message(sid, "user", "planla")
    client = Fake([ChatResult(content="Plan: a.py'yi değiştireceğim.", finish_reason="stop")])
    r = AgentRunner(client, "m", session_id=sid, store=db, events=Ev(), workspace=Workspace(root),
                    mode="plan", stream=False)
    out = r.run(db.get_session_messages(sid))
    db.close()
    assert out.stopped == "done" and len(client.requests) == 1
