"""Derin Mod: doğrulama KANITA dayanır + alt ajanlar proje haritasıyla başlar (2026-11-12, "derin modu en iyi hale getir").

Bulgu (kodla doğrulandı): denetçiler Plan (salt okunur) kipinde çalışır → komut ÇALIŞTIRAMAZ; istem "komutla çalıştır"
diyordu ama son doğrulamada testler hiç koşmuyordu, denetim yalnız okuyarak verilen kanaatti. Ayrıca 7 alt ajan (3 anla +
2 plan + 2 denetçi) proje haritası olmadan kuruluyor, aynı yapıyı her biri yeniden keşfediyordu.
Tetiklenen ve tetiklenmeyen durumlar ayrı (R-22); denetleyici gerçek akıştan da sınanır (R-31).
"""
from __future__ import annotations

import os
import sys

import pytest
from test_derin_mod import win  # noqa: F401  (pytest fixture)

from evren_studio.agent import deep as dp

PASS_TEST = "import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertEqual(1 + 1, 2)\n"
FAIL_TEST = ("import unittest\n\nclass T(unittest.TestCase):\n    def test_bozuk(self):\n"
             "        self.assertEqual(1 + 1, 3, 'toplama yanlis')\n")


@pytest.mark.skipif(os.name != "nt" and not sys.executable, reason="python gerekli")
def test_proje_testleri_gercekten_calisir(tmp_path):
    (tmp_path / "test_iyi.py").write_text(PASS_TEST, encoding="utf-8")
    ok = dp.project_tests(tmp_path)
    assert ok is not None and ok["durum"] == "gecti" and ok["cikis"] == 0 and ok["komut"]   # pytest ya da unittest
    (tmp_path / "test_kotu.py").write_text(FAIL_TEST, encoding="utf-8")
    bad = dp.project_tests(tmp_path)
    assert bad["durum"] == "dustu" and bad["cikis"] != 0 and "toplama yanlis" in bad["son"]


def test_test_yoksa_none(tmp_path):
    (tmp_path / "app.py").write_text("print('x')\n", encoding="utf-8")
    assert dp.project_tests(tmp_path) is None


def _sub_returning(issues):
    import json

    def sub(prompt, marker, label=""):
        sub.prompts.append(prompt)
        return dp.SubResult("<denetim>" + json.dumps({"sorunlar": issues, "genel": "-"}) + "</denetim>", "done")
    sub.prompts = []
    return sub


def test_dusen_test_denetci_gormese_de_onayli_yuksek_sorun():
    sub = _sub_returning([])
    st = dp.DeepState(goal="div ekle")
    tests = {"komut": "python -m unittest", "durum": "dustu", "cikis": 1, "son": "FAIL: test_div\nAssertionError"}
    issues = dp.verify(st, "--- a\n+++ b\n+x\n", sub, tests=tests, with_tests=True)
    assert len(issues) == 1 and issues[0]["ciddiyet"] == "yuksek" and "DÜŞÜYOR" in issues[0]["aciklama"]
    assert "AssertionError" in issues[0]["aciklama"]
    assert all("GERÇEK TEST SONUCU" in p and "DÜŞTÜ" in p for p in sub.prompts), "denetçiler kanıtı görür"
    assert "düzelt" in dp.fix_prompt("div ekle", issues).lower() and "DÜŞÜYOR" in dp.fix_prompt("div ekle", issues)


def test_gecen_testte_ek_sorun_yok_ve_kanit_istemde():
    """Tetiklenmeyen durum: testler geçti → otomatik sorun eklenmez; istem "geçti" der."""
    sub = _sub_returning([])
    st = dp.DeepState(goal="div ekle")
    tests = {"komut": "python -m unittest", "durum": "gecti", "cikis": 0, "son": "OK"}
    assert dp.verify(st, "--- a\n+++ b\n+x\n", sub, tests=tests, with_tests=True) == []
    assert all("GEÇTİ" in p and "Bu sonuç kanıttır" in p for p in sub.prompts)


def test_test_bulunamayinca_istem_soyler_eski_cagri_degismez():
    sub = _sub_returning([])
    dp.verify(dp.DeepState(goal="g"), "+x", sub, tests=None, with_tests=True)
    assert all("otomatik test bulunamadı" in p for p in sub.prompts)
    sub2 = _sub_returning([])
    dp.verify(dp.DeepState(goal="g"), "+x", sub2)                     # eski çağrı biçimi (kanıtsız)
    assert all("GERÇEK TEST SONUCU" not in p for p in sub2.prompts)


