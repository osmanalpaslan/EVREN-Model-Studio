"""Klasörsüz sohbette yalnız web araçları (DEVIR_NOTU Madde 6, 2026-11-04): web_search / web_fetch sunulur ve
çalışır; dosya/komut araçları SUNULMAZ ve çalışmaz; ayar kapalıyken eski davranış (araçsız). Tetiklenen ve
tetiklenmeyen ipucu (R-22) ve gerçek tur akışı (R-31)."""
from __future__ import annotations

import json
import os
import time

import pytest

from evren_studio.agent import prompts, websearch
from evren_studio.agent.runner import AgentEvents, AgentRunner
from evren_studio.agent.tools import WEB_TOOLS
from evren_studio.api.client import ChatResult
from evren_studio.db import Database


class Script:
    def __init__(self, seq):
        self.seq = list(seq)
        self.systems: list[str] = []
        self.lasts: list[str] = []
        self.tool_names: list[list[str]] = []

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, on_reasoning=None, tools=None, **kw):
        self.systems.append(messages[0]["content"])
        self.lasts.append(str(messages[-1]["content"]))  # Madde 22 B: tura özel ipucu kuyruk notunda (son mesaj)
        self.tool_names.append([t["function"]["name"] for t in tools or []])
        return self.seq.pop(0) if self.seq else ChatResult(content="yanıt", finish_reason="stop")

    def close(self):
        pass


def call(name, **args):
    return ChatResult(content="", tool_calls=[{"id": "c1", "name": name, "arguments": json.dumps(args)}],
                      finish_reason="tool_calls")


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "t.db")
    yield d
    d.close()


@pytest.fixture()
def sahte_arama(monkeypatch):
    calls: list = []

    def fake(query, guncel=False, haber=False, max_results=5, **kw):
        calls.append(query)
        return websearch.SearchResult("tavily", "cevap", [{"title": "T", "url": "https://kaynak.org", "date": "",
                                                           "snippet": "özet"}])
    monkeypatch.setattr(websearch, "search", fake)
    return calls


def run(db, seq, text="soru", chat_tools=True, mode="auto"):
    sid = db.create_session("m", None)
    db.add_session_message(sid, "user", text)
    c = Script(seq)
    r = AgentRunner(c, "m", session_id=sid, store=db, events=AgentEvents(), workspace=None, mode=mode,
                    stream=False, chat_tools=chat_tools)
    out = r.run(db.get_session_messages(sid))
    tools = [m for m in db.get_session_messages(sid) if m["role"] == "tool"]
    return c, tools, out


def test_klasorsuz_sohbette_yalniz_web_araclari_sunulur_ve_calisir(db, sahte_arama):
    c, tools, out = run(db, [call("web_search", query="dolar kuru")])
    assert set(c.tool_names[0]) == WEB_TOOLS                          # dosya/komut araçları YOK
    assert sahte_arama == ["dolar kuru"] and "https://kaynak.org" in tools[0]["content"]
    assert prompts.CHAT_WEB_NOTE.strip()[:30] in c.systems[0] and out.stopped == "done"


def test_dosya_araci_cagrilirsa_calismaz(db, sahte_arama):
    _c, tools, _o = run(db, [call("write_file", path="a.txt", content="x")])
    assert "yalnız web_search ve web_fetch" in tools[0]["content"]


def test_ayar_kapaliyken_eski_davranis_aracsiz(db, sahte_arama):
    c, tools, _o = run(db, [], chat_tools=False)
    assert c.tool_names[0] == [] and not tools and prompts.CHAT_WEB_NOTE.strip()[:30] not in c.systems[0]


def test_manuel_modda_arama_sorulur(db, sahte_arama):
    asked = []

    class Ev(AgentEvents):
        def approval_needed(self, request):
            asked.append(request.title)
            request.resolve(request.DENY)
    sid = db.create_session("m", None)
    db.add_session_message(sid, "user", "x")
    r = AgentRunner(Script([call("web_search", query="x")]), "m", session_id=sid, store=db, events=Ev(),
                    workspace=None, mode="manuel", stream=False, chat_tools=True)
    r.run(db.get_session_messages(sid))
    assert asked == ["İnternette arama yapılsın mı?"] and not sahte_arama


@pytest.mark.parametrize("metin,beklenen", [
    ("bugünkü dolar fiyatı ne, internette ara", True),
    ("Python'da liste nasıl sıralanır?", False),                  # genel bilgi: ipucu yok
])
def test_sohbette_ipucu_tetiklenir_tetiklenmez(db, metin, beklenen):
    c, _t, _o = run(db, [], text=metin)
    # Madde 22 B: ipucu sabit sistem isteminde DEĞİL, son mesajın kuyruk notunda (önek önbelleği bozulmasın)
    assert ("# Web araması (bu tur)" in c.lasts[0]) is beklenen
    assert "# Web araması (bu tur)" not in c.systems[0]


# ---- gerçek tur akışı: oturum ekranı → koşucu (R-31) ----------------------------------------------

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


@pytest.mark.parametrize("acik", [True, False])
def test_arayuzden_klasorsuz_turda_ayara_gore(win, sahte_arama, acik):
    app, w = win
    c = Script([call("web_search", query="euro kuru")] if acik else [])
    w.ctx.make_client = lambda log_sink=None: c
    w.ctx.make_client_for = lambda provider, log_sink=None: c
    w.ctx.settings.web_tools_chat = acik
    s = w.session
    s.new_session()
    s.welcome._choose(None)
    s.composer.set_model("deepseek-v4.1-flash", emit=True)
    s.set_mode("auto")                                    # Manuel'de arama onay bekler (ayrı test)
    s.send("euro kuru bugün kaç, internette ara")
    end = time.monotonic() + 8
    while (s.running or not c.tool_names) and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)
    assert (set(c.tool_names[0]) == WEB_TOOLS) if acik else (c.tool_names[0] == [])
    assert (sahte_arama == ["euro kuru"]) if acik else (sahte_arama == [])
