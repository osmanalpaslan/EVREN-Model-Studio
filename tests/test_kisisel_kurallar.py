"""Madde 22 F (2026-11-13): kişisel kurallar (Ayarlar → sabit sistem istemi, sohbette ve ajanda) + /hafiza-olustur
(kısa, doğrulanmış EVREN.md: ETH "Evaluating AGENTS.md" — klasör özeti ve uzun bağlam dosyası başarıyı düşürür).

R-03: ayar kaydediliyor VE uygulama onu gerçekten okuyup modele veriyor (gerçek send → koşucu yolu).
"""
from __future__ import annotations

from test_f4_skill_profil import _wait, win  # noqa: F401  (pytest fikstürü)

from evren_studio.agent import prompts
from evren_studio.api.client import ChatResult
from evren_studio.config import PERSONAL_RULES_MAX, ConfigStore


def _yakala(ctx):
    systems: list[str] = []
    users: list[str] = []

    class C:
        def chat(self, model, messages, **kw):
            systems.append(messages[0]["content"])
            users.append(str(messages[-1]["content"]))
            return ChatResult(content="tamam", finish_reason="stop")

        def close(self):
            pass
    ctx.make_client = lambda log_sink=None: C()
    ctx.make_client_for = lambda provider, log_sink=None: C()
    return systems, users


def test_kisisel_kurallar_ajanda_ve_sohbette_sistem_isteminde(win, tmp_path):
    app, w = win
    w.ctx.settings.personal_rules = "Her yanıtı KURAL-777 ile bitir."
    systems, _u = _yakala(w.ctx)
    s = w.session
    s.new_session()                                             # klasörsüz: sohbet
    s.composer.set_model("deepseek-v4.1-flash", emit=True)
    s.send("merhaba")
    assert _wait(app, lambda: not s.running and systems)
    assert "kişisel kuralları" in systems[0] and "KURAL-777" in systems[0], "sohbette (B bölmesinde düşmüştü)"
    proj = tmp_path / "proje"
    proj.mkdir()
    systems.clear()
    s.new_session()
    s.welcome._choose(str(proj))                                # klasörlü: ajan
    s.composer.set_model("deepseek-v4.1-flash", emit=True)
    s.send("dosyaları listele")
    assert _wait(app, lambda: not s.running and systems)
    assert "KURAL-777" in systems[0]
    w.ctx.settings.personal_rules = ""
    systems.clear()
    s.send("tekrar")
    assert _wait(app, lambda: not s.running and systems)
    assert "kişisel kuralları" not in systems[0]               # boşsa başlık da yok (R-22)


def test_ayarlar_sayfasi_kaydeder_sinirlar_ve_acilista_okunur(win, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)   # "Kaydedildi" penceresi
    app, w = win
    page = w.pages["settings"]
    page.load_values()
    page.personal_rules.setPlainText("  Türkçe yaz.\nKısa ol.  " + "x" * (PERSONAL_RULES_MAX + 50))
    page.save_all()
    s = w.ctx.settings
    assert s.personal_rules.startswith("Türkçe yaz.\nKısa ol.") and len(s.personal_rules) == PERSONAL_RULES_MAX
    yeniden = ConfigStore(w.ctx.store.data_dir).load()           # açılışta diskten okunur
    assert yeniden.personal_rules == s.personal_rules
    page.load_values()
    assert page.personal_rules.toPlainText() == s.personal_rules


def test_hafiza_olustur_kisa_dogrulanmis_hafiza_ister(win, tmp_path):
    app, w = win
    _systems, users = _yakala(w.ctx)
    s = w.session
    proj = tmp_path / "proje"
    proj.mkdir()
    s.new_session()
    s.welcome._choose(str(proj))
    s.composer.set_model("deepseek-v4.1-flash", emit=True)
    s.send("/hafiza-olustur")
    assert _wait(app, lambda: not s.running and users)
    assert prompts.INIT_PROMPT.split("\n")[0] in users[0]
    p = prompts.INIT_PROMPT
    assert "EN ÇOK 40 satır" in p and "klasör/dosya listesi" in p and "doğrula" in p and "silme" in p
