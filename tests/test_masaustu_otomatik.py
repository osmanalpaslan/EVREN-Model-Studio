"""Madde 13 ek (kullanıcı 2026-11-05):
1) Kullanıcı test sırasında fareyi/klavyeyi kullanırsa test durmaz: ajan bekler, kontrol dönünce kaldığı yerden sürer;
   çok uzun sürerse güvenli noktada duraklar ve "Devam et" kartı çıkar.
2) Ajan gerektiğinde test aracını (tarayıcı / masaüstü) kendisi kurup açar; kullanıcı kapattıysa açmaz.
Gerçek fare/klavye/masaüstü YOK. Her otomatik davranış için tetiklenen ve tetiklenmeyen durum (R-22)."""
from __future__ import annotations

import json
import os
import time

import pytest

from evren_studio.agent import mcp
from evren_studio.agent.runner import TEST_TOOL_NAME, AgentEvents, AgentRunner
from evren_studio.agent.tools import EXEC, Workspace
from evren_studio.api.client import ChatResult
from evren_studio.db import Database


def blocked(code="USER_CONTROL", wait=0.0, steps=None):
    st = {"state": "user", "generation": 4, "wait_seconds": wait}
    if steps is not None:
        st["executed_steps"] = steps
    return {"isError": True, "content": [{"type": "text", "text": "Error calling tool: " +
                                          json.dumps({"code": code, "status": st})}]}


def ok_text(text):
    return {"content": [{"type": "text", "text": text}]}


class Mgr:
    """Sahte MCP yöneticisi: araç adı → sıralı yanıtlar; ControlStatus → sıralı durumlar."""

    def __init__(self, replies, states=()):
        self.replies = {k: list(v) for k, v in replies.items()}
        self.states = list(states)
        self.calls = []

    restarts = 0

    def running(self, *_a):
        return object()

    def restart(self, name, root):
        self.restarts += 1

    def call(self, cfg, root, tool, args):
        self.calls.append((tool, dict(args)))
        self.envs = getattr(self, "envs", []) + [dict(cfg.env)]
        if tool == "ControlStatus":
            st = self.states.pop(0) if self.states else "ready"
            return ok_text(json.dumps({"state": st, "generation": 4, "wait_seconds": 0.0}))
        return self.replies[tool].pop(0)


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def toolset(mgr, server="masaustu", when="masaustu", names=("Click", "Type")):
    cfg = mcp.McpServerConfig(name=server, command="x", when=when, blocked_keys=["End"])
    tools = [mcp.McpTool(server, n, mcp.tool_spec(server, {"name": n}, False), False) for n in names]
    notes = []
    ts = mcp.McpToolset(tools, mgr, {server: cfg}, None, status=notes.append)
    clk = Clock()
    ts._sleep, ts._clock = clk.sleep, clk.now
    ts._hung = lambda: set()                    # gerçek masaüstüne bakmasın
    return ts, notes, clk


# ---- askıdaki pencere (2026-11-05: VS Code yanıt vermezken Snapshot sonsuza kadar bekledi) -------------

def test_askidaki_pencere_bir_kez_bildirilir_sunucu_yenilenmez():
    """Atlamayı sunucudaki başlatıcı yapar (wmcp_baslatici); burada yalnız kullanıcıya bilgi. 6. gerçek deneme: ortam
    değişkeni + yeniden başlatma takılmayı çözmedi (0.8.8 onu pencere listesinde uygulamıyor)."""
    mgr = Mgr({"Snapshot": [ok_text("ağaç"), ok_text("ağaç"), ok_text("ağaç")]})
    ts, notes, _c = toolset(mgr, names=("Snapshot",))
    ts._hung = lambda: {"Code.exe"}
    ts.call("mcp__masaustu__Snapshot", {})
    assert [n for n in notes if "Yanıt vermeyen" in n] == [mcp.HUNG_NOTE.format(names="Code.exe")]
    assert mgr.restarts == 0 and mcp.EXCLUDE_ENV not in mgr.envs[-1]
    ts.call("mcp__masaustu__Snapshot", {})                # aynı pencere hâlâ askıda: ikinci not yok (R-22)
    assert sum("Yanıt vermeyen" in n for n in notes) == 1
    ts._hung = lambda: {"Code.exe", "dwm.exe"}            # yeni askıdaki program: yalnız o söylenir
    ts.call("mcp__masaustu__Snapshot", {})
    assert notes[-1] == mcp.HUNG_NOTE.format(names="dwm.exe") and mgr.restarts == 0


