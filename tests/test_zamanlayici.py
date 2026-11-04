"""Zamanlanmış görevler (Madde 12c, 2026-11-05): zaman hesabı, çalıştırma motoru, gerçek tur akışı (R-31),
kalıcılık (R-03). Her otomatik tetik için tetiklenen ve tetiklenmeyen durum (R-22)."""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta

import pytest

from evren_studio.agent import schedule as sched
from evren_studio.agent.schedule import Spec

# 2026-11-05 Perşembe
THU_0830 = datetime(2026, 11, 5, 8, 30)


# ---- zaman hesabı -----------------------------------------------------------------------------------

def test_gunluk_saatlik_haftaici_haftalik_elle():
    assert Spec("daily", "09:00").next_after(THU_0830) == datetime(2026, 11, 5, 9, 0)
    assert Spec("daily", "08:00").next_after(THU_0830) == datetime(2026, 11, 6, 8, 0)
    assert Spec("hourly", "00:15").next_after(THU_0830) == datetime(2026, 11, 5, 9, 15)
    fri_after = datetime(2026, 11, 6, 10, 0)                      # Cuma 10:00 → Pazartesi 09:00
    assert Spec("weekdays", "09:00").next_after(fri_after) == datetime(2026, 11, 9, 9, 0)
    assert Spec("weekly", "09:00", weekday=0).next_after(THU_0830) == datetime(2026, 11, 9, 9, 0)
    assert Spec("weekly", "09:00", weekday=3).next_after(THU_0830) == datetime(2026, 11, 5, 9, 0)
    assert Spec("manual").next_after(THU_0830) is None


def test_ozel_cron_ve_kurallari():
    s = Spec("custom", cron="0 9 * * 1-5")
    assert s.next_after(datetime(2026, 11, 7, 12, 0)) == datetime(2026, 11, 9, 9, 0)   # Cmt → Pzt
    assert Spec("custom", cron="30 */6 * * *").next_after(THU_0830) == datetime(2026, 11, 5, 12, 30)
    # ayın günü VE haftanın günü kısıtlıysa standart cron: VEYA
    c = sched.parse_cron("0 9 1 * 1")
    assert c.matches(datetime(2026, 12, 1, 9, 0)) and c.matches(datetime(2026, 11, 9, 9, 0))
    assert sched.validate_cron("0 9 * * 1-5") == ""
    assert "saatte birden sık" in sched.validate_cron("*/15 * * * *").lower()
    assert "Pazar 0" in sched.validate_cron("0 9 * * 7")
    assert "sayı" in sched.validate_cron("0 9 * * MON")
    assert "hiçbir zaman" in sched.validate_cron("0 9 31 2 *")
    assert "5 alan" in sched.validate_cron("0 9 * *")


def test_dogrulama_ve_aciklama():
    assert Spec("daily", "25:00").validate()
    assert Spec("daily", "9").validate()
    assert Spec("weekly", "09:00", weekday=4).describe() == "Her Cuma 09:00"
    assert Spec("weekdays", "07:30").describe() == "Hafta içi her gün 07:30"
    assert sched.slug("Sabah Test Denetimi İş") == "sabah-test-denetimi-is"


def test_telafi_en_yenisi_calisir_eskiler_atlanir():
    spec = Spec("daily", "09:00")
    created = datetime(2026, 10, 1)
    last = datetime(2026, 11, 2, 9, 0)                            # 3, 4, 5 Kasım 09:00 kaçırıldı
    d = sched.due(spec, last, created, datetime(2026, 11, 5, 11, 0))
    assert d.run_for == datetime(2026, 11, 5, 9, 0)
    assert d.skipped == [datetime(2026, 11, 3, 9, 0), datetime(2026, 11, 4, 9, 0)]
    assert d.catch_up is True


def test_telafi_yalniz_son_7_gun():
    d = sched.due(Spec("daily", "09:00"), datetime(2026, 9, 1), datetime(2026, 8, 1), datetime(2026, 11, 5, 9, 0))
    assert d.run_for == datetime(2026, 11, 5, 9, 0) and len(d.skipped) <= 6


def test_zamaninda_calisma_telafi_sayilmaz_ve_tekrar_tetiklenmez():
    spec = Spec("daily", "09:00")
    now = datetime(2026, 11, 5, 9, 0, 40)
    d = sched.due(spec, datetime(2026, 11, 4, 9, 0), datetime(2026, 10, 1), now)
    assert d.run_for == datetime(2026, 11, 5, 9, 0) and not d.catch_up and not d.skipped
    again = sched.due(spec, d.run_for, datetime(2026, 10, 1), now + timedelta(minutes=1))
    assert again.run_for is None                                  # aynı zaman ikinci kez çalışmaz


