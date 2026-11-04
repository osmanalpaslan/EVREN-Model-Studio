"""Madde 9 — sade "Sağlayıcı ekle": OpenAI uyumlu ağ geçitleri (OpenRouter, Kilo, özel sunucu). Ücretli istek
YAPILMAZ: istemci sahte HTTP ile sınanır (R-17). Auto Pro bu modelleri otomatik kullanmaz (tetiklenmeyen durum)."""
from __future__ import annotations

import json
import os
import time

import httpx
import pytest

from evren_studio import secrets
from evren_studio.api import providers
from evren_studio.api.client import ChatResult
from evren_studio.api.compat_client import CompatClient, join_model, split_model


def _client(base, seen):
    def handler(req: httpx.Request):
        seen.append((req.method, req.url.path, json.loads(req.content) if req.content else None,
                     req.headers.get("authorization")))
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "anthropic/claude-x"}, {"id": "openai/gpt-y"}]})
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "selam"},
                                                       "finish_reason": "stop"}], "usage": {}})
    return CompatClient(base, "sk-or-SAHTE1234567890", "gw-openrouter", transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("base,prefix", [("https://openrouter.ai/api/v1", "/api/v1"),
                                         ("https://api.kilo.ai/api/gateway", "/api/gateway")])
def test_istemci_yollari_ve_model_on_eki(base, prefix):
    seen: list = []
    c = _client(base, seen)
    ids = [m.id for m in c.list_models()]
    assert ids == ["gw-openrouter::anthropic/claude-x", "gw-openrouter::openai/gpt-y"]
    r = c.chat("gw-openrouter::anthropic/claude-x", [{"role": "user", "content": "x"}])
    assert r.content == "selam" and r.model == "gw-openrouter::anthropic/claude-x"
    assert seen[0][1] == f"{prefix}/models" and seen[1][1] == f"{prefix}/chat/completions"
    assert seen[1][2]["model"] == "anthropic/claude-x"                     # ön ek sunucuya gitmez
    assert seen[1][3] == "Bearer sk-or-SAHTE1234567890"


def test_kimlik_kayit_ve_saglayici_cozumu():
    assert split_model("gw-kilo::a/b") == ("gw-kilo", "a/b") and split_model("qwen") == ("", "qwen")
    assert join_model("gw-kilo", "a/b") == "gw-kilo::a/b"
    assert providers.gateway_id("openrouter", {"gw-openrouter"}) == "gw-openrouter-2"
    assert providers.provider_of_model("gw-kilo::a/b") == "gw-kilo"
    providers.register_gateway("gw-test", "openrouter")
    try:
        info = providers.PROVIDERS["gw-test"]
        assert info.paid and not info.verified and info.base_url.startswith("https://openrouter.ai")
        providers.unregister_gateways(set())
        assert "gw-test" not in providers.PROVIDERS and "openai" in providers.PROVIDERS   # yerleşikler kalır
    finally:
        providers.PROVIDERS.pop("gw-test", None)


def test_anahtar_adi_ve_gecersiz_kimlik(fake_keyring):
    secrets.save_api_key("sk-or-ABCDEF1234567890", "gw-openrouter")
    assert ("EVREN-Model-Studio", "gw-openrouter_api_key") in fake_keyring.store
    with pytest.raises(ValueError):
        secrets.save_api_key("x", "gw-../kotu")


# ---- AppContext + arayüz ----------------------------------------------------------------------------

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
    providers.unregister_gateways(set())


GW = {"id": "gw-openrouter", "kind": "openrouter", "name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1",
      "models": ["anthropic/claude-x"]}


def test_baglam_modelleri_anahtarla_gorunur_auto_pro_kullanmaz_ve_kalici(win, fake_keyring):
    app, w, tmp = win
    ctx = w.ctx
    ctx.settings.gateways = [dict(GW)]
    ctx.save_settings()
    mid = "gw-openrouter::anthropic/claude-x"
    assert mid not in {m.id for m in ctx.chat_models()}                     # anahtar yok → görünmez
    secrets.save_api_key("sk-or-ABCDEF1234567890", "gw-openrouter")
    ctx._provider_keys.clear()
    assert mid in {m.id for m in ctx.chat_models()} and ctx.provider_of(mid) == "gw-openrouter"
    assert mid not in ctx.available_model_ids()                             # Auto Pro sırasına girmez
    assert isinstance(ctx.make_client_for("gw-openrouter"), CompatClient)
    from evren_studio.ui.app_context import AppContext

    ctx2 = AppContext()                                                      # yeniden açılış (R-03)
    assert ctx2.gateways()[0]["models"] == ["anthropic/claude-x"] and "gw-openrouter" in providers.PROVIDERS


def test_ekle_penceresi_model_getir_kaydet_sil(win, fake_keyring, monkeypatch):
    app, w, tmp = win
    from PySide6.QtWidgets import QDialog, QMessageBox

    from evren_studio.ui import gateways_card

    monkeypatch.setattr(CompatClient, "list_models", lambda self: [
        type("M", (), {"id": join_model(self.provider_id, "anthropic/claude-x")})(),
        type("M", (), {"id": join_model(self.provider_id, "openai/gpt-y")})()])
    dlg = gateways_card.GatewayDialog(w.ctx)
    dlg.kind.setCurrentIndex(dlg.kind.findData("openrouter"))
    dlg.key.setText("sk-or-ABCDEF1234567890")
    dlg.fetch_models()
    end = time.monotonic() + 5
    while dlg.models.count() < 2 and time.monotonic() < end:
        app.processEvents()
    assert dlg.models.count() == 2
    dlg.save()
    assert dlg.result_gateway is None and "işaretleyin" in dlg.status.text()    # model seçilmeden kaydedilmez
    from PySide6.QtCore import Qt

    dlg.models.item(0).setCheckState(Qt.Checked)
    dlg.save()
    g = dlg.result_gateway
    assert g["id"] == "gw-openrouter" and g["models"] == ["anthropic/claude-x"]
    assert fake_keyring.store[("EVREN-Model-Studio", "gw-openrouter_api_key")] == "sk-or-ABCDEF1234567890"
    assert "sk-or-" not in json.dumps(g)                                     # anahtar ayara yazılmaz

    sec = w.pages["settings"].gateways
    def fake_exec(self):
        self.result_gateway = g
        return QDialog.Accepted
    monkeypatch.setattr(gateways_card.GatewayDialog, "exec", fake_exec)
    sec.edit(None)
    assert [x["id"] for x in w.ctx.gateways()] == ["gw-openrouter"]
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    sec.remove(w.ctx.gateways()[0])
    assert w.ctx.gateways() == [] and ("EVREN-Model-Studio", "gw-openrouter_api_key") not in fake_keyring.store


def test_tur_akisinda_ag_gecidi_modeline_istek_gider(win, fake_keyring, monkeypatch):
    app, w, tmp = win
    secrets.save_api_key("sk-or-ABCDEF1234567890", "gw-openrouter")
    w.ctx._provider_keys.clear()
    w.ctx.settings.gateways = [dict(GW)]
    w.ctx.save_settings()
    sent = []

    def fake_chat(self, model, messages, **kw):
        sent.append((self.provider_id, model))
        return ChatResult(content="tamam", finish_reason="stop", model=model)
    monkeypatch.setattr(CompatClient, "chat", fake_chat)
    s = w.session
    s.new_session()
    s.welcome._choose(None)
    s.set_model("gw-openrouter::anthropic/claude-x")
    s.send("merhaba")
    end = time.monotonic() + 6
    while (s.running or not sent) and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)
    assert sent and sent[0] == ("gw-openrouter", "gw-openrouter::anthropic/claude-x")