def test_hata_duzeltme_isteminde_imkansiz_komut_talebi_yok():
    """Denetçi salt okunur: "komutla çalıştır" demek yapamayacağı bir şeyi istemekti."""
    assert "komutla çalıştır" not in dp.REPRO_VERIFY and "GERÇEK test" in dp.REPRO_VERIFY


# ---- gerçek denetleyici akışı (R-31) --------------------------------------------------------------------------------

def test_akista_dogrulama_once_testleri_calistirir_dusen_test_duzeltme_turu_acar(win, tmp_path, monkeypatch):
    from test_derin_mod import FakeClient, _session, _wait

    from evren_studio.ui.project_ui import PlanCard

    app, w = win
    if True:
        client = FakeClient()
        client.verify_n = 99                                  # denetçiler sorun BULMAZ: yalnız test kanıtı açar
        s, proj = _session(w, tmp_path, client)
        monkeypatch.setattr(s.deep, "_diff", lambda: "--- a/notlar.txt\n+++ b/notlar.txt\n+merhaba\n")
        runs = []
        dusuk = {"komut": "python -m unittest", "durum": "dustu", "cikis": 1, "son": "FAIL: test_x\nAssertionError"}
        monkeypatch.setattr(dp, "project_tests", lambda root, cancel=None, timeout=None: runs.append(str(root)) or (
            dusuk if len(runs) == 1 else {**dusuk, "durum": "gecti", "cikis": 0, "son": "OK"}))
        seen_kw = []
        real = dp.run_subagent
        monkeypatch.setattr(dp, "run_subagent", lambda **kw: seen_kw.append(kw.get("runner_kw")) or real(**kw))
        s.send("/derin Basit bir not uygulaması ekle: notlar.txt ve README")
        assert _wait(app, lambda: s.findChildren(PlanCard))
        s.findChildren(PlanCard)[-1].approved.emit()
        assert _wait(app, lambda: not s.deep.active, 40)
        assert len(runs) == 2 and runs[0] == str(proj), "her doğrulamadan önce testler çalıştı (ilk + düzeltme sonrası)"
        duzelt = [k for k, _m in client.calls if k == "duzelt"]
        assert len(duzelt) == 1, "düşen test (denetçi görmese de) bir düzeltme turu açtı"
        assert s.deep.state.status == "bitti" and not s.deep.state.issues, "düzeltmeden sonra testler geçti"
        assert seen_kw and all(kw and kw.get("project_map") is True for kw in seen_kw), "alt ajanlar haritayla"


def test_harita_ayari_kapaliysa_alt_ajanlara_verilmez(win, tmp_path, monkeypatch):
    """Tetiklenmeyen durum: kullanıcı proje haritasını kapattıysa Derin alt ajanları da almaz."""
    from test_derin_mod import FakeClient, _session

    app, w = win
    w.ctx.settings.project_map = False
    client = FakeClient()
    s, proj = _session(w, tmp_path, client)
    seen = []
    monkeypatch.setattr(dp, "run_subagent", lambda **kw: seen.append(kw.get("runner_kw")) or dp.SubResult("", "done"))
    s.deep.start("Basit bir not uygulaması ekle")
    sub = s.deep._sub(None, "kod")
    sub("istem", "<bulgu>", "anla-yapi")
    assert seen and seen[-1] == {"project_map": False}


# ---- soru birleştirme (2026-11-12 gerçek ölçümündeki sorular) -------------------------------------------------------

GERCEK_SORULAR = [
    "satislar.xlsx ve bolgeler.tsv proje klasöründe yok. Bu iki dosyayı klasöre ekleyecek misin, yoksa örnek/üretik "
    "veriyle mi ilerleyeyim?",
    "bolgeler.tsv sağlanmazsa bölge sayfaları nasıl belirlensin: musteriler.csv'deki şehirler mi sayfa olsun, yoksa "
    "tüm kayıtlar tek sayfaya mı yazılsın?",
    "satislar.xlsx ve bolgeler.tsv klasörde yok; bu iki dosyayı sağlayacak mısınız, yoksa kuralları göstermek için "
    "örnek/örnek veriyle mi ilerleyeyim? (dosyalar gelmezse rapor üretilemez)",
    "Hangi ay/yıl süzülecek ve hedef şehir/bölge eşlemesinde olmayan şehirler 'Diğer' sayfasına mı yazılsın?",
]


