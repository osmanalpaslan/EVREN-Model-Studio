"""API istemcisi testleri (sahte taşımalarla — gerçek ağ kullanılmaz)."""
from __future__ import annotations

import json

import httpx
import pytest

from evren_studio.api.client import CancelToken, EvrenClient
from evren_studio.api.errors import ApiError, ErrorKind

BASE = "https://test.example/v1"
KEY = "evren_llm_TESTKEY"


def make_client(handler, **kw) -> EvrenClient:
    transport = httpx.MockTransport(handler)
    return EvrenClient(BASE, KEY, transport=transport, **kw)


# ---- model listesi --------------------------------------------------------


def test_model_listesi():
    payload = {
        "object": "list",
        "data": [{
            "id": "glm-5.3", "created": 1, "task": "chat",
            "modalities": ["text"], "context_length": 524288,
            "default_max_output_tokens": None,
            "capabilities": {"tools": True, "vision": False,
                             "response_format": True},
            "pricing": {"prompt_token_price": 0.0,
                        "completion_token_price": 0.0,
                        "free_until": "2026-11-01"},
        }, {
            "id": "dots-ocr", "created": 1, "task": "ocr",
            "modalities": ["image", "text"], "context_length": 131072,
            "default_max_output_tokens": None, "capabilities": {},
            "pricing": None,
        }],
    }

    def handler(request):
        assert request.url.path == "/v1/models"
        assert request.headers["Authorization"] == f"Bearer {KEY}"
        return httpx.Response(200, json=payload)

    models = make_client(handler).list_models()
    assert len(models) == 2
    m = models[0]
    assert m.id == "glm-5.3"
    assert m.supports_chat and m.supports_tools and not m.supports_vision
    assert m.free_until == "2026-11-01"
    o = models[1]
    assert not o.supports_chat, "OCR modeli sohbet listesinde OLMAMALI"
    assert o.supports_vision, "image modalitesi görsel girdi demektir"


def test_yeteneği_doğrulanmamış_model():
    """Görsel yeteneği bildirilmemiş model vision desteklemez."""
    from evren_studio.api.client import ModelInfo

    m = ModelInfo(id="x", task="chat", modalities=["text"],
                  context_length=100, default_max_output_tokens=None,
                  capabilities={})
    assert not m.supports_tools
    assert not m.supports_vision


# ---- sohbet -----------------------------------------------------------------


def test_sohbet_basarili():
    payload = {
        "id": "req-1", "object": "chat.completion", "created": 1,
        "model": "zai/glm-5.3-fp8",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": "Merhaba!"}}],
        "usage": {"evren": {"routed_model": "zai/glm-5.3-fp8"}},
    }

    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "glm-5.3"
        return httpx.Response(200, json=payload)

    res = make_client(handler).chat(
        "glm-5.3", [{"role": "user", "content": "selam"}]
    )
    assert res.content == "Merhaba!"
    assert res.finish_reason == "stop"
    assert res.routed_model == "zai/glm-5.3-fp8"


def test_sohbet_akiszli_sse():
    chunks = [
        b'data: {"id":"c1","choices":[{"index":0,"delta":{"role":"assistant","content":""}}]}\n\n',
        b'data: {"id":"c1","choices":[{"index":0,"delta":{"reasoning":"dusunuyorum"}}]}\n\n',
        b'data: {"id":"c1","choices":[{"index":0,"delta":{"content":"Mer"}}]}\n\n',
        b'data: {"id":"c1","choices":[{"index":0,"delta":{"content":"haba"}}]}\n\n',
        b'data: {"id":"c1","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n',
        b"data: [DONE]\n\n",
    ]

    def handler(request):
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"},
            content=iter(chunks),
        )

    got: list[str] = []
    reasoning: list[str] = []
    res = make_client(handler).chat(
        "glm-5.3", [{"role": "user", "content": "x"}], stream=True,
        on_delta=lambda c, f: got.append(c),
        on_reasoning=lambda r: reasoning.append(r),
    )
    assert res.content == "Merhaba"
    assert res.reasoning == "dusunuyorum"
    assert got == ["Mer", "haba"]
    assert reasoning == ["dusunuyorum"]
    assert res.finish_reason == "stop"


# ---- iptal ---------------------------------------------------------------------


def test_gonderim_oncesi_iptal():
    def handler(request):  # pragma: no cover - çağrılmamalı
        raise AssertionError("İptal sonrası istek GITMEMELİ")

    cancel = CancelToken()
    cancel.cancel()
    res = make_client(handler).chat(
        "glm-5.3", [{"role": "user", "content": "x"}], cancel=cancel
    )
    assert res.finish_reason == "cancelled_by_user"
    assert res.content == ""


def test_akis_sirasinda_iptal():
    import itertools
    import time

    def chunk_gen():
        for i in itertools.count():
            yield (
                f'data: {{"id":"c1","choices":[{{"index":0,'
                f'"delta":{{"content":"par{i}"}}}}]}}\n\n'
            ).encode()
            time.sleep(0.01)

    def handler(request):
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"},
            content=chunk_gen(),
        )

    cancel = CancelToken()

    def on_delta(c, f):
        if c == "par2":
            cancel.cancel()

    res = make_client(handler).chat(
        "glm-5.3", [{"role": "user", "content": "x"}], stream=True,
        cancel=cancel, on_delta=on_delta,
    )
    assert res.finish_reason == "cancelled_by_user"
    assert res.content.startswith("par")


# ---- hata kodları ----------------------------------------------------------------


