"""Hata düzeltmede önce yeniden üretme testi (Madde 20 B1, 2026-11-11; Agentless / SWE-agent yaklaşımı).
Plan (Proje ajanı + Derin Mod) hata düzeltme isteğinde 1. görevi "hatayı yeniden üreten, ŞU AN KALAN test" yapar; Derin
doğrulama bu testin düzeltmeden sonra geçtiğini ve zayıflatılmadığını denetler. Tetiklenen + tetiklenmeyen (R-22)."""
from __future__ import annotations

import pytest

from evren_studio.agent import deep, project

HATA = [
    "hesapla() sıfıra bölünce çöküyor, düzelt",
    "Fatura toplamı yanlış hesaplıyor",
    "Giriş sayfası çalışmıyor",
    "ValueError hatası alıyorum, bakar mısın",
    "fix the crash on empty input",
    "Rapor ekranı açılırken donuyor",
]
DEGIL = [
    "README'ye kurulum bölümü ekle",
    "Yeni bir satış raporu ekranı oluştur",
    "Metni daha resmi bir dille yaz",
    "Kullanıcı listesine arama kutusu ekle",
]


@pytest.mark.parametrize("goal", HATA)
def test_hata_duzeltme_isteginde_once_yeniden_uretme_testi(goal):
    assert project.is_bugfix(goal)
    p = project.planning_prompt(goal)
    assert project.REPRO_RULE in p and "ŞU AN KALIYOR" in p
    assert deep.REPRO_VERIFY in deep.verify_prompt(goal, "diff", deep.VERIFY_LENSES[0])


@pytest.mark.parametrize("goal", DEGIL)
def test_ozellik_isteginde_kural_eklenmez(goal):
    assert not project.is_bugfix(goal)
    assert project.REPRO_RULE not in project.planning_prompt(goal)
    assert deep.REPRO_VERIFY not in deep.verify_prompt(goal, "diff", deep.VERIFY_LENSES[0])


def test_derin_plan_istemi_kurali_tasir():
    """Derin Mod planı Proje planlama istemini kullanır (deep.plan_prompt) — kural oradan gelir."""
    p = deep.plan_prompt("div(1, 0) çöküyor, ValueError vermeli", [])
    assert project.REPRO_RULE in p


def test_kural_testi_degistirmeyi_yasaklar():
    assert "testi değiştirme" in project.REPRO_RULE and "zayıflat" in deep.REPRO_VERIFY