@pytest.mark.skipif(os.name != "nt", reason="Windows süreç listesi")
def test_korumali_surecin_adi_sureci_acmadan_okunur():
    """2026-11-05 gerçek deneme: "Yanıt Vermiyor" hayalet penceresi korumalı dwm.exe'ye aitti; OpenProcess reddettiği için
    adı okunamadı, atlanmadı ve tarama yine takıldı. System (pid 4) da açılamaz: ad süreç listesinden gelmeli."""
    import sys

    assert mcp._process_name(4) == "System"
    assert mcp._name_from_snapshot(os.getpid()).lower() == os.path.basename(sys.executable).lower()
    assert mcp._process_name(os.getpid()).lower() == os.path.basename(sys.executable).lower()
    assert mcp._process_name(0x7FFFFFF0) == ""          # olmayan süreç: boş, hata yok


def test_askida_pencere_yoksa_sunucuya_dokunulmaz():
    mgr = Mgr({"Snapshot": [ok_text("ağaç")]})
    ts, notes, _c = toolset(mgr, names=("Snapshot",))
    ts.call("mcp__masaustu__Snapshot", {})
    assert mgr.restarts == 0 and mcp.EXCLUDE_ENV not in mgr.envs[-1] and notes == []


def test_zaman_asiminda_bir_kez_yenileyip_yeniden_dener_ikincide_vazgecer():
    class Slow(Mgr):
        def __init__(self, fails):
            super().__init__({})
            self.fails = fails

        def call(self, cfg, root, tool, args):
            self.calls.append(tool)
            if self.fails:
                self.fails -= 1
                raise mcp.McpError("'masaustu' sunucusu 90 sn içinde yanıt vermedi")
            return ok_text("ağaç")

    m1 = Slow(1)
    ts, _n, _c = toolset(m1, names=("Snapshot",))
    assert ts.call("mcp__masaustu__Snapshot", {}) == ("ağaç", False) and m1.restarts == 1
    m2 = Slow(2)
    ts2, _n2, _c2 = toolset(m2, names=("Snapshot",))
    with pytest.raises(mcp.McpError):
        ts2.call("mcp__masaustu__Snapshot", {})
    assert m2.restarts == 1 and m2.calls == ["Snapshot", "Snapshot"]


# ---- 1) kullanıcı araya girince bekle ve sürdür ---------------------------------------------------

def test_kullanici_fareyi_kullaninca_bekler_ve_ayni_adimi_tekrarlar():
    mgr = Mgr({"Click": [blocked(wait=3), blocked(), ok_text("Single left clicked at (10,20).")]},
              states=["user", "ready", "user", "ai"])
    ts, notes, clk = toolset(mgr)
    text, err = ts.call("mcp__masaustu__Click", {"loc": [10, 20]})
    assert not err and "Single left clicked" in text and "bekleyip sürdürdü" in text
    clicks = [c for c in mgr.calls if c[0] == "Click"]
    assert clicks == [("Click", {"loc": [10, 20]})] * 3                # aynı adım, aynı argüman
    assert notes == [mcp.TAKEOVER_NOTE]                                 # kullanıcıya bir kez söylenir
    assert not ts.user_paused and clk.t >= 3                           # önce sunucunun dediği kadar bekler


