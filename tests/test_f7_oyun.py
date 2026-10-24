"""F7 oyun (2026-10-24): araç bulma, godot-mcp ön ayarı (E9), Poly Haven API, convert_model, Godot şablonu,
güvenilmeyen klasöre .gdignore, oyun araçlarının yalnız gerektiğinde sunulması (R-22). Ağ yok (sahte aktarım);
Blender kuruluysa kısa bir gerçek dönüştürme."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import httpx
import pytest

from evren_studio.agent import gametools, godot_sablon as gs, mcp, polyhaven, untrusted as untr
from evren_studio.agent.runner import AgentEvents, AgentRunner
from evren_studio.agent.tools import Workspace
from evren_studio.api.client import ChatResult
from evren_studio.db import Database


def fake_tools(tmp: Path) -> Path:
    t = tmp / "araclar"
    (t / "godot" / "editor_data" / "export_templates" / "4.7.2.stable").mkdir(parents=True)
    (t / "godot" / "Godot_v4.7.2-stable_win64.exe").write_bytes(b"")
    (t / "godot" / "Godot_v4.7.2-stable_win64_console.exe").write_bytes(b"")
    (t / "blender" / "blender-5.2.3-windows-x64").mkdir(parents=True)
    (t / "blender" / "blender-5.2.3-windows-x64" / "blender.exe").write_bytes(b"")
    (t / "godot-mcp" / "build").mkdir(parents=True)
    (t / "godot-mcp" / "build" / "index.js").write_text("", encoding="utf-8")
    return t


def test_arac_bulma_ve_sablon_durumu(tmp_path):
    t = fake_tools(tmp_path)
    g = gametools.find_godot(str(t))
    assert g.endswith("_console.exe") and gametools.find_godot(str(t), console=False).endswith("win64.exe")
    assert gametools.find_blender(str(t)).endswith("blender.exe") and gametools.find_godot_mcp(str(t))
    assert not gametools.templates_ready(g)                                  # şablon dosyası yok
    (t / "godot" / "editor_data" / "export_templates" / "4.7.2.stable" / "windows_release_x86_64.exe").write_bytes(b"")
    assert gametools.templates_ready(g)
    sec = gametools.prompt_section(str(t))
    assert "Godot 4.7.2" in sec and "convert_model" in sec and "şablonları kurulu" in sec


def test_kurulu_degilse_istem_kendin_indirme_der(tmp_path, monkeypatch):
    monkeypatch.setattr(gametools, "tools_dirs", lambda setting="": [])
    monkeypatch.setattr(gametools.shutil, "which", lambda n: None)
    assert "kurulu değil" in gametools.prompt_section() and "indirmeye çalışma" in gametools.prompt_section()


# ---- E9: godot-mcp ön ayarı ------------------------------------------------------------------------

def test_godot_mcp_onayari_ve_ne_zaman(tmp_path, monkeypatch):
    t = fake_tools(tmp_path)
    monkeypatch.setattr(gametools, "tools_dirs", lambda setting="": [t])
    cfg = mcp.godot_config()
    assert "launch_editor" not in cfg.allowed_tools and "run_project" in cfg.allowed_tools   # editör açılmaz
    argv = cfg.argv(tmp_path, tmp_path)
    assert argv[-1].endswith("index.js") and cfg.environment(tmp_path, tmp_path)["GODOT_PATH"].endswith(".exe")
    assert "godot" in mcp.PRESETS and mcp.godot_ready(tmp_path)
    back = mcp.configs_from_settings([{**cfg.to_dict(), "enabled": False}])[0]
    assert back.name == "godot" and back.when == "godot" and back.enabled is False
    proj = tmp_path / "oyun"
    proj.mkdir()
    assert mcp.needed(cfg, mcp.project_profile(proj), "dosyayı düzelt")[0] is False         # tetiklenmemeli
    assert mcp.needed(cfg, mcp.project_profile(proj), "godot sahnesi kur")[0] is True
    (proj / "project.godot").write_text("", encoding="utf-8")
    assert mcp.needed(cfg, mcp.project_profile(proj), "dosyayı düzelt")[0] is True


# ---- Poly Haven ------------------------------------------------------------------------------------

def ph_client(seen: list):
    assets = {"Barrel_01": {"name": "Barrel 01", "categories": ["industrial"], "tags": ["wood"], "download_count": 9},
              "Sword_01": {"name": "Kılıç", "categories": ["weapons"], "tags": ["sword", "medieval"],
                           "download_count": 5, "polycount": 1200}}
    files = {"gltf": {"1k": {"gltf": {"url": "https://dl.polyhaven.org/Sword_01_1k.gltf", "size": 10,
                                       "include": {"textures/diff.jpg": {"url": "https://dl.polyhaven.org/diff.jpg", "size": 5},
                                                   "../kotu.txt": {"url": "https://dl.polyhaven.org/k", "size": 1}}}},
                      "4k": {"gltf": {"url": "https://dl.polyhaven.org/x", "size": 999_000_000}}}}

    def handler(req: httpx.Request):
        seen.append(req.headers.get("user-agent"))
        if req.url.path == "/assets":
            return httpx.Response(200, json=assets)
        if req.url.path == "/files/Sword_01":
            return httpx.Response(200, json=files)
        if req.url.path.startswith("/files/"):
            return httpx.Response(404)
        return httpx.Response(200, content=b"veri")
    return httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": polyhaven.USER_AGENT})


def test_polyhaven_arama_indirme_ve_guvenlik(tmp_path):
    seen: list = []
    c = ph_client(seen)
    out = polyhaven.search("sword", client=c)
    assert "Sword_01: Kılıç" in out and "1200 üçgen" in out and "Barrel" not in out
    assert "bulunamadı" in polyhaven.search("uzay gemisi", client=c)
    with pytest.raises(polyhaven.PolyHavenError, match="Geçersiz dosya yolu"):        # ../ ile dışarı yazamaz
        polyhaven.download("Sword_01", tmp_path / "a", client=c)
    assert not (tmp_path / "kotu.txt").exists()
    with pytest.raises(polyhaven.PolyHavenError, match="Çok büyük"):
        polyhaven.download("Sword_01", tmp_path / "b", resolution="4k", client=c)
    with pytest.raises(polyhaven.PolyHavenError, match="Böyle bir varlık yok"):
        polyhaven.download("Yok_01", tmp_path / "c", client=c)
    assert all(ua == polyhaven.USER_AGENT for ua in seen)                    # ToS 2.4: uygulamaya özgü UA


def test_polyhaven_indirme_kaynak_notu(tmp_path):
    files = {"gltf": {"1k": {"gltf": {"url": "https://dl.polyhaven.org/Rock_1k.gltf", "size": 3,
                                       "include": {"textures/r.jpg": {"url": "https://dl.polyhaven.org/r.jpg", "size": 3}}}}}}

    def handler(req):
        return httpx.Response(200, json=files) if req.url.path == "/files/Rock_01" else httpx.Response(200, content=b"abc")
    c = httpx.Client(transport=httpx.MockTransport(handler))
    written = polyhaven.download("Rock_01", tmp_path / "rock", client=c)
    assert {p.name for p in written} == {"Rock_1k.gltf", "r.jpg"}
    assert "Poly Haven (CC0)" in (tmp_path / "rock" / "KAYNAK.txt").read_text(encoding="utf-8")


# ---- koşucu: araçlar yalnız oyun işinde, convert_model güvenliği -----------------------------------

class Script:
    def __init__(self, seq):
        self.seq = list(seq)
        self.tools, self.systems = [], []

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, on_reasoning=None, tools=None, **kw):
        self.tools.append([t["function"]["name"] for t in tools or []])
        self.systems.append(messages[0]["content"])
        return self.seq.pop(0) if self.seq else ChatResult(content="bitti", finish_reason="stop")


def call(tool, cid="c1", **args):
    return ChatResult(content="", tool_calls=[{"id": cid, "name": tool, "arguments": json.dumps(args)}],
                      finish_reason="tool_calls")


def run(root, seq, **kw):
    db = Database(root / ".t.db")
    sid = db.create_session("m", str(root))
    db.add_session_message(sid, "user", "görev")
    c = Script(seq)
    r = AgentRunner(c, "m", session_id=sid, store=db, events=AgentEvents(), workspace=Workspace(root), mode="auto",
                    stream=False, **kw)
    r.run(db.get_session_messages(sid))
    tools = [m["content"] for m in db.get_session_messages(sid) if m["role"] == "tool"]
    db.close()
    return c, tools


def test_oyun_araclari_yalniz_istenince(tmp_path):
    c, _ = run(tmp_path, [ChatResult(content="bitti", finish_reason="stop")])
    assert "convert_model" not in c.tools[0] and "# Oyun araçları" not in c.systems[0]
    c2, _ = run(tmp_path, [ChatResult(content="bitti", finish_reason="stop")], game_tools=True)
    assert {"convert_model", "polyhaven_search", "polyhaven_download"} <= set(c2.tools[0])
    assert "# Oyun araçları" in c2.systems[0]


def test_convert_model_guvenligi_ve_sonuc(tmp_path, monkeypatch):
    (tmp_path / "mods").mkdir()
    (tmp_path / "mods" / "a.blend").write_bytes(b"BLENDER")
    monkeypatch.setattr(gametools, "find_blender", lambda setting="": None)
    _c, tools = run(tmp_path, [call("convert_model", path="mods/a.blend")], game_tools=True)
    assert "Blender kurulu değil" in tools[0]
    monkeypatch.setattr(gametools, "find_blender", lambda setting="": "blender.exe")
    seen = []

    def fake_run(argv, **kw):
        seen.append(argv)
        out = Path(argv[argv.index("--") + 2])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"glb")
        info = {"nesne": 1, "yuz_once": 100, "yuz_sonra": 50, "doku": 0, "kucultulen_doku": 0, "boyut_kb": 1,
                "uyarilar": []}
        return subprocess.CompletedProcess(argv, 0, "SONUC " + json.dumps(info), "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    d = [str(tmp_path / "mods")]
    _c, tools = run(tmp_path, [call("convert_model", path="mods/a.blend", ratio=0.5),
                               call("convert_model", "c2", path="mods/a.blend", output="mods/x.glb"),
                               call("convert_model", "c3", path="mods/a.blend", output="a.fbx")],
                    game_tools=True, untrusted=d)
    assert "yüz 100 → 50" in tools[0] and (tmp_path / "assets" / "a.glb").is_file()   # güvenilmeyen GİRDİ serbest
    assert "--disable-autoexec" in seen[0] and "--factory-startup" in seen[0]
    assert "güvenilmeyen" in tools[1] and len(seen) == 1                     # güvenilmeyen ÇIKTI yasak
    assert ".glb veya .gltf" in tools[2]
    assert (tmp_path / "mods" / ".gdignore").exists()                        # Godot güvenilmeyeni içe aktarmaz


def test_godot_sablonu_dosyalari(tmp_path):
    gs.yeni_proje(tmp_path, "Alev Kılıcı!", "assets/k.glb")
    assert gs.safe_name("Alev Kılıcı!") == "Alev_K_l_c"
    pr = (tmp_path / "export_presets.cfg").read_text(encoding="utf-8")
    assert "progressive_web_app/enabled=true" in pr and 'platform="Windows Desktop"' in pr and "include_filter" in pr
    assert "gl_compatibility" in (tmp_path / "project.godot").read_text(encoding="utf-8")
    assert 'path="res://assets/k.glb"' in (tmp_path / "main.tscn").read_text(encoding="utf-8")
    gs.yeni_proje(tmp_path / "bos")
    assert "CSGBox3D" in (tmp_path / "bos" / "main.tscn").read_text(encoding="utf-8")


def test_gdignore_isaretlemede(tmp_path):
    (tmp_path / "m").mkdir()
    untr.ensure_gdignore([str(tmp_path / "m"), str(tmp_path / "yok")])
    assert (tmp_path / "m" / ".gdignore").exists() and not (tmp_path / "yok").exists()


@pytest.mark.skipif(not gametools.find_blender(), reason="Blender kurulu değil")
def test_gercek_blender_donusturme(tmp_path):
    obj = tmp_path / "k.obj"
    obj.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nv 0 0 1\nf 1 2 3\nf 1 2 4\nf 1 3 4\nf 2 3 4\n", encoding="utf-8")
    script = Path(gametools.__file__).with_name("blender_donustur.py")
    r = subprocess.run([gametools.find_blender(), "--background", "--factory-startup", "--disable-autoexec",
                        "-noaudio", "--python", str(script), "--", str(obj), str(tmp_path / "k.glb"), "1", "0"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    line = next(ln for ln in r.stdout.splitlines() if ln.startswith("SONUC "))
    info = json.loads(line[6:])
    assert info["yuz_once"] == 4 and (tmp_path / "k.glb").stat().st_size > 100


# ---- oturum: oyun araçları ne zaman ------------------------------------------------------------------

@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    yield app, w
    w.close()


def test_oturum_oyun_araclari_karari(win, tmp_path):
    _app, w = win
    s = w.session
    root = tmp_path / "p"
    root.mkdir()
    h = lambda t: [{"role": "user", "content": t}]   # noqa: E731
    assert not s._wants_game_tools(root, "kod", h("hesap.py'deki hatayı düzelt"))
    assert not s._wants_game_tools(root, "kod", h("oyun.py'yi çalıştır"))                  # dosya adı sayılmaz
    assert s._wants_game_tools(root, "kod", h("bu FBX modeli oyuna ekle"))
    assert s._wants_game_tools(root, "oyun", h("bir şey yap"))
    assert not s._wants_game_tools(None, "oyun", h("x"))
    (root / "project.godot").write_text("", encoding="utf-8")
    assert s._wants_game_tools(root, "kod", h("hesap.py'deki hatayı düzelt"))


def test_godot_export_araci(tmp_path, monkeypatch):
    from evren_studio.agent import godot_sablon

    monkeypatch.setattr(gametools, "find_godot", lambda setting="", console=True: "godot.exe")
    monkeypatch.setattr(gametools, "templates_ready", lambda g: True)
    _c, tools = run(tmp_path, [call("godot_export")], game_tools=True)
    assert "project.godot yok" in tools[0]
    (tmp_path / "project.godot").write_text("", encoding="utf-8")
    calls = []

    def fake(godot, kok, ad="oyun", hedef="ikisi"):
        calls.append((ad, hedef))
        return {"import": 0, "exe": str(kok / "build/windows/x.exe"), "web": str(kok / "build/web/index.html"),
                "log": {"import": "", "exe": "", "web": "ERROR: No loader found for resource: res://a.glb"}}
    monkeypatch.setattr(godot_sablon, "disa_aktar", fake)
    _c, tools = run(tmp_path, [call("godot_export", target="pwa", name="Kılıç Oyunu")], game_tools=True)
    assert calls[-1] == ("K_l_Oyunu", "web") and "export_presets.cfg hazır" in tools[0]
    assert "No loader found" in tools[0] and "düzelt" in tools[0]                # hata satırı modele gider
    (tmp_path / "export_presets.cfg").write_text("benim", encoding="utf-8")
    run(tmp_path, [call("godot_export")], game_tools=True)
    assert (tmp_path / "export_presets.cfg").read_text(encoding="utf-8") == "benim"   # kullanıcınınkine dokunmaz


def test_guvenilmeyen_klasore_yazma_engeli(tmp_path):
    (tmp_path / "mods").mkdir()
    _c, tools = run(tmp_path, [call("write_file", path="mods/x.txt", content="a"),
                               call("write_file", "c2", path="notlar.txt", content="b")],
                    untrusted=[str(tmp_path / "mods")])
    assert "Güvenilmeyen klasöre yazılamaz" in tools[0] and not (tmp_path / "mods" / "x.txt").exists()
    assert (tmp_path / "notlar.txt").read_text(encoding="utf-8") == "b"
