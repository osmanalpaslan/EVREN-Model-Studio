"""Token tahmini kalibrasyonu (runner.calibrate / calibration): EVREN gerçek ölçümünde Türkçe/araç çıktısı
2,2-2,6 karakter/token iken uygulama 3,5 varsayıyor, bağlamı %40-60 küçük görüyordu (otomatik özet geç
tetikleniyordu, 2026-11-01). Tetiklenen ve tetiklenmeyen durumlar birlikte sınanır (R-22, R-31)."""
from __future__ import annotations

import json

import pytest

from evren_studio.agent import runner
from evren_studio.agent.compaction import CompactPolicy, history_tokens, needs_compaction
from evren_studio.agent.runner import (AgentEvents, AgentRunner, calibrate, calibration, estimate_tokens,
                                       trim_for_context)
from evren_studio.agent.tools import Workspace
from evren_studio.api.client import ChatResult
from evren_studio.db import Database


def test_varsayilan_olculmus_orana_yakin_ve_ek_yuk_gercekci():
    cpt, overhead = calibration()
    assert cpt <= 2.6 and overhead >= 5_000                     # ölçüm: 2,16-2,55 kr/token, ilk istek 5.620 token
    turkce = "Bu klasörde kütüphane uygulamasını güncelledim, testleri çalıştırıp sonucu özetliyorum. " * 100
    assert estimate_tokens([{"content": turkce}]) >= len(turkce) / 2.6 - 1


def test_kalibrasyon_ogrenir_yumusatir_ve_sinirlar():
    calibrate("m1", sent_chars=22_000, overhead_chars=12_000, input_tokens=10_000)
    assert calibration("m1") == (pytest.approx(2.2), int(12_000 / 2.2))
    calibrate("m1", sent_chars=30_000, overhead_chars=12_000, input_tokens=10_000)     # 3,0 → ortalama 2,6
    assert calibration("m1")[0] == pytest.approx(2.6)
    calibrate("m2", sent_chars=100_000, overhead_chars=1, input_tokens=1_000)           # 100 → üst sınır
    assert calibration("m2")[0] == runner.CPT_MAX
    calibrate("m3", sent_chars=500, overhead_chars=1, input_tokens=100)                 # az veri → öğrenmez
    assert "m3" not in runner._CALIB
    # model bilinmiyorsa en temkinli (en küçük oran, en büyük ek yük)
    assert calibration(None)[0] == pytest.approx(2.6) and calibration("yok")[0] == pytest.approx(2.6)


def test_gorsel_base64_sayilmaz():
    big = "A" * 200_000
    msg = [{"role": "user", "content": [{"type": "text", "text": "bu ne?"},
                                        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + big}}]}]
    assert estimate_tokens(msg) < 10


def _turkce_gecmis(n: int) -> list[dict]:
    h = []
    for i in range(n):
        h.append({"role": "user", "content": f"{i}. adım: kitap listesini güncelle ve testleri çalıştır. " * 20})
        h.append({"role": "assistant", "content": "Güncelledim; testler geçti, sıradaki adıma geçiyorum. " * 20})
    return h


def test_ozet_esigi_artik_gercek_boyutta_tetiklenir_kucukte_tetiklenmez():
    policy = CompactPolicy(enabled=True, percent=75, max_tokens=100_000)
    ctx = 128_000
    buyuk = _turkce_gecmis(110)              # ~250k karakter: gerçekte ~100k token (2,5 kr/token)
    need, tokens, limit = needs_compaction(buyuk, policy, ctx)
    eski = int(sum(len(m["content"]) for m in buyuk) / 3.5) + 2_500
    assert need and tokens > limit and eski < limit, (tokens, limit, eski)   # eski hesap tetiklemiyordu
    kucuk = _turkce_gecmis(10)
    assert not needs_compaction(kucuk, policy, ctx)[0]
    once = history_tokens(kucuk)
    calibrate("m", sent_chars=30_000, overhead_chars=9_000, input_tokens=10_000)         # kod ağırlıklı: 3,0
    assert history_tokens(kucuk) < once                                                 # öğrenilen oran kullanılır


def test_kirpma_kalibre_oranla_calisir():
    h = [{"role": "tool", "content": "x" * 3_000, "tool_call_id": str(i)} for i in range(20)]
    h.append({"role": "user", "content": "son"})
    # 60k karakter: 2,6 ile ~23k (24,5k bütçeye sığar), 2,0 ile 30k token (aşar → kırpılır)
    assert not any(m["content"] == runner.TRIMMED_NOTE for m in trim_for_context(h, 35_000))   # 2,6: ~23k sığar
    calibrate("dar", sent_chars=20_000, overhead_chars=1, input_tokens=10_000)
    kirpik = trim_for_context(h, 35_000, model="dar")
    assert any(m["content"] == runner.TRIMMED_NOTE for m in kirpik)


# ---- gerçek tur akışı: sahte istemcinin bildirdiği usage'tan öğrenir (R-31) ----------------------

class Script:
    def __init__(self, seq):
        self.seq = list(seq)

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, on_reasoning=None, tools=None, **kw):
        sent = sum(len(m.get("content") or "") for m in messages if isinstance(m.get("content"), str))
        sent += len(json.dumps(tools, ensure_ascii=False)) if tools else 0
        r = self.seq.pop(0) if self.seq else ChatResult(content="bitti", finish_reason="stop")
        r.usage = {"prompt_tokens": int(sent / 2.2), "completion_tokens": 10}      # sunucu 2,2 kr/token sayıyor
        return r


def test_tur_akisinda_usage_ile_kalibre_olur(tmp_path):
    db = Database(tmp_path / "t.db")
    proj = tmp_path / "p"
    proj.mkdir()
    sid = db.create_session("m", str(proj))
    db.add_session_message(sid, "user", "görev")
    call = ChatResult(content="", tool_calls=[{"id": "c1", "name": "list_files", "arguments": "{}"}],
                      finish_reason="tool_calls")
    r = AgentRunner(Script([call]), "olcum-modeli", session_id=sid, store=db, events=AgentEvents(),
                    workspace=Workspace(proj), mode="auto", stream=False)
    r.run(db.get_session_messages(sid))
    cpt, overhead = calibration("olcum-modeli")
    assert cpt == pytest.approx(2.2, abs=0.05)
    assert overhead > 4_000                                  # sistem istemi + araç tanımları gerçekten sayıldı
    assert r._history_tokens(db.get_session_messages(sid)) > overhead
    db.close()
