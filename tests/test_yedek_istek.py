"""Madde 22 E2 (2026-11-13): kısa iç isteklerde yedek istek (hedging).

Ölçüm: aynı kısa istek çoğunlukla 1,5-4 sn, arada 50-53 sn takılıyor (EVREN). İlk EVREN modeli HEDGE_AFTER_S içinde
yanıtlamazsa sıradaki EVREN modeline paralel istek; önce gelen başarılı yanıt alınır. Tetiklenmeyen durumlar (R-22): ilk
model zamanında yanıtlıyor (ikinci istek YOK), ücretli sağlayıcı (asla), kota/anahtar hatası (hemen yükselir).
"""
from __future__ import annotations

import threading
import time

import pytest

from evren_studio.api.client import ChatResult
from evren_studio.api.errors import ApiError, ErrorKind
from evren_studio.ui import app_context as ac


class Route:
    def __init__(self, chain):
        self.model, self.fallbacks = chain[0], chain[1:]


class Ctx:
    """AppContext'in ai_chat'i için gereken en küçük yüzey (gerçek yöntemler bağlanır)."""

    _ai_attempt = ac.AppContext._ai_attempt
    _ai_chat_hedged = ac.AppContext._ai_chat_hedged
    ai_chat = ac.AppContext.ai_chat

    def __init__(self, chain, behave, providers=None):
        self.chain, self.behave, self.calls, self.events = chain, behave, [], []
        self.providers = providers or {}
        self.lock = threading.Lock()

    def ai_route(self, role):
        return Route(self.chain)

    def provider_of(self, model):
        return self.providers.get(model, "evren")

    def model_info(self, model):
        return None

    def record_model_call(self, rec):
        self.events.append(rec)

    def make_client_for(self, provider):
        ctx = self

        class C:
            def chat(self, model, messages, **kw):
                with ctx.lock:
                    ctx.calls.append(model)
                gecikme, sonuc = ctx.behave[model]
                time.sleep(gecikme)
                if isinstance(sonuc, Exception):
                    raise sonuc
                return ChatResult(content=sonuc)

            def close(self):
                pass
        return C()


@pytest.fixture(autouse=True)
def kisa_esik(monkeypatch):
    monkeypatch.setattr(ac, "HEDGE_AFTER_S", 0.15)


def test_ilk_model_zamaninda_yanitlarsa_yedek_istek_yok():
    c = Ctx(["a", "b"], {"a": (0.01, "A"), "b": (0.01, "B")})
    assert c.ai_chat("inceleme", [{"role": "user", "content": "x"}]) == ("A", "a")
    time.sleep(0.2)
    assert c.calls == ["a"] and c.events == []


def test_takilan_ilk_model_yerine_yedek_yanit_doner():
    c = Ctx(["a", "b"], {"a": (1.0, "A"), "b": (0.02, "B")})
    t0 = time.monotonic()
    assert c.ai_chat("inceleme", [{"role": "user", "content": "x"}]) == ("B", "b")
    assert time.monotonic() - t0 < 0.6 and c.calls == ["a", "b"]
    assert c.events and c.events[0]["event"] == "hedge"


def test_yedek_de_yavassa_once_biten_kazanir():
    c = Ctx(["a", "b"], {"a": (0.3, "A"), "b": (1.0, "B")})
    assert c.ai_chat("inceleme", [{"role": "user", "content": "x"}]) == ("A", "a")


def test_hizli_basarisizlikta_sira_ve_kalan_zincir():
    hata = ApiError(ErrorKind.SERVER_UNAVAILABLE, "503")
    c = Ctx(["a", "b", "c"], {"a": (0.0, hata), "b": (0.0, ""), "c": (0.0, "C")})
    assert c.ai_chat("inceleme", [{"role": "user", "content": "x"}]) == ("C", "c")       # a hata, b boş → c
    assert c.calls == ["a", "b", "c"] and not c.events                                 # hedge olayı yok


def test_kota_hatasi_hemen_yukselir_yedege_gecmez():
    kota = ApiError(ErrorKind.RATE_LIMIT, "429")
    c = Ctx(["a", "b", "c"], {"a": (0.0, kota), "b": (0.0, "B"), "c": (0.0, "C")})
    with pytest.raises(ApiError):
        c.ai_chat("inceleme", [{"role": "user", "content": "x"}])
    assert c.calls == ["a"], "kota hatası zincirin geri kalanına da geçmez"


def test_ucretli_saglayicida_yedek_istek_yok(monkeypatch):
    c = Ctx(["a", "p"], {"a": (0.4, "A"), "p": (0.0, "P")}, providers={"p": "openai"})
    assert c.ai_chat("inceleme", [{"role": "user", "content": "x"}]) == ("A", "a")
    assert c.calls == ["a"] and not c.events


def test_esik_sifirsa_kapali(monkeypatch):
    monkeypatch.setattr(ac, "HEDGE_AFTER_S", 0)
    c = Ctx(["a", "b"], {"a": (0.3, "A"), "b": (0.0, "B")})
    assert c.ai_chat("inceleme", [{"role": "user", "content": "x"}]) == ("A", "a") and c.calls == ["a"]