def test_yarida_kesilen_islem_tekrarlanmaz_model_ekrani_yeniden_okur():
    mgr = Mgr({"Type": [blocked("CONTROL_PREEMPTED", steps=3)]}, states=["user", "ready"])
    ts, _notes, _clk = toolset(mgr)
    text, err = ts.call("mcp__masaustu__Type", {"text": "merhaba", "loc": [5, 5]})
    assert err and "YARIDA" in text and "Snapshot" in text
    assert [c[0] for c in mgr.calls].count("Type") == 1               # yarım yazı iki kez yazılmaz


def test_hic_baslamadan_kesilen_islem_tekrarlanir():
    mgr = Mgr({"Click": [blocked("CONTROL_PREEMPTED", steps=0), ok_text("ok")]}, states=["ready"])
    ts, _n, _c = toolset(mgr)
    assert ts.call("mcp__masaustu__Click", {"loc": [1, 1]}) == ("ok", False)


def test_uzun_sure_birakilmazsa_duraklatma_isareti():
    mgr = Mgr({"Click": [blocked()]}, states=["user"] * 1000)
    ts, _n, clk = toolset(mgr)
    ts.takeover_limit = 30
    text, err = ts.call("mcp__masaustu__Click", {"loc": [1, 1]})
    assert err and ts.user_paused and "DURAKLATILDI" in text and clk.t >= 30


def test_durdurulunca_beklemeden_cikar_duraklatma_sayilmaz():
    mgr = Mgr({"Click": [blocked()]}, states=["user"] * 1000)
    ts, _n, _c = toolset(mgr)
    ts.cancelled = lambda: True
    text, err = ts.call("mcp__masaustu__Click", {"loc": [1, 1]})
    assert err and "iptal" in text and not ts.user_paused


@pytest.mark.parametrize("reply", [ok_text("Typed 2"), {"isError": True, "content": [{"type": "text",
                                                                                      "text": "Element not found"}]}])
def test_kontrol_reddi_olmayan_yanit_beklenmez(reply):
    mgr = Mgr({"Click": [reply]})
    ts, notes, clk = toolset(mgr)
    ts.call("mcp__masaustu__Click", {"loc": [1, 1]})
    assert [c[0] for c in mgr.calls] == ["Click"] and notes == [] and clk.t == 0


def test_masaustu_disindaki_sunucuda_bekleme_yok():
    mgr = Mgr({"Click": [blocked()]})
    ts, notes, _c = toolset(mgr, server="baska", when="her_zaman")
    _text, err = ts.call("mcp__baska__Click", {"loc": [1, 1]})
    assert err and [c[0] for c in mgr.calls] == ["Click"] and notes == []


def test_tembel_kume_iptal_ve_duraklatmayi_tasir():
    mgr = Mgr({"Click": [blocked()]}, states=["user"] * 1000)
    inner, _n, _c = toolset(mgr)
    inner.takeover_limit = 5
    lazy = mcp.LazyToolset(lambda: inner)
    lazy.cancelled = lambda: False
    lazy.call("mcp__masaustu__Click", {"loc": [1, 1]})
    assert lazy.user_paused
    # Durdur (koşucunun iptali) tembel küme üzerinden gerçek kümeye ulaşır: bekleme hemen kesilir
    mgr2 = Mgr({"Click": [blocked()]}, states=["user"] * 1000)
    inner2, _n2, clk2 = toolset(mgr2)
    lazy2 = mcp.LazyToolset(lambda: inner2)
    lazy2.cancelled = lambda: True
    text, err = lazy2.call("mcp__masaustu__Click", {"loc": [1, 1]})
    assert err and "iptal" in text and not lazy2.user_paused and clk2.t < 1


def test_ajan_isteyince_masaustu_sozcugu_olmasa_da_sunulur_istemezse_sunulmaz(tmp_path):
    import sys
    from pathlib import Path

    fake = str(Path(__file__).with_name("fake_mcp_server.py"))
    cfg = mcp.McpServerConfig(name="masaustu", command=sys.executable, args=[fake], when="masaustu")
    m = mcp.McpManager(tmp_path)
    try:
        assert m.toolset([cfg], tmp_path, "README'yi güncelle").specs() == []                    # istenmedi
        assert m.toolset([cfg], tmp_path, "README'yi güncelle", force={"masaustu"}).specs()       # ajan istedi
    finally:
        m.close_all()


