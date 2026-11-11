"""Gidiş gözetmeni (Madde 20 B4, 2026-11-11): ayrı hızlı model gözetimsiz görevi 8 adımda bir puanlar.

R-22: hem tetiklenmesi (iki düşük puan → dur; tek düşük → yalnız not) hem tetiklenmemesi gereken durumlar (iyi puan,
"emin değilim", eleştirmen hatası, okunamayan yanıt, erken adım) sınanır. Gerçek tur akışı: AgentRunner + Proje
yürütücüsü (erken durdurulan görev gerekçeyle yeniden denenir).
"""
from __future__ import annotations

import json

import pytest

from evren_studio.agent import critic as cr
from evren_studio.agent import project as pj
from evren_studio.agent.runner import AgentEvents, AgentRunner
from evren_studio.agent.tools import Workspace
from evren_studio.api.client import ChatResult
from evren_studio.db import Database


def scores(*seq):
    """Sırayla puan döndüren sahte eleştirmen modeli (+ gelen istemleri kaydeder)."""
    calls = []
    it = iter(seq)

    def chat(messages):
        calls.append(messages)
        v = next(it)
        if isinstance(v, Exception):
            raise v
        return v if isinstance(v, str) else json.dumps({"puan": v, "neden": f"puan {v}", "oneri": "testi çalıştır"})
    return chat, calls


HIST = [{"role": "user", "content": "PROJE GÖREVİ 1/3: a.py'ye topla() ekle"},
        {"role": "assistant", "content": "Bakıyorum", "tool_calls": [{"id": "1", "name": "read_file",
                                                                      "arguments": '{"path": "a.py"}'}]},
        {"role": "tool", "name": "read_file", "content": "x = 1", "meta": {"error": False}}]


def test_yalniz_her_8_adimda_ve_8den_once_hic():
    chat, calls = scores(9, 9)
    c = cr.Critic(chat=chat)
    assert [c.check(s, HIST) for s in range(1, 8)] == [None] * 7 and calls == []
    assert c.check(8, HIST) is None and len(calls) == 1
    assert c.check(9, HIST) is None and len(calls) == 1
    assert c.check(16, HIST) is None and len(calls) == 2


def test_tek_dusuk_puan_yalniz_not_iki_ust_uste_dur():
    chat, _ = scores(2, 1)
    c = cr.Critic(chat=chat)
    kind, text = c.check(8, HIST)
    assert kind == "not" and "puan 2" in text and "testi çalıştır" in text
    kind, why = c.check(16, HIST)
    assert kind == "dur" and why == "puan 1"
    assert [x["puan"] for x in c.log] == [2, 1]


@pytest.mark.parametrize("seq", [(2, 7, 2), (3, 6, 3)])
def test_arada_iyi_puan_sayaci_sifirlar(seq):
    chat, _ = scores(*seq)
    c = cr.Critic(chat=chat)
    out = [c.check(s, HIST) for s in (8, 16, 24)]
    assert [o[0] if o else None for o in out] == ["not", None, "not"]          # asla "dur" değil


@pytest.mark.parametrize("reply", [RuntimeError("bağlantı yok"), "anlamsız yanıt", '{"puan": "bilmem"}',
                                   json.dumps({"neden": "puansız"})])
def test_elestirmen_hatasi_veya_okunamayan_yanit_isi_durdurmaz(reply):
    chat, _ = scores(reply, reply)
    c = cr.Critic(chat=chat)
    assert c.check(8, HIST) is None and c.check(16, HIST) is None and c.strikes == 0


def test_puan_sinirlari_ve_bozuk_json():
    assert cr.parse('{"puan": 14, "neden": "x"}')[0] == 10 and cr.parse('{"puan": -3}')[0] == 0
    assert cr.parse('Değerlendirme: {"puan": 4, "neden": "ilgisiz dosya", }')[0:2] == (4, "ilgisiz dosya")


def test_dokum_kisa_ve_gorev_metni_ilk_kullanici_mesaji():
    long = [{"role": "tool", "name": "run_command", "content": "x" * 10_000, "meta": {"error": True}}] * 30
    task, steps = cr.digest(HIST + long)
    assert task.startswith("PROJE GÖREVİ 1/3")
    assert len(steps) < cr.TAIL * (cr.TOOL_OUT_CHARS + 60) and "HATA" in steps


# ---- gerçek koşucu akışı ----

def tc(name, cid, **args):
    return ChatResult(tool_calls=[{"id": cid, "name": name, "arguments": json.dumps(args, ensure_ascii=False)}],
                      finish_reason="tool_calls")


class Fake:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, on_reasoning=None, tools=None, **kw):
        self.requests.append(messages)
        if not self.responses:
            return ChatResult(content="Bitti: dosyalar yazıldı.", finish_reason="stop")
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
    db = Database(tmp_path / "t.db")
    yield root, db
    db.close()


