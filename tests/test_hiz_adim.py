"""Madde 7 (hız, 2026-11-04): adım azaltma ve doğruluğu koruyan tur içi düzenlemeler.

- Tur içinde eski araç çıktıları sert sınırdan ÖNCE kısaltılır; tur yalnız kısaltma yetmezse durur
  (gözlem a0d2b1645e16: 1M bağlamlı modelde kısaltma ~700k'da başlıyordu, sert sınır ~150k hep önce geliyordu).
- Kısaltılan çıktıyı yeniden okumak döngü sayılmaz.
- Dürtmeden sonra da boş yanıt gelirse yedek model sürdürür (tur boş "bitti" sayılmaz).
- İstem: bağımsız okumalar tek yanıtta.
Her davranış için tetiklenen ve tetiklenmeyen durum (R-22); tur akışı gerçek koşucudan (R-31).
"""
from __future__ import annotations

import json

import pytest

from evren_studio.agent import prompts
from evren_studio.agent.runner import TRIMMED_NOTE, AgentEvents, AgentRunner, trim_for_context
from evren_studio.agent.tools import Workspace
from evren_studio.api.client import ChatResult
from evren_studio.db import Database


def tc(name, cid, **args):
    return ChatResult(tool_calls=[{"id": cid, "name": name, "arguments": json.dumps(args, ensure_ascii=False)}],
                      finish_reason="tool_calls")


class Fake:
    """Model adına göre de yanıt verebilen sahte istemci; gönderilen mesajları saklar."""

    def __init__(self, responses, by_model=None):
        self.responses = list(responses)
        self.by_model = {k: list(v) for k, v in (by_model or {}).items()}
        self.requests = []

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, on_reasoning=None, tools=None, **kw):
        self.requests.append({"model": model, "messages": messages})
        q = self.by_model.get(model)
        if q:
            return q.pop(0)
        if self.responses:
            return self.responses.pop(0)
        return ChatResult(content="Bitti: dosyalar incelendi.", finish_reason="stop")


class Ev(AgentEvents):
    def __init__(self):
        self.statuses = []

    def status(self, text):
        self.statuses.append(text)


