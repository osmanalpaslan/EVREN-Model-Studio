"""Bozuk JSON bloğunu anahtar anahtar okuma (R-26). Girdiler 2026-11-07 gerçek Derin Mod koşusundan (qwen3.8-flash-next):
karışık tırnak, erken kapanan `]},`, uydurma ek alan → <bulgu> okunamıyor, "anla" 3 incelemeden 0-1'i sayılıyordu."""
from __future__ import annotations

from evren_studio.agent import deep, qa

GERCEK_BOZUK = """...açıklama metni...
<bulgu>
{"ozet": "calc.py'de yalnız add/sub var, div yok; import satırı (from calc import add, sub) güncellenmeli.", "dosyalar": ["calc.py: div(a, b) buraya eklenecek; b==0 için ValueError", "test_calc.py: import genişletilmeli"], "riskler": ["Bölme türü belirtilmedi; gerçek bölme (/) varsayılıyor", 'Sıfır kontrolü "b == 0" olmalı ki 0.0 de yakalansın', "Hata mesajı metni spesifikasyonu yok"]},
"riskler_dummy": null, "oneri": "calc.py'nin sonuna div fonksiyonunu ekle; sonra python -m pytest ile çalıştır.", "sorular": []}
</bulgu>"""


def test_gercek_bozuk_bulgu_okunur():
    d = deep._block(GERCEK_BOZUK, "bulgu")
    assert d and d["ozet"].startswith("calc.py'de yalnız add/sub")
    assert d["dosyalar"] == ["calc.py: div(a, b) buraya eklenecek; b==0 için ValueError", "test_calc.py: import genişletilmeli"]
    assert len(d["riskler"]) == 3 and d["riskler"][1] == 'Sıfır kontrolü "b == 0" olmalı ki 0.0 de yakalansın'
    assert d["oneri"].startswith("calc.py'nin sonuna") and d["sorular"] == []
    assert d.get("riskler_dummy") is None


def test_gecerli_json_aynen_ve_bloksuz_metin_uydurulmaz():
    ok = '<bulgu>{"ozet": "x", "sorular": ["a"]}</bulgu>'
    assert deep._block(ok, "bulgu") == {"ozet": "x", "sorular": ["a"]}
    assert deep._block("Hiç blok yok, düz yanıt.", "bulgu") is None              # tetiklenmemeli (R-22)
    assert deep._block('<bulgu>"ozet": "tek alan"</bulgu>', "bulgu") is None    # tek alan: güvenilmez → None


def test_qa_sonuc_yolu_degismez():
    raw = '<qa_sonuc>{"sonuc": "kaldi", "gerceklesen": "çıktı "yanlış" görünüyor", "kanit": "ekran"}</qa_sonuc>'
    d = qa._json_block(raw, qa._RES_RE)                     # kaçışsız tırnak: eski QA esnek yolu
    assert d["sonuc"] == "kaldi" and d["kanit"] == "ekran"
    assert qa.loose_object('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}
