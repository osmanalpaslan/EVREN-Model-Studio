"""Kota kapısı ve kota sonrası otomatik sürdürme (2026-10-21; gerçek ağ yok)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from evren_studio.agent.quota import QuotaGate, resume_delay_ms, seconds_until


def _q(ratio=0.1, daily=10_000_000, reset_s=30, daily_reset_s=3600):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(usage_ratio=ratio, daily_remaining_tokens=daily,
                           reset_at=(now + timedelta(seconds=reset_s)).isoformat(),
                           daily_reset_at=(now + timedelta(seconds=daily_reset_s)).isoformat())


class Clock:
    def __init__(self):
        self.t = 0.0
        self.slept = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s
        self.slept += s


def _gate(q, clock=None, **kw):
    clock = clock or Clock()
    return QuotaGate(lambda: q, sleep=clock.sleep, clock=clock.now, **kw), clock


def test_paralellik_pencereye_gore_iner():
    assert _gate(_q(0.2), max_parallel=3)[0].parallel_limit() == 3
    assert _gate(_q(0.65), max_parallel=3)[0].parallel_limit() == 1
    g, _ = _gate(None)
    assert g.parallel_limit() == 2 and g.before_call() is None       # kota okunamazsa engel yok


def test_pencere_doluysa_kodla_bekler_gunluk_azsa_duraklat():
    g, clock = _gate(_q(0.9, reset_s=40))
    notes = []
    assert g.before_call(status=notes.append) is None
    assert 40 <= clock.slept <= 50 and "token harcamaz" in notes[0]
    g2, _ = _gate(_q(0.1, daily=100_000))
    assert g2.before_call() == "daily"
    g3, _ = _gate(_q(0.5))
    assert g3.before_call() is None


def test_bekleme_iptal_edilebilir_ve_ust_sinirli():
    tok = SimpleNamespace(cancelled=True)
    g, _ = _gate(_q(0.95, reset_s=30))
    assert g.before_call(cancel=tok) == "cancelled"
    g2, clock = _gate(_q(0.95, reset_s=9999))
    g2.before_call()
    assert clock.slept <= 362                                        # en çok ~6 dk


def test_sure_hesaplari():
    soon = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    assert 7190 <= seconds_until(soon) <= 7201
    assert 2 * 3600 * 1000 <= resume_delay_ms(soon) <= (2 * 3600 + 130) * 1000
    assert resume_delay_ms(None) == 3600 * 1000 and resume_delay_ms("bozuk") == 3600 * 1000
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assert resume_delay_ms(past) == 60 * 1000                        # en az 1 dk


# ---- arayüz: otomatik sürdürme -------------------------------------------------------------------

@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    # oturumsuz not kalıcı bilgi penceresi açar; testte beklemesin
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    yield app, w
    w.close()


def _oturum(w, tmp):
    proj = tmp / "proje"
    proj.mkdir(exist_ok=True)
    sid = w.ctx.db.create_session("deepseek-v4.1-flash", str(proj))   # proje/QA her zaman bir oturumda çalışır
    w.session.open_session(sid)
    w.ctx.save_settings = lambda: None
    return w.session


def _bekle(app, cond, timeout=8.0):
    import time

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_gunluk_kota_sonrasi_otomatik_surdurur_ve_iptal_edilebilir(win, monkeypatch, tmp_path):
    """2026-11-01: Proje/QA/Derin de sohbetteki ortak kota kartını ve kalıcı devam planını kullanır
    (agent/resume.py); saatinde kota yoklanır, yeterliyse akış kaldığı yerden sürer."""
    app, w = win
    from evren_studio.agent import resume
    from evren_studio.ui.project_ui import schedule_auto_resume

    s = _oturum(w, tmp_path)
    proj = s.project
    proj._quota_cache = (0, _q(daily=1, daily_reset_s=7200))
    resumed = []
    monkeypatch.setattr(proj, "resume", lambda: resumed.append(1))
    note = schedule_auto_resume(proj, "günlük EVREN kotası azaldı (kalan ~1 token)")
    plan = resume.ResumePlan.from_json(w.ctx.db.get_meta(resume.META_KEY))
    assert "otomatik sürdürülecek" in note and plan.flow == "proje" and plan.kind == "gunluk"
    assert s._resume_timer.isActive() and 7200_000 <= s._resume_timer.remainingTime() <= 7330_000
    s._fetch_quota = lambda: _q()                                    # kota yenilendi
    s._resume_timer.timeout.emit()                                   # süre doldu → yoklama → devam
    assert _bekle(app, lambda: resumed == [1])
    assert w.ctx.db.get_meta(resume.META_KEY) is None
    # iptal: durdur komutu bekleyen devamı siler ve zamanlayıcıyı kapatır
    proj._quota_cache = (0, _q(ratio=0.99, reset_s=60))
    schedule_auto_resume(proj, "kota: pencere")
    t = s._resume_timer
    assert t.isActive() and t.remainingTime() <= (60 + resume.WINDOW_EXTRA_S + 2) * 1000
    proj.stop()
    assert not t.isActive() and w.ctx.db.get_meta(resume.META_KEY) is None


def test_ayar_kapaliysa_ve_kota_disi_nedende_zamanlanmaz(win, tmp_path):
    _app, w = win
    from evren_studio.agent import resume
    from evren_studio.ui.project_ui import schedule_auto_resume

    s = _oturum(w, tmp_path)
    proj = s.project
    assert schedule_auto_resume(proj, "kullanıcı durdurdu") == ""
    assert w.ctx.db.get_meta(resume.META_KEY) is None                # kota dışı neden: kart/plan yok
    w.ctx.settings.auto_resume = False
    note = schedule_auto_resume(proj, "günlük EVREN kotası azaldı")
    assert "kapalı" in note                                          # kart açılır, elle sürdürülebilir
    assert s._resume_timer is None or not s._resume_timer.isActive()  # ama zamanlayıcı KURULMAZ


def test_qa_da_otomatik_surdurme(win, monkeypatch, tmp_path):
    app, w = win
    from evren_studio.agent import resume
    from evren_studio.ui.project_ui import schedule_auto_resume

    s = _oturum(w, tmp_path)
    qa = s.qa
    resumed = []
    monkeypatch.setattr(qa, "resume", lambda: resumed.append(1))
    assert schedule_auto_resume(qa, "kota: 429")
    assert resume.ResumePlan.from_json(w.ctx.db.get_meta(resume.META_KEY)).flow == "qa"
    s._fetch_quota = lambda: _q()
    s._resume_timer.timeout.emit()
    assert _bekle(app, lambda: resumed == [1])
