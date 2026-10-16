"""İzin politikası ve metin araç protokolü testleri."""
from __future__ import annotations

import json

from evren_studio.agent import textproto
from evren_studio.agent.permissions import (
    Decision,
    SessionPermissions,
    command_prefix,
    decide,
    is_chained,
)
from evren_studio.agent.tools import EXEC, META, READ, WRITE


def test_okuma_her_modda_serbest():
    for mode in ("plan", "onayli", "otomatik"):
        assert decide(mode, READ, SessionPermissions())[0] == Decision.ALLOW
        assert decide(mode, META, SessionPermissions())[0] == Decision.ALLOW


def test_plan_modu_yazma_ve_komutu_engeller():
    assert decide("plan", WRITE, SessionPermissions())[0] == Decision.DENY
    assert decide("plan", EXEC, SessionPermissions(), "dir")[0] == Decision.DENY


def test_onayli_mod_sorar_otomatik_mod_yalnizca_komutu_sorar():
    perms = SessionPermissions()
    assert decide("onayli", WRITE, perms)[0] == Decision.ASK
    assert decide("onayli", EXEC, perms, "git status")[0] == Decision.ASK
    assert decide("otomatik", WRITE, perms)[0] == Decision.ALLOW
    assert decide("otomatik", EXEC, perms, "git status")[0] == Decision.ASK, \
        "Komutlar hiçbir modda kendiliğinden çalışmamalı"


def test_oturum_izinleri():
    perms = SessionPermissions(allow_all_writes=True, command_prefixes={"python -m pytest"})
    assert decide("onayli", WRITE, perms)[0] == Decision.ALLOW
    assert decide("onayli", EXEC, perms, "python -m pytest -q")[0] == Decision.ALLOW
    assert decide("onayli", EXEC, perms, "python -m pip install x")[0] == Decision.ASK
    # zincirleme komut önek iznine rağmen sorulur
    assert decide("onayli", EXEC, perms, "python -m pytest; Remove-Item x")[0] == Decision.ASK
    assert decide("onayli", EXEC, perms, "python -m pytest | Out-File a")[0] == Decision.ASK


def test_komut_oneki():
    assert command_prefix("git status --short") == "git status"
    assert command_prefix("python -m pytest -q") == "python -m pytest"
    assert command_prefix("dir src") == "dir"
    assert is_chained("a && b") and not is_chained("git log --oneline")


# ---- metin protokolü ----------------------------------------------------------------


def test_bloklar_ayristirilir():
    text = (
        "Dosyayı okuyorum.\n<arac_cagrisi>\n"
        '{"name": "read_file", "arguments": {"path": "a.py"}}\n</arac_cagrisi>\n'
        "<arac_cagrisi>```json\n"
        '{"name": "list_files", "arguments": "{}"}\n```</arac_cagrisi>'
    )
    clean, calls, errors = textproto.parse_tool_calls(text)
    assert clean == "Dosyayı okuyorum."
    assert [c["name"] for c in calls] == ["read_file", "list_files"]
    assert json.loads(calls[0]["arguments"]) == {"path": "a.py"}
    assert errors == []


def test_bozuk_ve_yarim_blok_hata_verir():
    _c, calls, errors = textproto.parse_tool_calls("<arac_cagrisi>{bozuk}</arac_cagrisi>")
    assert not calls and "JSON" in errors[0]
    clean, calls, errors = textproto.parse_tool_calls('Tamam <arac_cagrisi>{"name": "read_file"')
    assert clean == "Tamam" and not calls and errors


def test_akista_bloklar_gizlenir():
    assert textproto.display_text('Merhaba <arac_cagrisi>{"name":') == "Merhaba "
    assert textproto.display_text("Merhaba <arac_ca") == "Merhaba "
    assert textproto.display_text("Düz metin") == "Düz metin"


def test_sonuc_ve_cagri_bicimi():
    block = textproto.render_call("read_file", '{"path": "x"}')
    _c, calls, _e = textproto.parse_tool_calls(block)
    assert calls[0]["name"] == "read_file"
    assert 'durum="hata"' in textproto.render_result("x", "olmadı", False)
