"""EVREN Akıllı yönlendirici (agent/router.py) ve koşucunun yedek modele geçişi."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

from evren_studio.agent import router
from evren_studio.agent.runner import AgentEvents, AgentRunner
from evren_studio.agent.tools import Workspace
from evren_studio.api.client import ChatResult
from evren_studio.api.errors import ApiError, ErrorKind
from evren_studio.db import Database


def test_rol_secimi_onceligi():
    ctx = {"deepseek-v4-flash": 1_048_576, "qwen3.8-flash-next": 262_144}
    assert router.classify(agentic=False)[0] == "sohbet"
    assert router.classify(agentic=True)[0] == "kod"
    assert router.classify(agentic=True, mode="plan")[0] == "plan"
    assert router.classify(agentic=True, mode="plan", has_images=True)[0] == "gorsel"
    assert router.classify(agentic=True, est_tokens=700_000, context_of=ctx)[0] == "buyuk_baglam"
    assert router.classify(agentic=True, est_tokens=10_000, context_of=ctx)[0] == "kod"


def test_secim_yedekler_ve_gorsel_kurali():
    r = router.choose("kod")
    assert r.model == router.ROUTES["kod"][0] and r.fallbacks == router.ROUTES["kod"][1:]
    g = router.choose("gorsel")
    assert g.model not in router.TEXT_ONLY and all(m not in router.TEXT_ONLY for m in g.fallbacks)
    assert "EVREN Akıllı →" in r.label


def test_listede_olmayan_atlanir_sagliksiz_sona():
    first, second = router.ROUTES["kod"][:2]
    r = router.choose("kod", available={second, router.ROUTES["kod"][2]})
    assert r.model == second
    now = datetime.now(timezone.utc)
    health = {first: {"healthy": 0, "last_test_at": (now - timedelta(minutes=5)).isoformat()}}
    r = router.choose("kod", health=health, now=now)
    assert r.model == second and r.fallbacks[-1] == first
    old = {first: {"healthy": 0, "last_test_at": (now - timedelta(hours=3)).isoformat()}}
    assert router.choose("kod", health=old, now=now).model == first        # eski ölçüm sayılmaz


# ---- koşucu: yedeğe geçiş -------------------------------------------------------------------

class Events(AgentEvents):
    def __init__(self):
        self.statuses = []

    def status(self, text):
        self.statuses.append(text)


class Client:
    def __init__(self, plan):
        self.plan = list(plan)
        self.models = []

    def chat(self, model, messages, **kw):
        self.models.append(model)
        step = self.plan.pop(0) if self.plan else ChatResult(content="bitti", finish_reason="stop")
        if isinstance(step, Exception):
            raise step
        return step


def _run(tmp_path, plan, fallbacks):
    db = Database(tmp_path / "t.db")
    try:
        sid = db.create_session("akilli", str(tmp_path))
        db.add_session_message(sid, "user", "merhaba")
        c, ev = Client(plan), Events()
        out = AgentRunner(c, "deepseek-v4-flash", session_id=sid, store=db, events=ev,
                          workspace=Workspace(tmp_path), stream=False,
                          fallback_models=fallbacks).run(db.get_session_messages(sid))
        saved = [m for m in db.get_session_messages(sid) if m["role"] == "assistant"]
        return out, c, ev, saved
    finally:
        db.close()


def test_sunucu_hatasinda_yedege_gecer(tmp_path):
    err = ApiError(kind=ErrorKind.SERVER_UNAVAILABLE, message="aşırı yük", status=503)
    out, c, ev, saved = _run(tmp_path, [err, ChatResult(content="tamam", finish_reason="stop")],
                             ["qwen3.8-flash-next", "deepseek-v4.1-flash"])
    assert c.models == ["deepseek-v4-flash", "qwen3.8-flash-next"]
    assert out.stopped == "done" and out.model_switches[0][:2] == ("deepseek-v4-flash", "qwen3.8-flash-next")
    assert any("yedek modele geçti" in s for s in ev.statuses)


@pytest.mark.parametrize("kind", [ErrorKind.RATE_LIMIT, ErrorKind.AUTH, ErrorKind.QUOTA_EXHAUSTED])
def test_kota_ve_yetki_hatasinda_gecmez(tmp_path, kind):
    with pytest.raises(ApiError):
        _run(tmp_path, [ApiError(kind=kind, message="x", status=429)], ["qwen3.8-flash-next"])


def test_yedek_yoksa_hata_aynen_firlar(tmp_path):
    with pytest.raises(ApiError):
        _run(tmp_path, [ApiError(kind=ErrorKind.SERVER_ERROR, message="x", status=500)], [])


def test_gorsel_reddinde_yedege_gecer(tmp_path):
    err = ApiError(kind=ErrorKind.VALIDATION, message="'image_url' feature_not_enabled", status=400)
    out, c, _ev, _s = _run(tmp_path, [err, ChatResult(content="kırmızı", finish_reason="stop")], ["qwen3-vl-30b"])
    assert c.models == ["deepseek-v4-flash", "qwen3-vl-30b"] and out.stopped == "done"


# ---- arayüz -------------------------------------------------------------------------------------

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
    import time

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def test_akilli_secicide_ve_api_ye_gercek_model_gider(win, tmp_path):
    app, w = win
    s = w.session
    ids = s.composer.model_ids()
    assert ids[0] == "akilli" and ids[1] == "auto"
    calls = []

    class C:
        def chat(self, model, messages, **kw):
            calls.append(model)
            return ChatResult(content="tamam", finish_reason="stop")

        def close(self):
            pass

    w.ctx.make_client = lambda log_sink=None: C()
    s.new_session()
    proj = tmp_path / "proje"
    proj.mkdir()
    s.welcome._choose(str(proj))
    s.composer.set_model("akilli", emit=True)
    s.send("app.py'yi incele")
    assert _wait(app, lambda: not s.running and calls)
    assert calls[0] == router.ROUTES["kod"][0]             # "akilli" API'ye gitmedi
    row = w.ctx.db.get_session(s.session_id)
    assert row["model"] == "akilli"                         # oturum seçimi korunur
    a = [m for m in w.ctx.db.get_session_messages(s.session_id) if m["role"] == "assistant"][-1]
    assert a["model"] == router.ROUTES["kod"][0] or (a.get("meta") or {}).get("requested_model") == router.ROUTES["kod"][0]
