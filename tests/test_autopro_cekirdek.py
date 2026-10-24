"""Auto Pro çekirdeği (F1, 2026-10-24): A1 gerçek kullanım kaydı, A2 yanıt vermeme, A3 yavaşlama kuralı
(DECISIONS #88), A4 bekleme süresi, A9 model listesi uyarısı, A12 şeffaflık. Gerçek ağ yok (yerel sunucu hariç)."""
from __future__ import annotations

import http.server
import json
import os
import socketserver
import threading
import time
from datetime import datetime, timezone

import pytest

from evren_studio.agent import modelstats, router
from evren_studio.agent.runner import AgentEvents, AgentRunner
from evren_studio.agent.tools import Workspace
from evren_studio.api.client import ChatResult, EvrenClient
from evren_studio.api.errors import ApiError, ErrorKind
from evren_studio.db import Database


def call(name, cid="c1", **args):
    return {"id": cid, "name": name, "arguments": json.dumps(args, ensure_ascii=False)}


def res(content="", calls=None, out=400, first=1.0, model="m"):
    return ChatResult(content=content, tool_calls=calls or [], model=model, finish_reason="stop",
                      usage={"completion_tokens": out}, first_chunk_s=first)


class Script:
    """Model başına sıralı yanıtlar; hangi modelle çağrıldığını kaydeder."""

    def __init__(self, by_model: dict[str, list]):
        self.by = {k: list(v) for k, v in by_model.items()}
        self.models: list[str] = []

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, on_reasoning=None, tools=None, **kw):
        self.models.append(model)
        seq = self.by.get(model) or []
        r = seq.pop(0) if seq else res("bitti", out=10)
        if isinstance(r, Exception):
            raise r
        return r


class Ev(AgentEvents):
    def __init__(self):
        self.statuses: list[str] = []

    def status(self, text):
        self.statuses.append(text)

    def approval_needed(self, request):
        request.resolve(request.ALLOW)


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "t.db")
    yield d
    d.close()


def runner_for(db, tmp_path, client, *, base=None, factor=modelstats.FACTOR_TURN, fallbacks=("y",), sink=None):
    proj = tmp_path / "p"
    proj.mkdir(exist_ok=True)
    sid = db.create_session("x", str(proj))
    db.add_session_message(sid, "user", "görev")
    hist = db.get_session_messages(sid)
    ev = Ev()
    r = AgentRunner(client, "x", session_id=sid, store=db, events=ev, workspace=Workspace(proj), mode="auto",
                    stream=False, fallback_models=list(fallbacks), baselines=base, slow_factor=factor,
                    stats_sink=sink, route_role="kod")
    return r, hist, ev


BASE = {"x": modelstats.Baseline("x", tps=100.0, first_chunk_s=1.0, samples=10)}


# ---- modelstats (saf kurallar) ------------------------------------------------------------------

def test_hiz_ve_normal_hesabi():
    assert modelstats.gen_speed({"out_tokens": 100, "duration_s": 1}) is None          # kısa yanıt güvenilmez
    assert modelstats.gen_speed({"out_tokens": 400, "duration_s": 5, "first_chunk_s": 1}) == 100
    rows = [{"model": "a", "ok": 1, "out_tokens": 400, "duration_s": 5, "first_chunk_s": 1}] * 5
    assert modelstats.baselines(rows) == {}                                             # 5 < MIN_SAMPLES
    b = modelstats.baselines(rows + rows[:1] + [{"model": "a", "ok": 0}, {"model": "a", "ok": 0, "event": "switch"}])
    assert b["a"].tps == 100 and b["a"].first_chunk_s == 1 and b["a"].samples == 6


def test_yavaslik_gerekcesi_ve_sayac():
    hizli = {"ok": 1, "out_tokens": 400, "duration_s": 5, "first_chunk_s": 1}
    yavas = {"ok": 1, "out_tokens": 400, "duration_s": 11, "first_chunk_s": 1}          # 40 tok/sn < 50
    gec = {"ok": 1, "out_tokens": 20, "duration_s": 30, "first_chunk_s": 25}            # ilk yanıt 25 sn
    assert modelstats.slow_reason(hizli, BASE["x"], 0.5) == ""
    assert "üretim hızı" in modelstats.slow_reason(yavas, BASE["x"], 0.5)
    assert "ilk yanıt" in modelstats.slow_reason(gec, BASE["x"], 0.5)
    assert modelstats.slow_reason({"ok": 1, "out_tokens": 20, "duration_s": 3, "first_chunk_s": 3}, BASE["x"], 0.5) == ""
    assert modelstats.slow_reason(yavas, BASE["x"], modelstats.FACTOR_TASK) == ""      # görev içi: ~3 kat gerekir
    d = modelstats.SlowDetector(BASE)
    assert d.observe("x", yavas) == "" and d.observe("x", hizli) == ""                  # ara kesilirse sıfırlanır
    assert d.observe("x", yavas) == "" and "art arda 2" in d.observe("x", yavas)
    d.used = True
    assert d.observe("x", yavas) == "" and d.observe("x", yavas) == ""                  # görev başına bir kez
    assert modelstats.SlowDetector(None).observe("x", yavas) == ""                      # ölçüm yoksa kural yok


