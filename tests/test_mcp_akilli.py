"""MCP: gerektiğinde açma/boşta kapama, ücretli sağlayıcıda yasak, hata bekçisi (2026-10-19).

Kullanıcı kararları: MCP ihtiyaç duyulduğunda açılsın, duyulmadığında kapalı kalsın; ücretli
sağlayıcıyla MCP KESİNLİKLE çalışmasın; ajan düzenlemesinden sonra hatalar modele bildirilsin.
Gerçek ağ/program yok (sahte stdio sunucusu).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from evren_studio.agent import diagnostics, mcp, router

FAKE = str(Path(__file__).with_name("fake_mcp_server.py"))


def _cfg(**kw) -> mcp.McpServerConfig:
    base = dict(name="sahte", command=sys.executable, args=[FAKE], read_only_tools=["topla"],
                startup_timeout=20, call_timeout=5)
    base.update(kw)
    return mcp.McpServerConfig(**base)


@pytest.fixture()
def manager(tmp_path):
    m = mcp.McpManager(tmp_path / "veri")
    yield m
    m.close_all()


def _proj(root: Path, n_files: int, lines: int = 3) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for i in range(n_files):
        (root / f"m{i}.py").write_text("x = 1\n" * lines, encoding="utf-8")
    return root


# ---- gereklilik ---------------------------------------------------------------------------

def test_kod_sunucusu_kucuk_projede_sunulmaz_buyukte_ve_sembol_isinde_sunulur(tmp_path):
    cfg = _cfg(when="kod")
    small = mcp.project_profile(_proj(tmp_path / "kucuk", 2))
    big = mcp.project_profile(_proj(tmp_path / "buyuk", 6))
    assert mcp.needed(cfg, small, "README'yi düzelt")[0] is False
    assert mcp.needed(cfg, big, "README'yi düzelt")[0] is True
    assert mcp.needed(cfg, small, "hesapla fonksiyonunu yeniden adlandır")[0] is True
    assert mcp.needed(cfg, mcp.project_profile(tmp_path / "yok"), "yeniden adlandır")[0] is False


def test_web_sunucusu_yalniz_tarayici_isinde(tmp_path):
    cfg = _cfg(when="web")
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<button>Tamam</button>", encoding="utf-8")
    prof = mcp.project_profile(web)
    assert prof.web is True
    assert mcp.needed(cfg, prof, "başlığı değiştir")[0] is False                # tarayıcı gerektirmiyor
    assert mcp.needed(cfg, prof, "butona tıklayınca hata veriyor, düzelt")[0] is True
    plain = mcp.project_profile(_proj(tmp_path / "py", 6))
    assert mcp.needed(cfg, plain, "butonu düzelt")[0] is False                   # web projesi değil
    assert mcp.needed(cfg, plain, "http://localhost:8000 sayfasını aç")[0] is True


def test_package_json_web_bagimliligi_algilanir(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"react": "18"}}), encoding="utf-8")
    assert mcp.project_profile(tmp_path).web is True


def test_gerekmeyen_sunucu_baslatilmaz_ve_arac_sunulmaz(manager, tmp_path):
    ts = manager.toolset([_cfg(when="kod")], _proj(tmp_path / "p", 1), "yazım hatasını düzelt")
    assert ts.specs() == [] and ts.skipped and manager._clients == {}


# ---- tembel açılış, önbellek, boşta kapanma ------------------------------------------------------

def test_onbellekli_araclar_surec_baslatmadan_sunulur_ilk_cagrida_acilir(manager, tmp_path):
    cfg = _cfg()
    proj = _proj(tmp_path / "p", 1)
    manager.toolset([cfg], proj)                     # ilk kez: liste için açılır, önbelleğe yazılır
    assert manager.cached_tools(cfg)
    manager.close_all()
    m2 = mcp.McpManager(manager.data_dir)
    try:
        ts = m2.toolset([cfg], proj)
        assert "mcp__sahte__topla" in {s.name for s in ts.specs()}
        assert m2._clients == {}                      # süreç yok: araçlar önbellekten
        started = []
        ts.status = started.append
        assert ts.call("mcp__sahte__topla", {"a": 2, "b": 2})[0].startswith("Toplam: 4")
        assert m2.running("sahte", proj) is not None and started == ["MCP sunucusu açılıyor: sahte"]
    finally:
        m2.close_all()


def test_bosta_kalan_surec_kapanir_mesgulse_kapanmaz(manager, tmp_path):
    cfg = _cfg(idle_seconds=60)
    proj = _proj(tmp_path / "p", 1)
    ts = manager.toolset([cfg], proj)
    ts.call("mcp__sahte__topla", {"a": 1, "b": 1})
    key = manager._key("sahte", proj)
    now = manager._last_used[key]
    assert manager.reap_idle(now + 30) == []                      # 30 sn: hâlâ açık
    manager._busy[key] = 1
    assert manager.reap_idle(now + 120) == []                     # çağrı sürerken kapanmaz
    manager._busy[key] = 0
    client = manager.running("sahte", proj)
    assert manager.reap_idle(now + 120) == ["sahte"] and not client.alive
    assert ts.call("mcp__sahte__topla", {"a": 3, "b": 4})[0].startswith("Toplam: 7")   # yeniden açılır


def test_dene_onbellegi_tazeler(manager, tmp_path):
    cfg = _cfg()
    manager._save_tools(cfg, [{"name": "eski"}])
    tools, _secs = manager.test(cfg, tmp_path)
    assert {t["name"] for t in tools} >= {"topla"} and manager.cached_tools(cfg)[0]["name"] != "eski"


# ---- ücretli sağlayıcıda MCP yok ---------------------------------------------------------------

def test_yedekler_ayni_saglayiciyla_sinirli():
    prov = {"deepseek-v4-flash": "evren", "gemma-4-31b": "evren", "claude-sonnet-5-5": "anthropic"}.get
    assert router.same_provider(["gemma-4-31b", "claude-sonnet-5-5"], "deepseek-v4-flash", prov) == ["gemma-4-31b"]
    assert router.same_provider(["gemma-4-31b"], "claude-sonnet-5-5", prov) == []


def test_ucretli_saglayicida_mcp_arac_kumesi_yok(tmp_path, monkeypatch, fake_keyring):
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    from evren_studio.ui.app_context import AppContext

    ctx = AppContext()
    try:
        ctx.settings.mcp_servers = [_cfg().to_dict()]
        assert ctx.mcp_toolset(tmp_path, "x", provider="evren") is not None
        for paid in ("openai", "anthropic"):
            assert ctx.mcp_toolset(tmp_path, "x", provider=paid) is None
    finally:
        ctx.close()


# ---- hata bekçisi ----------------------------------------------------------------------------

def test_yerlesik_denetim_python_json_toml():
    assert diagnostics.builtin_problems("a.py", "def f(:\n  pass\n")[0].startswith("satır 1: sözdizimi")
    assert diagnostics.builtin_problems("a.py", "def f():\n    return 1\n") == []
    assert "geçersiz JSON" in diagnostics.builtin_problems("a.json", '{"a": 1,}')[0]
    assert diagnostics.builtin_problems("a.json", '{"a": 1}') == []
    assert diagnostics.builtin_problems("a.toml", "a = ")[0].startswith("geçersiz TOML")
    assert diagnostics.builtin_problems("README.md", "def (") == []          # kod değil → denetim yok


@pytest.mark.skipif(not (shutil.which("node") or Path(r"C:\Program Files\nodejs\node.exe").exists()),
                    reason="Node yok")
def test_yerlesik_denetim_javascript(tmp_path):
    (tmp_path / "a.js").write_text("function f( {\n", encoding="utf-8")
    assert diagnostics.builtin_problems("a.js", "x", tmp_path)
    (tmp_path / "b.js").write_text("function f() { return 1 }\n", encoding="utf-8")
    assert diagnostics.builtin_problems("b.js", "x", tmp_path) == []


# 2026-10-19 gerçek Serena (pyright) çıktısı
SERENA_OUT = json.dumps({"hata.py": {
    "Warning": {"<file>": [{"message": 'Import "requests" could not be resolved from source',
                            "range": {"start": {"line": 0}}, "code": "reportMissingModuleSource", "source": "Pyright"}]},
    "Error": {
        "topla": [{"message": '"c" is not defined', "range": {"start": {"line": 5}},
                   "code": "reportUndefinedVariable", "source": "Pyright"}],
        "<file>": [{"message": 'Type "Literal[\'metin\']" is not assignable to declared type "int"',
                    "range": {"start": {"line": 11}}, "code": "reportAssignmentType", "source": "Pyright"},
                   {"message": 'Argument missing for parameter "b"', "range": {"start": {"line": 12}},
                    "code": "reportCallIssue", "source": "Pyright"},
                   {"message": 'Import "numpy" could not be resolved', "range": {"start": {"line": 1}},
                    "code": "reportMissingImports", "source": "Pyright"}]}}})


def test_serena_teshisinden_yalniz_kesin_hatalar():
    probs = diagnostics.serena_problems(SERENA_OUT)
    assert probs == ['satır 6 (topla içinde): "c" is not defined [reportUndefinedVariable]',
                     'satır 13: Argument missing for parameter "b" [reportCallIssue]']
    assert diagnostics.serena_problems("{}") == [] and diagnostics.serena_problems("bozuk") == []
    ts_out = json.dumps({"a.ts": {"Error": {"f": [{"message": "Cannot find name 'y'.", "code": 2304,
                                                   "source": "typescript", "range": {"start": {"line": 2}}}],
                                            "<file>": [{"message": "Cannot find module 'lodash'", "code": 2307,
                                                        "source": "typescript", "range": {"start": {"line": 0}}}]}}})
    assert diagnostics.serena_problems(ts_out) == ["satır 3 (f içinde): Cannot find name 'y'. [2304]"]
    cs_out = json.dumps({"A.cs": {"Error": {"A/F": [
        {"message": "'yokDegisken' adı geçerli bağlamda yok", "code": "CS0103", "range": {"start": {"line": 1}}},
        {"message": "'Newtonsoft' türü veya ad alanı adı bulunamadı", "code": "CS0246", "range": {"start": {"line": 0}}}]}}})
    assert diagnostics.serena_problems(cs_out) == ["satır 2 (A/F içinde): 'yokDegisken' adı geçerli bağlamda yok [CS0103]"]


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
    (root / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    return root


def _tool_msg(client, i=1):
    return [m for m in client.calls[i]["messages"] if m["role"] == "tool"][-1]["content"]


def test_bekci_sozdizimi_hatasini_ayni_turda_modele_bildirir(db, proj):
    client = FakeClient([
        ChatResult(tool_calls=[call("edit_file", path="app.py", old_string="return 1", new_string="return (1")]),
        ChatResult(content="tamam", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, proj, mode="auto")
    runner.run(history)
    msg = _tool_msg(client)
    assert "HATA BEKÇİSİ" in msg and "sözdizimi" in msg


def test_bekci_gecerli_duzenlemede_sessiz_ve_kapatilabilir(db, proj):
    for check in (True, False):
        client = FakeClient([
            ChatResult(tool_calls=[call("edit_file", path="app.py", old_string="return 1", new_string="return 2")]),
            ChatResult(content="tamam", finish_reason="stop"),
        ])
        runner, history, _ = make_runner(db, client, proj, mode="auto", edit_check=check)
        runner.run(history)
        assert "HATA BEKÇİSİ" not in _tool_msg(client)
        (proj / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    client = FakeClient([
        ChatResult(tool_calls=[call("edit_file", path="app.py", old_string="return 1", new_string="return (1")]),
        ChatResult(content="tamam", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, proj, mode="auto", edit_check=False)
    runner.run(history)
    assert "HATA BEKÇİSİ" not in _tool_msg(client)                   # ayar kapalı


class _DiagToolset:
    """MCP teşhisi veren sahte araç kümesi (araç sunmaz)."""

    def __init__(self, problems):
        self.problems, self.asked = problems, []
        self.notes = []

    def specs(self, read_only_only=False):
        return []

    def get(self, name):
        return None

    def diagnostics(self, rel):
        self.asked.append(rel)
        return list(self.problems)


def test_bekci_sozdizimi_temizse_serena_teshisini_ekler(db, proj):
    ts = _DiagToolset(['satır 2 (f içinde): "c" is not defined [reportUndefinedVariable]'])
    client = FakeClient([
        ChatResult(tool_calls=[call("edit_file", path="app.py", old_string="return 1", new_string="return c")]),
        ChatResult(content="tamam", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, proj, mode="auto", mcp=ts)
    runner.run(history)
    assert ts.asked == ["app.py"] and '"c" is not defined' in _tool_msg(client)
    # sözdizimi hatası varken Serena'ya hiç sorulmaz (önce yerleşik)
    ts2 = _DiagToolset(["olmamalı"])
    client2 = FakeClient([
        ChatResult(tool_calls=[call("edit_file", path="app.py", old_string="return c", new_string="return (c")]),
        ChatResult(content="tamam", finish_reason="stop"),
    ])
    r2, h2, _ = make_runner(db, client2, proj, mode="auto", mcp=ts2)
    r2.run(h2)
    assert ts2.asked == [] and "sözdizimi" in _tool_msg(client2)


def test_serena_hazir_ayari_kod_projesinde_ve_teshisli():
    s = mcp.serena_config()
    assert s.when == "kod" and s.diagnostics_tool == "get_diagnostics_for_file"
    assert s.diagnostics_tool not in s.allowed_tools                  # modele sunulmaz, bekçi kullanır


# ---- hazır ayarlar, Playwright, yerel web sunucusu ---------------------------------------------

def test_eski_kayitli_serena_guncel_tanimdan_kurulur():
    old = {"name": "serena", "command": "{serena}", "args": ["start-mcp-server"], "enabled": False}
    cfg = mcp.configs_from_settings([old])[0]
    assert cfg.when == "kod" and cfg.diagnostics_tool and cfg.enabled is False
    assert "--context" in cfg.args                                      # güncel argümanlar
    own = {"name": "serena", "command": "C:/baska/serena.exe", "args": ["x"]}
    assert mcp.configs_from_settings([own])[0].command == "C:/baska/serena.exe"   # elle kurulan dokunulmaz


def test_playwright_hazir_ayari_guvenli():
    p = mcp.playwright_config()
    assert p.when == "web" and "--isolated" in p.args and "--headless" in p.args
    assert set(p.read_only_tools) <= {"browser_snapshot", "browser_console_messages",
                                      "browser_network_requests", "browser_wait_for"}
    for risky in ("browser_navigate", "browser_click", "browser_type", "browser_evaluate"):
        assert risky in p.allowed_tools and risky not in p.read_only_tools  # onaya tabi
    assert "--allow-unrestricted-file-access" not in p.args
    assert "omit" in p.args                                               # görüntü yanıtı yok (kota)


def test_yerel_web_sunucusu_gizli_dosyalari_vermez(tmp_path):
    import urllib.error
    import urllib.request

    (tmp_path / "index.html").write_text("<h1>merhaba</h1>", encoding="utf-8")
    (tmp_path / ".env").write_text("SIR=1", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x", encoding="utf-8")
    srv = mcp.ProjectWebServer(tmp_path)
    try:
        assert srv.url.startswith("http://127.0.0.1:")
        assert b"merhaba" in urllib.request.urlopen(srv.url + "index.html", timeout=5).read()
        for secret in (".env", ".git/config", "%2Eenv"):
            with pytest.raises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(srv.url + secret, timeout=5)
            assert e.value.code == 403
    finally:
        srv.close()


def test_playwright_turunda_yerel_adres_istemde(manager, tmp_path):
    proj = tmp_path / "web"
    proj.mkdir()
    (proj / "index.html").write_text("<button>x</button>", encoding="utf-8")
    cfg = _cfg(name="playwright", when="web", args=[FAKE, "{playwright_cli}"])
    ts = manager.toolset([cfg], proj, "butona tıklayınca ne oluyor tarayıcıda dene")
    assert ts.hints and "127.0.0.1" in ts.hints[0]
    note = mcp.prompt_section([mcp.tool_spec("playwright", {"name": "browser_snapshot"}, True)], ts.hints)
    assert "browser_console_messages" in note and "127.0.0.1" in note


def test_kart_node_yokken_node_kur_dugmesi(tmp_path, monkeypatch, fake_keyring):
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    QApplication.instance() or QApplication([])
    from evren_studio.ui.app_context import AppContext
    from evren_studio.ui.mcp_settings import McpSettingsCard

    ctx = AppContext()
    try:
        monkeypatch.setattr(mcp, "find_node", lambda: None)
        card = McpSettingsCard(ctx)
        card.load(ctx.settings)
        r = card.rows["playwright"]
        assert r["node"].isVisibleTo(card) and not r["install"].isVisibleTo(card)
        assert "Node.js gerekli" in r["status"].text()
        monkeypatch.setattr(mcp, "find_node", lambda: "node.exe")
        card._refresh()
        assert not r["node"].isVisibleTo(card) and r["install"].isVisibleTo(card)
    finally:
        ctx.close()