# ---- koşucu: duraklatma ve test aracı ---------------------------------------------------------

class FakeMcp:
    """AgentRunner.mcp yerine: masaüstü araçları; çağrı user_paused'ı açabilir."""

    def __init__(self, pause=False):
        self.pause = pause
        self.user_paused = False
        self.calls = []
        self.notes = []
        self.hints = []

    def specs(self, read_only_only=False):
        return [mcp.tool_spec("masaustu", {"name": "Click"}, False)]

    def get(self, name):
        return mcp.McpTool("masaustu", "Click", mcp.tool_spec("masaustu", {"name": "Click"}, False), False)

    def call(self, name, arguments):
        self.calls.append(name)
        if self.pause:
            self.user_paused = True
            return mcp.TAKEOVER_PAUSE_TEXT.format(sec=300), True
        return "Single left clicked", False

    def servers(self):
        return ["masaustu"]


class Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, on_reasoning=None, tools=None, **kw):
        self.requests.append({"tools": [t["function"]["name"] for t in (tools or [])]})
        return self.responses.pop(0) if self.responses else ChatResult(content="Bitti.", finish_reason="stop")


def call(name, cid, **args):
    return ChatResult(tool_calls=[{"id": cid, "name": name, "arguments": json.dumps(args)}], finish_reason="tool_calls")