@pytest.fixture()
def env(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    for i in range(8):
        (root / f"b{i}.txt").write_text(f"dosya {i}\n" + "x" * 12_000, encoding="utf-8")
    (root / "kucuk.txt").write_text("küçük\n", encoding="utf-8")
    db = Database(tmp_path / "t.db")
    yield root, db
    db.close()


def runner(env, client, model="m", **kw):
    root, db = env
    sid = db.create_session(model, str(root), "kabul")
    db.add_session_message(sid, "user", "dosyaları incele")
    ev = Ev()
    kw.setdefault("stream", False)
    r = AgentRunner(client, model, session_id=sid, store=db, workspace=Workspace(root), mode="kabul",
                    events=ev, **kw)
    return r, db, sid, ev


def tool_contents(messages):
    return [m.get("content") or "" for m in messages if m.get("role") == "tool"]


# ---- tur içi kısaltma -------------------------------------------------------------------------

def test_sert_sinir_varken_eski_ciktilar_sinirdan_once_kisaltilir_ve_tur_surer(env):
    # 8 büyük okuma (~12k karakter) → kısaltılmamış geçmiş sert sınırı aşar; eskiler kısaltılınca sığar
    calls = [tc("read_file", f"c{i}", path=f"b{i}.txt") for i in range(8)]
    client = Fake(calls)
    r, db, sid, ev = runner(env, client, hard_context_limit=30_000, output_limit=20_000)
    out = r.run(db.get_session_messages(sid))
    assert out.stopped == "done", out.stopped                 # eskiden: context_limit (tur durup özetlenirdi)
    last = client.requests[-1]["messages"]
    assert TRIMMED_NOTE in tool_contents(last), "en eski çıktılar modele kısaltılmış gitmeli"
    assert any("x" * 1000 in c for c in tool_contents(last)[-2:]), "son çıktılar tam kalmalı"
    kayit = [m["content"] for m in db.get_session_messages(sid) if m["role"] == "tool"]
    assert TRIMMED_NOTE not in kayit, "kalıcı kayıt değişmemeli"


def test_kucuk_gecmiste_kisaltma_tetiklenmez(env):
    client = Fake([tc("read_file", "c1", path="kucuk.txt"), tc("read_file", "c2", path="b0.txt")])
    r, db, sid, ev = runner(env, client, hard_context_limit=150_000)
    assert r.run(db.get_session_messages(sid)).stopped == "done"
    assert all(TRIMMED_NOTE not in tool_contents(q["messages"]) for q in client.requests)


def test_kisaltma_yetmezse_tur_yine_guvenli_noktada_durur(env):
    # Tek dev çıktı en son mesajda: kısaltılamaz (son mesajlar korunur) → context_limit
    root, _ = env
    (root / "dev.txt").write_text("satır\n" * 30_000, encoding="utf-8")
    client = Fake([tc("read_file", "c1", path="dev.txt")])
    r, db, sid, ev = runner(env, client, hard_context_limit=8_000, output_limit=60_000)
    out = r.run(db.get_session_messages(sid))
    assert out.stopped == "context_limit" and len(client.requests) == 1


def test_trim_budget_ve_baglam_birlikte_kucugu_alinir():
    hist = [{"role": "user", "content": "x"}]
    for i in range(12):
        hist.append({"role": "assistant", "content": "", "tool_calls": [{"id": str(i), "name": "read_file",
                                                                        "arguments": "{}"}]})
        hist.append({"role": "tool", "tool_call_id": str(i), "content": "a" * 5000})
    # bağlam büyük (kısaltma gerekmez), açık hedef küçük → kısaltılır
    assert TRIMMED_NOTE in tool_contents(trim_for_context(hist, 1_000_000, budget=10_000))
    assert TRIMMED_NOTE not in tool_contents(trim_for_context(hist, 1_000_000))
    assert TRIMMED_NOTE not in tool_contents(trim_for_context(hist, None))
    assert TRIMMED_NOTE in tool_contents(trim_for_context(hist, None, budget=10_000))


def test_kisaltilan_ciktiyi_yeniden_okumak_dongu_sayilmaz(env):
    # b0 okunur, sonra diğerleri okunup b0'ın çıktısı kısaltılır; b0 iki kez daha okunur (toplam 3 = REPEAT_STOP)
    calls = [tc("read_file", "c0", path="b0.txt")] + [tc("read_file", f"c{i}", path=f"b{i}.txt")
                                                       for i in range(1, 7)]
    calls += [tc("read_file", "r1", path="b0.txt"), tc("read_file", "r2", path="b0.txt")]
    client = Fake(calls)
    r, db, sid, ev = runner(env, client, hard_context_limit=30_000)
    out = r.run(db.get_session_messages(sid))
    assert out.stopped == "done", (out.stopped, ev.statuses)


def test_kisaltma_yokken_ayni_okuma_yine_dongu_sayilir(env):
    client = Fake([tc("read_file", f"c{i}", path="kucuk.txt") for i in range(3)])
    r, db, sid, ev = runner(env, client, hard_context_limit=150_000)
    assert r.run(db.get_session_messages(sid)).stopped == "loop"


# ---- boş yanıtta yedek model ------------------------------------------------------------------

def test_durtmeden_sonra_da_bos_yanit_yedek_modele_gecer(env):
    client = Fake([], by_model={"m": [ChatResult(content=""), ChatResult(content="")],
                                "yedek": [ChatResult(content="kucuk.txt içinde 'küçük' yazıyor.")]})
    r, db, sid, ev = runner(env, client, fallback_models=["yedek"])
    out = r.run(db.get_session_messages(sid))
    assert out.stopped == "done"
    assert [s[1] for s in out.model_switches] == ["yedek"]
    assert out.last_text.startswith("kucuk.txt")
    assert [q["model"] for q in client.requests] == ["m", "m", "yedek"]


def test_bos_yanitta_yedek_yoksa_eski_davranis(env):
    client = Fake([], by_model={"m": [ChatResult(content=""), ChatResult(content="")]})
    r, db, sid, ev = runner(env, client)
    out = r.run(db.get_session_messages(sid))
    assert out.stopped == "done" and not out.model_switches and len(client.requests) == 2
    assert any("boş yanıt" in s for s in ev.statuses)


def test_ilk_bos_yanitta_once_durtulur_gecilmez(env):
    client = Fake([], by_model={"m": [ChatResult(content=""), ChatResult(content="Tamam, bitti.")]})
    r, db, sid, ev = runner(env, client, fallback_models=["yedek"])
    out = r.run(db.get_session_messages(sid))
    assert out.stopped == "done" and not out.model_switches


def test_bos_yanitta_kod_rolunde_zayif_modele_gecilmez(env):
    client = Fake([], by_model={"m": [ChatResult(content=""), ChatResult(content="")]})
    r, db, sid, ev = runner(env, client, fallback_models=["gemma-4-31b"], route_role="kod")
    out = r.run(db.get_session_messages(sid))
    assert not out.model_switches and all(q["model"] == "m" for q in client.requests)


def test_bos_yanit_gecisi_tur_basina_bir_kez(env):
    client = Fake([], by_model={"m": [ChatResult(content="")] * 2,
                                "y1": [ChatResult(content="")] * 2,
                                "y2": [ChatResult(content="olmamalı")]})
    r, db, sid, ev = runner(env, client, fallback_models=["y1", "y2"])
    out = r.run(db.get_session_messages(sid))
    assert [s[1] for s in out.model_switches] == ["y1"]
    assert "y2" not in [q["model"] for q in client.requests]


# ---- damla akış (çağrı içinde çok yavaş akış) -------------------------------------------------

class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class StreamFake:
    """Akışı benzetir: her 'olay'da saat ilerler, istemci gibi her satırda cancel.cancelled okunur.
    plan[model] = (toplam_sn, olay_sayısı, olay_başına_karakter, son yanıt)"""

    def __init__(self, clock, plan, user_cancel=None):
        self.clock, self.plan, self.user_cancel = clock, plan, user_cancel
        self.calls = []

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, on_reasoning=None, tools=None, **kw):
        self.calls.append(model)
        total, events, chars, final = self.plan[model]
        step = total / events
        got = 0
        for i in range(events):
            if self.user_cancel is not None and i == 10:          # damla eşiğinden (120 sn) çok önce
                self.user_cancel.cancelled = True
            if cancel is not None and cancel.cancelled:
                return ChatResult(reasoning="d" * got, finish_reason="cancelled_by_user")
            self.clock.t += step
            if chars and on_reasoning:
                on_reasoning("d" * chars)
                got += chars
        return final


