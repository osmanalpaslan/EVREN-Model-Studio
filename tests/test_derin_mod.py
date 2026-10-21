"""Derin Mod: çekirdek (agent/deep.py) ve arayüz akışı (ui/deep_ui.py) — sahte model, ağ yok."""
from __future__ import annotations

import json
import os
import threading
import time

import pytest

from evren_studio.agent import deep as dp
from evren_studio.agent import project as pj
from evren_studio.api.client import CancelToken, ChatResult

PLAN = """<plan>
- [ ] 1. notlar.txt dosyasını oluştur
  Bitti ölçütü: notlar.txt var
- [ ] 2. README yaz
  Bitti ölçütü: README.md kullanım içerir
</plan>"""

BULGU = '<bulgu>{"ozet": "giriş app.py", "dosyalar": ["app.py: ana"], "riskler": [], "oneri": "küçük adım"}</bulgu>'


def call(name, cid="c1", **args):
    return {"id": cid, "name": name, "arguments": json.dumps(args, ensure_ascii=False)}


# ---- çekirdek ------------------------------------------------------------------------------------

def test_is_soru_ayrimi():
    assert dp.classify("Bu fonksiyon ne yapar?") == "soru"
    assert dp.classify("Notlar nerede saklanıyor?") == "soru"
    assert dp.classify("login sayfası ekle ve test yaz") == "is"
    assert dp.classify("Hatayı düzeltir misin?") == "is"
    assert dp.classify("README'yi incele") == "soru"


def test_cekismeli_karar():
    a = {"sorunlar": [{"ciddiyet": "yuksek", "dosya": "a.py", "aciklama": "None kontrolü yok"},
                      {"ciddiyet": "orta", "dosya": "b.py", "aciklama": "isim kötü"},
                      {"ciddiyet": "dusuk", "dosya": "c.py", "aciklama": "yorum eksik"}]}
    b = {"sorunlar": [{"ciddiyet": "orta", "dosya": "b.py", "aciklama": "isim tutarsız"},
                      {"ciddiyet": "yüksek", "dosya": "a.py", "aciklama": "None kontrolü yok"}]}
    got = dp.confirmed_issues([a, b])
    descs = [g["aciklama"] for g in got]
    assert descs.count("None kontrolü yok") == 1                    # tekrar yok
    assert "isim kötü" in descs and "isim tutarsız" in descs         # iki denetçi aynı dosyada → kabul
    assert "yorum eksik" not in descs                               # düşük tek başına → ret
    assert dp.confirmed_issues([{"sorunlar": [{"ciddiyet": "orta", "dosya": "x", "aciklama": "y"}]}]) == []


class ScriptClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def chat(self, model, messages, **kw):
        self.calls += 1
        return self.replies.pop(0) if self.replies else ChatResult(content="bitti", finish_reason="stop")

    def close(self):
        pass


def test_alt_ajan_yazamaz_onay_aninda_reddedilir(tmp_path):
    """Arayüzsüz alt ajan yazma isterse onay HEMEN reddedilir (sonsuz bekleme yok), dosya oluşmaz."""
    client = ScriptClient([
        ChatResult(tool_calls=[call("write_file", path="x.py", content="print(1)\n")]),
        ChatResult(content="Yazamadım; bulgum:\n" + BULGU, finish_reason="stop")])
    out = {}
    t = threading.Thread(target=lambda: out.setdefault("r", dp.run_subagent(
        client=client, model="m", fallbacks=[], root=tmp_path, prompt="incele", marker="<bulgu>")))
    t.start()
    t.join(10)
    assert not t.is_alive(), "alt ajan onay beklerken takıldı"
    assert not (tmp_path / "x.py").exists()
    assert dp._block(out["r"].text, "bulgu")["ozet"] == "giriş app.py"


def test_kota_kapisi_gunluk_bitince_alt_ajan_durur(tmp_path):
    class Gate:
        def before_call(self, cancel=None, status=None):
            return "daily"
    res = dp.run_subagent(client=ScriptClient([]), model="m", fallbacks=[], root=tmp_path, prompt="x",
                          marker="<bulgu>", gate=Gate())
    assert res.stopped == "quota_daily"


