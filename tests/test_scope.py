"""Kapsam koruması: istem kuralı, kapsam denetimi (istenmemiş değişiklik), turu geri al,
"önce plan" akışı. Gerçek API yok; sahte istemci."""
from __future__ import annotations

import json
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from evren_studio.agent import scope  # noqa: E402
from evren_studio.agent.prompts import AGENT_RULES  # noqa: E402
from evren_studio.api.client import ChatResult  # noqa: E402

# ---- çekirdek ------------------------------------------------------------------------------


def test_istem_kapsam_kurali():
    assert "YALNIZCA kullanıcının açıkça istediği" in AGENT_RULES
    assert "Öneriler" in AGENT_RULES and "soru sor" in AGENT_RULES


def test_denetim_istegi_farklari_ve_baglami_icerir():
    msgs = scope.build_messages(
        ["uygulama simgesini ay-yıldız yap", "devam et"],
        [{"path": "ui/brand.py", "before_text": None, "after_text": "x = 1\n"},
         {"path": "ui/theme.py", "before_text": "a\n", "after_text": "b\n"},
         {"path": "ui/theme.py", "before_text": "b\n", "after_text": "c\n"}])
    user = msgs[1]["content"]
    assert "ay-yıldız" in user and "KULLANICININ İSTEĞİ:\ndevam et" in user
    assert "YENİ DOSYA: ui/brand.py" in user and "(2 dosya)" in user
    assert "-a" in user and "+c" in user, "aynı dosyada ilk önce → son sonra birleştirilir"


def test_yanit_ayristirma_yalniz_gercek_yollar():
    text = ('Sonuç: {"kapsam_disi": [{"dosya": "ui/theme.py", "neden": "tema istenmedi"}, '
            '{"dosya": "uydurma.py", "neden": "x"}]}')
    out = scope.parse_response(text, {"src/ui/theme.py", "src/ui/brand.py"})
    assert [(o.path, o.reason) for o in out] == [("src/ui/theme.py", "tema istenmedi")]
    assert scope.parse_response("bozuk", {"a"}) == []
    assert scope.parse_response('{"kapsam_disi": []}', {"a"}) == []


# ---- arayüz akışı --------------------------------------------------------------------------


class FakeClient:
    """Ajan yanıtları sırayla; kapsam denetimi isteği (SCOPE_SYSTEM) ayrıca yanıtlanır."""

    def __init__(self, responses, scope_reply='{"kapsam_disi": []}'):
        self.responses = list(responses)
        self.scope_reply = scope_reply
        self.tools_seen = []
        self.scope_calls = 0

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None,
             on_reasoning=None, tools=None, **kw):
        if messages and messages[0]["content"] == scope.SCOPE_SYSTEM:
            self.scope_calls += 1
            return ChatResult(content=self.scope_reply, finish_reason="stop")
        self.tools_seen.append([t["function"]["name"] for t in (tools or [])])
        return self.responses.pop(0) if self.responses else ChatResult(content="Bitti.", finish_reason="stop")

    def close(self):
        pass


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


def _edit(cid, path, old, new):
    return {"id": cid, "name": "edit_file",
            "arguments": json.dumps({"path": path, "old_string": old, "new_string": new})}


def _proj(tmp_path):
    proj = tmp_path / "proje"
    proj.mkdir()
    (proj / "simge.py").write_text("SIMGE = 'eski'\n", encoding="utf-8")
    (proj / "tema.py").write_text("RENK = 'mavi'\n", encoding="utf-8")
    return proj


def test_kapsam_disi_degisiklik_isaretlenir_ve_geri_alinir(window, tmp_path):
    from evren_studio.ui.transcript import ActionCard

    app, w = window
    proj = _proj(tmp_path)
    fake = FakeClient([
        ChatResult(tool_calls=[_edit("c1", "simge.py", "'eski'", "'ay-yıldız'"),
                               _edit("c2", "tema.py", "'mavi'", "'kırmızı'")]),
        ChatResult(content="Simgeyi değiştirdim, temayı da güzelleştirdim.", finish_reason="stop"),
    ], scope_reply='{"kapsam_disi": [{"dosya": "tema.py", "neden": "tema rengi istenmedi"}]}')
    w.ctx.make_client = lambda log_sink=None: fake
    w.session.welcome._choose(str(proj))
    w.session.set_mode("auto")
    w.session.send("uygulama simgesini ay-yıldız yap")
    assert wait_until(app, lambda: not w.session.running)
    # değişiklikler tura bağlı kaydedildi
    rows = w.ctx.db.list_file_changes(w.session.session_id)
    assert rows and all(r["turn_id"] == w.session._turn_id for r in rows)

    def card(prefix):
        return next((c for c in w.session.findChildren(ActionCard) if c.title.text().startswith(prefix)), None)

    assert wait_until(app, lambda: card("İstenmemiş olabilecek"))
    assert fake.scope_calls == 1
    summary = card("Bu tur 2 dosyayı")
    assert summary is not None
    warn = card("İstenmemiş olabilecek")
    assert "tema.py" in warn.body.text() and "tema rengi istenmedi" in warn.body.text()
    warn.buttons["Kapsam dışını geri al"].click()
    app.processEvents()
    assert (proj / "tema.py").read_text(encoding="utf-8") == "RENK = 'mavi'\n", "kapsam dışı geri alındı"
    assert "ay-yıldız" in (proj / "simge.py").read_text(encoding="utf-8"), "istenen değişiklik kaldı"


