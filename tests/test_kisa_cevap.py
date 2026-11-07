"""Sohbette kısa ve öz yanıt (Madde 17A, kullanıcı 2026-11-07: "hız konusunda takıntılarım var").

Ölçüm (CHALLENGE_RESULTS "auto ↔ Auto Pro"): EVREN ~15 token/sn yazar; aynı sorularda "kısa ve öz" talimatı çıktıyı
ortalama yarıya indirdi, cevaplar doğru kaldı. Varsayılan kısa; Ayarlar > Genel > Sohbet yanıtları: Ayrıntılı.
Tetiklenen/tetiklenmeyen (R-22) ve gerçek tur akışı (R-31: gönder → koşucu → istem).
"""
from __future__ import annotations

import time

import pytest

from evren_studio.agent import prompts
from evren_studio.agent.runner import AgentEvents, AgentRunner
from evren_studio.config import Settings
from tests.test_sohbet_web import Script, db, win  # noqa: F401 — ortak düzenek


def test_varsayilan_kisa_ve_oz_ayrintili_secilince_eski_bicim():
    kisa = prompts.build_chat_system()
    uzun = prompts.build_chat_system(brief=False)
    assert prompts.STYLE_BRIEF in kisa and prompts.STYLE_DETAILED not in kisa
    assert prompts.STYLE_DETAILED in uzun and prompts.STYLE_BRIEF not in uzun
    for s in (kisa, uzun):                                   # temel kurallar iki biçimde de korunur
        assert "Emin olmadığın bilgiyi kesinmiş gibi sunma" in s and "araçların YOK" in s
    assert "doğruluktan" in prompts.STYLE_BRIEF                # kısalık doğruluğu feda etmez
    assert Settings().answer_style == "kisa"


@pytest.mark.parametrize("brief", [True, False])
def test_kosucu_ayara_gore_istem(db, brief):  # noqa: F811
    sid = db.create_session("m", None)
    db.add_session_message(sid, "user", "soru")
    c = Script([])
    AgentRunner(c, "m", session_id=sid, store=db, events=AgentEvents(), workspace=None, mode="auto", stream=False,
                brief_answers=brief).run(db.get_session_messages(sid))
    assert (prompts.STYLE_BRIEF in c.systems[0]) is brief


def test_ajan_istemi_degismez(tmp_path, db):  # noqa: F811
    """Kısa cevap yalnız SOHBET içindir: ajanın kod/rapor özetini kısaltmaz."""
    from evren_studio.agent.tools import Workspace

    sid = db.create_session("m", str(tmp_path))
    db.add_session_message(sid, "user", "soru")
    c = Script([])
    AgentRunner(c, "m", session_id=sid, store=db, events=AgentEvents(), workspace=Workspace(tmp_path), mode="auto",
                stream=False, brief_answers=True).run(db.get_session_messages(sid))
    assert prompts.STYLE_BRIEF not in c.systems[0]


@pytest.mark.parametrize("stil,beklenen", [("kisa", True), ("ayrintili", False)])
def test_arayuzden_ayara_gore(win, stil, beklenen):  # noqa: F811
    app, w = win
    c = Script([])
    w.ctx.make_client = lambda log_sink=None: c
    w.ctx.make_client_for = lambda provider, log_sink=None: c
    w.ctx.settings.answer_style = stil
    s = w.session
    s.new_session()
    s.welcome._choose(None)
    s.composer.set_model("deepseek-v4.1-flash", emit=True)
    s.send("liste ile demet farkı nedir")
    end = time.monotonic() + 8
    while (s.running or not c.systems) and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)
    assert (prompts.STYLE_BRIEF in c.systems[0]) is beklenen


def test_ayarlar_ekraninda_kaydedilir_ve_okunur(win, monkeypatch):  # noqa: F811
    """R-03: kaydedilen ayar diskten yeniden okununca da aynı."""
    app, w = win
    from PySide6.QtWidgets import QMessageBox

    from evren_studio.config import ConfigStore

    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.Ok))

    page = w.pages["settings"]
    page.load_values()
    page.answer_style.setCurrentIndex(page.answer_style.findData("ayrintili"))
    page.save_all()
    assert ConfigStore(w.ctx.settings.resolved_data_dir()).load().answer_style == "ayrintili"
    page.load_values()
    assert page.answer_style.currentData() == "ayrintili"