@pytest.fixture()
def saat(monkeypatch):
    from evren_studio.agent import runner as runner_mod

    c = Clock()
    monkeypatch.setattr(runner_mod, "_now", c)
    return c


DRIP = (300.0, 600, 3, ChatResult(content="olmamalı", finish_reason="stop"))       # 6 karakter/sn, 2 olay/sn
OK_FINAL = ChatResult(content="Tamam: iş bitti.", finish_reason="stop")


def test_damla_akista_cagri_kesilir_ve_yedek_ayni_adimi_yapar(env, saat):
    client = StreamFake(saat, {"m": DRIP, "yedek": (5.0, 50, 20, OK_FINAL)})
    r, db, sid, ev = runner(env, client, fallback_models=["yedek"], stream=True)
    out = r.run(db.get_session_messages(sid))
    assert client.calls == ["m", "yedek"]
    assert out.stopped == "done" and out.last_text == "Tamam: iş bitti."
    assert out.model_switches and "akış damlıyor" in out.model_switches[0][2]
    asst = [m for m in db.get_session_messages(sid) if m["role"] == "assistant"]
    assert len(asst) == 1 and asst[0]["content"] == "Tamam: iş bitti.", "yarım yanıt kaydedilmemeli"
    assert out.steps == 1, "kesilen çağrı adım sayılmaz"


def test_yavas_ama_saglikli_akista_kesilmez(env, saat):
    # 200 sn sürüyor ama 40 karakter/sn → normal (uzun düşünme/uzun yanıt)
    client = StreamFake(saat, {"m": (200.0, 2000, 4, OK_FINAL), "yedek": (5.0, 50, 20, OK_FINAL)})
    r, db, sid, ev = runner(env, client, fallback_models=["yedek"], stream=True)
    out = r.run(db.get_session_messages(sid))
    assert client.calls == ["m"] and not out.model_switches