@pytest.fixture()
def env(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    db = Database(tmp_path / "t.db")
    yield root, db
    db.close()


def make(env, client, **kw):
    root, db = env
    sid = db.create_session("m", str(root), "auto")
    db.add_session_message(sid, "user", "uygulamayı dene")
    r = AgentRunner(client, "m", session_id=sid, store=db, workspace=Workspace(root), mode="auto", stream=False,
                    events=AgentEvents(), **kw)
    return r, db, sid


def test_kosucu_kullanici_uzun_sure_birakmazsa_guvenli_noktada_durur(env):
    fake = FakeMcp(pause=True)
    client = Client([call("mcp__masaustu__Click", "c1", loc=[1, 1]), ChatResult(content="olmamalı")])
    r, db, sid = make(env, client, mcp=fake)
    out = r.run(db.get_session_messages(sid))
    assert out.stopped == "user_control" and len(client.requests) == 1
    assert db.get_session_messages(sid)[-1]["role"] == "tool", "araç sonucu kaydedildikten sonra durur"


def test_kosucu_duraklatma_yoksa_surer(env):
    fake = FakeMcp(pause=False)
    client = Client([call("mcp__masaustu__Click", "c1", loc=[1, 1]), ChatResult(content="Tamam.")])
    r, db, sid = make(env, client, mcp=fake)
    assert r.run(db.get_session_messages(sid)).stopped == "done"


class Gate:
    def __init__(self, available=(True, ""), installed=True, result=None):
        self._available, self._installed = available, installed
        self.result = result
        self.enabled = []

    def available(self, kind):
        return self._available

    def installed(self, kind):
        return self._installed

    def enable(self, kind, log=None):
        self.enabled.append(kind)
        return True, "", self.result


def test_test_araci_sunulur_kapaliyken_planda_ve_qada_sunulmaz(env):
    client = Client([])
    for kw, beklenen in (({"test_tools": Gate()}, True), ({}, False),
                         ({"test_tools": Gate(), "no_writes": True}, False)):
        r, _db, _sid = make(env, client, **kw)
        assert (TEST_TOOL_NAME in [s.name for s in r._specs()]) == beklenen, kw
    r, _db, _sid = make(env, client, test_tools=Gate())
    r.mode = "plan"
    assert TEST_TOOL_NAME not in [s.name for s in r._specs()]


def test_ajan_test_aracini_acinca_masaustu_araclari_sonraki_adimda_gelir(env):
    """R-31: gerçek tur akışı — ajan aracı ister, sonraki model çağrısında mcp__masaustu__ araçları sunulur."""
    gate = Gate(result=FakeMcp())
    client = Client([call(TEST_TOOL_NAME, "t1", tur="masaustu", neden="pencereyi dene"),
                     call("mcp__masaustu__Click", "c1", loc=[3, 3]), ChatResult(content="Denendi.")])
    r, db, sid = make(env, client, test_tools=gate)
    out = r.run(db.get_session_messages(sid))
    assert out.stopped == "done" and gate.enabled == ["masaustu"]
    assert "mcp__masaustu__Click" not in client.requests[0]["tools"]
    assert "mcp__masaustu__Click" in client.requests[1]["tools"]
    tool_msgs = [m for m in db.get_session_messages(sid) if m["role"] == "tool"]
    assert "açıldı" in tool_msgs[0]["content"] and "Single left clicked" in tool_msgs[1]["content"]


def test_kullanici_kapattiysa_test_araci_acilmaz_neden_soylenir(env):
    gate = Gate(available=(False, "kullanıcı Masaüstü kontrolü aracını kapatmış"))
    client = Client([call(TEST_TOOL_NAME, "t1", tur="masaustu"), ChatResult(content="Elle deneyin.")])
    r, db, sid = make(env, client, test_tools=gate)
    r.run(db.get_session_messages(sid))
    tool_msg = next(m for m in db.get_session_messages(sid) if m["role"] == "tool")
    assert "kapatmış" in tool_msg["content"] and gate.enabled == []


def test_manuel_kurulumda_kurulum_sorulur_reddedilince_kurulmaz(env):
    gate = Gate(installed=False, result=FakeMcp())
    client = Client([call(TEST_TOOL_NAME, "t1", tur="web"), ChatResult(content="Tamam.")])
    r, db, sid = make(env, client, test_tools=gate, install_mode="manuel")
    asked = []
    r._approve = lambda *a, **k: (asked.append(a[2]) or (False, ""))
    r.run(db.get_session_messages(sid))
    assert asked and "kurulsun mu" in asked[0] and gate.enabled == []
    gate2 = Gate(installed=True, result=FakeMcp())                    # kuruluysa sorulmaz (R-22)
    r2, db2, sid2 = make(env, Client([call(TEST_TOOL_NAME, "t1", tur="web"), ChatResult(content="ok")]),
                         test_tools=gate2, install_mode="manuel")
    r2._approve = lambda *a, **k: pytest.fail("sorulmamalı")
    r2.run(db2.get_session_messages(sid2))
    assert gate2.enabled == ["web"]


# ---- uygulama kapısı (TestTools) ----------------------------------------------------------------

@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
    yield app, w
    w.close()


def test_kapi_kullanici_kapattiysa_acmaz(win, tmp_path):
    app, w = win
    s = w.ctx.settings
    tt = w.ctx.test_tools(tmp_path, "", "evren")
    assert tt.available("masaustu")[0]                                 # hiç yapılandırılmamış → açabilir
    s.mcp_servers = [{**mcp.windows_config().to_dict(), "enabled": False}]
    assert not tt.available("masaustu")[0] and "kapatmış" in tt.available("masaustu")[1]
    assert tt.available("web")[0] or "Node" in tt.available("web")[1]
    s.mcp_servers = []
    s.mcp_enabled = False
    assert not tt.available("masaustu")[0]
    s.mcp_enabled = True
    s.auto_test_tools = False
    assert w.ctx.test_tools(tmp_path, "", "evren") is None              # özellik kapalı → araç hiç sunulmaz
    s.auto_test_tools = True
    assert w.ctx.test_tools(tmp_path, "", "openai") is None             # ücretli sağlayıcıda yok
    assert w.ctx.test_tools(None, "", "evren") is None


def test_kapi_kurar_kaydeder_ve_zorla_sunar(win, tmp_path, monkeypatch):
    app, w = win
    installed = []
    ready = {"v": False}
    monkeypatch.setitem(mcp.PRESETS["masaustu"], "ready", lambda d: ready["v"])
    monkeypatch.setitem(mcp.PRESETS["masaustu"], "install",
                        lambda d, log=None: (installed.append(d), ready.update(v=True)))
    seen = {}
    monkeypatch.setattr(w.ctx.mcp, "toolset",
                        lambda configs, root, message, status=None, force=None: seen.update(force=force,
                                                                                            names=[c.name for c in configs]) or "KUME")
    tt = w.ctx.test_tools(tmp_path, "README'yi güncelle", "evren")
    ok, _msg, ts = tt.enable("masaustu")
    assert ok and ts == "KUME" and installed
    assert seen["force"] == {"masaustu"} and "masaustu" in seen["names"]   # mesajda masaüstü sözcüğü olmasa da
    from evren_studio.config import ConfigStore

    saved = ConfigStore(w.ctx.store.data_dir).load()
    assert any(d["name"] == "masaustu" and d.get("enabled", True) for d in saved.mcp_servers)   # R-03
    installed.clear()
    tt.enable("masaustu")
    assert installed == []                                             # kuruluysa yeniden kurulmaz


def test_oturum_duraklatma_karti_ve_devam_et(win, tmp_path, monkeypatch):
    """R-31: send → koşucu → _on_done: kullanıcı uzun süre bırakmayınca 'Devam et' kartı; tıklayınca sürer."""
    app, w = win
    from evren_studio.agent import prompts
    from evren_studio.ui.transcript import ActionCard

    proj = tmp_path / "uyg"
    proj.mkdir()
    fake = FakeMcp(pause=True)
    monkeypatch.setattr(w.ctx, "mcp_toolset", lambda *a, **k: fake)
    client = Client([call("mcp__masaustu__Click", "c1", loc=[1, 1]), ChatResult(content="Devam ettim.")])
    client.close = lambda: None
    w.ctx.make_client = lambda log_sink=None: client
    sv = w.session
    sv.welcome._choose(str(proj))
    sv.set_mode("auto")
    sv.set_model("glm-5.3")
    sv.send("masaüstünde uygulamayı dene")
    end = time.monotonic() + 10
    while sv.running and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)
    from PySide6.QtWidgets import QLabel, QPushButton

    texts = [lab.text() for c in sv.transcript.findChildren(ActionCard) for lab in c.findChildren(QLabel)]
    assert any("Masaüstü işi duraklatıldı" in t for t in texts)
    fake.pause = False
    btn = next(b for c in sv.transcript.findChildren(ActionCard) for b in c.findChildren(QPushButton)
               if b.text() == "Devam et")
    btn.click()
    end = time.monotonic() + 10
    while (sv.running or not any(m["content"] == prompts.DESKTOP_RESUME_PROMPT
                                 for m in w.ctx.db.get_session_messages(sv.session_id))) and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)
    msgs = w.ctx.db.get_session_messages(sv.session_id)
    assert any(m["role"] == "user" and m["content"] == prompts.DESKTOP_RESUME_PROMPT for m in msgs)


def test_qa_masaustu_araci_kendisi_kurar_kullanici_kapattiysa_kurmaz(win, tmp_path, monkeypatch):
    app, w = win
    qc = w.session.qa
    proj = tmp_path / "uyg2"
    proj.mkdir()
    w.session.welcome._choose(str(proj))
    started = []
    monkeypatch.setattr(qc, "_auto_install", lambda kind, then: started.append(kind))
    qc.command("/qa-masaustu", "hesap aracını test et")
    assert started == ["masaustu"]
    started.clear()
    w.ctx.settings.mcp_servers = [{**mcp.windows_config().to_dict(), "enabled": False}]
    notes = []
    monkeypatch.setattr(w.session, "_note", lambda text, icon="dot": notes.append(text))
    qc.command("/qa-masaustu", "hesap aracını test et")
    assert started == [] and any("Masaüstü kontrolünü kur" in n for n in notes)
