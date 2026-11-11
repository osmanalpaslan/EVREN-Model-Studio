"""Proje ajanı arayüz akışı: /proje → plan kartı → onay → görevler → rapor (sahte model, ağ yok)."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from evren_studio.agent import project as pj
from evren_studio.agent import router
from evren_studio.api.client import ChatResult

PLAN = """<plan>
- [ ] 1. notlar.txt dosyasını oluştur
  Bitti ölçütü: notlar.txt var
- [ ] 2. README yaz
  Bitti ölçütü: README.md kullanım içerir
  Bağımlı: 1
</plan>"""


class FakeClient:
    def __init__(self, slow: float = 0.0):
        self.calls = []
        self.slow = slow

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, tools=None, **kw):
        sys_text = messages[0]["content"] if messages else ""
        last = [m for m in messages if m["role"] == "user"][-1]["content"]
        kind = ("review" if sys_text == pj.REVIEW_SYSTEM else "plan" if "PROJE PLANLAMA" in last
                else "task")
        self.calls.append((kind, model, last[:60]))
        if self.slow:
            end = time.monotonic() + self.slow
            while time.monotonic() < end:
                if cancel is not None and cancel.cancelled:
                    return ChatResult(content="", finish_reason="cancelled_by_user")
                time.sleep(0.02)
        if kind == "review":
            return ChatResult(content='{"tamam": true, "neden": "ölçüt sağlandı"}', finish_reason="stop")
        if kind == "plan":
            return ChatResult(content="İnceledim.\n" + PLAN, finish_reason="stop")
        return ChatResult(content="Görev tamamlandı.", finish_reason="stop")

    def close(self):
        pass


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
    w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
    yield app, w
    w.close()


def _wait(app, cond, timeout=15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def _start(w, tmp_path, client):
    from evren_studio.ui.project_ui import PlanCard

    proj = tmp_path / "proje"
    proj.mkdir()
    w.ctx.make_client = lambda log_sink=None: client
    s = w.session
    s.new_session()
    s.welcome._choose(str(proj))
    s.composer.set_model("auto-pro", emit=True)
    s.send("/proje Basit bir not uygulaması: notlar.txt ve README")
    return s, proj, PlanCard


def test_proje_akisi_plan_onay_yurutme_rapor(win, tmp_path):
    app, w = win
    client = FakeClient()
    notes = []
    w.session.notify.connect(lambda t, x: notes.append((t, x)))
    s, proj, PlanCard = _start(w, tmp_path, client)
    assert _wait(app, lambda: s.findChildren(PlanCard))
    card = s.findChildren(PlanCard)[-1]
    assert client.calls[0][0] == "plan"
    assert client.calls[0][1] == "deepseek-v4.1-flash"                # plan rolü (router)
    assert (proj / pj.PLAN_FILE).is_file()
    # onaydan önce yürütme yok
    assert not s.project.active and [c for c in client.calls if c[0] == "task"] == []
    s.send("araya mesaj")                                                # plan beklerken serbest mesaj olur
    card.approved.emit()
    assert _wait(app, lambda: not s.project.active and s.project.state and s.project.state.status == "bitti")
    st = s.project.state
    assert [t.status for t in st.tasks] == ["bitti", "bitti"]
    tasks = [c for c in client.calls if c[0] == "task" and "PROJE GÖREVİ" in c[2]]
    assert tasks[0][1] == router.EVREN_ROUTES["kod"][0] and "PROJE GÖREVİ 1/2" in tasks[0][2]   # kod rolü birincili
    assert len([c for c in client.calls if c[0] == "review"]) == 2
    assert (proj / pj.REPORT_FILE).is_file()
    assert "[x] 2. README yaz" in (proj / pj.PLAN_FILE).read_text(encoding="utf-8")
    assert notes and "tamamlandı" in notes[-1][0]
    row = w.ctx.db.latest_project_run(s.session_id)
    assert row["status"] == "bitti"
    # temiz bağlam: 2. görevin ajan turu 1. görevin mesajlarını görmedi
    msgs = w.ctx.db.get_session_messages(s.session_id)
    disp = [(m.get("meta") or {}).get("display", "") for m in msgs if m["role"] == "user"]
    assert any(d.startswith("Proje görevi 2/2") for d in disp)


def test_proje_surerken_mesaj_engellenir_durdur_ve_devam(win, tmp_path):
    app, w = win
    client = FakeClient(slow=0.6)
    s, proj, PlanCard = _start(w, tmp_path, client)
    assert _wait(app, lambda: s.findChildren(PlanCard))
    s.findChildren(PlanCard)[-1].approved.emit()
    assert _wait(app, lambda: s.running)
    s.composer.set_text("ara mesaj")
    s.composer._submit()
    assert s.composer.edit.toPlainText() == "ara mesaj"                 # engellendi, metin geri kondu
    s.send("/proje-durdur")
    assert _wait(app, lambda: not s.project.active)
    assert s.project.state.status == "duraklatildi"
    assert w.ctx.db.latest_project_run(s.session_id)["status"] == "duraklatildi"
    client.slow = 0.0
    s.composer.edit.clear()
    s.send("/proje-devam")
    assert _wait(app, lambda: not s.project.active and s.project.state.status == "bitti")
    assert [t.status for t in s.project.state.tasks] == ["bitti", "bitti"]


def test_klasorsuz_ve_bos_hedef(win):
    app, w = win
    s = w.session
    s.new_session()
    s.welcome._choose(None)
    notes = []
    orig = s._note
    s._note = lambda text, icon="dot": (notes.append(text), orig(text, icon))
    s.send("/proje bir şey yap")
    assert any("proje klasöründe" in n for n in notes) and not s.project.planning


PLAN3 = """<plan>
- [ ] 1. a.txt dosyasını oluştur
  Bitti ölçütü: a.txt var
