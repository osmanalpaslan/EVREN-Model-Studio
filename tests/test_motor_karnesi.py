"""Madde 14 — motor karnesi ve akıllı yönlendirme (kullanıcı 2026-11-06). Gerçek API YOK.

Kullanıcı: gerçek kalite motorun EN İYİ gününde ölçülsün, puan gerçek kapasiteyi göstersin; günlük hafif yoklamada
zayıfsa daha güçlü yedeğe geçilsin; QA basit iş için dakikalarca sürmesin, motor kötüyse "QA için uygun değil" desin.
Her otomatik karar için tetiklenen ve tetiklenmeyen durum (R-22)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from evren_studio.agent import karne, qa, router
from evren_studio.db import Database

NOW = datetime(2026, 11, 6, 19, 0, tzinfo=timezone.utc)


def probe(model, minutes_ago, dur=1.0, ok=True, kind=None):
    return {"model": model, "role": "yoklama", "ok": ok, "duration_s": dur, "error_kind": kind,
            "at": (NOW - timedelta(minutes=minutes_ago)).isoformat()}


def history(model, dur=1.0, n=4):
    return [probe(model, 60 * 24 * (i + 1), dur) for i in range(n)]       # önceki günlerin yoklamaları


# ---- 1) günlük hafif yoklama → "bugün zayıf" ----------------------------------------------------------------

def test_yoklamada_hata_veren_motor_bugun_zayif():
    rows = history("a") + [probe("a", 10, ok=False, kind="sunucu_yok")]
    assert karne.day_state(rows, "a", NOW)[0] == "zayif"
    assert "a" in karne.weak_models(rows, NOW)


def test_normalinden_cok_yavas_yoklama_zayif_biraz_yavas_degil():
    slow = history("a", 2.0) + [probe("a", 5, dur=12.0)]                 # 6 kat ve 8 sn üstü
    assert karne.day_state(slow, "a", NOW)[0] == "zayif"
    bit = history("a", 2.0) + [probe("a", 5, dur=3.5)]                   # 1,75 kat: zayıf DEĞİL (R-22)
    assert karne.day_state(bit, "a", NOW)[0] != "zayif"
    noisy = history("a", 0.5) + [probe("a", 5, dur=2.0)]                 # 4 kat ama 2 sn: gürültü, zayıf değil
    assert karne.day_state(noisy, "a", NOW)[0] != "zayif"


def test_iyi_gun_ve_bilinmeyen_gun():
    assert karne.day_state(history("a", 2.0) + [probe("a", 5, 2.1)], "a", NOW)[0] == "iyi"
    assert karne.day_state(history("a", 2.0) + [probe("a", 60 * 5, 2.1)], "a", NOW)[0] == "bilinmiyor"   # eski
    assert karne.day_state([probe("a", 5, 4.0)], "a", NOW)[0] == "ilk"                                 # geçmiş yok
    assert karne.day_state([probe("a", 5, 4.0, ok=False)], "a", NOW)[0] == "zayif"                    # geçmişsiz hata
    assert karne.day_state([probe("a", 5, 45.0)], "a", NOW)[0] == "zayif"                              # çok yavaş
    assert karne.day_state([], "a", NOW)[0] == "bilinmiyor"


def test_yoklama_disindaki_cagrilar_ve_olaylar_sayilmaz():
    rows = history("a", 2.0) + [probe("a", 5, 2.0),
                                {"model": "a", "role": "kod", "ok": False, "at": NOW.isoformat()},
                                {**probe("a", 1, 99.0), "event": "switch"}]
    assert karne.weak_models(rows, NOW) == {}


# ---- 2) gerçek puan (karne) ---------------------------------------------------------------------------------

def rapor(passes, sure=15.0, hata=0):
    return {"model": "x", "sonuclar": [
        {"gorev": f"g{i}", "sure": sure, "zaman_icinde": True, "hata_karti": hata, "tekrar_3": {},
         "kontroller": [{"ad": "a", "gecti": True}, {"ad": "b", "gecti": p}]} for i, p in enumerate(passes)]}


def test_puan_dogrulugu_hizdan_once_tartar():
    tam = karne.score_report(rapor([True] * 4))
    assert tam["score"] == 100.0 and tam["tam_gecen"] == 4
    yavas_dogru = karne.score_report(rapor([True] * 4, sure=240.0))["score"]
    hizli_yanlis = karne.score_report(rapor([True, False, False, False], sure=20.0))["score"]
    assert yavas_dogru > hizli_yanlis                                    # doğruluk bir tık daha önemli
    assert karne.score_report(rapor([True] * 4, hata=1))["score"] < 100.0
    assert karne.score_report({"sonuclar": []})["score"] == 0.0


def test_gercek_puan_en_iyi_iyi_gun_olcumu_kotu_gun_sayilmaz():
    rows = [{"model": "a", "score": 88, "good_day": 1}, {"model": "a", "score": 70, "good_day": 1},   # son değil en iyi
            {"model": "a", "score": 95, "good_day": 0},                 # kötü gün: sayılmaz
            {"model": "b", "score": 60, "good_day": 0}]
    assert karne.best_scores(rows) == {"a": 88.0}
    c = karne.card([{**r, "at": "2026-11-06"} for r in rows])
    assert c[0]["model"] == "a" and c[0]["puan"] == 88.0 and (c[0]["iyi"], c[0]["toplam"]) == (2, 3)
    assert c[1]["model"] == "b" and c[1]["puan"] is None


def test_karne_veritabaninda_kalici(tmp_path):
    """R-03: kaydedilen puan uygulama yeniden açılınca da okunur."""
    db = Database(tmp_path / "e.db")
    db.add_model_score("qwen3.8-flash-next", "zorluk", 91.5, good_day=True, details="{}")
    db.add_model_score("qwen3.8-flash-next", "zorluk", 99.0, good_day=False)
    db.conn.close()
    rows = Database(tmp_path / "e.db").model_scores()
    assert karne.best_scores(rows) == {"qwen3.8-flash-next": 91.5}


# ---- 3) yönlendirme: puana göre sıra, bugün zayıfsa güçlü yedek --------------------------------------------

def test_puan_iki_aday_puanliysa_sirayi_belirler_puansizin_yeri_degismez():
    r = router.choose("kod", scores={"qwen3.8-flash-next": 92, "gemma-4-31b": 70, "deepseek-v4.1-flash": 80})
    assert [r.model] + r.fallbacks == ["qwen3.8-flash-next", "deepseek-v4.1-flash", "gemma-4-31b"]
    assert "gerçek puana göre" in r.reason
    tek = router.choose("kod", scores={"gemma-4-31b": 99})               # tek puan: sıra değişmez (R-22)
    assert tek.model == "deepseek-v4.1-flash" and "puan" not in tek.reason
    kismi = router.choose("kod", scores={"qwen3.8-flash-next": 50, "gemma-4-31b": 90})
    assert [kismi.model] + kismi.fallbacks == ["deepseek-v4.1-flash", "gemma-4-31b", "qwen3.8-flash-next"]


def test_puan_olcmedigi_islerde_kullanilmaz():
    first = router.EVREN_ROUTES["baslik"][0]
    r = router.choose("baslik", scores={first: 10, "gemma-4-31b": 99})
    assert r.model == first and "puan" not in r.reason


def test_bugun_zayif_motor_guclu_yedege_birakir_gerekcesiyle():
    r = router.choose("kod", weak={"deepseek-v4.1-flash": "yoklama 40 sn, normali ~2 sn"})
    # yavaş ama güçlü deepseek, kodda hile eğilimli gemma'nın ÖNÜNDE kalır
    assert r.model == "qwen3.8-flash-next" and r.fallbacks == ["deepseek-v4.1-flash", "gemma-4-31b"]
    assert "bugün zayıf" in r.reason and "40 sn" in r.reason
    temiz = router.choose("kod", weak={})                                # tetiklenmeyen (R-22)
    assert temiz.model == "deepseek-v4.1-flash" and "zayıf" not in temiz.reason


def test_zayiflik_yuzunden_zayif_role_hileci_motor_one_gecmez():
    """Kodda gemma yalnız sunucu hatasında öne geçer; güçlü ikisi de bugün yavaşsa sıra korunur."""
    weak = {"deepseek-v4.1-flash": "yavaş", "qwen3.8-flash-next": "yavaş"}
    r = router.choose("kod", weak=weak)
    assert r.model != "gemma-4-31b"


def test_puan_ve_zayiflik_birlikte_en_guclu_saglam_motor():
    r = router.choose("qa", scores={"qwen3.8-flash-next": 95, "deepseek-v4.1-flash": 85},
                      weak={"qwen3.8-flash-next": "yoklamada hata"})
    assert r.model == "deepseek-v4.1-flash" and r.fallbacks == ["qwen3.8-flash-next"]


def test_bugun_zayif_motor_hiz_kuraliyla_one_alinmaz():
    r = router.choose("kod", speeds={"deepseek-v4.1-flash": 10, "qwen3.8-flash-next": 50},
                      weak={"qwen3.8-flash-next": "yoklamada hata"})
    assert r.model == "deepseek-v4.1-flash"


def test_qa_rolu_hizli_ve_dogru_motorla_hilecisiz():
    assert router.EVREN_ROUTES["qa"][0] == "qwen3.8-flash-next"
    assert "gemma-4-31b" not in router.EVREN_ROUTES["qa"]
    assert "qa" in router.ROLE_LABELS and "qa" in router.PAID_ROUTES


# ---- 4) QA hızı: senaryo sayısı isteğin büyüklüğüne göre -----------------------------------------------------

@pytest.mark.parametrize("goal,hi", [
    ("Topla işlevini test et", 4), ("giriş düğmesi çalışıyor mu", 4), ("sadece kaydet düğmesini dene", 4),
    ("tüm uygulamayı kapsamlı test et", 12), ("baştan sona her ekranı dene", 12),
    ("Topla işlevini test et. En fazla 3 senaryo yeter.", 3)])
def test_senaryo_sayisi_is_buyuklugune_gore(goal, hi):
    lo, got, _why = qa.scenario_range(goal)
    assert got == hi and 1 <= lo <= got
    for target in ("web", "masaustu"):
        assert f"{lo} ile {hi} arasında senaryo" in qa.planning_prompt(goal, target=target)


def test_orta_istek_orta_aralik():
    goal = ("Sipariş formunu test et: ürün seçimi, adet alanı, indirim kodu, teslimat adresi ve onay ekranı "
            "birlikte doğru çalışıyor mu, hatalı girişte uyarı veriyor mu bak")
    assert qa.scenario_range(goal)[1] == 7


# ---- 5) QA hazırlık: motorların hepsi bugün zayıfsa uyar -----------------------------------------------------

class _Ctx:
    def __init__(self, weak):
        self._weak = weak

    def model_weak(self):
        return self._weak

    def available_model_ids(self):
        return {"qwen3.8-flash-next", "deepseek-v4.1-flash", "gemma-4-31b"}

    def provider_of(self, m):
        return "evren"


def test_qa_hazirlik_hepsi_zayifsa_uygun_degil_biri_saglamsa_uygun():
    from evren_studio.ui.app_context import AppContext

    hepsi = {"qwen3.8-flash-next": "yoklamada hata", "deepseek-v4.1-flash": "yoklama 40 sn"}
    ok, why = AppContext.qa_readiness(_Ctx(hepsi))
    assert not ok and "QA motorları" in why and "40 sn" in why
    ok2, why2 = AppContext.qa_readiness(_Ctx({"qwen3.8-flash-next": "yoklamada hata"}))
    assert ok2 and why2 == ""                                             # biri sağlam: o motora devredilir
    assert AppContext.qa_readiness(_Ctx({}))[0]


# ---- 6) gerçek ekran akışı (R-31): veritabanındaki yoklama → QA motor seçimi ve uyarı ---------------------

@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
    yield app, w
    w.close()


def _fail_probe(ctx, model):
    ctx.db.add_model_call(model, role="yoklama", ok=False, error_kind="sunucu_yok", duration_s=30.0)


def test_qa_bugun_zayif_motoru_atlar_ve_hepsi_zayifsa_once_uyarir(win, monkeypatch):
    app, w = win
    qc = w.session.qa
    notes, planned = [], []
    monkeypatch.setattr(w.session, "_note", lambda text, icon="dot": notes.append(text))
    monkeypatch.setattr(qc, "precheck", lambda target="web": "")
    monkeypatch.setattr(qc, "_auto_install_kind", lambda target: "")
    monkeypatch.setattr(qc, "plan", lambda goal, feedback="", target="web": planned.append(goal))

    qc.command("/qa", "Topla işlevini test et")                           # yoklama yok: doğrudan başlar (R-22)
    assert planned == ["Topla işlevini test et"] and not any("QA motorları" in n for n in notes)

    _fail_probe(w.ctx, "qwen3.8-flash-next")
    model, fallbacks, role = qc._evren_model("qa")                       # biri zayıf: sağlam güçlü yedek
    assert (model, role) == ("deepseek-v4.1-flash", "qa") and fallbacks == ["qwen3.8-flash-next"]
    assert any("bugün zayıf" in n for n in notes)

    _fail_probe(w.ctx, "deepseek-v4.1-flash")                            # hepsi zayıf: başlamadan uyar
    planned.clear()
    qc.command("/qa", "Topla işlevini test et")
    assert planned == [] and any("QA motorları şu an" in n for n in notes)
    qc.command("/qa", "başka bir iş")                                     # FARKLI komut onay sayılmaz
    assert planned == []
    qc.command("/qa", "Topla işlevini test et")                           # uyarı artık "başka bir iş" için
    assert planned == []
    qc.command("/qa", "Topla işlevini test et")                           # aynı komut yeniden: kullanıcı istedi
    assert planned == ["Topla işlevini test et"]
    planned.clear()
    qc.command("/qa", "başka bir şey")                                    # farklı komut: yine uyarır
    assert planned == []


# ---- 7) ölçüm aracı (tools/motor_karnesi.py): yalnız iyi günde gerçek puan -------------------------------

def _tool():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("motor_karnesi", Path(__file__).parents[1] / "tools" / "motor_karnesi.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_olcum_karari_iyi_gunde_olcer_kotu_gunde_erteler():
    t = _tool()
    assert t.karar("iyi", False) == (True, True) and t.karar("ilk", False) == (True, True)
    assert t.karar("zayif", False) == (False, False) and t.karar("bilinmiyor", False) == (False, False)
    assert t.karar("zayif", True) == (True, False)                       # zorla: ölçer ama puana katmaz


def test_arac_raporu_puanlar_kaydeder_ve_karneyi_gosterir(tmp_path):
    t = _tool()
    db = Database(tmp_path / "e.db")
    assert "Henüz ölçüm yok" in t.goster(db)
    s = t.iceri_al(db, rapor([True] * 4), "qwen3.8-flash-next", True)
    t.iceri_al(db, rapor([True, False, False, False]), "deepseek-v4.1-flash", False)
    assert s["score"] == 100.0
    text = t.goster(db)
    assert "qwen3.8-flash-next" in text and "100.0" in text and "deepseek-v4.1-flash" in text
    assert karne.best_scores(db.model_scores()) == {"qwen3.8-flash-next": 100.0}


# ---- 8) Modeller ekranı: karne ve bugünkü durum görünür (R-03: kayıt → ekran) -----------------------------

def test_modeller_ekraninda_karne_ve_bugunku_yoklama(win):
    _app, w = win
    page = w.pages["models"]
    page.refresh()
    assert page.karne.rowCount() == 0 and not page.karne_hint.isHidden()           # ölçüm yok: ipucu görünür
    w.ctx.db.add_model_score("qwen3.8-flash-next", "zorluk", 91.5, good_day=True)
    w.ctx.db.add_model_score("qwen3.8-flash-next", "zorluk", 99.0, good_day=False)  # kötü gün: puana katılmaz
    _fail_probe(w.ctx, "deepseek-v4.1-flash")                                      # ölçülmemiş ama bugün zayıf
    w.ctx.record_model_call({"model": "deepseek-v4.1-flash", "ok": True, "duration_s": 5, "first_chunk_s": 1,
                             "out_tokens": 400})
    page.refresh()
    rows = {page.karne.item(r, 0).text(): [page.karne.item(r, c).text() for c in range(5)]
            for r in range(page.karne.rowCount())}
    assert rows["qwen3.8-flash-next"][1:3] == ["91.5", "1 / 2"]
    assert rows["deepseek-v4.1-flash"][1] == "-" and rows["deepseek-v4.1-flash"][4].startswith("zayıf")
    assert page.karne_hint.isHidden()
    durum = {page.stats.item(r, 0).text(): page.stats.item(r, 7).text() for r in range(page.stats.rowCount())}
    assert durum["deepseek-v4.1-flash"].startswith("bugün zayıf")


# ---- 9) ilk gerçek ölçümden (2026-11-06) çıkan düzeltmeler ------------------------------------------------

def test_yoklama_dusunme_alanini_desteklemeyen_motorda_alansiz_yeniden_dener():
    """gemma-4-31b `reasoning_effort` alanını 400 ile reddetti; araç onu haksız yere 'zayıf' sayıp erteledi."""
    from evren_studio.api.errors import ApiError, ErrorKind

    t = _tool()

    class C:
        def __init__(self, fail_kind):
            self.bodies, self.fail_kind = [], fail_kind

        def chat(self, model, messages, max_tokens=32, stream=True, extra_body=None):
            self.bodies.append(extra_body)
            if extra_body and self.fail_kind:
                raise ApiError(kind=self.fail_kind, message="desteklenmiyor")
            return "tamam"

    c = C(ErrorKind.VALIDATION)
    assert t.probe_chat(c, "gemma-4-31b") == "tamam" and c.bodies == [{"reasoning_effort": "none"}, None]
    ok = C(None)
    assert t.probe_chat(ok, "qwen") == "tamam" and ok.bodies == [{"reasoning_effort": "none"}]   # tek istek
    down = C(ErrorKind.SERVER_UNAVAILABLE)
    with pytest.raises(ApiError):
        t.probe_chat(down, "x")                                               # gerçek arıza yeniden denenmez
    assert down.bodies == [{"reasoning_effort": "none"}]


def test_hiz_ilk_gercek_olcumdeki_iki_motoru_ayirir_dogruluk_yine_once():
    """qwen ortanca 29 sn, deepseek 55 sn; ikisi de 12/12 — eski 60 sn eşiğinde ikisi 99,3 aldı."""
    hizli = karne.score_report(rapor([True] * 12, sure=29.0))["score"]
    yavas = karne.score_report(rapor([True] * 12, sure=55.0))["score"]
    assert hizli > yavas + 2
    bir_kalan = karne.score_report(rapor([True] * 11 + [False], sure=29.0))["score"]
    assert yavas > bir_kalan - 1 and hizli > bir_kalan               # bir görevde kalmak hızdan pahalı


def test_gorevde_kalan_hizli_motor_tam_gecen_yavasin_onune_gecemez():
    """İlk gerçek ölçüm: gemma 10/12 (ortanca ~18 sn) düz toplamla deepseek 12/12'nin (55 sn) önüne geçmişti."""
    def rap(n_ok, n, sure):
        # gerçek rapor gibi: görev başına 3 kontrol; kalan görevde yalnız biri düşer (gemma: 38/40 kontrol, 10/12 görev)
        return {"sonuclar": [{"sure": sure, "zaman_icinde": True, "hata_karti": 0, "tekrar_3": {},
                              "kontroller": [{"gecti": True}, {"gecti": True}, {"gecti": i < n_ok}]} for i in range(n)]}

    gemma = karne.score_report(rap(10, 12, 18.0))["score"]
    deepseek = karne.score_report(rap(12, 12, 55.0))["score"]
    qwen = karne.score_report(rap(12, 12, 29.0))["score"]
    assert qwen > deepseek > gemma
    assert karne.score_report(rap(12, 12, 10.0))["score"] == 100.0
