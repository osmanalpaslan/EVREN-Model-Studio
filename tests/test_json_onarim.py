"""Model çıktısındaki bozuk JSON'u onarma (Madde 20 A1, 2026-11-11; R-26). json_repair (MIT, bağımlılıksız).
Örnekler gerçek koşulardan: 2026-11-07 Derin Mod qwen <bulgu> (karışık tırnak, erken `]},`), 2026-10-19 QA sonucu
(kaçışsız tırnak). Tetiklenmemesi gereken: blok yokken bir şey uydurulmaz; araç argümanları ONARILMAZ."""
from __future__ import annotations

from evren_studio.agent import deep, jsonfix, project, qa, scope
from tests.test_bozuk_json_blok import GERCEK_BOZUK


def test_gecerli_aynen_bozuk_onarilir_cop_none():
    assert jsonfix.obj('{"a": 1}') == {"a": 1}
    assert jsonfix.obj('{"sonuc": "kaldi", "kanit": "çıktı "yanlış" görünüyor"}') == \
        {"sonuc": "kaldi", "kanit": 'çıktı "yanlış" görünüyor'}
    assert jsonfix.obj("{'secim': 'B', 'neden': 'kapsamlı'}") == {"secim": "B", "neden": "kapsamlı"}
    assert jsonfix.obj('{"a": 1, "b": [1, 2') == {"a": 1, "b": [1, 2]}            # yarıda kesilmiş
    assert jsonfix.obj("{}") == {} and jsonfix.obj("[]") is None                  # geçerli boş nesne aynen
    for cop in ("", "   ", "Hiç blok yok", '"ozet": "tek alan"'):
        assert jsonfix.obj(cop) is None, cop                                    # uydurma yok (R-22)


def test_derin_bulgu_gercek_bozuk_cikti():
    d = deep._block(GERCEK_BOZUK, "bulgu")
    assert d["sorular"] == [] and len(d["riskler"]) == 3 and d["oneri"].startswith("calc.py'nin sonuna")


def test_kapsam_karari_bozuksa_ihlal_kacmaz():
    """Önceden bozuk JSON → [] (ihlal yok sayılıyordu)."""
    raw = "Sonuç: {'kapsam_disi': [{'dosya': 'tema.py', 'neden': 'istenmedi'}]}"
    out = scope.parse_response(raw, {"tema.py", "a.py"})
    assert [o.path for o in out] == ["tema.py"]
    assert scope.parse_response("Değişiklikler istekle uyumlu.", {"a.py"}) == []      # tetiklenmeyen


def test_inceleme_karari_bozuksa_dogru_okunur():
    ok, why = project.parse_review("{'tamam': false, 'neden': 'test \"eksik\" kalmış'}")
    assert ok is False and "eksik" in why
    assert project.parse_review('{"tamam": true, "neden": "iyi"}') == (True, "iyi")


def test_derin_yargic_bozuk_karar_artik_hep_a_sayilmaz():
    class St:
        goal = "x"
    st = deep.DeepState(goal="x", kind="is")
    plans = [lambda: None]
    calls = {"n": 0}

    def sub_with_model(model, prompt, marker):
        calls["n"] += 1
        return deep.SubResult(f"<plan>\n1. Görev {model} | ölçüt: ok | doğrulama: python -c 1\n</plan>", "done", "", {},
                              0.1, "", model)
    import evren_studio.agent.project as pj
    orig = pj.parse_plan
    pj.parse_plan = lambda text: [pj.Task(idx=1, title=text[:20], criteria="ok")]
    try:
        tasks = deep.plan(st, sub_with_model, ["m1", "m2"], lambda msgs: "{'secim': 'B', 'neden': 'daha iyi'}")
    finally:
        pj.parse_plan = orig
    assert st.chosen == "B" and tasks


def test_qa_sonucu_once_onarim_sonra_eski_yedekler():
    d = qa._json_block('<qa_sonuc>{"sonuc": "gecti", "gerceklesen": "4 "doğru"", "kanit": "x"}</qa_sonuc>', qa._RES_RE)
    assert d["sonuc"] == "gecti"


def test_arac_argumanlari_onarilmaz():
    """Yarıda kesilmiş write_file argümanı onarılırsa dosya eksik yazılır → koşucu ve metin protokolü jsonfix KULLANMAZ."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "evren_studio" / "agent"
    for f in ("runner.py", "textproto.py"):
        assert "jsonfix" not in (root / f).read_text(encoding="utf-8"), f


def test_obj_en_cok_bilgiyi_kurtaran_okumayi_secer():
    """2026-10-19 gerçek QA çıktısı: değer içinde `'""'` — json_repair metni kesip 'kanit'i boş bırakır; anahtar-sınırı
    okuyucu tamamını alır. obj() (kapsam, inceleme, yargıç da bunu kullanır) iyisini seçmeli."""
    raw = ('{"sonuc": "gecti",\n  "gerceklesen": "Selamla tıklandı; mesaj \'""\' kaldı",\n'
           '  "kanit": "evaluate: mesaj \'""\'; konsol temiz",\n  "ozet": "beklenen davranış sağlandı"}')
    d = jsonfix.obj(raw)
    assert "konsol temiz" in d["kanit"] and d["ozet"] == "beklenen davranış sağlandı"


def test_loads_cop_metinde_none_doner():
    assert jsonfix.obj("{bozuk ve anahtarsız") is None          # onarım listeye çevirir; nesne değil → yok
    for cop in ("Hiç blok yok", "düz yanıt, JSON değil"):
        assert jsonfix.loads(cop) is None, cop
    assert jsonfix.loads('{"a": [1,') == {"a": [1]}