def test_turu_geri_al_ve_temiz_denetim(window, tmp_path):
    from evren_studio.ui.transcript import ActionCard

    app, w = window
    proj = _proj(tmp_path)
    fake = FakeClient([ChatResult(tool_calls=[_edit("c1", "simge.py", "'eski'", "'yeni'")]),
                       ChatResult(content="Tamam.", finish_reason="stop")])
    w.ctx.make_client = lambda log_sink=None: fake
    w.session.welcome._choose(str(proj))
    w.session.set_mode("auto")
    w.session.send("simgeyi değiştir")
    assert wait_until(app, lambda: not w.session.running)
    summary = None

    def find():
        nonlocal summary
        summary = next((c for c in w.session.findChildren(ActionCard)
                        if c.title.text().startswith("Bu tur 1")), None)
        return summary and "Kapsam denetimi" in summary.body.text()

    assert wait_until(app, find)
    assert "istenmemiş değişiklik görülmedi" in summary.body.text()
    summary.buttons["Turu geri al"].click()
    app.processEvents()
    assert (proj / "simge.py").read_text(encoding="utf-8") == "SIMGE = 'eski'\n"


def test_kapsam_denetimi_kapaliyken_cagrilmaz(window, tmp_path):
    from evren_studio.ui.transcript import ActionCard

    app, w = window
    proj = _proj(tmp_path)
    fake = FakeClient([ChatResult(tool_calls=[_edit("c1", "simge.py", "'eski'", "'yeni'")]),
                       ChatResult(content="Tamam.", finish_reason="stop")])
    w.ctx.make_client = lambda log_sink=None: fake
    w.ctx.settings.scope_check = False
    w.session.welcome._choose(str(proj))
    w.session.set_mode("auto")
    w.session.send("simgeyi değiştir")
    assert wait_until(app, lambda: not w.session.running)
    assert wait_until(app, lambda: any(c.title.text().startswith("Bu tur 1")
                                       for c in w.session.findChildren(ActionCard)))
    assert fake.scope_calls == 0


def test_once_plan_akisi(window, tmp_path):
    from evren_studio.ui.transcript import ActionCard

    app, w = window
    proj = _proj(tmp_path)
    fake = FakeClient([
        ChatResult(content="Plan: simge.py içinde SIMGE değerini değiştireceğim. Başka dosyaya dokunmayacağım.",
                   finish_reason="stop"),
        ChatResult(tool_calls=[_edit("c1", "simge.py", "'eski'", "'ay-yıldız'")]),
        ChatResult(content="Uygulandı.", finish_reason="stop"),
    ])
    w.ctx.make_client = lambda log_sink=None: fake
    w.ctx.settings.plan_first = True
    w.session.welcome._choose(str(proj))
    w.session.set_mode("auto")
    w.session.send("simgeyi ay-yıldız yap")
    assert wait_until(app, lambda: not w.session.running)
    assert "edit_file" not in fake.tools_seen[0] and "read_file" in fake.tools_seen[0], "plan turu salt okunur"
    assert (proj / "simge.py").read_text(encoding="utf-8") == "SIMGE = 'eski'\n"
    plan = next(c for c in w.session.findChildren(ActionCard) if c.title.text().startswith("Plan hazır"))
    plan.buttons["Uygula"].click()
    assert wait_until(app, lambda: "ay-yıldız" in (proj / "simge.py").read_text(encoding="utf-8")
                      and not w.session.running)
    assert "edit_file" in fake.tools_seen[1], "onaydan sonra seçili mod (Otomatik) geçerli"