# ---- koşucu: A3 yavaşlık, A2 akış kopması, A1 kayıt ---------------------------------------------

def test_art_arda_iki_yavas_adimda_guvenli_noktada_bir_kez_gecer(db, tmp_path):
    kayit = []
    c = Script({"x": [res("1", [call("list_files", cid="a", depth=1)], first=30),
                      res("2", [call("list_files", cid="b", depth=2)], first=30),
                      res("3", [call("list_files", cid="c", depth=3)], first=30)],
                "y": [res("4", [call("list_files", cid="d", depth=4)], first=30), res("5", [call("list_files", cid="e", depth=5)], first=30),
                      res("bitti", out=10)]})
    r, hist, ev = runner_for(db, tmp_path, c, base={**BASE, "y": BASE["x"]}, sink=kayit.append)
    out = r.run(hist)
    # x iki adım yavaş → üçüncü çağrıdan ÖNCE (araçlar bittikten sonra) y'ye geçti; y de yavaş ama ikinci geçiş yok
    assert c.models[:3] == ["x", "x", "y"] and set(c.models[2:]) == {"y"}
    assert len(out.model_switches) == 1 and out.model_switches[0][2].startswith("yavaşlık")
    assert any("yavaşlık" in s and "Auto Pro yedek modele geçti" in s for s in ev.statuses)
    olay = [k for k in kayit if k.get("event") == "switch"]
    assert len(olay) == 1 and olay[0]["model"] == "x" and "yavaşlık" in olay[0]["detail"]
    assert sum(1 for k in kayit if not k.get("event")) == len(c.models) and all(k["role"] == "kod" for k in kayit)


def test_normal_hizda_veya_olcum_yokken_gecis_yok(db, tmp_path):
    adimlar = {"x": [res(str(i), [call("list_files", cid=f"c{i}", depth=i + 1)], first=1.0) for i in range(4)] + [res("bitti", out=10)]}
    r, hist, ev = runner_for(db, tmp_path, Script(adimlar), base=BASE)
    assert r.run(hist).model_switches == []
    yavas = {"x": [res(str(i), [call("list_files", cid=f"c{i}", depth=i + 1)], first=30) for i in range(4)] + [res("bitti", out=10)]}
    r2, hist2, _ = runner_for(db, tmp_path, Script(yavas), base=None)                  # bugün ölçüm yok
    assert r2.run(hist2).model_switches == []


def test_proje_gorevi_icinde_esik_uc_kat(db, tmp_path):
    iki_kat = {"x": [res(str(i), [call("list_files", cid=f"c{i}", depth=i + 1)], first=2.5) for i in range(3)] + [res("bitti", out=10)]}
    r, hist, _ = runner_for(db, tmp_path, Script(iki_kat), base=BASE, factor=modelstats.FACTOR_TASK)
    assert r.run(hist).model_switches == []                                             # 2,5 sn < 11 sn eşiği


def test_akis_kopmasi_artik_turu_bitirmez_yedege_gecer(db, tmp_path):
    kopma = ApiError(kind=ErrorKind.UNKNOWN_RESULT, message="Akış kesildi: ReadTimeout")
    kayit = []
    r, hist, ev = runner_for(db, tmp_path, Script({"x": [kopma], "y": [res("tamam", out=10)]}), sink=kayit.append)
    out = r.run(hist)
    assert out.stopped == "done" and out.model_switches[0][:2] == ("x", "y")
    assert any(k.get("error_kind") == ErrorKind.UNKNOWN_RESULT.value and not k["ok"] for k in kayit)
    # kota hatası hâlâ geçirmez (kota hesap başına)
    kota = ApiError(kind=ErrorKind.QUOTA_EXHAUSTED, message="kota")
    r2, hist2, _ = runner_for(db, tmp_path, Script({"x": [kota]}))
    with pytest.raises(ApiError):
        r2.run(hist2)


# ---- istemci: donan akış gerçek yerel sunucuyla (A2) -------------------------------------------