def run(env, n_steps, critic):
    root, db = env
    sid = db.create_session("m", str(root), "kabul")
    db.add_session_message(sid, "user", "PROJE GÖREVİ: dosyaları yaz")
    client, ev = Fake([tc("write_file", f"c{i}", path=f"f{i}.txt", content=str(i)) for i in range(n_steps)]), Ev()
    r = AgentRunner(client, "m", session_id=sid, store=db, events=ev, workspace=Workspace(root), mode="kabul",
                    stream=False, critic=critic)
    return r.run(db.get_session_messages(sid)), client, ev


def test_kosucu_iki_dusuk_puanla_critic_ile_durur(env):
    chat, calls = scores(2, 1)
    out, client, ev = run(env, 20, cr.Critic(chat=chat))
    assert out.stopped == "critic" and out.critic_reason == "puan 1" and out.steps == 16
    assert any("Gözetmen notu" in s for s in ev.statuses) and any("yeniden yapılacak" in s for s in ev.statuses)
    nudged = [m for m in client.requests[8] if m["role"] == "user" and "Gözetmen notu" in (m.get("content") or "")]
    assert nudged                                                       # 8. adımdan sonraki çağrıda not vardı


def test_kosucu_iyi_puanla_sonuna_kadar_gider(env):
    chat, calls = scores(9, 8)
    out, client, ev = run(env, 20, cr.Critic(chat=chat))
    assert out.stopped == "done" and len(calls) == 2 and not any("Gözetmen" in s for s in ev.statuses)


def test_gozetmensiz_kosucu_degismez(env):
    out, client, ev = run(env, 12, None)
    assert out.stopped == "done" and not any("Gözetmen" in s for s in ev.statuses)


# ---- proje yürütücüsü: erken durdurulan görev gerekçeyle yeniden ----

def test_proje_gozetmen_durdurunca_gerekceyle_yeniden_dener(tmp_path):
    prompts, runs = [], iter([
        pj.TaskRun(stopped="critic", summary="ilgisiz klasörleri tarıyor", model="m",
                   critic=[{"adim": 8, "puan": 2}, {"adim": 16, "puan": 1}]),
        pj.TaskRun(stopped="done", summary="topla() eklendi", model="m", critic=[{"adim": 8, "puan": 9}])])

    def run_task(task, prompt, fallback):
        prompts.append(prompt)
        return next(runs)
    hooks = pj.ProjectHooks(run_task=run_task, review=lambda m: '{"tamam": true, "neden": "ok"}',
                            run_check=lambda c: (0, "OK"), save=lambda st: None, sleep=lambda s: None)
    st = pj.ProjectState(goal="hedef", tasks=[pj.Task(idx=1, title="topla ekle", criteria="topla var")])
    out = pj.ProjectRunner(st, tmp_path, hooks, use_git=False).run()
    assert out.status == "bitti" and out.tasks[0].attempts == 2
    assert "ilgisiz klasörleri tarıyor" in prompts[1] and "gözetmen" in prompts[1]
    assert any("8:2, 16:1 → ERKEN DURDURDU" in x for x in out.log) and any("8:9" in x for x in out.log)


def test_alt_ajan_gozetmen_gerekcesini_sonuc_metnine_tasir(monkeypatch, tmp_path):
    from evren_studio.agent import deep

    class R:
        def __init__(self, *a, **kw):
            self.model = "m"

        def run(self, history):
            history.append({"role": "assistant", "content": "yarım iş"})
            return type("O", (), {"stopped": "critic", "critic_reason": "ilgisiz klasör"})()
    monkeypatch.setattr(deep, "AgentRunner", R)
    res = deep.run_subagent(client=None, model="m", fallbacks=[], root=tmp_path, prompt="p", marker="", mode="auto")
    assert res.stopped == "critic" and res.text == "ilgisiz klasör"


def test_paralel_gorevin_gozetmen_puanlari_gunlukte(tmp_path):
    import shutil

    if shutil.which("git") is None:
        pytest.skip("git yok")
    from tests.test_paralel_gorev import Fake, _git_repo, tasks

    root = tmp_path / "p"
    root.mkdir()
    _git_repo(root)
    fake = Fake(root, {1: ("a.py", "A = 1"), 2: ("b.py", "B = 2"), 3: ("c.py", "C = 3")})
    orig = fake.run_task_in

    def with_marks(task, prompt, r):
        res = orig(task, prompt, r)
        res.critic = [{"adim": 8, "puan": 7}]
        return res
    fake.run_task_in = with_marks
    st = pj.ProjectState(goal="hedef", tasks=tasks([], [], [1, 2]))
    out = pj.ProjectRunner(st, root, fake.hooks(tmp_path / "wt")).run()
    assert out.status == "bitti"
    assert sum("gözetmen puanları (adım:puan) 8:7" in x for x in out.log) == 2
