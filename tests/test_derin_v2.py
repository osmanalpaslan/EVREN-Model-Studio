"""Derin Mod Madde 8 (2026-11-03): alt ajan canlı durum cümlesi, aşamaya göre düşünme seviyesi (effort) ve
ölçümle seçilen aşama modelleri. Ağ yok."""
from __future__ import annotations

import json

from test_derin_mod import win  # noqa: F401  (pytest fixture)

from evren_studio.agent import deep as dp
from evren_studio.api.client import ChatResult


def _call(name, cid="c1", **args):
    return {"id": cid, "name": name, "arguments": json.dumps(args, ensure_ascii=False)}


class _Client:
    def __init__(self, replies):
        self.replies = list(replies)
        self.kw = []

    def chat(self, model, messages, **kw):
        self.kw.append(kw)
        return self.replies.pop(0) if self.replies else ChatResult(content="bitti", finish_reason="stop")

    def close(self):
        pass


def test_alt_ajan_her_aracta_canli_durum_bildirir(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    client = _Client([ChatResult(tool_calls=[_call("read_file", path="app.py")]),
                      ChatResult(tool_calls=[_call("list_files", "c2", path=".")]),
                      ChatResult(content='<bulgu>{"ozet": "ok"}</bulgu>', finish_reason="stop")])
    seen = []
    res = dp.run_subagent(client=client, model="m", fallbacks=[], root=tmp_path, prompt="incele",
                          marker="<bulgu>", progress=seen.append)
    assert res.stopped == "done" and len(seen) == 2
    assert "app.py" in seen[0]


def test_durum_bildirimi_hata_verse_de_alt_ajan_surer(tmp_path):
    client = _Client([ChatResult(tool_calls=[_call("list_files", path=".")]),
                      ChatResult(content='<bulgu>{"ozet": "ok"}</bulgu>', finish_reason="stop")])

    def bozuk(_t):
        raise RuntimeError("arayüz gitti")
    res = dp.run_subagent(client=client, model="m", fallbacks=[], root=tmp_path, prompt="x", marker="<bulgu>",
                          progress=bozuk)
    assert res.stopped == "done" and "ok" in res.text


class _KwClient:
    """test_derin_mod.FakeClient + her çağrının (tür, model, extra_body) kaydı."""

    def __init__(self):
        from test_derin_mod import FakeClient

        self.inner = FakeClient()
        self.bodies = []

    def chat(self, model, messages, **kw):
        res = self.inner.chat(model, messages, **kw)
        self.bodies.append((self.inner.calls[-1][0], model, (kw.get("extra_body") or {}).get("reasoning_effort")))
        return res

    def close(self):
        pass


def test_dogrulamada_ikinci_denetci_glm_high_ve_canli_durum(win, tmp_path, monkeypatch):
    """R-31: gerçek Derin akışı (sahte model) → doğrulama glm-5.3 + high; diğer modellere effort gitmez;
    durum satırına alt ajan cümlesi düşer."""
    from test_derin_mod import _session, _wait

    from evren_studio.ui.project_ui import PlanCard

    app, w = win
    client = _KwClient()
    s, proj = _session(w, tmp_path, client)
    monkeypatch.setattr(s.deep, "_diff", lambda: "--- a/notlar.txt\n+++ b/notlar.txt\n+merhaba\n")
    labels = []
    orig = s.deep._set_label
    monkeypatch.setattr(s.deep, "_set_label", lambda t: (labels.append(t), orig(t))[1])
    s.deep.sig_label.disconnect()
    s.deep.sig_label.connect(s.deep._set_label)
    s.send("/derin Basit bir not uygulaması ekle: notlar.txt ve README")
    assert _wait(app, lambda: s.findChildren(PlanCard))
    s.findChildren(PlanCard)[-1].approved.emit()
    assert _wait(app, lambda: not s.deep.active, 40)
    dogrula = [(m, e) for k, m, e in client.bodies if k == "dogrula"]
    modeller = {m for m, _e in dogrula}
    assert "glm-5.3" in modeller and len(modeller) == 2                       # iki farklı denetçi
    assert all(e == "high" for m, e in dogrula if m == "glm-5.3")
    # glm dışında "high" yok; alt ajanlar effort göndermez. Yargıç/inceleme ai_chat'ten "none" ile gider
    # (bilinçli: kısa iç iş; yargıç ölçümünde none ile 8/8).
    assert all(e != "high" for k, m, e in client.bodies if m != "glm-5.3")
    assert all(e is None for k, m, e in client.bodies if m != "glm-5.3" and k not in ("judge", "review"))
    assert any("düşünüyor" in t and "anla" in t for t in labels)
    assert not s.composer.run_bar.isVisible()                    # Derin bitince kendi çubuğunu kapattı


def test_arka_plan_fazinda_calisma_cubugu_gorunur(win, tmp_path):
    """2026-11-03 ekran görüntüsü: anla/planla/doğrula'da oturumda tur yok → Derin etiketi hiç çizilmiyordu."""
    from test_derin_mod import FakeClient, _session, _wait

    app, w = win
    client = FakeClient(slow=0.6)
    s, _proj = _session(w, tmp_path, client)
    s.send("/derin Basit bir not uygulaması ekle: notlar.txt ve README")
    assert _wait(app, lambda: s.deep.busy and s.composer.run_bar.isVisible(), 10)
    assert not s.running and "Derin · anla" in s.composer.run_text.text()
    s.deep.stop()
    assert _wait(app, lambda: not s.deep.active, 10)
    assert not s.composer.run_bar.isVisible()


def test_glm_listede_yoksa_eski_denetci_eslesmesi(win, monkeypatch):
    app, w = win
    d = w.session.deep
    m1, m2 = d._verifier_models()
    assert m2 == "glm-5.3" and m1 != m2
    w.ctx.models = [m for m in w.ctx.models if m.id != "glm-5.3"]
    m1, m2 = d._verifier_models()
    assert m2 != "glm-5.3" and m1 != m2
    assert d._effort_body("kod", "deepseek-v4.1-flash") is None


def test_base_body_alt_ajanin_model_cagrisina_gider(tmp_path):
    client = _Client([ChatResult(content='<bulgu>{"ozet": "ok"}</bulgu>', finish_reason="stop")])
    dp.run_subagent(client=client, model="m", fallbacks=[], root=tmp_path, prompt="x", marker="<bulgu>",
                    base_body={"reasoning_effort": "high"})
    assert client.kw[0].get("extra_body", {}).get("reasoning_effort") == "high"
    client2 = _Client([ChatResult(content='<bulgu>{"ozet": "ok"}</bulgu>', finish_reason="stop")])
    dp.run_subagent(client=client2, model="m", fallbacks=[], root=tmp_path, prompt="x", marker="<bulgu>")
    assert "reasoning_effort" not in (client2.kw[0].get("extra_body") or {})
