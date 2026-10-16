"""Otomatik özet (/compact): eşikler, güvenli nokta, göndermeden önce özet, otomatik devam."""
from __future__ import annotations

import json
import os
import time

import pytest

from evren_studio.agent.compaction import (
    CompactPolicy,
    build_summary_request,
    needs_compaction,
)
from evren_studio.agent.prompts import AUTO_CONTINUE_PROMPT, SUMMARY_SYSTEM
from evren_studio.api.client import ChatResult


def test_esikler():
    p = CompactPolicy()
    assert p.soft_limit(524_288) == 100_000 and p.hard_limit(524_288) == 150_000
    assert p.soft_limit(32_768) == 24_576 and p.hard_limit(32_768) == 29_491
    assert p.soft_limit(None) == 100_000
    assert CompactPolicy(percent=50).soft_limit(100_000) == 50_000
    assert p.hard_limit(32_768) <= int(32_768 * 0.9)


def _hist(n_pairs: int, size: int) -> list[dict]:
    h = []
    for i in range(n_pairs):
        h.append({"role": "user", "content": f"soru {i}"})
        h.append({"role": "assistant", "content": "y" * size})
    return h


def test_ozet_gerekip_gerekmedigi():
    p = CompactPolicy(max_tokens=10_000)
    assert not needs_compaction(_hist(3, 100), p, 524_288)[0]
    need, tokens, limit = needs_compaction(_hist(3, 15_000), p, 524_288)
    assert need and tokens >= limit == 10_000
    assert not needs_compaction(_hist(1, 50_000), p, 524_288)[0], "çok kısa konuşma özetlenmez"
    assert not needs_compaction(_hist(3, 15_000), CompactPolicy(enabled=False, max_tokens=10_000), None)[0]
    # son özetten öncesi sayılmaz
    h = _hist(3, 15_000) + [{"role": "summary", "content": "kısa özet"}] + _hist(2, 10)
    assert not needs_compaction(h, p, 524_288)[0]


def test_ozet_istegi_odak_ve_kisaltma():
    h = [{"role": "user", "content": "görev"},
         {"role": "assistant", "content": "", "tool_calls": [{"id": "a", "name": "read_file", "arguments": "{}"}]},
         {"role": "tool", "tool_call_id": "a", "name": "read_file", "content": "x" * 400_000}]
    h += _hist(5, 10)
    msgs = build_summary_request(h, focus="dosya yollarına odaklan", context_tokens=32_768)
    assert msgs[0]["content"] == SUMMARY_SYSTEM
    assert "dosya yollarına odaklan" in msgs[-1]["content"]
    assert sum(len(m["content"]) for m in msgs) < 32_768 * 3.5, "istek modele sığmalı"


def test_ajan_dongusu_guvenli_noktada_durur(tmp_path):
    from evren_studio.agent.runner import AgentRunner
    from evren_studio.agent.tools import Workspace
    from evren_studio.db import Database

    (tmp_path / "buyuk.txt").write_text("satır\n" * 30_000, encoding="utf-8")
    db = Database(tmp_path / "t.db")
    sid = db.create_session("m", str(tmp_path), "manuel")
    db.add_session_message(sid, "user", "oku")

    class C:
        calls = 0

        def chat(self, *a, **k):
            C.calls += 1
            return ChatResult(tool_calls=[{"id": f"c{C.calls}", "name": "read_file",
                                           "arguments": json.dumps({"path": "buyuk.txt"})}])

    r = AgentRunner(C(), "m", session_id=sid, store=db, workspace=Workspace(tmp_path), stream=False,
                    hard_context_limit=8_000, output_limit=60_000)
    out = r.run(db.get_session_messages(sid))
    assert out.stopped == "context_limit" and C.calls == 1
    roles = [m["role"] for m in db.get_session_messages(sid)]
    assert roles[-1] == "tool", "araç sonucu kaydedildikten SONRA durmalı (güvenli nokta)"


# ---- arayüz ------------------------------------------------------------------------


class ScriptClient:
    """Özet çağrısını (SUMMARY_SYSTEM) ayırt eden sahte istemci."""

    def __init__(self, chat_responses, summary="## Özet\nHedef: test.", delay=0.0):
        self.chat_responses = list(chat_responses)
        self.summary = summary
        self.delay = delay
        self.log = []

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None,
             on_reasoning=None, tools=None, **kw):
        if messages and messages[0]["content"] == SUMMARY_SYSTEM:
            self.log.append(("summary", messages))
            time.sleep(self.delay)
            return ChatResult(content=self.summary, model=model, finish_reason="stop")
        self.log.append(("chat", messages))
        r = self.chat_responses.pop(0) if self.chat_responses else ChatResult(content="bitti", finish_reason="stop")
        return r

    def close(self):
        pass


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
    w.ctx.settings.auto_compact_max_tokens = 10_000
    yield app, w
    w.close()