- [ ] 2. b.txt dosyasını oluştur
  Bitti ölçütü: b.txt var
- [ ] 3. README yaz
  Bitti ölçütü: README.md iki dosyayı anlatır
  Bağımlı: 1, 2
</plan>"""


class Plan3Client(FakeClient):
    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, tools=None, **kw):
        res = super().chat(model, messages, stream=stream, cancel=cancel, on_delta=on_delta, tools=tools, **kw)
        if self.calls[-1][0] == "plan":
            return ChatResult(content="İnceledim.\n" + PLAN3, finish_reason="stop")
        return res


@pytest.mark.skipif(__import__("shutil").which("git") is None, reason="git yok")
def test_bagimsiz_gorevler_paralel_ve_arayuzsuz(win, tmp_path, monkeypatch):
    """B3 (R-31): gerçek tur akışı — bağımsız 1 ve 2 çalışma kopyalarında arayüzsüz, 3 (toparlama) oturumda."""
    from evren_studio.ui.project_ui import PlanCard
    from tests.test_project_agent import _git_repo

    from evren_studio.agent import deep

    app, w = win
    client = Plan3Client()
    gates, kws = [], []
    real_sub = deep.run_subagent

    def spy(**kw):
        gates.append(kw.get("gate"))
        kws.append(kw.get("runner_kw") or {})
        return real_sub(**kw)
    monkeypatch.setattr(deep, "run_subagent", spy)
    proj = tmp_path / "proje"
    proj.mkdir()
    _git_repo(proj)
    w.ctx.make_client = lambda log_sink=None: client
    w.ctx.settings.project_parallel = 3
    w.ctx.settings.install_mode = "manuel"                         # varsayılandan farklı
    s = w.session
    s.new_session()
    s.welcome._choose(str(proj))
    s.composer.set_model("auto", emit=True)
    s.project._headless_rules = lambda root: ("KURAL", Path(root))      # kablolama: kopyanın kuralı
    s.send("/proje iki dosya ve README")
    assert _wait(app, lambda: s.findChildren(PlanCard))
    s.findChildren(PlanCard)[-1].approved.emit()
    assert _wait(app, lambda: not s.project.active and s.project.state and s.project.state.status == "bitti", 30)
    st = s.project.state
    assert [t.status for t in st.tasks] == ["bitti"] * 3
    assert any("AYNI ANDA" in x for x in st.log)
    msgs = w.ctx.db.get_session_messages(s.session_id)
    disp = [(m.get("meta") or {}).get("display", "") for m in msgs if m["role"] == "user"]
    assert [d for d in disp if d.startswith("Proje görevi")] == ["Proje görevi 3/3: README yaz"]
    assert len([c for c in client.calls if c[0] == "task" and "PROJE GÖREVİ" in c[2]]) == 3
    assert not any((w.ctx.settings.resolved_data_dir() / "worktrees").rglob("*.txt"))
    gate = s.project._par_gate                                         # kota kapısı: paralel görevlerin hepsinde
    assert gate is not None and gate.max_parallel == 3 and len(gates) == 2 and all(g is gate for g in gates)
    s_ = w.ctx.settings                                               # oturum ajanıyla aynı ayarlar
    for kw in kws:
        assert kw["install_mode"] == s_.install_mode and kw["command_timeout"] == s_.command_timeout_seconds
        assert kw["untrusted"] == list(s_.untrusted_dirs or []) and kw["edit_check"] == s_.edit_diagnostics
        assert kw["route_role"] == "kod" and "skills" in kw
        assert kw["user_rules"][0] == "KURAL" and "worktrees" in str(kw["user_rules"][1])


def test_paralel_yalniz_evren_modelinde(win, tmp_path):
    """Arayüzsüz ajanın kullanımı maliyet kaydına girmez → birincil kod modeli ücretliyse paralel KAPALI."""
    app, w = win
    s = w.session
    s.new_session()
    pc = s.project
    w.ctx.settings.project_parallel = 3
    pc._model_for = lambda role, fallback=False: ("evren-x", ["ucretli-y"], role)
    real = w.ctx.provider_of
    w.ctx.provider_of = lambda m: "openai" if m.startswith("ucretli") else "evren" if m.startswith("evren") else real(m)
    assert pc._parallel_width() == 3 and pc._free_chain() == ["evren-x"]          # ücretli yedek zincirden çıkar
    pc._model_for = lambda role, fallback=False: ("ucretli-y", ["evren-x"], role)
    assert pc._parallel_width() == 1 and pc._free_chain() == []
    w.ctx.settings.project_parallel = 1
    pc._model_for = lambda role, fallback=False: ("evren-x", [], role)
    assert pc._parallel_width() == 1


def test_kopyada_kurallar_yalniz_ana_klasorde_onayliysa(win, tmp_path):
    """Paralel görevin kopyasında proje kuralları: ana klasörde AYNI içerikle onaylıysa çalışır; onaysızsa kuralsız
    (arka plan iş parçacığından onay kartı açılmaz)."""
    import json as _json

    from evren_studio.agent import userrules

    app, w = win
    s = w.session
    s.new_session()
    main, wt = tmp_path / "ana", tmp_path / "kopya"
    for d in (main, wt):
        (d / ".evren").mkdir(parents=True)
        (d / userrules.RULES_FILE).write_text(_json.dumps(
            {"kurallar": [{"olay": "tur_sonu", "komut": "echo ok"}]}), encoding="utf-8")
    s.welcome._choose(str(main))
    pc = s.project
    assert pc._headless_rules(wt) is None                                    # onaysız
    _rules, digest = userrules.load(main)
    w.ctx.settings.approved_rules = {str(main.resolve()).lower(): digest}
    got = pc._headless_rules(wt)
    assert got is not None and Path(got.root) == wt and len(got.rules) == 1
    (wt / userrules.RULES_FILE).write_text(_json.dumps(
        {"kurallar": [{"olay": "tur_sonu", "komut": "del *"}]}), encoding="utf-8")
    assert pc._headless_rules(wt) is None                                    # kopyadaki içerik farklı → onaysız
