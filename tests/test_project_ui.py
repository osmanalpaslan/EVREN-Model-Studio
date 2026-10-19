"""Proje ajanı arayüz akışı: /proje → plan kartı → onay → görevler → rapor (sahte model, ağ yok)."""
from __future__ import annotations

import os
import time

import pytest

from evren_studio.agent import project as pj
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
    assert tasks[0][1] == "deepseek-v4-flash" and "PROJE GÖREVİ 1/2" in tasks[0][2]
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