def test_olusturulmadan_onceki_zaman_calismaz():
    d = sched.due(Spec("daily", "09:00"), None, datetime(2026, 11, 5, 9, 30), datetime(2026, 11, 5, 10, 0))
    assert d.run_for is None


# ---- çalıştırma motoru (sahte görünüm) ------------------------------------------------------------------

@pytest.fixture()
def ortam(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from evren_studio.config import Settings
    from evren_studio.db import Database

    class Ctx:
        def __init__(self):
            self.db = Database(tmp_path / "t.db")
            self.settings = Settings()

    ctx = Ctx()
    proj = tmp_path / "p"
    proj.mkdir()
    yield app, ctx, proj
    ctx.db.close()


def _host(ctx, clock, views):
    from PySide6.QtCore import QObject, Signal

    from evren_studio.ui.schedule_host import ScheduleHost

    class FakeView(QObject):
        sessions_changed = Signal()

        def __init__(self):
            super().__init__()
            self.running = False
            self.last_stop = ""
            self.last_error = ""
            self.started = None
            self.fail_start = ""
            self.plan = None
            self.stopped = False

        def start_unattended(self, **kw):
            self.started = kw
            if self.fail_start:
                self.last_error = self.fail_start
                return None
            self.running = True
            return 100 + len(views)

        def stop(self):
            self.stopped = True
            self.running = False
            self.last_stop = "cancelled"

        def _pending_plan(self):
            return self.plan

        def deleteLater(self):
            pass

    def factory():
        v = FakeView()
        views.append(v)
        return v, QObject()

    return ScheduleHost(ctx, view_factory=factory, now=lambda: clock[0])


def _pump(app, n=1):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.01)


def _gorev(ctx, proj, **kw):
    base = dict(name="test", prompt="testleri çalıştır", workspace=str(proj), model="glm-5.3", mode="auto",
                kind="daily", time_hm="09:00", last_handled_at=sched.to_utc_iso(datetime(2026, 11, 4, 9, 0)))
    base.update(kw)
    tid = ctx.db.create_scheduled_task(**base)
    ctx.db._exec("UPDATE scheduled_tasks SET created_at=? WHERE id=?",
                 (sched.to_utc_iso(datetime(2026, 10, 1)), tid))
    return tid


def _runs(ctx, tid):
    return [dict(r) for r in ctx.db.list_scheduled_runs(tid)]


def _bitir(app, host, view, stop="done"):
    view.running = False
    view.last_stop = stop
    for _ in range(4):
        host._poll()
    _pump(app, 3)


def test_zamani_gelen_gorev_bir_kez_calisir_ve_tamamlanir(ortam):
    app, ctx, proj = ortam
    clock = [datetime(2026, 11, 5, 9, 0, 30)]
    views = []
    host = _host(ctx, clock, views)
    tid = _gorev(ctx, proj)
    host.tick()
    _pump(app, 3)
    assert len(views) == 1 and views[0].started["workspace"] == str(proj)
    assert views[0].started["mode"] == "auto" and views[0].started["task_id"] == tid
    assert _runs(ctx, tid)[0]["status"] == "calisiyor"
    host.tick()                                            # aynı dakika: ikinci kez başlamaz (R-22)
    _pump(app, 3)
    assert len(views) == 1
    _bitir(app, host, views[0])
    r = _runs(ctx, tid)[0]
    assert r["status"] == "tamamlandi" and r["session_id"] == 101 and r["finished_at"]


def test_zamani_gelmeyen_duraklatilan_ve_zamanlayici_kapaliyken_calismaz(ortam):
    app, ctx, proj = ortam
    clock = [datetime(2026, 11, 5, 8, 59)]
    views = []
    host = _host(ctx, clock, views)
    _gorev(ctx, proj, name="erken")
    _gorev(ctx, proj, name="durak", enabled=0)
    _gorev(ctx, proj, name="elle", kind="manual")
    host.tick()
    _pump(app, 3)
    assert views == []
    ctx.db.update_scheduled_task(1, enabled=0)              # "erken" de duraklatıldı
    clock[0] = datetime(2026, 11, 5, 9, 0, 10)              # zamanı geldi: yine de duraklatılanlar çalışmaz
    host.tick()
    _pump(app, 3)
    assert views == []
    ctx.db.update_scheduled_task(1, enabled=1)
    ctx.settings.schedule_enabled = False                   # zamanlayıcı kapalı: etkin görev de çalışmaz
    host.tick()
    _pump(app, 3)
    assert views == []
    ctx.settings.schedule_enabled = True                    # tetiklenen durum (R-22)
    host.tick()
    _pump(app, 3)
    assert len(views) == 1 and views[0].started["task_id"] == 1


