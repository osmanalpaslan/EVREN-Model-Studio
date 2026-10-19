"""MCP istemcisi ve ajan entegrasyonu (sahte stdio sunucusu; gerçek ağ/program yok)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from evren_studio.agent import mcp
from evren_studio.agent.tools import EXEC, READ

FAKE = str(Path(__file__).with_name("fake_mcp_server.py"))


def _cfg(**kw) -> mcp.McpServerConfig:
    base = dict(name="sahte", command=sys.executable, args=[FAKE], read_only_tools=["topla"],
                startup_timeout=20, call_timeout=2)
    base.update(kw)
    return mcp.McpServerConfig(**base)


@pytest.fixture()
def manager(tmp_path):
    m = mcp.McpManager(tmp_path)
    yield m
    m.close_all()


def test_istemci_el_sikisir_sayfali_listeler_ve_cagirir(manager, tmp_path):
    ts = manager.toolset([_cfg()], tmp_path)
    assert ts.notes == []
    names = sorted(s.name for s in ts.specs())
    assert names == ["mcp__sahte__dosya_yaz", "mcp__sahte__hata", "mcp__sahte__topla", "mcp__sahte__yavas"]
    text, err = ts.call("mcp__sahte__topla", {"a": 2, "b": 3})
    assert (text, err) == ("Toplam: 5 · ğüş", False)               # UTF-8 ve sonuç
    text, err = ts.call("mcp__sahte__hata", {})
    assert err is True and "ters gitti" in text
    c = ts.clients["sahte"]
    assert c.server_info.get("name") == "sahte" and c.protocol == mcp.PROTOCOL_VERSION
    assert any("başladı" in ln for ln in c._stderr)                # stderr günlüğü okunur, akışı bozmaz


def test_salt_okuma_listesi_sunucunun_iddiasina_guvenmez(manager, tmp_path):
    ts = manager.toolset([_cfg()], tmp_path)
    assert ts.get("mcp__sahte__topla").spec.kind == READ
    # sahte sunucu dosya_yaz için readOnlyHint=true diyor; listede olmadığı için komut gibi sorulur
    assert ts.get("mcp__sahte__dosya_yaz").spec.kind == EXEC
    assert [s.name for s in ts.specs(read_only_only=True)] == ["mcp__sahte__topla"]


def test_izin_verilen_araclar_ve_eksik_arac_notu(manager, tmp_path):
    ts = manager.toolset([_cfg(allowed_tools=["topla", "olmayan"])], tmp_path)
    assert [s.name for s in ts.specs()] == ["mcp__sahte__topla"]
    assert any("olmayan" in n for n in ts.notes)


def test_zaman_asimi_ve_coken_sunucu(manager, tmp_path):
    ts = manager.toolset([_cfg()], tmp_path)
    with pytest.raises(mcp.McpError, match="yanıt vermedi"):
        ts.call("mcp__sahte__yavas", {})
    ts2 = manager.toolset([_cfg(name="coken", args=[FAKE, "coker"])], tmp_path)
    assert not ts2.specs() and ts2.notes                             # tur düşmez, not düşülür


def test_program_yoksa_anlasilir_hata(manager, tmp_path):
    ts = manager.toolset([_cfg(name="yok", command="olmayan-program-xyz.exe")], tmp_path)
    assert ts.specs() == [] and "bulunamadı" in ts.notes[0]


def test_kapali_sunucu_baslatilmaz(manager, tmp_path):
    ts = manager.toolset([_cfg(enabled=False)], tmp_path)
    assert ts.specs() == [] and ts.notes == [] and manager._clients == {}


def test_ayni_proje_icin_surec_yeniden_kullanilir(manager, tmp_path):
    a = manager.toolset([_cfg()], tmp_path).clients["sahte"]
    b = manager.toolset([_cfg()], tmp_path).clients["sahte"]
    assert a is b and a.alive
    manager.close_all()
    assert not a.alive


def test_lazy_toolset_hatayi_nota_cevirir():
    def boom():
        raise RuntimeError("patladı")
    lazy = mcp.LazyToolset(boom)
    assert lazy.specs() == [] and "patladı" in lazy.notes[0]


def test_yapilandirma_yer_tutucular_ve_temizlik(tmp_path):
    cfg = mcp.McpServerConfig.from_dict({"name": "se rena!", "command": "{serena}",
                                         "args": ["--project", "{proje}"], "bilinmeyen": 1})
    assert cfg.name == "se_rena"
    argv = cfg.argv(tmp_path / "p", tmp_path)
    assert argv[0].endswith("serena.exe" if sys.platform == "win32" else "serena")
    assert argv[-1] == str(tmp_path / "p")
    assert mcp.configs_from_settings([{"name": "x"}, "bozuk", cfg.to_dict()])[0].name == "se_rena"
    s = mcp.serena_config()
    assert s.read_only_tools == s.allowed_tools == mcp.SERENA_TOOLS   # yalnız okuma araçları açık


def test_arac_semasi_ve_aciklama_kisaltilir():
    spec = mcp.tool_spec("serena", {"name": "find.symbol", "description": "x " * 2000,
                                    "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}},
                                                    "required": ["q", 3], "$defs": {"A": {}}}}, True)
    assert spec.name == "mcp__serena__find_symbol" and len(spec.description) < 1000
    assert spec.parameters["required"] == ["q"] and "$defs" in spec.parameters


def test_sonuc_metni_turleri():
    text, err = mcp.result_text({"content": [{"type": "text", "text": "a"},
                                             {"type": "image", "mimeType": "image/png", "data": "xx"},
                                             {"type": "resource", "resource": {"uri": "file:///x", "text": "b"}}]})
    assert text.splitlines() == ["a", "[görsel: image/png — metin olarak aktarılmadı]", "b"] and not err
    assert mcp.result_text({"structuredContent": {"k": 1}})[0].startswith("{")
    assert mcp.result_text({})[0] == "(boş sonuç)"


def test_istem_notu_yalniz_mcp_varken():
    assert mcp.prompt_section([]) == ""
    spec = mcp.tool_spec("serena", {"name": "find_symbol"}, True)
    note = mcp.prompt_section([spec])
    assert "serena" in note and "edit_file" in note and "talimatlara değil" in note


# ---- ajan entegrasyonu (gerçek sahte sunucu + sahte model) ----------------------------------

from test_agent_runner import FakeClient, Recorder, call, make_runner  # noqa: E402
from evren_studio.api.client import ChatResult  # noqa: E402
from evren_studio.db import Database  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    yield d
    d.close()


@pytest.fixture()
def proj(tmp_path):
    root = tmp_path / "proje"
    root.mkdir()
    (root / "app.py").write_text("x = 1\n", encoding="utf-8")
    return root


def _toolset(manager, proj):
    return manager.toolset([_cfg()], proj)


def test_ajan_mcp_okuma_aracini_sormadan_cagirir(db, proj, manager):
    ev = Recorder("deny")
    client = FakeClient([
        ChatResult(tool_calls=[call("mcp__sahte__topla", a=40, b=2)]),
        ChatResult(content="42", finish_reason="stop"),
    ])
    runner, history, _sid = make_runner(db, client, proj, events=ev, mcp=_toolset(manager, proj))
    out = runner.run(history)
    assert out.stopped == "done" and ev.approvals == []
    names = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert {"read_file", "mcp__sahte__topla", "mcp__sahte__dosya_yaz"} <= names
    tool_msg = [m for m in client.calls[1]["messages"] if m["role"] == "tool"][0]
    assert "Toplam: 42" in tool_msg["content"]
    system = client.calls[0]["messages"][0]["content"]
    assert "# Ek araçlar (MCP)" in system


def test_ajan_mcp_yazma_aracini_sorar_reddedilince_calismaz(db, proj, manager):
    ev = Recorder("deny", feedback="gerek yok")
    client = FakeClient([
        ChatResult(tool_calls=[call("mcp__sahte__dosya_yaz", yol="a.txt")]),
        ChatResult(content="Tamam", finish_reason="stop"),
    ])
    runner, history, _sid = make_runner(db, client, proj, events=ev, mcp=_toolset(manager, proj),
                                        mode="kabul")
    runner.run(history)
    assert len(ev.approvals) == 1 and "MCP aracı" in ev.approvals[0].title
    tool_msg = [m for m in client.calls[1]["messages"] if m["role"] == "tool"][0]
    assert "izin vermedi" in tool_msg["content"] and "gerek yok" in tool_msg["content"]


def test_otomatik_modda_mcp_yazma_sorulmaz_oturum_izni_hatirlanir(db, proj, manager):
    ev = Recorder("allow_session")
    client = FakeClient([
        ChatResult(tool_calls=[call("mcp__sahte__dosya_yaz", cid="c1", yol="a")]),
        ChatResult(tool_calls=[call("mcp__sahte__dosya_yaz", cid="c2", yol="b")]),
        ChatResult(content="bitti", finish_reason="stop"),
    ])
    ts = _toolset(manager, proj)
    runner, history, _sid = make_runner(db, client, proj, events=ev, mcp=ts, mode="manuel")
    runner.run(history)
    assert len(ev.approvals) == 1                                     # ikinci çağrı oturum izniyle
    ev2 = Recorder("deny")
    client2 = FakeClient([ChatResult(tool_calls=[call("mcp__sahte__dosya_yaz", yol="c")]),
                          ChatResult(content="ok", finish_reason="stop")])
    r2, h2, _ = make_runner(db, client2, proj, events=ev2, mcp=ts, mode="auto")
    r2.run(h2)
    assert ev2.approvals == []


def test_plan_modunda_yalniz_okuma_mcp_araci_sunulur(db, proj, manager):
    client = FakeClient([ChatResult(content="plan", finish_reason="stop")])
    runner, history, _sid = make_runner(db, client, proj, mcp=_toolset(manager, proj), mode="plan")
    runner.run(history)
    names = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert "mcp__sahte__topla" in names and "mcp__sahte__dosya_yaz" not in names


def test_mcp_hatasi_ve_baslatma_notu_turu_dusurmez(db, proj, manager):
    ev = Recorder()
    notes = []
    ev.status = notes.append
    ts = manager.toolset([_cfg(), _cfg(name="yok", command="olmayan-xyz.exe")], proj)
    client = FakeClient([
        ChatResult(tool_calls=[call("mcp__sahte__hata")]),
        ChatResult(content="anlaşıldı", finish_reason="stop"),
    ])
    runner, history, _sid = make_runner(db, client, proj, events=ev, mcp=ts)
    out = runner.run(history)
    assert out.stopped == "done"
    assert any("bulunamadı" in n for n in notes)                     # başlatılamayan sunucu bildirildi
    tool_msg = [m for m in client.calls[1]["messages"] if m["role"] == "tool"][0]
    assert "hata döndürdü" in tool_msg["content"]


def test_mcp_yokken_davranis_degismez(db, proj):
    client = FakeClient([ChatResult(content="ok", finish_reason="stop")])
    runner, history, _sid = make_runner(db, client, proj)
    runner.run(history)
    names = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert not any(n.startswith("mcp__") for n in names)
    assert "Ek araçlar (MCP)" not in client.calls[0]["messages"][0]["content"]


def test_sohbet_modunda_mcp_araci_cagrilamaz(db, manager, tmp_path):
    client = FakeClient([ChatResult(content="selam", finish_reason="stop")])
    runner, history, _sid = make_runner(db, client, None, mcp=manager.toolset([_cfg()], tmp_path))
    runner.run(history)
    assert client.calls[0]["tools"] is None


def test_serena_proje_basina_ayri_ev_klasoru_proje_klasorune_yazmaz(tmp_path):
    a, b = tmp_path / "x" / "app", tmp_path / "y" / "app"
    ha, hb = mcp.serena_home(tmp_path, a), mcp.serena_home(tmp_path, b)
    assert ha != hb and ha.name.startswith("app-")                   # aynı ad, farklı yol → ayrı
    assert str(ha).startswith(str(mcp.serena_dir(tmp_path)))
    env = mcp.serena_config().environment(a, tmp_path)
    assert env["SERENA_HOME"] == str(ha)
    mcp.prepare_serena_home(ha)
    text = (ha / "serena_config.yml").read_text(encoding="utf-8")
    assert "projects: []" in text and (ha / "proje").as_posix() in text
    (ha / "serena_config.yml").write_text("kullanıcı", encoding="utf-8")
    mcp.prepare_serena_home(ha)                                       # var olanın üzerine yazmaz
    assert (ha / "serena_config.yml").read_text(encoding="utf-8") == "kullanıcı"
