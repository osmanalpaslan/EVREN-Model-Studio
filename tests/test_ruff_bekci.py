"""Hata bekçisinde ruff (Madde 20 A2, 2026-11-11): Serena kapalıyken de eksik import / tanımsız ad / yapı hatası
düzenlemeden hemen sonra modele bildirilir. YALNIZ kesin hatalar (E9,F63,F7,F82); stil ve kullanılmayan import yok (R-22)."""
from __future__ import annotations

from evren_studio.agent import diagnostics
from evren_studio.api.client import ChatResult
from tests.test_agent_runner import FakeClient, call
from tests.test_mcp_akilli import _tool_msg, make_runner, db, proj  # noqa: F401 — ortak düzenek


def test_tanimsiz_ad_ve_yapi_hatasi_bulunur():
    p = diagnostics.ruff_problems("a.py", "import json\n\ndef f(x):\n    return os.path.join(x, json.dumps(1))\n\nbreak\n")
    assert any("satır 4: F821" in x and "tanımsız ad" in x for x in p)
    assert any("satır 6: F701" in x for x in p)


def test_gecerli_kod_ve_stil_sorunlari_sessiz():
    stil = "import os, sys\nimport json\n\n\ndef f( x ):\n  y=1\n  return x\n"     # kullanılmayan import, biçim
    assert diagnostics.ruff_problems("a.py", stil) == []
    assert diagnostics.ruff_problems("a.py", "from x import *\n\nprint(bilinmeyen)\n") == []   # yıldız: yanlış alarm
    assert diagnostics.lint_problems("veri.json", '{"a": 1}') == [] and diagnostics.lint_problems("a.py", None) == []


def test_ruff_yoksa_sessizce_atlanir(monkeypatch):
    monkeypatch.setattr(diagnostics, "ruff_bin", lambda: None)
    assert diagnostics.ruff_problems("a.py", "print(tanimsiz)\n") == []


def test_ayni_satir_tekrarlanmaz():
    out = diagnostics.merge(["satır 2: F821 tanımsız ad"], ['satır 2: "c" is not defined', "satır 7: çağrı hatası"])
    assert out == ["satır 2: F821 tanımsız ad", "satır 7: çağrı hatası"]


def test_tur_akisinda_serena_olmadan_bildirilir(db, proj):  # noqa: F811
    client = FakeClient([
        ChatResult(tool_calls=[call("edit_file", path="app.py", old_string="return 1", new_string="return sayi")]),
        ChatResult(content="tamam", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, proj, mode="auto")
    runner.run(history)
    assert "HATA BEKÇİSİ" in _tool_msg(client) and "F821" in _tool_msg(client)
    temiz = FakeClient([
        ChatResult(tool_calls=[call("edit_file", path="app.py", old_string="return sayi", new_string="return 2")]),
        ChatResult(content="tamam", finish_reason="stop"),
    ])
    r2, h2, _ = make_runner(db, temiz, proj, mode="auto")
    r2.run(h2)
    assert "HATA BEKÇİSİ" not in _tool_msg(temiz)                    # tetiklenmeyen (R-22)


def test_paketleme_ruff_u_icerir():
    from pathlib import Path

    spec = (Path(__file__).resolve().parents[1] / "installer" / "evren_studio.spec").read_text(encoding="utf-8")
    assert 'with_name("ruff.exe")' in spec and '"tools"' in spec