def test_kacirilan_calistirmalar_tek_telafi_ve_bildirim(ortam):
    app, ctx, proj = ortam
    clock = [datetime(2026, 11, 5, 15, 0)]
    views, notes = [], []
    host = _host(ctx, clock, views)
    host.notify.connect(lambda t, m: notes.append(m))
    tid = _gorev(ctx, proj, last_handled_at=sched.to_utc_iso(datetime(2026, 11, 2, 9, 0)))
    host.tick()
    _pump(app, 3)
    assert len(views) == 1
    runs = _runs(ctx, tid)
    assert {r["status"] for r in runs} == {"atlandi", "calisiyor"}
    atl = next(r for r in runs if r["status"] == "atlandi")
    assert "2 çalıştırma kaçırıldı" in atl["reason"]
    assert next(r for r in runs if r["status"] == "calisiyor")["catch_up"] == 1
    assert any("kaçırılan" in n for n in notes)


def test_tek_seferde_tek_calistirma_ikincisi_sirada_bekler(ortam):
    app, ctx, proj = ortam
    clock = [datetime(2026, 11, 5, 9, 0, 5)]
    views = []
    host = _host(ctx, clock, views)
    a = _gorev(ctx, proj, name="a")
    b = _gorev(ctx, proj, name="b")
    host.tick()
    _pump(app, 3)
    assert len(views) == 1 and _runs(ctx, b)[0]["status"] == "sirada"
    _bitir(app, host, views[0])
    assert len(views) == 2 and _runs(ctx, b)[0]["status"] == "calisiyor"
    assert _runs(ctx, a)[0]["status"] == "tamamlandi"


def test_onceki_calistirma_surerken_gelen_zaman_atlanir(ortam):
    app, ctx, proj = ortam
    clock = [datetime(2026, 11, 5, 9, 0, 5)]
    views = []
    host = _host(ctx, clock, views)
    tid = _gorev(ctx, proj, kind="hourly", time_hm="00:00")
    host.tick()
    _pump(app, 3)
    clock[0] = datetime(2026, 11, 5, 10, 0, 5)              # hâlâ çalışıyor
    host.tick()
    _pump(app, 3)
    runs = _runs(ctx, tid)
    assert runs[0]["status"] == "atlandi" and "hâlâ sürüyordu" in runs[0]["reason"]
    assert len(views) == 1


def test_simdi_calistir_elle_gorevde_de_calisir_ve_durdurulur(ortam):
    app, ctx, proj = ortam
    clock = [THU_0830]
    views = []
    host = _host(ctx, clock, views)
    tid = _gorev(ctx, proj, kind="manual")
    host.run_now(tid)
    _pump(app, 3)
    assert len(views) == 1 and _runs(ctx, tid)[0]["manual"] == 1
    host.stop_task(tid)
    for _ in range(4):
        host._poll()
    r = _runs(ctx, tid)[0]
    assert views[0].stopped and r["status"] == "durduruldu" and "kullanıcı" in r["reason"]


def test_baslatilamazsa_hata_nedeniyle_yazilir(ortam):
    app, ctx, proj = ortam
    clock = [THU_0830]
    views = []
    host = _host(ctx, clock, views)
    orig = host._view_factory

    def failing():
        v, p = orig()
        v.fail_start = "EVREN API anahtarı yok"
        return v, p
    host._view_factory = failing
    tid = _gorev(ctx, proj, kind="manual")
    host.run_now(tid)
    _pump(app, 3)
    r = _runs(ctx, tid)[0]
    assert r["status"] == "hata" and "anahtarı yok" in r["reason"]
    assert host.active is None


