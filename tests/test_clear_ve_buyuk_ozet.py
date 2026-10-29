"""/clear (temiz sayfa) ve çok büyük oturumun özetlenebilmesi.

2026-10-29: 1.357 mesajlık (~1M token) oturumda /compact çalışmadı (özet isteği de sığmadı),
otomatik özet başarısız olunca mesaj yine gönderildi ve EVREN 4 kez reddetti.
"""
from __future__ import annotations

import json
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from evren_studio.agent import compaction as c  # noqa: E402
from evren_studio.api.client import ChatResult  # noqa: E402


def _dev_gecmis(n_tur: int = 400) -> list[dict]:
    """Proje ajanı benzeri dev geçmiş: uzun görev mesajları, dosya yazan araç çağrıları, uzun çıktılar."""
    h = [{"id": 1, "role": "user", "content": "HEDEF: GT-R sürüş oyunu yap. " + "ayrıntı " * 3000}]
    i = 2
    for k in range(n_tur):
        args = json.dumps({"path": f"scripts/s{k}.gd", "content": "var x = 1\n" * 900})
        h.append({"id": i, "role": "assistant", "content": f"Görev {k} için dosya yazıyorum.",
                  "tool_calls": [{"id": f"c{k}", "name": "write_file", "arguments": args}]})
        h.append({"id": i + 1, "role": "tool", "tool_call_id": f"c{k}", "name": "write_file",
                  "content": "çıktı satırı\n" * 1500})
        i += 2
    h.append({"id": i, "role": "user", "content": "oyunu hangi dosya adresine exe olarak oluşturdun?"})
    return h


@pytest.mark.parametrize("ctx", [1_048_576, 262_144, None])
def test_dev_gecmis_ozet_istegi_butceye_kesin_sigar(ctx):
    h = _dev_gecmis()
    assert c._conservative_tokens(c.to_api_messages("", h, "text", images=False)) > 1_000_000
    req = c.build_summary_request(h, None, ctx)
    assert c._conservative_tokens(req) <= c.summary_budget(ctx) * 1.05
    text = "\n".join(m["content"] for m in req)
    assert "HEDEF: GT-R" in text, "ilk hedef mesajı korunur"
    assert "exe olarak oluşturdun" in text, "son soru korunur"


def test_kucuk_gecmis_degismez():
    h = [{"id": 1, "role": "user", "content": "selam"}, {"id": 2, "role": "assistant", "content": "merhaba"}]
    assert [m["content"] for m in c.fit_for_summary(h, 262_144)] == ["selam", "merhaba"]


def test_arac_parametresi_gecerli_json_kalir():
    raw = json.dumps({"path": "a.py", "content": "x" * 5000})
    out = json.loads(c._shrink_args(raw))
    assert out["path"] == "a.py" and len(out["content"]) < 600 and "kısaltıldı" in out["content"]


def test_onceki_ozetten_sonrasi_sigdirilir():
    h = [{"id": 1, "role": "user", "content": "eski"}, {"id": 2, "role": "summary", "content": "ÖZET"}]
    h += _dev_gecmis(200)
    out = c.fit_for_summary(h, 262_144)
    assert out[0]["content"] == "eski" and out[1]["role"] == "summary"


# ---- arayüz: /clear ve özet başarısızken gönderme koruması -----------------------------------


def wait_until(app, cond, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


@pytest.fixture()
def window(tmp_path, monkeypatch, fake_keyring):
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
    yield app, w
    w.close()


def test_clear_ayni_klasor_model_modla_temiz_sayfa(window, tmp_path):
    app, w = window
    proj = tmp_path / "proje"
    proj.mkdir()
    sv = w.session
    sv.welcome._choose(str(proj))
    sid = sv._ensure_session("eski konuşma")
    sv.ctx.db.add_session_message(sid, "user", "eski mesaj")
    sv.set_mode("auto")
    sv.composer.set_mode("auto")
    model = sv.model
    sv.send("/clear")
    app.processEvents()
    assert sv.session_id is None, "yeni (henüz boş) oturum"
    assert sv.welcome.workspace and os.path.samefile(sv.welcome.workspace, proj)
    assert sv.mode == "auto" and sv.model == model
    assert sv.ctx.db.get_session(sid) is not None, "eski oturum silinmez"
    assert [m["content"] for m in sv.ctx.db.get_session_messages(sid)] == ["eski mesaj"]


def test_ozet_basarisiz_ve_gecmis_sigmiyorsa_mesaj_gonderilmez(window, tmp_path, monkeypatch):
    """R-31: send → otomatik özet (başarısız) → koruma yolu."""
    from evren_studio.ui.transcript import ActionCard

    app, w = window
    sv = w.session
    sent = []

    class Fake:
        def chat(self, model, messages, **kw):
            if messages and messages[0]["content"] == c.SUMMARY_SYSTEM:
                return ChatResult(content="", finish_reason="stop")      # özet boş → başarısız
            sent.append(messages)
            return ChatResult(content="cevap", finish_reason="stop")

        def close(self):
            pass

    w.ctx.make_client = lambda log_sink=None: Fake()
    sid = sv._ensure_session("büyük")
    for m in _dev_gecmis(60):
        if m["role"] == "tool":
            sv.ctx.db.add_session_message(sid, "tool", m["content"], tool_call_id=m["tool_call_id"], name=m["name"])
        else:
            sv.ctx.db.add_session_message(sid, m["role"], m["content"], tool_calls=m.get("tool_calls"))
    monkeypatch.setattr(sv, "_context_tokens", lambda: 32_000)          # küçük pencereli model
    sv.send("oyun nerede?")
    assert wait_until(app, lambda: any(a.title.text().startswith("Konuşma modelin sınırını aşıyor")
                                       for a in sv.findChildren(ActionCard)))
    assert not sent, "sığmayan geçmiş modele gönderilmemeli"
    assert "oyun nerede?" in sv.composer.edit.toPlainText(), "yazılan mesaj kaybolmaz"
    card = next(a for a in sv.findChildren(ActionCard) if a.title.text().startswith("Konuşma modelin"))
    card.buttons["Temiz sayfa aç (/clear)"].click()
    app.processEvents()
    assert sv.session_id is None