class _Donan(http.server.BaseHTTPRequestHandler):
    sus = 2.0

    def do_POST(self):  # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        ch = {"choices": [{"delta": {"content": "Merhaba"}}]}
        self.wfile.write(f"data: {json.dumps(ch)}\n\n".encode())
        self.wfile.flush()
        time.sleep(self.sus)                       # model "dondu"
        try:
            self.wfile.write(b"data: [DONE]\n\n")
        except OSError:
            pass

    def log_message(self, *a):
        pass


@pytest.fixture()
def sunucu():
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Donan)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_akis_susarsa_timeout_ve_ilk_parca_suresi(sunucu):
    c = EvrenClient(sunucu, "k", timeout=10, max_retries=0, stream_idle_timeout=0.5)
    with pytest.raises(ApiError) as e:
        c.chat("m", [{"role": "user", "content": "x"}], stream=True)
    assert e.value.kind == ErrorKind.TIMEOUT and "yanıt vermedi" in e.value.message
    _Donan.sus = 0.0
    ok = EvrenClient(sunucu, "k", timeout=10, max_retries=0, stream_idle_timeout=0.5).chat(
        "m", [{"role": "user", "content": "x"}], stream=True)
    assert ok.content == "Merhaba" and ok.first_chunk_s is not None and ok.first_chunk_s < 0.5
    _Donan.sus = 2.0
    eski = EvrenClient(sunucu, "k", timeout=10, max_retries=0)                         # eşik yok → bekler
    assert eski.chat("m", [{"role": "user", "content": "x"}], stream=True).content == "Merhaba"


# ---- A4 bekleme süresi, A1 kaydın okunması (R-03), A9, A12 ----------------------------------------

@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    yield app, w
    w.close()


def test_yedege_gecen_model_bekleme_suresinde_sona_alinir_ve_normal_hiz_okunur(win):
    _app, w = win
    ctx = w.ctx
    for _ in range(6):
        ctx.record_model_call({"model": "deepseek-v4.1-flash", "ok": True, "duration_s": 5, "first_chunk_s": 1,
                               "out_tokens": 400, "role": "kod"})
    base = ctx.model_baselines()
    assert base["deepseek-v4.1-flash"].tps == 100 and base["deepseek-v4.1-flash"].samples == 6
    ctx.record_model_call({"model": "deepseek-v4.1-flash", "ok": False, "event": "switch", "detail": "x → y: yavaşlık"})
    health = {r["model"]: dict(r) for r in ctx.db.all_model_health()}
    r = router.choose("kod", health=health)
    assert r.model != "deepseek-v4.1-flash" and r.fallbacks[-1] == "deepseek-v4.1-flash"    # A4
    sonra = datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1)  # bekleme bitti
    assert router.choose("kod", health=health, now=sonra).model == "deepseek-v4.1-flash"


def test_model_listesi_degisince_uyari_ilk_yuklemede_degil(win):
    from evren_studio.api.client import ModelInfo

    _app, w = win
    ctx = w.ctx
    calls = []
    ctx.on_model_list_change(lambda rem, add: calls.append((rem, add)))

    def mi(i):
        return ModelInfo(id=i, task="chat", modalities=["text"], context_length=262144,
                         default_max_output_tokens=16384, capabilities={"tools": True})
    ctx.settings.known_model_ids = []
    ctx.set_models([mi("a"), mi("deepseek-v4-flash")])
    assert calls == [] and ctx.settings.known_model_ids == ["a", "deepseek-v4-flash"]
    ctx.set_models([mi("a"), mi("yeni-model")])
    assert calls == [(["deepseek-v4-flash"], ["yeni-model"])]


def test_modeller_sayfasinda_son_24_saat_tablosu_ve_ipucu(win):
    _app, w = win
    ctx = w.ctx
    for i in range(3):
        ctx.record_model_call({"model": "qwen3.8-flash-next", "ok": i != 2, "duration_s": 5, "first_chunk_s": 1,
                               "out_tokens": 400, "error_kind": None if i != 2 else "timeout"})
    page = w.pages["models"]
    page.refresh()
    assert page.stats.rowCount() == 1 and page.stats.item(0, 0).text() == "qwen3.8-flash-next"
    assert page.stats.item(0, 1).text() == "3" and page.stats.item(0, 2).text() == "%33"
    s = w.session
    s._run_route = router.Route("qwen3.8-flash-next", "kod", "proje klasöründe ajan görevi", ["gemma-4-31b"])
    tip = s._route_explain("qwen3.8-flash-next", ["gemma-4-31b"])
    assert "rol: kod" in tip and "3 çağrı" in tip and "gemma-4-31b" in tip
