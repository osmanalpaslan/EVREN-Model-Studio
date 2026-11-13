"""Madde 23 c — EVREN dışındaki API'de de otomatik işleyiş.

Kullanıcı 2026-11-13: "her zaman evren apisi de kullanılmayabilir. farklı bir api kullanıldığında oluşturduğun
agentları/bekçileri kısaca bütün otomatik işleyişi mevcut apinin agentları yapabilmeli."

Kural: EVREN anahtarı varken otomatik işler (Derin, QA, paralel görev, MCP/test araçları) yalnız EVREN ile (eski karar:
ücretli sağlayıcıya otomatik iş yok). EVREN yoksa kullanıcının API'si; ücretli ise maliyet kaydı + aylık bütçe durdurması
arayüzsüz alt ajanlarda da işler.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from evren_studio import secrets
from evren_studio.agent import deep
from evren_studio.api import providers
from evren_studio.api.client import ChatResult
from test_agent_runner import FakeClient

GW = {"id": "gw-yerel", "kind": "ollama", "name": "Yerel", "base_url": "http://127.0.0.1:11434/v1",
      "models": ["qwen-yerel", "llama-yerel"]}


@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.ctx._cached_key = None
    yield app, w, tmp_path
    w.close()
    providers.unregister_gateways(set())


def _evren(ctx, on: bool):
    ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456" if on else None
    ctx.api_key = (lambda refresh=False: "evren_llm_SAHTE_ANAHTAR_123456") if on else (lambda refresh=False: None)


def _openai(ctx):
    secrets.save_api_key("sk-SAHTE-OPENAI-1234567890", "openai")
    ctx._provider_keys.clear()


def _paid_model(ctx, provider="openai"):
    return next(m.id for m in ctx.paid_models if m.provider == provider)


def test_otomatik_isler_kurali_varsa_yoksa_kullanicinin_api_si(win):
    _app, w, _ = win
    ctx = w.ctx
    _evren(ctx, False)
    assert ctx.auto_providers() == {"evren"} and not ctx.available_providers()   # hiç anahtar yok → EVREN varsayılır
    _openai(ctx)
    w.session.model = _paid_model(ctx)
    assert ctx.current_model == w.session.model                       # oturum motoru bağlama yansır
    assert ctx.auto_providers() == {"openai"} and ctx.auto_label() == "OpenAI"
    _evren(ctx, True)
    assert ctx.auto_providers() == {"evren"}                          # EVREN varken eski karar: yalnız EVREN


def test_ic_ve_otomatik_is_kendi_api_siyle_maliyet_kaydedilir(win):
    _app, w, _ = win
    ctx = w.ctx
    _evren(ctx, False)
    _openai(ctx)
    w.session.model = _paid_model(ctx)
    used = []

    class C:
        def chat(self, model, messages, **kw):
            used.append(model)
            return ChatResult(content='{"durum": "iyi"}', usage={"prompt_tokens": 100, "completion_tokens": 20})

        def close(self):
            pass
    ctx.make_client_for = lambda provider, log_sink=None: C()
    text, model = ctx.ai_chat("elestirmen", [{"role": "user", "content": "x"}], evren_only=True)
    assert ctx.provider_of(model) == "openai" and used == [model]   # eskiden: "yalnız EVREN" hatası
    rows = ctx.db._exec("SELECT model FROM usage_costs").fetchall()
    assert [r[0] for r in rows] == [model]                             # ücretli kullanım kaydedildi (bütçe)


def test_evrenli_otomatik_is_ucretliye_gitmez(win):
    _app, w, _ = win
    ctx = w.ctx
    _evren(ctx, True)
    _openai(ctx)
    w.session.model = _paid_model(ctx)                                # oturum ücretli modelde olsa bile
    r = ctx.ai_route("qa", evren_only=True)
    assert all(ctx.provider_of(m) == "evren" for m in [r.model, *r.fallbacks] if m)
    from evren_studio.agent import mcp

    ctx.settings.mcp_servers = [mcp.playwright_config().to_dict()]
    ctx.settings.auto_test_tools = True
    assert ctx.mcp_toolset(Path("."), "", "evren") is not None        # yapılandırma gerçekten var
    assert ctx.test_tools(Path("."), "", "openai") is None and ctx.mcp_toolset(Path("."), "", "openai") is None
    _evren(ctx, False)                                                # EVREN yokken kullanıcının API'sinde açılır
    assert ctx.mcp_toolset(Path("."), "", "openai") is not None


def test_test_araclari_ve_derin_qa_evren_yokken_acilir(win):
    _app, w, tmp = win
    ctx = w.ctx
    _evren(ctx, False)
    _openai(ctx)
    w.session.model = _paid_model(ctx)
    ctx.settings.auto_test_tools = True
    assert ctx.test_tools(tmp, "", "openai") is not None
    proj = tmp / "proje"
    proj.mkdir()
    w.session.welcome._choose(str(proj))
    assert w.session.deep.unavailable_reason() == ""                  # eskiden "yalnız EVREN"
    assert "EVREN" not in (w.session.qa.precheck("web") or "")
    assert w.session.deep._evren_chain("plan") and all(
        ctx.provider_of(m) == "openai" for m in w.session.deep._evren_chain("plan"))
    _evren(ctx, False)
    ctx._provider_keys.clear()
    secrets.delete_api_key("openai")
    ctx._provider_keys["openai"] = None
    assert "API anahtarı gerekli" in w.session.deep.unavailable_reason()


def test_yalniz_yerel_sunucu_ile_ic_isler_ve_yedek(win):
    _app, w, _ = win
    ctx = w.ctx
    _evren(ctx, False)
    ctx.settings.gateways = [dict(GW)]
    ctx.sync_gateways()
    ids = {m.id for m in ctx.gateway_models}
    pick = next(i for i in ids if i.endswith("qwen-yerel"))        # alfabetik sırada SONDA: tercih sınansın
    w.session.model = pick
    assert ids <= ctx.available_model_ids()                           # eskiden boş → "API anahtarı yok"
    r = ctx.ai_route("baslik")
    assert r.model == pick and r.fallbacks                            # seçilen önce, diğeri yedek
    assert ctx.headless_billing(pick) == (None, None)                 # yerel sunucu ücretsiz: maliyet yok
    _openai(ctx)                                                      # iki API varken: otomatik iş SEÇİLİ olanda
    assert ctx.auto_providers() == {"gw-yerel"}
    w.session.model = _paid_model(ctx)
    assert ctx.auto_providers() == {"openai"}


def test_evren_yokken_kota_sorgusu_yapilmaz(win, monkeypatch):
    _app, w, _ = win
    ctx = w.ctx
    _evren(ctx, False)
    _openai(ctx)
    w.session.model = _paid_model(ctx)

    def no_evren():
        raise AssertionError("EVREN istemcisi açılmamalı")
    monkeypatch.setattr(ctx, "make_client", no_evren)
    assert w.session.deep._quota() is None and w.session.project._fetch_quota() is None


def test_evrenli_ag_gecidi_siraya_girmez(win):
    _app, w, _ = win
    ctx = w.ctx
    _evren(ctx, True)
    ctx.settings.gateways = [dict(GW)]
    ctx.sync_gateways()
    assert not ({m.id for m in ctx.gateway_models} & ctx.available_model_ids())


def test_ucretli_alt_ajan_maliyeti_kaydeder_butce_dolunca_durur(win, tmp_path):
    _app, w, _ = win
    ctx = w.ctx
    _openai(ctx)
    m = _paid_model(ctx)
    sink, stop = ctx.headless_billing(m, None)
    assert sink is not None and stop is not None and ctx.headless_billing("glm-5.3") == (None, None)
    root = tmp_path / "p"
    root.mkdir()
    client = FakeClient([ChatResult(content="<sonuc>{}</sonuc>", finish_reason="stop",
                                    usage={"prompt_tokens": 1000, "completion_tokens": 50})])
    res = deep.run_subagent(client=client, model=m, fallbacks=[], root=root, prompt="incele", marker="<sonuc>",
                            cost_sink=sink, budget_stop=lambda: False)
    assert res.stopped == "done"
    assert [r[0] for r in ctx.db._exec("SELECT model FROM usage_costs").fetchall()] == [m]
    client2 = FakeClient([ChatResult(content="x", finish_reason="stop")])
    res2 = deep.run_subagent(client=client2, model=m, fallbacks=[], root=root, prompt="incele", marker="",
                             cost_sink=sink, budget_stop=lambda: True)
    assert res2.stopped == "budget" and client2.calls == []           # bütçe doldu: hiç çağrı yapılmadı


def test_paralel_gorev_zinciri_kullanicinin_api_si(win):
    _app, w, tmp = win
    ctx = w.ctx
    _evren(ctx, False)
    _openai(ctx)
    w.session.model = _paid_model(ctx)
    proj = tmp / "proje2"
    proj.mkdir()
    w.session.welcome._choose(str(proj))
    chain = w.session.project._free_chain()
    assert chain and all(ctx.provider_of(m) == "openai" for m in chain)
    _evren(ctx, True)
    assert all(ctx.provider_of(m) == "evren" for m in w.session.project._free_chain())
