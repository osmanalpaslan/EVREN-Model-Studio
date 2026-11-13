"""Madde 23 b — auto dışındaki işlerde bozulan motordan yedeğe geçiş.

Kullanıcı 2026-11-13: "evren ortamı motorları geliştirilmeye devam ediyor; bugün iyi olan bir motor gelecekte bakımdaysa
iyi olmayabilir. auto haricinde farklı alanlarda kullandığın motorlarda performansı düşükse yedek motor veya motorlara
geçebilmeli."
"""
from __future__ import annotations

import os
import time

import pytest

from evren_studio.agent import modelstats, router
from evren_studio.api.client import ChatResult
from evren_studio.api.errors import ApiError, ErrorKind
from evren_studio.db import Database
from evren_studio.ui import app_context as ac


def _calls(model, ok=0, bad=0, empty=0, role="kod", kind="sunucu_hatası"):
    rows = [{"model": model, "role": role, "ok": 1} for _ in range(ok)]
    rows += [{"model": model, "role": role, "ok": 0, "error_kind": kind} for _ in range(bad)]
    rows += [{"model": model, "role": role, "ok": 1, "empty": 1} for _ in range(empty)]
    return rows


# ---- ölçü ---------------------------------------------------------------------------------------------------------


def test_cogunlukla_basarisiz_motor_zayif_sayilir():
    out = modelstats.failing(_calls("a", ok=1, bad=2, empty=1) + _calls("b", ok=5))
    assert set(out) == {"a"}
    assert "3/4 çağrı başarısız" in out["a"] and "sunucu_hatası ×2" in out["a"] and "boş yanıt ×1" in out["a"]


@pytest.mark.parametrize("rows", [
    _calls("a", ok=0, bad=2),                         # az örnek: 2 hata tek başına yetmez
    _calls("a", ok=7, bad=3),                         # oran düşük (%30): ara sıra hata normal
    [{"model": "a", "ok": 0, "event": "loop"}] * 5,   # kalite olayı çağrı değildir
])
def test_ara_sira_hata_ya_da_olay_zayif_saydirmaz(rows):
    assert modelstats.failing(rows) == {}            # R-22: gereksiz tetiklenme yok


def test_ic_isler_ajan_kalite_puanini_sulandirmaz():
    ajan = _calls("m", ok=6) + [{"model": "m", "ok": 1, "event": "loop"}] * 3
    ic = _calls("m", ok=20, role=modelstats.INTERNAL_PREFIX + "baslik")
    assert "m" in modelstats.penalized(ajan)
    assert "m" in modelstats.penalized(ajan + ic)     # 20 kısa iç çağrı 3 döngü olayını gizlemez
    assert modelstats.failing(ic + _calls("m", bad=0)) == {}
    assert "m" in modelstats.failing(_calls("m", bad=4, role=modelstats.INTERNAL_PREFIX + "ozet"))  # ama bozulma sayılır


# ---- yönlendirici ---------------------------------------------------------------------------------------------------


def test_zayif_motor_yedeklerin_arkasina_alinir_ve_cikarilmaz():
    chain = router.chain_for("baslik", None)
    first = chain[0]
    r = router.choose("baslik", available=set(chain), weak=modelstats.failing(_calls(first, bad=3)))
    assert r.model != first and first in r.fallbacks and "bugün zayıf" in r.reason


def test_tabloda_tek_motor_kalinca_digerleri_yedek_olur_secilen_once():
    avail = {"deepseek-v4.1-flash", "yeni-motor-x", "auto"}
    r = router.choose("baslik", available=avail)      # baslik tablosundan yalnız biri yok, hiçbiri yok → yedek
    assert r.model and len(r.fallbacks) >= 1 and r.model not in r.fallbacks
    r2 = router.choose("sohbet", available={"ag-gecidi/model-1", "ag-gecidi/model-2"}, prefer=["ag-gecidi/model-2"])
    assert r2.model == "ag-gecidi/model-2" and r2.fallbacks == ["ag-gecidi/model-1"]
    # tabloda iki motor varsa yedek eklenmez (davranış aynı kalır)
    two = set(router.EVREN_ROUTES["baslik"][:2])
    assert router.choose("baslik", available=two | {"baska"}).fallbacks == [m for m in router.EVREN_ROUTES["baslik"][:2]
                                                                             if m != router.choose("baslik", available=two | {"baska"}).model]


