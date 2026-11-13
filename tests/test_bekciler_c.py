"""Madde 22 C bekçileri (2026-11-13): C1 bozma koruması, C2 iddia bekçisi, C3 hata düzeltmede önce yeniden üretme ipucu.

Her bekçi için tetiklenen ve tetiklenmeyen durum (R-22) ve en az bir gerçek koşucu akışı (R-31).
"""
from __future__ import annotations

import json

import pytest

from evren_studio.agent import claims, tools
from evren_studio.agent.runner import AgentEvents, AgentRunner
from evren_studio.api.client import ChatResult
from evren_studio.db import Database

GECERLI = "def f(x):\n    if x > 0:\n        return x\n    return -x\n"


def _box(tmp_path, name="a.py", text=GECERLI):
    (tmp_path / name).write_text(text, encoding="utf-8")
    return tools.ToolBox(tools.Workspace(tmp_path))


# ---- C1 bozma koruması --------------------------------------------------------------------------------------------

def test_saglam_dosyayi_bozan_duzenleme_yazilmaz_ve_satiri_gosterir(tmp_path):
    box = _box(tmp_path)
    with pytest.raises(tools.ToolError) as e:
        box.prepare_edit("a.py", "    if x > 0:", "    if x > 0")              # iki nokta unutuldu
    msg = str(e.value)
    assert "BOZARDI" in msg and "DEĞİŞTİRİLMEDİ" in msg and "    2>     if x > 0" in msg
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == GECERLI


def test_zaten_bozuk_dosyayi_duzeltme_ve_saglam_degisiklik_engellenmez(tmp_path):
    box = _box(tmp_path, text="def f(:\n    return 1\n")
    assert box.prepare_edit("a.py", "def f(:", "def f():").after.startswith("def f():")
    iki_hata = _box(tmp_path, name="c.py", text="def f(:\n    return 1\ndef g(:\n    return 2\n")
    assert iki_hata.prepare_edit("c.py", "def f(:", "def f():").after.count("def g(:") == 1   # adım adım düzeltme
    box2 = _box(tmp_path, name="b.py")
    assert "return -x * 1" in box2.prepare_edit("b.py", "return -x", "return -x * 1").after


def test_json_ustune_bozuk_yazma_reddedilir_yeni_dosya_ve_metin_serbest(tmp_path):
    box = _box(tmp_path, name="ayar.json", text='{"a": 1}\n')
    with pytest.raises(tools.ToolError, match="BOZARDI"):
        box.prepare_write("ayar.json", '{"a": 1,,}\n')
    assert box.prepare_write("yeni.json", "{bozuk").before is None              # yeni dosya: sonra bildirilir
    (tmp_path / "not.txt").write_text("x", encoding="utf-8")
    assert box.prepare_write("not.txt", "((((").after == "(((("                 # denetlenmeyen tür


def _client(script):
    class C:
        n = 0
        seen: list[list[dict]] = []

        def chat(self, model, messages, **kw):
            C.seen.append(messages)
            r = script[min(C.n, len(script) - 1)]
            C.n += 1
            return r

        def close(self):
            pass
    return C()


def _call(name, **args):
    return ChatResult(tool_calls=[{"id": f"c{name}{len(args)}", "name": name, "arguments": json.dumps(args)}],
                      finish_reason="tool_calls")


def _run(tmp_path, client, text, files=None, mode="auto", test_check=False):
    root = tmp_path / "p"
    root.mkdir(exist_ok=True)
    for rel, body in (files or {"a.py": GECERLI}).items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body, encoding="utf-8")
    db = Database(tmp_path / "t.db")
    sid = db.create_session("m", str(root), mode)
    db.add_session_message(sid, "user", text)
    out = AgentRunner(client, "m", session_id=sid, store=db, workspace=tools.Workspace(root), mode=mode,
                      stream=False, events=AgentEvents(), test_check=test_check).run(db.get_session_messages(sid))
    msgs = db.get_session_messages(sid)
    db.close()
    return root, out, msgs


def test_akista_bozan_duzenleme_reddedilir_model_duzeltir(tmp_path):
    c = _client([_call("edit_file", path="a.py", old_string="    if x > 0:", new_string="    if x >= 0"),
                 _call("edit_file", path="a.py", old_string="    if x > 0:", new_string="    if x >= 0:"),
                 ChatResult(content="Düzelttim.", finish_reason="stop")])
    root, _out, msgs = _run(tmp_path, c, "a.py'de sıfırı da pozitif say")
    tool_msgs = [m for m in msgs if m["role"] == "tool"]
    assert "BOZARDI" in tool_msgs[0]["content"] and "if x >= 0:" in (root / "a.py").read_text(encoding="utf-8")


# ---- C2 iddia bekçisi ---------------------------------------------------------------------------------------------

def _t(name, **meta):
    return {"role": "tool", "name": name, "content": "", "meta": meta}


def test_test_iddiasi_kanitsiz_ise_dureter_kanitliysa_degil(tmp_path):
    yaz = _t("edit_file", path="a.py")
    test_ok = _t("run_command", command="python -m pytest -q", exit_code=0)
    test_kotu = _t("run_command", command="python -m pytest -q", exit_code=1)
    iddia = "Değişikliği yaptım. Tüm testler başarıyla geçti."
    assert claims.check(iddia, [yaz], tmp_path) == claims.TEST_NUDGE                      # hiç test yok
    assert claims.check(iddia, [test_ok, yaz], tmp_path) == claims.TEST_NUDGE             # test yazmadan ÖNCE
    assert claims.check(iddia, [yaz, test_kotu], tmp_path) == claims.TEST_NUDGE           # test düştü
    assert claims.check(iddia, [yaz, test_ok], tmp_path) == ""                            # kanıtlı
    assert claims.check(iddia, [yaz], tmp_path, gate_passed=True) == ""                   # test bekçisi geçirdi
    assert claims.check("Çıktı: 4 passed in 0.1s", [yaz], tmp_path) == claims.TEST_NUDGE