def test_arac_argumani_akarken_karakter_gelmese_de_kesilmez(env, saat):
    # Büyük write_file: argüman parçaları geri çağrıya gelmez (0 karakter) ama olaylar sık (25/sn)
    client = StreamFake(saat, {"m": (200.0, 5000, 0, OK_FINAL), "yedek": (5.0, 50, 20, OK_FINAL)})
    r, db, sid, ev = runner(env, client, fallback_models=["yedek"], stream=True)
    out = r.run(db.get_session_messages(sid))
    assert client.calls == ["m"] and not out.model_switches


def test_damla_akis_ilk_iki_dakikada_kesilmez(env, saat):
    client = StreamFake(saat, {"m": (110.0, 220, 3, OK_FINAL), "yedek": (5.0, 50, 20, OK_FINAL)})
    r, db, sid, ev = runner(env, client, fallback_models=["yedek"], stream=True)
    assert r.run(db.get_session_messages(sid)).stopped == "done" and client.calls == ["m"]


def test_damla_akista_yedek_yoksa_beklenir(env, saat):
    final = ChatResult(content="Geç ama doğru yanıt.", finish_reason="stop")
    client = StreamFake(saat, {"m": (300.0, 600, 3, final)})
    r, db, sid, ev = runner(env, client, stream=True)
    out = r.run(db.get_session_messages(sid))
    assert client.calls == ["m"] and out.last_text == "Geç ama doğru yanıt."


def test_damla_akista_yalniz_zayif_yedek_varsa_kesilmez(env, saat):
    final = ChatResult(content="Güçlü modelden yanıt.", finish_reason="stop")
    client = StreamFake(saat, {"m": (300.0, 600, 3, final), "gemma-4-31b": (5.0, 50, 20, OK_FINAL)})
    r, db, sid, ev = runner(env, client, fallback_models=["gemma-4-31b"], route_role="kod", stream=True)
    out = r.run(db.get_session_messages(sid))
    assert client.calls == ["m"] and out.last_text == "Güçlü modelden yanıt."


def test_damla_akis_gecisi_gorev_basina_bir_kez(env, saat):
    final = ChatResult(content="İkinci yedekten yanıt.", finish_reason="stop")
    client = StreamFake(saat, {"m": DRIP, "y1": (300.0, 600, 3, final), "y2": (5.0, 50, 20, OK_FINAL)})
    r, db, sid, ev = runner(env, client, fallback_models=["y1", "y2"], stream=True)
    out = r.run(db.get_session_messages(sid))
    assert client.calls == ["m", "y1"] and out.last_text == "İkinci yedekten yanıt."


def test_akissiz_istekte_damla_denetimi_yok(env, saat):
    client = StreamFake(saat, {"m": (300.0, 600, 3, OK_FINAL), "yedek": (5.0, 50, 20, OK_FINAL)})
    r, db, sid, ev = runner(env, client, fallback_models=["yedek"], stream=False)
    assert r.run(db.get_session_messages(sid)).stopped == "done" and client.calls == ["m"]


def test_kullanici_iptali_damla_sayilmaz(env, saat):
    class Tok:
        cancelled = False

    tok = Tok()
    client = StreamFake(saat, {"m": DRIP, "yedek": (5.0, 50, 20, OK_FINAL)}, user_cancel=tok)
    r, db, sid, ev = runner(env, client, fallback_models=["yedek"], stream=True, cancel=tok)
    out = r.run(db.get_session_messages(sid))
    assert out.stopped == "cancelled" and client.calls == ["m"] and not out.model_switches


# ---- istem --------------------------------------------------------------------------------------

def test_istem_bagimsiz_okumalari_tek_yanitta_ister_bagimliyi_ayirir():
    rules = prompts.AGENT_RULES
    assert "BAĞIMSIZ okuma/inceleme" in rules and "birden çok araç çağrısıyla" in rules
    assert "ayrı yanıtta" in rules, "bağımlı işler (düzenle → test) ayrı adımda kalmalı"