@pytest.mark.parametrize("status,kind", [
    (401, ErrorKind.AUTH),
    (403, ErrorKind.AUTH),
    (429, ErrorKind.RATE_LIMIT),
    (503, ErrorKind.SERVER_UNAVAILABLE),
    (504, ErrorKind.SERVER_ERROR),
    (404, ErrorKind.NOT_FOUND),
    (413, ErrorKind.REQUEST_TOO_LARGE),
    (422, ErrorKind.VALIDATION),
])
def test_hata_siniflandirma(status, kind):
    def handler(request):
        return httpx.Response(status, json={"detail": "test hatası"})

    with pytest.raises(ApiError) as ei:
        make_client(handler, max_retries=0).list_models()
    assert ei.value.kind == kind
    assert ei.value.status == status


def test_hata_mesajinda_anahtar_maskelenir():
    def handler(request):
        return httpx.Response(401, json={"detail": f"invalid key {KEY}"})

    with pytest.raises(ApiError) as ei:
        make_client(handler).list_models()
    assert KEY not in ei.value.message
    assert "***MASKED***" in ei.value.message


# ---- Retry-After ve tekrar politikası ------------------------------------------------


def test_503_retry_after_ile_yeniden_dener():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(
                503, json={"detail": "sağlıklı endpoint yok"},
                headers={"Retry-After": "0"},
            )
        return httpx.Response(200, json={"object": "list", "data": []})

    models = make_client(handler, max_retries=3).list_models()
    assert models == []
    assert calls["n"] == 3, "İki başarısız denemeden sonra üçüncüsü başarılı olmalı"


def test_503_tekrar_limiti_asilinca_hata_verir():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(
            503, json={"detail": "sağlıklı endpoint yok"},
            headers={"Retry-After": "0"},
        )

    with pytest.raises(ApiError) as ei:
        make_client(handler, max_retries=3).list_models()
    assert ei.value.kind == ErrorKind.SERVER_UNAVAILABLE
    assert calls["n"] == 4, "1 asıl deneme + en fazla 3 otomatik tekrar"


def test_uzun_retry_after_kullanicuya_birakilir():
    def handler(request):
        return httpx.Response(429, json={"detail": "limit"},
                              headers={"Retry-After": "3600"})

    with pytest.raises(ApiError) as ei:
        make_client(handler, max_retries=3).list_models()
    assert ei.value.kind == ErrorKind.RATE_LIMIT
    assert "3600" in ei.value.message


def test_401_tekrar_denemez():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401, json={"detail": "yetkisiz"})

    with pytest.raises(ApiError):
        make_client(handler, max_retries=3).list_models()
    assert calls["n"] == 1, "Kimlik hataları TEKRAR DENENMEMELİ"


# ---- belirsiz sonuç -------------------------------------------------------------------


def test_zaman_asimi_belirsiz_sonuç_tekrarsız():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        raise httpx.ReadTimeout("okuma zaman aşımı")

    with pytest.raises(ApiError) as ei:
        make_client(handler, max_retries=3).list_models()
    assert ei.value.kind == ErrorKind.UNKNOWN_RESULT
    assert calls["n"] == 1, "Sonucu belirsiz istek otomatik TEKRAR GÖNDERİLMEZ"


def test_akis_kopmasi_belirsiz_sonuç():
    def handler(request):
        def gen():
            yield b'data: {"id":"c1","choices":[{"index":0,"delta":{"content":"kismi"}}]}\n\n'
            raise httpx.ReadTimeout("akış koptu")

        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=gen()
        )

    with pytest.raises(ApiError) as ei:
        make_client(handler).chat(
            "glm-5.3", [{"role": "user", "content": "x"}], stream=True
        )
    assert ei.value.kind == ErrorKind.UNKNOWN_RESULT


def test_istek_durumu_sorgusu():
    def handler(request):
        if request.url.path.startswith("/v1/requests/"):
            return httpx.Response(200, json={
                "request_id": "r-1", "execution_terminal": "success",
                "charge_terminal": True,
            })
        raise AssertionError("beklenmeyen istek")

    client = make_client(handler)
    status = client.resolve_unknown_request("r-1")
    assert status["execution_terminal"] == "success"


def test_istek_durumu_bulunamazsa_belirsiz():
    def handler(request):
        return httpx.Response(404, json={"detail": "yok"})

    status = make_client(handler).resolve_unknown_request("yok-olan")
    assert status["execution_terminal"] == "unknown"


# ---- kota -------------------------------------------------------------------------------


def test_kota_okuma():
    def handler(request):
        return httpx.Response(200, json={
            "used_tokens": 100, "cap": 1000, "window_minutes": 5,
            "reset_at": "2026-10-15T20:30:00+00:00", "usage_ratio": 0.1,
            "level": "ok", "held_cr": "0", "remaining_cr": "500",
            "daily_used_tokens": 10, "daily_limit_tokens": 100,
            "daily_remaining_tokens": 90, "daily_reset_at": None,
        })

    q = make_client(handler).get_quota()
    assert q.level == "ok"
    assert q.remaining_cr == "500"
    assert q.daily_limit_tokens == 100


# ---- sağlık uçları -----------------------------------------------------------------------


def test_saglik_uctan_kimliksiz_cagrilir():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("Authorization")
        if request.url.path == "/healthz":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(200, json={"status": "ready"})

    client = make_client(handler)
    assert client.healthz() == {"status": "ok"}
    assert client.readyz() == {"status": "ready"}
    assert seen["auth"] is None, "healthz/readya kimlik başlığı GİTMEMELİ"