def test_gercek_olcumdeki_tekrar_soru_birlesir():
    f = [{"data": {"sorular": GERCEK_SORULAR[:2]}}, {"data": {"sorular": GERCEK_SORULAR[2:]}}]
    qs = dp.collect_questions(f)
    assert qs == [GERCEK_SORULAR[0], GERCEK_SORULAR[1], GERCEK_SORULAR[3]], qs


def test_farkli_dosyalari_soran_benzer_sorular_birlesmez():
    """Tetiklenmeyen durum: aynı kalıp, farklı dosya → iki ayrı karar."""
    f = [{"data": {"sorular": ["musteriler.csv klasörde yok; sağlayacak mısınız?",
                               "urunler.csv klasörde yok; sağlayacak mısınız?"]}}]
    assert len(dp.collect_questions(f)) == 2


# 2026-11-13 gerçek koşu (e2e_derin_real_api, harita + test kanıtı açık): 4 soru vardı, ikişer tanesi aynı karardı —
# eksik dosyalar farklı sözcüklerle, ay seçimi "raporlanacak/Rapor" ekleriyle soruldu.
GERCEK_SORULAR_2 = [
    "satislar.xlsx ve bolgeler.tsv dosyaları klasörde yok; bu dosyaları ekleyecek misin, yoksa elindeki başka bir "
    "yol/farklı adlı dosya mı kaynak olarak kullanılmalı",
    "Hangi ay (yıl-ay) raporlanacak: verideki son ay mı, yoksa sabit bir ay mı?",
    "satislar.xlsx ve bolgeler.tsv proje klasöründe yok — bu dosyaları Klasöre sen mi koyacaksın, yoksa "
    "örnek/uydurma veriyle mi ilerleyeyim?",
    "Rapor tek bir ay için mi (hangisi) yoksa verideki tüm aylar için mi (ay başına ayrı blok/sayfa) olsun, çıktı "
    "dosyasının adı/ne olsun?",
]


def test_ikinci_gercek_olcumde_ek_ve_sozcuk_farkli_tekrarlar_birlesir():
    f = [{"data": {"sorular": [q]}} for q in GERCEK_SORULAR_2]
    assert dp.collect_questions(f) == GERCEK_SORULAR_2[:2]


def test_ayni_dosyanin_yoklugu_farkli_sozcuklerle_tek_soru():
    f = [{"data": {"sorular": ["veri.xlsx klasörde yok; ekler misin?"]}},
         {"data": {"sorular": ["veri.xlsx projede bulunmuyor — örnek veriyle mi devam edeyim?"]}}]
    assert dp.collect_questions(f) == ["veri.xlsx klasörde yok; ekler misin?"]


def test_farkli_kararlar_birlesmez():
    """Tetiklenmeyen durumlar (R-22): ortak kalıp sözcüğü ("hangi", "Rapor") ya da aynı dosyanın başka bir sorunu
    (dosyada OLMAYAN kayıtlar) soruları birleştirmemeli."""
    qs = ["Rapor hangi biçimde olsun (xlsx mi csv mi)?",
          "Raporda hangi ay kullanılsın?",
          "musteriler.csv klasörde yok; sağlayacak mısınız?",
          "musteriler.csv'de bulunmayan müşteri id'leri nereye yazılsın?",
          "KDV oranı %18 mi %20 mi alınsın?",
          "Negatif tutarlı satırlar iade mi sayılsın, atılsın mı?",
          "Tarih nasıl olsun?",                        # tek ortak kök (tarih) iki kararı birleştirmez
          "Tarih sütunu silinsin mi?"]
    assert dp.collect_questions([{"data": {"sorular": qs}}], limit=99) == qs


def test_ayni_dosyanin_iki_ayri_karari_birlesmez_ama_ayni_karar_birlesir():
    """Dosya adı ortak sözcük sayılmaz (çok parçalı ad 4 ortak "sözcük" üretip iki ayrı kararı birleştiriyordu); aynı
    dosyayı anan ve anmayan aynı karar tek soru olur."""
    farkli = ["satis-raporu-2026.xlsx'te hangi sayfa okunacak?",
              "satis-raporu-2026.xlsx'teki negatif tutarlar iade mi sayılsın?"]
    assert dp.collect_questions([{"data": {"sorular": farkli}}]) == farkli
    ayni = ["Negatif tutarlı satırlar iade mi sayılsın, atılsın mı?", farkli[1]]
    assert dp.collect_questions([{"data": {"sorular": ayni}}]) == ayni[:1]
