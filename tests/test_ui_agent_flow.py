"""Arayüz uçtan uca: oturum aç → ajan araç çağırır → onay kutusu → dosya değişir.

Gerçek API kullanılmaz; model istemcisi sahte yanıtlar döndürür. Bu test
arka plan iş parçacığı ↔ Qt sinyal köprüsünü ve onay akışını doğrular.
"""
from __future__ import annotations

import json
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from evren_studio.api.client import ChatResult  # noqa: E402


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None,
             on_reasoning=None, tools=None, **kw):
        r = self.responses.pop(0) if self.responses else ChatResult(content="(bitti)", finish_reason="stop")
        if on_reasoning:
            on_reasoning("düşünüyorum…")
        if on_delta and r.content:
            for part in r.content.split(" "):
                on_delta(part + " ", "")
        return r

    def close(self):
        pass


def wait_until(app, cond, timeout=8.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture()
def window(tmp_path, monkeypatch, fake_keyring):
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    yield app, w
    w.close()


def test_ajan_onayli_duzenleme_akisi(window, tmp_path):
    from evren_studio.ui.transcript import ApprovalWidget, ToolCallWidget

    app, w = window
    proj = tmp_path / "proje"
    proj.mkdir()
    (proj / "a.py").write_text("x = 1\n", encoding="utf-8")
    fake = FakeClient([
        ChatResult(content="Dosyayı düzenliyorum.", tool_calls=[{
            "id": "c1", "name": "edit_file",
            "arguments": json.dumps({"path": "a.py", "old_string": "x = 1", "new_string": "x = 2"})}]),
        ChatResult(content="Tamamlandı: **x artık 2**.", finish_reason="stop"),
    ])
    w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
    w.ctx.make_client = lambda log_sink=None: fake

    w.session.welcome._choose(str(proj))
    w.session.send("x'i 2 yap")
    assert w.session.session_id is not None
    assert wait_until(app, lambda: w.session.findChildren(ApprovalWidget)), "onay kutusu görünmeli"
    assert (proj / "a.py").read_text(encoding="utf-8") == "x = 1\n", "onaydan önce dosya değişmemeli"

    w.session.findChildren(ApprovalWidget)[0]._decide("allow")
    assert wait_until(app, lambda: not w.session.running), "tur bitmeli"
    assert (proj / "a.py").read_text(encoding="utf-8") == "x = 2\n"

    # Panel ve kayıtlar güncel
    assert len(w.panel.changes.rows) == 1
    msgs = w.ctx.db.get_session_messages(w.session.session_id)
    assert [m["role"] for m in msgs] == ["user", "assistant", "tool", "assistant"]
    cards = w.session.findChildren(ToolCallWidget)
    assert cards and "Düzenlendi" in cards[0].title.text()

    # Oturum yeniden açılınca geçmiş aynı biçimde çizilir
    sid = w.session.session_id
    w.session.new_session()
    w.session.open_session(sid)
    app.processEvents()
    assert any("Düzenlendi" in c.title.text() for c in w.session.findChildren(ToolCallWidget))

    # Değişikliği geri al
    row = w.panel.changes.rows[0]
    assert w.panel.changes._revert(row, ask_force=False)
    assert (proj / "a.py").read_text(encoding="utf-8") == "x = 1\n"


def test_sohbet_oturumu_ve_durdurma(window):
    app, w = window
    w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
    w.ctx.make_client = lambda log_sink=None: FakeClient([
        ChatResult(content="Merhaba, nasıl yardımcı olabilirim?", finish_reason="stop")])
    w.session.welcome._choose(None)
    w.session.send("selam")
    assert wait_until(app, lambda: not w.session.running)
    msgs = w.ctx.db.get_session_messages(w.session.session_id)
    assert msgs[-1]["content"].startswith("Merhaba")
    assert w.ctx.db.get_session(w.session.session_id)["workspace"] is None
    # Eğik çizgi komutu modeli çağırmadan çalışır
    w.session.send("/plan")
    assert w.session.mode == "plan"