def test_paralel_kota_doluysa_tek_tek():
    class Gate:
        def __init__(self, lim):
            self.lim = lim

        def parallel_limit(self):
            return self.lim
    live, peak = [0], [0]
    lock = threading.Lock()

    def job():
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        time.sleep(0.05)
        with lock:
            live[0] -= 1
        return 1
    assert dp.run_parallel([job] * 4, Gate(1), 3) == [1] * 4 and peak[0] == 1
    peak[0] = 0
    dp.run_parallel([job] * 4, Gate(3), 2)
    assert peak[0] == 2                                              # ayar tavanı


def test_yargic_secimi_ve_ek_fikir():
    st = dp.DeepState(goal="g")
    plans = {"a": "<plan>\n- [ ] 1. A işi\n  Bitti ölçütü: a\n</plan>",
             "b": "<plan>\n- [ ] 1. B işi\n  Bitti ölçütü: b\n- [ ] 2. B iki\n</plan>"}
    sub = lambda m, p, k: dp.SubResult(plans[m], "done")
    judge = lambda msgs: '{"secim": "B", "neden": "daha eksiksiz", "eklenecek": "loglama"}'
    tasks = dp.plan(st, sub, ["a", "b"], judge)
    assert [t.title for t in tasks] == ["B işi", "B iki"] and st.chosen == "B"
    assert "loglama" in tasks[-1].criteria
    # yargıç bozuk yanıt verirse ilk plan
    st2 = dp.DeepState(goal="g")
    assert dp.plan(st2, sub, ["a", "b"], lambda m: "anlamsız")[0].title == "A işi"


# ---- arayüz akışı ----------------------------------------------------------------------------------

class FakeClient:
    """İsteğin türüne göre yanıt verir. Denetçiler ilk turda 'yüksek' sorun bulur, sonra bulmaz."""

    def __init__(self, slow=0.0):
        self.calls = []
        self.slow = slow
        self.verify_n = 0
        self.lock = threading.Lock()

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, tools=None, **kw):
        sys_text = messages[0]["content"] if messages else ""
        users = [m for m in messages if m["role"] == "user"]
        first = users[0]["content"] if users else ""
        last = users[-1]["content"] if users else ""
        kind = ("review" if sys_text == pj.REVIEW_SYSTEM else "judge" if "tarafsız bir yargıç" in sys_text
                else "anla" if "DERİN MOD · ANLA" in first else "dogrula" if "ÇEKİŞMELİ DOĞRULAMA" in first
                else "plan" if "PROJE PLANLAMA" in first else "duzelt" if "DERİN MOD · DÜZELT" in last
                else "yanit" if "DERİN MOD · YANIT" in last else "task")
        with self.lock:
            self.calls.append((kind, model))
        if self.slow:
            end = time.monotonic() + self.slow
            while time.monotonic() < end:
                if cancel is not None and cancel.cancelled:
                    return ChatResult(content="", finish_reason="cancelled_by_user")
                time.sleep(0.02)
        if kind == "review":
            return ChatResult(content='{"tamam": true, "neden": "ok"}', finish_reason="stop")
        if kind == "judge":
            return ChatResult(content='{"secim": "A", "neden": "net"}', finish_reason="stop")
        if kind == "anla":
            return ChatResult(content="İnceledim.\n" + BULGU, finish_reason="stop")
        if kind == "plan":
            return ChatResult(content="Plan:\n" + PLAN, finish_reason="stop")
        if kind == "dogrula":
            with self.lock:
                self.verify_n += 1
                n = self.verify_n
            issues = ([{"ciddiyet": "yuksek", "dosya": "notlar.txt", "aciklama": "boş dosya"}] if n <= 2 else [])
            return ChatResult(content="<denetim>" + json.dumps({"sorunlar": issues, "genel": "-"}) + "</denetim>",
                              finish_reason="stop")
        return ChatResult(content={"duzelt": "Düzelttim.", "yanit": "Notlar app.py:3'te."}.get(kind, "Görev tamamlandı."),
                          finish_reason="stop")

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