@pytest.mark.parametrize("metin", ["Testleri çalıştıramadım; doğrulanmadı.", "Testlerin geçmesi bekleniyor.",
                                   "Testler geçti mi? Kontrol etmedim.", "Testleri siz çalıştırın.",
                                   "Dosyayı düzenledim.", "test_a.py içinde 3 test var.",
                                   "Testler geçmedi, hata satır 4'te."])
def test_olumsuz_ya_da_iddiasiz_cumleler_dureptmez(tmp_path, metin):
    assert claims.check(metin, [_t("edit_file", path="a.py")], tmp_path) == ""


def test_olusturuldu_denen_dosya_yoksa_dureter(tmp_path):
    (tmp_path / "var.py").write_text("x = 1\n", encoding="utf-8")
    assert claims.check("`var.py` dosyasını oluşturdum.", [], tmp_path) == ""
    out = claims.check("`rapor.xlsx` ve `var.py` oluşturuldu.", [], tmp_path)
    assert "`rapor.xlsx`" in out and "`var.py`" not in out
    assert claims.check("`rapor.xlsx` oluşturulamadı.", [], tmp_path) == ""               # olumsuz


def test_akista_kanitsiz_iddia_bir_kez_dureter_sonra_biter(tmp_path):
    c = _client([_call("edit_file", path="a.py", old_string="return -x", new_string="return abs(x)"),
                 ChatResult(content="Tamam, tüm testler geçti.", finish_reason="stop"),
                 ChatResult(content="Testleri çalıştırmadım; testler doğrulanmadı.", finish_reason="stop")])
    _root, out, _msgs = _run(tmp_path, c, "a.py'de mutlak değer kullan")
    nudges = [m[-1]["content"] for m in c.seen if "İDDİA BEKÇİSİ" in str(m[-1]["content"])]
    assert len(nudges) == 1, "tur başına bir kez"
    assert out.stopped == "done" and len(c.seen) == 3                       # dürtmeden sonra model dürüst yanıtla bitirdi


def test_iddia_tekrarlansa_da_tur_basina_bir_kez(tmp_path):
    c = _client([_call("edit_file", path="a.py", old_string="return -x", new_string="return abs(x)"),
                 ChatResult(content="Tüm testler geçti.", finish_reason="stop")])     # model iddiayı tekrarlıyor
    _root, out, _msgs = _run(tmp_path, c, "a.py'de mutlak değer kullan")
    assert sum("İDDİA BEKÇİSİ" in str(m[-1]["content"]) for m in c.seen) == 1 and out.stopped == "done"
    assert len(c.seen) == 3, "ikinci iddiada döngüye girmeden biter"


def test_test_bekcisi_gecirdiyse_iddia_kanitli(tmp_path):
    """Gerçek akış: test bekçisi tur sonunda projenin testlerini GERÇEKTEN çalıştırıp geçirdi → iddia kanıtlı."""
    files = {"a.py": GECERLI, "tests/test_a.py": "from a import f\n\n\ndef test_f():\n    assert f(-2) == 2\n"}
    c = _client([_call("edit_file", path="a.py", old_string="return -x", new_string="return abs(x)"),
                 ChatResult(content="Değiştirdim, testler geçti.", finish_reason="stop")])
    _root, out, _msgs = _run(tmp_path, c, "a.py'de mutlak değer kullan", files=files, test_check=True)
    assert not any("İDDİA BEKÇİSİ" in str(m[-1]["content"]) for m in c.seen) and out.stopped == "done"


def test_plan_kipinde_iddia_bekcisi_calismaz(tmp_path):
    c = _client([ChatResult(content="Plan: testler geçti sayılır.", finish_reason="stop")])
    _run(tmp_path, c, "planla", mode="plan")
    assert not any("İDDİA BEKÇİSİ" in str(m[-1]["content"]) for m in c.seen)


# ---- C3 hata düzeltmede önce yeniden üret -------------------------------------------------------------------------

def _hint_for(tmp_path, text, files, mode="auto"):
    c = _client([ChatResult(content="Tamam.", finish_reason="stop")])
    _run(tmp_path, c, text, files=files, mode=mode)
    return str(c.seen[0][-1]["content"])


def test_hata_duzeltmede_testli_projede_ipucu_verilir(tmp_path):
    files = {"a.py": GECERLI, "tests/test_a.py": "from a import f\n\ndef test_f():\n    assert f(-2) == 2\n"}
    assert "önce hatayı GÖSTEREN" in _hint_for(tmp_path, "f fonksiyonu negatiflerde yanlış sonuç veriyor, düzelt", files)


@pytest.mark.parametrize("text, files, mode", [
    ("a.py'ye yeni bir fonksiyon ekle", {"a.py": GECERLI, "tests/test_a.py": "def test_x():\n    pass\n"}, "auto"),
    ("f yanlış sonuç veriyor, düzelt", {"a.py": GECERLI}, "auto"),                       # testsiz proje
    ("f yanlış sonuç veriyor, düzelt", {"a.py": GECERLI, "tests/test_a.py": "def test_x():\n    pass\n"}, "plan"),
])
def test_hata_duzeltme_ipucu_gereksiz_yerde_cikmaz(tmp_path, text, files, mode):
    assert "önce hatayı GÖSTEREN" not in _hint_for(tmp_path, text, files, mode)