def test_hata_ve_yarim_kalan_tur_durumu(ortam):
    app, ctx, proj = ortam
    clock = [THU_0830]
    views = []
    host = _host(ctx, clock, views)
    t1 = _gorev(ctx, proj, name="h", kind="manual")
    host.run_now(t1)
    _pump(app, 3)
    views[0].last_error = "HTTP 503"
    _bitir(app, host, views[0], stop="error")
    assert _runs(ctx, t1)[0]["status"] == "hata" and "503" in _runs(ctx, t1)[0]["reason"]
    t2 = _gorev(ctx, proj, name="y", kind="manual")
    host.run_now(t2)
    _pump(app, 3)
    _bitir(app, host, views[1], stop="max_steps")
    assert _runs(ctx, t2)[0]["status"] == "yarim"


def test_kota_beklerken_bitmis_sayilmaz_sonra_tamamlanir(ortam):
    app, ctx, proj = ortam
    clock = [THU_0830]
    views = []
    host = _host(ctx, clock, views)
    tid = _gorev(ctx, proj, kind="manual")
    host.run_now(tid)
    _pump(app, 3)
    v = views[0]
    v.running = False
    v.plan = type("P", (), {"session_id": 101})()
    for _ in range(6):
        host._poll()
    assert host.active is not None and _runs(ctx, tid)[0]["status"] == "kota_bekliyor"
    v.plan = None
    _bitir(app, host, v)
    assert _runs(ctx, tid)[0]["status"] == "tamamlandi"


def test_sure_siniri_asilinca_durdurulur(ortam):
    app, ctx, proj = ortam
    clock = [THU_0830]
    views = []
    host = _host(ctx, clock, views)
    ctx.settings.schedule_max_minutes = 5
    tid = _gorev(ctx, proj, kind="manual")
    host.run_now(tid)
    _pump(app, 3)
    host.active["t0"] -= 6 * 60
    host._poll()
    assert views[0].stopped
    for _ in range(4):
        host._poll()
    r = _runs(ctx, tid)[0]
    assert r["status"] == "durduruldu" and "süre sınırı" in r["reason"]


def test_sure_siniri_altinda_durdurulmaz(ortam):
    app, ctx, proj = ortam
    clock = [THU_0830]
    views = []
    host = _host(ctx, clock, views)
    tid = _gorev(ctx, proj, kind="manual")
    host.run_now(tid)
    _pump(app, 3)
    host.active["t0"] -= 60
    host._poll()
    assert not views[0].stopped


def test_gorev_silinince_oturumlar_kalir_ve_kayit_kalicidir(ortam, tmp_path):
    app, ctx, proj = ortam
    tid = _gorev(ctx, proj, kind="manual")
    sid = ctx.db.create_session("glm-5.3", str(proj), "auto", title="x")
    ctx.db.update_session(sid, scheduled_task_id=tid)
    from evren_studio.db import Database

    again = Database(tmp_path / "t.db")                       # R-03: yeni bağlantı aynı görevi okur
    assert again.get_scheduled_task(tid)["prompt"] == "testleri çalıştır"
    again.close()
    ctx.db.delete_scheduled_task(tid)
    assert ctx.db.get_scheduled_task(tid) is None
    row = ctx.db.get_session(sid)
    assert row is not None and row["scheduled_task_id"] is None


def test_uyanik_tut_yalniz_ayar_acik_ve_etkin_gorev_varken(ortam, monkeypatch):
    app, ctx, proj = ortam
    host = _host(ctx, [THU_0830], [])
    calls = []
    monkeypatch.setattr(type(host), "_set_awake", lambda self, on: calls.append(on))
    host.apply_keep_awake()
    _gorev(ctx, proj)
    host.apply_keep_awake()
    ctx.settings.schedule_keep_awake = True
    host.apply_keep_awake()
    assert calls == [False, False, True]


# ---- gerçek oturum görünümü ile uçtan uca (R-31) ------------------------------------------------------

class _Client:
    def __init__(self):
        self.calls = []

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, on_reasoning=None, tools=None, **kw):
        from evren_studio.api.client import ChatResult

        self.calls.append({"model": model, "messages": messages, "tools": tools})
        return ChatResult(content="Testler geçti; rapor hazır.", finish_reason="stop")

    def close(self):
        pass


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