def _wait(app, cond, timeout=8.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def _seed_big_session(w, workspace=None):
    db = w.ctx.db
    sid = db.create_session("glm-5.3", workspace, "manuel", title="uzun")
    for i in range(3):
        db.add_session_message(sid, "user", f"soru {i}")
        db.add_session_message(sid, "assistant", "uzun yanıt " * 5_000)
    w.session.open_session(sid)
    return sid


def test_gondermeden_once_otomatik_ozet(win):
    app, w = win
    client = ScriptClient([ChatResult(content="Yeni yanıt.", finish_reason="stop")])
    w.ctx.make_client = lambda log_sink=None: client
    sid = _seed_big_session(w)
    w.session.send("yeni soru")
    assert _wait(app, lambda: not w.session.running and len(client.log) == 2)
    assert [k for k, _ in client.log] == ["summary", "chat"], "önce özet, sonra mesaj"
    msgs = w.ctx.db.get_session_messages(sid)
    roles = [m["role"] for m in msgs]
    assert roles[-3:] == ["summary", "user", "assistant"]
    assert msgs[-3]["meta"]["auto"] is True and "eşiği" in msgs[-3]["meta"]["reason"]
    sent = client.log[1][1]
    assert not any("uzun yanıt" in (m.get("content") or "") for m in sent), "eski mesajlar özetle değişmeli"
    assert any("## Özet" in (m.get("content") or "") for m in sent)


def test_uzun_gorevde_ozetleyip_otomatik_devam(win, tmp_path):
    app, w = win
    proj = tmp_path / "proje"
    proj.mkdir()
    # read_file en fazla 2000 satır döndürür: uzun satırlarla ~80k karakter (~23k token)
    (proj / "buyuk.txt").write_text(("satır " + "x" * 100 + "\n") * 3000, encoding="utf-8")
    w.ctx.settings.tool_output_limit = 80_000
    client = ScriptClient([
        ChatResult(tool_calls=[{"id": "r1", "name": "read_file", "arguments": json.dumps({"path": "buyuk.txt"})}]),
        ChatResult(content="Özetten sonra devam ettim ve bitirdim.", finish_reason="stop"),
    ])
    w.ctx.make_client = lambda log_sink=None: client
    w.session.welcome._choose(str(proj))
    w.session.send("buyuk.txt dosyasını oku ve özetle")
    assert _wait(app, lambda: not w.session.running and [k for k, _ in client.log] == ["chat", "summary", "chat"], 12)
    msgs = w.ctx.db.get_session_messages(w.session.session_id)
    roles = [m["role"] for m in msgs]
    assert "summary" in roles
    cont = [m for m in msgs if m["role"] == "user" and (m.get("meta") or {}).get("auto_continue")]
    assert len(cont) == 1 and cont[0]["content"] == AUTO_CONTINUE_PROMPT
    assert msgs[-1]["content"].startswith("Özetten sonra devam")
    assert w.session._auto_resumes == 1


def test_ozet_sirasinda_esc_mesaji_geri_koyar(win):
    app, w = win
    client = ScriptClient([], delay=0.8)
    w.ctx.make_client = lambda log_sink=None: client
    sid = _seed_big_session(w)
    before = len(w.ctx.db.get_session_messages(sid))
    w.session.send("kaybolmamalı")
    assert _wait(app, lambda: w.session.running, 2)
    w.session.stop()
    assert _wait(app, lambda: not w.session.running, 5)
    msgs = w.ctx.db.get_session_messages(sid)
    assert not any(m["role"] == "user" and m["content"] == "kaybolmamalı" for m in msgs)
    assert w.session.composer.edit.toPlainText() == "kaybolmamalı"
    assert [k for k, _ in client.log] == ["summary"]
    assert len(msgs) == before + 1   # özet yine de kaydedildi


def test_compact_komutu_odakla(win):
    app, w = win
    client = ScriptClient([])
    w.ctx.make_client = lambda log_sink=None: client
    sid = _seed_big_session(w)
    w.session.send("/compact dosya yollarına odaklan")
    assert _wait(app, lambda: not w.session.running and client.log)
    assert "dosya yollarına odaklan" in client.log[0][1][-1]["content"]
    last = w.ctx.db.get_session_messages(sid)[-1]
    assert last["role"] == "summary" and last["meta"]["focus"] == "dosya yollarına odaklan"
    assert last["meta"]["auto"] is False


def test_kapanista_gec_gelen_sonuc_islenmez(win):
    """Pencere kapandıktan sonra gelen arka plan sonucu kapalı veritabanına yazmamalı."""
    import sys

    app, w = win
    errors = []
    old = sys.excepthook
    sys.excepthook = lambda t, v, tb: errors.append(f"{t.__name__}: {v}")
    try:
        class Slow:
            def list_models(self):
                time.sleep(0.5)
                from evren_studio.api.client import ModelInfo
                return [ModelInfo("glm-5.3", "chat", ["text"], 1000, None, {"tools": True})]

            def close(self):
                pass

        w.ctx.make_client = lambda log_sink=None: Slow()
        w.pages["models"].refresh_models()
        w.close()
        end = time.monotonic() + 2
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.02)
    finally:
        sys.excepthook = old
    assert not errors, errors
