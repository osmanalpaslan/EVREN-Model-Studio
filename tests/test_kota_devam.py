"""Kota bitince otomatik devam (agent/resume.py + oturum kartı). Kullanıcı isteği 2026-11-01: "token bittiğinde
proje yarıda kalıyor; token yenilenince otomatik devam etsin mi paneli olmalı, işaretliyse kaldığı yerden doğru
devam etmeli." Tetiklenen ve tetiklenmeyen (kutu kapalı) durumlar, kalıcılık ve 429 yolu (R-22, R-31)."""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from evren_studio.agent import prompts, resume
from evren_studio.api.client import ChatResult
from evren_studio.api.errors import ApiError, ErrorKind


def Q(daily_remaining=None, ratio=None, daily_reset_in=None, reset_in=None):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        daily_remaining_tokens=daily_remaining, usage_ratio=ratio,
        daily_reset_at=(now + timedelta(seconds=daily_reset_in)).isoformat() if daily_reset_in else None,
        reset_at=(now + timedelta(seconds=reset_in)).isoformat() if reset_in else None)


# ---- çekirdek ---------------------------------------------------------------------------------------

def test_plan_saati_ve_kalicilik_bicimi():
    p = resume.make_plan(7, "gunluk", Q(daily_remaining=10, daily_reset_in=3600), "neden", now=1000.0)
    assert 1000 + 3600 + 100 < p.resume_at <= 1000 + 3600 + resume.DAILY_EXTRA_S + 2
    assert resume.ResumePlan.from_json(p.to_json()) == p
    assert resume.ResumePlan.from_json("bozuk") is None and resume.ResumePlan.from_json(None) is None
    w = resume.make_plan(7, "pencere", Q(reset_in=100), now=0.0)
    assert 100 < w.resume_at <= 100 + resume.WINDOW_EXTRA_S + 2
    assert resume.make_plan(7, "gunluk", None, now=0.0).resume_at == resume.DAILY_FALLBACK_S   # saat bilinmiyor
    assert "dk sonra" in resume.describe(resume.ResumePlan(1, "gunluk", time.time() + 600))


def test_kota_yeterli_mi_ve_tur():
    assert resume.quota_ok(None) and resume.quota_ok(Q())                       # okunamayan engel değil
    assert not resume.quota_ok(Q(daily_remaining=1000))
    assert not resume.quota_ok(Q(daily_remaining=10_000_000, ratio=0.95))
    assert resume.quota_ok(Q(daily_remaining=10_000_000, ratio=0.2))
    assert resume.kind_for(Q(daily_remaining=5)) == "gunluk" and resume.kind_for(Q(ratio=0.99)) == "pencere"
    p = resume.ResumePlan(1, "gunluk", 0.0)
    n = resume.after_probe(p, None, now=50.0)
    assert n.resume_at == 50.0 + resume.PROBE_RETRY_S and n.attempts == 1


# ---- arayüz akışı (gerçek send → koşucu → _on_done yolu) -------------------------------------------

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
    yield app, w, tmp_path
    w.close()