def test_model_weak_gercek_kayittan_okur_karne_kapali_olsa_da(tmp_path):
    db = Database(tmp_path / "t.db")
    try:
        class Ctx:
            model_weak = ac.AppContext.model_weak

        c = Ctx()
        c.db = db
        c.settings = type("S", (), {"motor_karnesi": False})()
        assert c.model_weak() == {}
        for _ in range(3):
            db.add_model_call("bozuk", role="kod", ok=False, error_kind="sunucu_hatası")
        db.add_model_call("bozuk", role="kod", ok=True)
        assert "bozuk" in c.model_weak()
    finally:
        db.close()


# ---- iç işler kayda girer --------------------------------------------------------------------------------------------


class _Route:
    def __init__(self, chain):
        self.model, self.fallbacks = chain[0], chain[1:]


class _Ctx:
    _ai_attempt = ac.AppContext._ai_attempt
    _ai_record = ac.AppContext._ai_record
    _ai_chat_hedged = ac.AppContext._ai_chat_hedged
    ai_chat = ac.AppContext.ai_chat

    def __init__(self, chain, behave):
        self.chain, self.behave, self.records = chain, behave, []

    def ai_route(self, role, **_kw):
        return _Route(self.chain)

    def provider_of(self, model):
        return "evren"

    def model_info(self, model):
        return None

    def record_model_call(self, rec):
        self.records.append(rec)

    def make_client_for(self, provider):
        ctx = self

        class C:
            def chat(self, model, messages, **kw):
                r = ctx.behave[model]
                if isinstance(r, Exception):
                    raise r
                return ChatResult(content=r)

            def close(self):
                pass
        return C()


def test_ic_is_cagrilari_basari_ve_hatayla_kaydedilir(monkeypatch):
    monkeypatch.setattr(ac, "HEDGE_AFTER_S", 0.0)     # sıralı yol
    c = _Ctx(["a", "b", "c"], {"a": ApiError(ErrorKind.SERVER_ERROR, "503"), "b": "", "c": "Başlık"})
    assert c.ai_chat("baslik", [{"role": "user", "content": "x"}]) == ("Başlık", "c")
    recs = [(r["model"], r["ok"], bool(r.get("empty")), r["role"]) for r in c.records if not r.get("event")]
    assert recs == [("a", False, False, "ic:baslik"), ("b", True, True, "ic:baslik"), ("c", True, False, "ic:baslik")]
    assert c.records[0]["error_kind"] == ErrorKind.SERVER_ERROR.value


def test_kota_hatasi_motor_bozulmasi_sayilmaz(monkeypatch):
    monkeypatch.setattr(ac, "HEDGE_AFTER_S", 0.0)
    c = _Ctx(["a"], {"a": ApiError(ErrorKind.RATE_LIMIT, "429")})
    with pytest.raises(ApiError):
        c.ai_chat("baslik", [{"role": "user", "content": "x"}])
    assert c.records == []                            # hesap düzeyi hata: motorun suçu değil


def test_paralel_yedek_yolunda_da_kayit(monkeypatch):
    monkeypatch.setattr(ac, "HEDGE_AFTER_S", 5.0)
    c = _Ctx(["a", "b"], {"a": ApiError(ErrorKind.SERVER_UNAVAILABLE, "bakımda"), "b": "Tamam"})
    assert c.ai_chat("yargic", [{"role": "user", "content": "x"}]) == ("Tamam", "b")
    time.sleep(0.05)
    assert {(r["model"], r["ok"]) for r in c.records if not r.get("event")} == {("a", False), ("b", True)}


# ---- uçtan uca: gerçek AppContext ---------------------------------------------------------------------------------


@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
    yield app, w
    w.close()


def test_bozulan_motor_ic_islerde_ve_rollerde_yedege_birakir(win):
    _app, w = win
    first = w.ctx.ai_route("baslik").model
    assert first
    for _ in range(3):
        w.ctx.record_model_call({"model": first, "role": "ic:baslik", "ok": False, "error_kind": "sunucu_hatası"})
    r = w.ctx.ai_route("baslik")
    assert r.model != first and first in r.fallbacks and "zayıf" in r.reason
    k = w.ctx.ai_route("kod")                         # aynı motor başka rolde de geri alınır (Derin/Proje görevleri)
    if first in [k.model, *k.fallbacks]:
        assert k.model != first