def _wait(app, cond, timeout=20.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def _session(w, tmp_path, client):
    proj = tmp_path / "proje"
    proj.mkdir()
    w.ctx.make_client = lambda log_sink=None: client
    s = w.session
    s.new_session()
    s.welcome._choose(str(proj))
    s.composer.set_model("auto-pro", emit=True)
    return s, proj


def test_derin_is_akisi_anla_planla_onay_uygula_dogrula_duzelt(win, tmp_path, monkeypatch):
    from evren_studio.ui.project_ui import PlanCard

    app, w = win
    client = FakeClient()
    s, proj = _session(w, tmp_path, client)
    monkeypatch.setattr(s.deep, "_diff", lambda: "--- a/notlar.txt\n+++ b/notlar.txt\n+merhaba\n")
    notes = []
    w.session.notify.connect(lambda t, x: notes.append((t, x)))
    s.composer.deep_btn.click()                                         # düğmeyle aç
    assert w.ctx.settings.deep_mode and s.deep_on
    s.send("Basit bir not uygulaması ekle: notlar.txt ve README")
    assert _wait(app, lambda: s.findChildren(PlanCard))
    kinds = [c[0] for c in client.calls]
    assert kinds.count("anla") >= 3 and kinds.count("plan") >= 2 and "judge" in kinds
    plan_models = {m for k, m in client.calls if k == "plan"}
    assert len(plan_models) == 2                                         # iki farklı model planladı
    assert all(w.ctx.provider_of(m) == "evren" for _k, m in client.calls)   # yalnız EVREN
    assert "task" not in kinds                                           # onaydan önce yürütme yok
    card = s.findChildren(PlanCard)[-1]
    assert "Derin Mod planı" in card.findChildren(type(card.result))[1].text()
    card.approved.emit()
    assert _wait(app, lambda: not s.deep.active, 40)
    st = s.deep.state
    assert st.status == "bitti" and st.fix_round == 1, (st.status, st.pause_reason, st.log)
    kinds = [c[0] for c in client.calls]
    assert kinds.count("dogrula") >= 4 and "duzelt" in kinds
    assert (proj / dp.REPORT_FILE).is_file()
    assert "Düzeltme turu: 1" in (proj / dp.REPORT_FILE).read_text(encoding="utf-8")
    assert notes and "Derin Mod bitti" in notes[-1][0]


def test_derin_soru_yolu_dosya_degistirmez(win, tmp_path):
    from evren_studio.ui.project_ui import PlanCard

    app, w = win
    client = FakeClient()
    s, proj = _session(w, tmp_path, client)
    s.send("/derin Notlar nerede saklanıyor?")
    assert _wait(app, lambda: s.deep.state is not None and not s.deep.active, 30)
    kinds = [c[0] for c in client.calls]
    assert kinds.count("anla") == 2 and "yanit" in kinds and "plan" not in kinds
    assert not s.findChildren(PlanCard)
    assert s.deep.state.status == "bitti" and not w.ctx.settings.deep_mode   # tek seferlik; düğme kapalı


def test_derin_esc_ile_durur(win, tmp_path):
    app, w = win
    client = FakeClient(slow=1.5)
    s, _proj = _session(w, tmp_path, client)
    s.send("/derin login sayfası ekle")
    assert _wait(app, lambda: s.deep.busy)
    s.stop()                                                             # Esc
    assert _wait(app, lambda: not s.deep.active and not s.deep.busy, 20)
    assert s.deep.state.status == "durduruldu"
    s.composer.set_text("")
    s.send("/derin-durdur")                                              # tekrar: "yok" notu, hata yok


def test_klasorsuz_derin_normal_tura_duser(win, tmp_path):
    app, w = win
    s = w.session
    s.new_session()
    s.welcome._choose(None)
    w.ctx.settings.deep_mode = True
    assert "proje klasöründe" in s.deep.unavailable_reason()
    s.send("/derin bir şey yap")
    assert not s.deep.active


def test_derin_ayari_kalici(win, tmp_path):
    from evren_studio.ui.main_window import MainWindow

    app, w = win
    w.session.composer.deep_btn.click()
    w2 = MainWindow()
    try:
        assert w2.ctx.settings.deep_mode and w2.session.composer.deep_btn.isChecked()
        assert "açık" in w2.session.composer.deep_btn.text()
    finally:
        w2.close()