def _wait(app, cond, timeout=8.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


class Client:
    def __init__(self, raise_exc=None):
        self.calls = 0
        self.raise_exc = raise_exc

    def chat(self, model, messages, **kw):
        self.calls += 1
        if self.raise_exc is not None:
            raise self.raise_exc
        return ChatResult(content="tamam", finish_reason="stop")

    def close(self):
        pass


def _setup(w, tmp_path, quota, client):
    w.ctx.make_client = lambda log_sink=None: client
    w.ctx.make_client_for = lambda provider, log_sink=None: client
    w.ctx.save_settings = lambda: None
    s = w.session
    s._fetch_quota = lambda: quota[0]
    proj = tmp_path / "proje"
    proj.mkdir(exist_ok=True)
    s.new_session()
    s.welcome._choose(str(proj))
    s.composer.set_model("deepseek-v4.1-flash", emit=True)
    s.set_mode("auto")
    return s


def _cards(s):
    from evren_studio.ui.transcript import QuotaResumeCard

    return [c for c in s.findChildren(QuotaResumeCard)]


def test_gunluk_kota_azsa_guvenli_noktada_durur_kart_ve_kalici_plan(win):
    app, w, tmp = win
    quota = [Q(daily_remaining=50_000, daily_reset_in=7200)]
    c = Client()
    s = _setup(w, tmp, quota, c)
    w.ctx.settings.auto_resume = True
    s.send("uzun projeye devam et")
    assert _wait(app, lambda: not s.running)
    assert c.calls == 0                                              # model çağrılmadan durdu (token harcanmadı)
    cards = _cards(s)
    assert len(cards) == 1 and cards[0].check.isChecked() and "Günlük" in cards[0].title.text()
    plan = resume.ResumePlan.from_json(w.ctx.db.get_meta(resume.META_KEY))
    assert plan.session_id == s.session_id and plan.kind == "gunluk"
    assert s._resume_timer is not None and s._resume_timer.isActive()
    assert 7000_000 < s._resume_timer.remainingTime() <= (7200 + resume.DAILY_EXTRA_S + 5) * 1000

    # kota hâlâ yetersiz: yeni saat kurulur, devam edilmez
    s._resume_probe()
    assert _wait(app, lambda: resume.ResumePlan.from_json(w.ctx.db.get_meta(resume.META_KEY)).attempts == 1)
    assert c.calls == 0
    # kota yenilendi: aynı oturumda kaldığı yerden devam
    quota[0] = Q(daily_remaining=10_000_000, ratio=0.1)
    s._resume_probe()
    assert _wait(app, lambda: c.calls >= 1 and not s.running)
    msgs = w.ctx.db.get_session_messages(s.session_id)
    assert any(m["role"] == "user" and m["content"] == prompts.QUOTA_CONTINUE_PROMPT for m in msgs)
    assert w.ctx.db.get_meta(resume.META_KEY) is None
    assert not cards[0].check.isEnabled()                             # kart kapandı


def test_kutu_kapaliysa_durmaz_eski_davranis(win):
    app, w, tmp = win
    quota = [Q(daily_remaining=50_000, daily_reset_in=7200)]
    c = Client()
    s = _setup(w, tmp, quota, c)
    w.ctx.settings.auto_resume = False
    s.send("devam")
    assert _wait(app, lambda: not s.running)
    assert c.calls == 1 and not _cards(s)                             # yalnız uyarı, tur sürdü
    assert w.ctx.db.get_meta(resume.META_KEY) is None


def test_kart_kutusu_ayari_degistirir_ve_zamanlayiciyi_durdurur(win):
    app, w, tmp = win
    s = _setup(w, tmp, [Q(daily_remaining=1, daily_reset_in=600)], Client())
    w.ctx.settings.auto_resume = True
    s.send("devam")
    assert _wait(app, lambda: bool(_cards(s)))
    card = _cards(s)[0]
    card.check.setChecked(False)
    assert w.ctx.settings.auto_resume is False and not s._resume_timer.isActive()
    assert w.ctx.db.get_meta(resume.META_KEY) is not None              # plan durur: "Şimdi dene" çalışır
    card.check.setChecked(True)
    assert s._resume_timer.isActive()


def test_elle_mesaj_ve_vazgec_bekleyen_devami_iptal_eder(win):
    app, w, tmp = win
    quota = [Q(daily_remaining=1, daily_reset_in=600)]
    c = Client()
    s = _setup(w, tmp, quota, c)
    w.ctx.settings.auto_resume = True
    s.send("devam")
    assert _wait(app, lambda: bool(_cards(s)))
    s.cancel_auto_resume()
    assert w.ctx.db.get_meta(resume.META_KEY) is None and not s._resume_timer.isActive()
    s.send("devam")                                                   # yeniden durur, yeni kart
    assert _wait(app, lambda: w.ctx.db.get_meta(resume.META_KEY) is not None and not s.running)
    w.ctx.settings.auto_resume = False                                # kullanıcı kendisi yazıyor → iptal
    quota[0] = Q(daily_remaining=10_000_000)
    s.send("ben devam ettiriyorum")
    assert _wait(app, lambda: not s.running and c.calls >= 1)
    assert w.ctx.db.get_meta(resume.META_KEY) is None


def test_429_hata_karti_yerine_kota_karti(win):
    app, w, tmp = win
    c = Client(raise_exc=ApiError(ErrorKind.RATE_LIMIT, "429 Too Many Requests", status=429,
                                  model="deepseek-v4.1-flash"))
    s = _setup(w, tmp, [Q(daily_remaining=10_000_000, ratio=0.99, reset_in=120)], c)
    w.ctx.settings.auto_resume = True
    w.ctx.settings.quota_guard_turns = False                          # kapı beklemesin: doğrudan 429 yolu
    s.send("devam")
    assert _wait(app, lambda: not s.running)
    assert _cards(s) and "429" in (resume.ResumePlan.from_json(w.ctx.db.get_meta(resume.META_KEY)).reason)


def test_uygulama_yeniden_acilinca_kart_ve_zamanlayici_geri_gelir(win):
    app, w, tmp = win
    s = _setup(w, tmp, [Q(daily_remaining=1, daily_reset_in=900)], Client())
    w.ctx.settings.auto_resume = True
    s.send("devam")
    assert _wait(app, lambda: bool(_cards(s)))
    sid = s.session_id
    w.close()
    from evren_studio.ui.main_window import MainWindow

    w2 = MainWindow()                                                 # aynı veri klasörü: yeni açılış
    w2.show()
    try:
        w2.ctx.settings.auto_resume = True
        assert _wait(app, lambda: bool(_cards(w2.session)))
        assert w2.session.session_id == sid and w2.session._resume_timer.isActive()
    finally:
        w2.close()