def _wait(app, cond, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def test_gercek_gorunumle_calisir_kullanici_oturumunu_bolmez_ayarlari_degistirmez(win, tmp_path):
    app, w = win
    client = _Client()
    w.ctx.make_client = lambda log_sink=None: client
    w.ctx.settings.plan_first = True                       # gözetimsizde plan kartı açılmamalı
    w.ctx.settings.suggest_project = True
    w.ctx.settings.default_model, w.ctx.settings.agent_mode = "deepseek-v4.1-flash", "manuel"
    proj = tmp_path / "proje"
    proj.mkdir()
    user_sid = w.session.session_id
    tid = w.ctx.db.create_scheduled_task(name="sabah", prompt="testleri çalıştır ve raporla",
                                         workspace=str(proj), model="glm-5.3", mode="auto", kind="manual")
    w.scheduler.run_now(tid)
    assert _wait(app, lambda: w.ctx.db.list_scheduled_runs(tid)[0]["status"] == "tamamlandi", 15)
    run = w.ctx.db.list_scheduled_runs(tid)[0]
    s = w.ctx.db.get_session(run["session_id"])
    assert s["scheduled_task_id"] == tid and s["workspace"] == str(proj) and s["mode"] == "auto"
    msgs = w.ctx.db.get_session_messages(run["session_id"])
    assert msgs[0]["role"] == "user" and "testleri çalıştır" in msgs[0]["content"]
    assert any(m["role"] == "assistant" and "rapor hazır" in m["content"] for m in msgs)
    assert client.calls and client.calls[0]["model"] == "glm-5.3"
    # "Önce plan" açık olsa da görev plan turuna (salt okuma) düşmedi: yazma araçları sunuldu
    names = {t["function"]["name"] for t in client.calls[0]["tools"] or []}
    assert "write_file" in names
    # kullanıcının görünümü ve varsayılanları değişmedi
    assert w.session.session_id == user_sid
    assert w.ctx.settings.default_model == "deepseek-v4.1-flash" and w.ctx.settings.agent_mode == "manuel"
    # kenar çubuğunda "Zamanlanmış" alt yazısıyla görünür
    w.sidebar.refresh()
    from evren_studio.ui.sidebar import ROLE_SUB

    subs = [w.sidebar.list.item(i).data(ROLE_SUB) or "" for i in range(w.sidebar.list.count())]
    assert any(x.startswith("Zamanlanmış") for x in subs)


def test_gozetimsiz_gorunum_secimleri_varsayilana_yazmaz_normal_gorunum_yazar(win):
    app, w = win
    from evren_studio.ui.session_view import SessionView
    from evren_studio.ui.side_panel import SidePanel

    s = w.ctx.settings
    s.agent_mode, s.default_model = "manuel", "deepseek-v4.1-flash"
    hidden = SessionView(w.ctx, SidePanel(w.ctx))
    hidden.unattended = True
    hidden.set_mode("plan")
    hidden.set_model("glm-5.3")
    assert (s.agent_mode, s.default_model) == ("manuel", "deepseek-v4.1-flash")
    w.session.set_mode("plan")                               # kullanıcının görünümü hatırlar (R-22)
    assert s.agent_mode == "plan"
    hidden.deleteLater()


def test_sayfa_olustur_ayrinti_gecmis_ve_sil(win, tmp_path, monkeypatch):
    app, w = win
    from evren_studio.ui import scheduled_page as sp

    proj = tmp_path / "proje2"
    proj.mkdir()
    w.show_page("scheduled")
    page = w.pages["scheduled"]
    assert page.empty.isVisible()
    dlg = sp.TaskDialog(w.ctx, None, page)
    assert dlg.problem() == "Ad gerekli."
    dlg.name.setText("Haftalık özet")
    dlg.prompt.setPlainText("özet yaz")
    dlg.workspace.setText(str(proj))
    dlg.kind.setCurrentIndex(sched.KINDS.index("custom"))
    dlg.cron.setText("*/10 * * * *")
    assert "saatte birden sık" in dlg.problem().lower()
    dlg.cron.setText("0 17 * * 5")
    assert dlg.problem() == ""
    monkeypatch.setattr(sp.TaskDialog, "exec", lambda self: sp.QDialog.Accepted)
    girilen = dlg.values()
    monkeypatch.setattr(sp.TaskDialog, "values", lambda self: dict(girilen))
    page.new_task()
    tid = page.current_id
    row = w.ctx.db.get_scheduled_task(tid)
    assert row["cron"] == "0 17 * * 5" and row["kind"] == "custom"
    assert page.stack.currentIndex() == 1 and "Haftalık özet" in page.d_title.text()
    assert "Henüz çalışmadı" in page.history.item(0).text()
    page.enabled.setChecked(False)
    assert w.ctx.db.get_scheduled_task(tid)["enabled"] == 0
    page.show_list()
    assert page.list.count() == 1
    page.show_task(tid)
    page.delete_task()
    assert w.ctx.db.get_scheduled_task(tid) is None and page.stack.currentIndex() == 0
