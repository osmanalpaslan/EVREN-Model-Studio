"""F7 kabul ölçütü: örnek mod → Godot sahnesi → EXE ve PWA çıktısı; PWA Playwright'ta açılır. pytest toplamaz.

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_oyun_real_api.py hat            # modelsiz, belirlenimli hat
    .\\.venv\\Scripts\\python.exe -u tests\\e2e_oyun_real_api.py ajan [model]   # gerçek API: ajan aynı işi yapar

Gerekenler (araç klasörü, gametools): Godot 4.7.2 + dışa aktarma şablonları, Blender 5.2.3; Playwright MCP
(build/mcp_data altında, tests/e2e_mcp_real_api.py kurulumu). "hat" adımları:
 1. Blender ile örnek "mod" üret (mods/alev_kilici/kilic.obj) + gömülü otomatik betikli kotu.blend (çalışırsa İZ yazar)
 2. mods/ güvenilmeyen; convert_model ARACI (koşucu üzerinden): kilic.obj → assets/kilic.glb (oran 0.5, doku 1024),
    kotu.blend → assets/kotu.glb — İZ oluşmamalı (--disable-autoexec)
 3. Godot projesi (godot_sablon) → --import → EXE + Web/PWA
 4. EXE ekransız 120 kare çalışır, çıkış 0
 5. PWA 127.0.0.1'de yayınlanır, Playwright (Edge) açar: Godot motoru başlar, tuval var, manifest + service worker
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from evren_studio.agent import gametools, godot_sablon as gs  # noqa: E402

URET = """import bpy, sys
a = sys.argv[sys.argv.index("--") + 1:]
obj_yolu, blend_yolu, iz = a[0], a[1], a[2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cylinder_add(vertices=48, depth=3, radius=0.08, location=(0, 0, 0.5))
bpy.ops.mesh.primitive_cube_add(size=0.5, location=(0, 0, -1.1))
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.15, location=(0, 0, -1.5))
bpy.ops.wm.obj_export(filepath=obj_yolu)
t = bpy.data.texts.new("kotu_niyet.py")
t.write("open(r'" + iz + "', 'w').write('calisti')\\n")
t.use_module = True                       # .blend açılınca otomatik çalışır (autoexec açıksa)
bpy.ops.wm.save_as_mainfile(filepath=blend_yolu)
print("URETILDI")
"""


def uret_mod(proj: Path) -> Path:
    blender = gametools.find_blender()
    mod = proj / "mods" / "alev_kilici"
    mod.mkdir(parents=True, exist_ok=True)
    script = proj.parent / "_uret_mod.py"
    script.write_text(URET, encoding="utf-8")
    r = subprocess.run([blender, "--background", "--factory-startup", "-noaudio", "--python", str(script), "--",
                        str(mod / "kilic.obj"), str(mod / "kotu.blend"), str(proj / "IZ.txt")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    if "URETILDI" not in (r.stdout or ""):
        raise RuntimeError("örnek mod üretilemedi: " + (r.stderr or r.stdout)[-400:])
    (mod / "README.md").write_text("# Alev Kılıcı\nKılıç modeli (OBJ). Kurulum: setup.bat çalıştırın.\n",
                                   encoding="utf-8")
    return mod


def exe_calisir(exe: str) -> tuple[bool, str]:
    try:
        r = subprocess.run([exe, "--headless", "--quit-after", "120"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=90)
    except subprocess.TimeoutExpired:
        return False, "zaman aşımı"
    out = (r.stdout or "") + (r.stderr or "")
    hatalar = [ln for ln in out.splitlines() if "ERROR" in ln]
    return r.returncode == 0 and not hatalar, f"çıkış {r.returncode}; " + " | ".join(hatalar[:3])


def pwa_acilir(web_dir: Path, data_dir: Path) -> tuple[bool, dict]:
    from evren_studio.agent import mcp

    srv = mcp.ProjectWebServer(web_dir)
    cfg = mcp.playwright_config()
    client = mcp.McpClient(cfg.argv(web_dir, data_dir), env=cfg.environment(web_dir, data_dir), name="playwright")
    info: dict = {}
    try:
        client.start(timeout=90)
        url = f"http://127.0.0.1:{srv.port}/index.html"
        client.call_tool("browser_navigate", {"url": url}, timeout=90)
        client.call_tool("browser_wait_for", {"time": 8}, timeout=60)
        cons, _ = mcp.result_text(client.call_tool("browser_console_messages", {}, timeout=60))
        js = ("() => { const c = document.querySelector('canvas'); const m = document.querySelector('link[rel=manifest]');"
              " return JSON.stringify({canvas: !!c, w: c ? c.width : 0, h: c ? c.height : 0,"
              " manifest: m ? m.getAttribute('href') : null, sw: 'serviceWorker' in navigator}); }")
        ev, _ = mcp.result_text(client.call_tool("browser_evaluate", {"function": js}, timeout=60))
        info["konsol"] = cons[-1500:]
        info["sayfa"] = ev[-600:]
    finally:
        client.close()
        srv.close()
    sayfa = info.get("sayfa", "").replace(" ", "").replace("\\", "")
    konsol = info.get("konsol", "")
    hatalar = [ln for ln in konsol.splitlines() if "ERROR" in ln or "Failed loading" in ln]
    info["hatalar"] = hatalar[:5]
    ok = "Godot Engine v4.7" in konsol and '"canvas":true' in sayfa and not hatalar
    return ok, info


def hat() -> int:
    from evren_studio.agent.runner import AgentEvents, AgentRunner
    from evren_studio.agent.tools import Workspace
    from evren_studio.api.client import ChatResult
    from evren_studio.db import Database

    base = ROOT / "build" / "oyun" / "hat"
    shutil.rmtree(base, ignore_errors=True)
    proj = base / "proje"
    proj.mkdir(parents=True)
    t0 = time.monotonic()
    sonuc: list[tuple[str, bool, str]] = []
    uret_mod(proj)
    sonuc.append(("örnek mod üretildi (OBJ + gömülü betikli .blend)", True, ""))

    def cagri(i, **a):
        return ChatResult(content="", tool_calls=[{"id": f"c{i}", "name": "convert_model", "arguments": json.dumps(a)}],
                          finish_reason="tool_calls")

    class Script:
        seq = [cagri(1, path="mods/alev_kilici/kilic.obj", output="assets/kilic.glb", ratio=0.5, max_texture=1024),
               cagri(2, path="mods/alev_kilici/kotu.blend", output="assets/kotu.glb"),
               cagri(3, path="mods/alev_kilici/kilic.obj", output="mods/alev_kilici/cikti.glb"),
               ChatResult(content="bitti", finish_reason="stop")]

        def chat(self, model, messages, **kw):
            return self.seq.pop(0)
    db = Database(base / "t.db")
    sid = db.create_session("m", str(proj))
    db.add_session_message(sid, "user", "modeli dönüştür")
    runner = AgentRunner(Script(), "m", session_id=sid, store=db, events=AgentEvents(), workspace=Workspace(proj),
                         mode="auto", stream=False, untrusted=[str(proj / "mods")], game_tools=True)
    runner.run(db.get_session_messages(sid))
    tools = [m["content"] for m in db.get_session_messages(sid) if m["role"] == "tool"]
    db.close()
    sonuc.append(("convert_model: OBJ → GLB (poligon azaltıldı)", (proj / "assets" / "kilic.glb").is_file()
                  and "yüz" in tools[0], tools[0][:160]))
    sonuc.append((".blend dönüştürüldü, gömülü betik ÇALIŞMADI", (proj / "assets" / "kotu.glb").is_file()
                  and not (proj / "IZ.txt").exists(), tools[1][:120]))
    sonuc.append(("çıktı güvenilmeyen klasöre yazılamaz", "güvenilmeyen" in tools[2], tools[2][:100]))
    gs.yeni_proje(proj, "alev_kilici", "assets/kilic.glb")
    r = gs.disa_aktar(gametools.find_godot(), proj, "alev_kilici")
    sonuc.append(("Godot içe aktarma", r["import"] == 0, ""))
    sonuc.append(("EXE dışa aktarıldı", bool(r["exe"]), (r["log"]["exe"] or "")[-160:]))
    web = proj / "build" / "web"
    sonuc.append(("PWA dosyaları (manifest, service worker)", bool(r["web"]) and (web / "index.manifest.json").is_file()
                  and (web / "index.service.worker.js").is_file(), ""))
    if r["exe"]:
        ok, d = exe_calisir(r["exe"])
        sonuc.append(("EXE ekransız 120 kare çalıştı", ok, d))
    if r["web"]:
        ok, info = pwa_acilir(web, ROOT / "build" / "mcp_data")
        sonuc.append(("PWA Playwright'ta açıldı (Godot başladı, tuval)", ok, info.get("sayfa", "")[-200:]))
        (base / "pwa_konsol.txt").write_text(info.get("konsol", ""), encoding="utf-8")
    return rapor("hat", sonuc, time.monotonic() - t0, base)


def rapor(ad: str, sonuc, sure: float, base: Path) -> int:
    gecen = sum(1 for _n, ok, _d in sonuc if ok)
    for n, ok, d in sonuc:
        print(f"{'GEÇTİ' if ok else 'KALDI'} | {n}" + (f" | {d}" if d and not ok else ""), flush=True)
    print(f"SONUÇ ({ad}): {gecen}/{len(sonuc)} · {sure:.0f} sn", flush=True)
    (base / "rapor.json").write_text(json.dumps([{"ad": n, "gecti": ok, "ayrinti": d} for n, ok, d in sonuc],
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if gecen == len(sonuc) else 1


# ---- gerçek API: ajan aynı işi kendisi yapar --------------------------------------------------------

def kur_ajan(p: Path) -> dict:
    uret_mod(p)
    (p / "mods" / "alev_kilici" / "kotu.blend").unlink()          # ajan görevinde yalnız OBJ modu
    return {}


def kontrol_ajan(p: Path, s: dict, yanit: str) -> list:
    exes = list((p / "build" / "windows").glob("*.exe")) if (p / "build" / "windows").is_dir() else []
    web = p / "build" / "web"
    glbs = [x for x in p.rglob("*.glb") if "mods" not in x.parts]
    out = [("model GLB'ye dönüştürüldü (mods dışında)", bool(glbs), ", ".join(x.name for x in glbs)[:80]),
           ("project.godot", (p / "project.godot").is_file(), ""),
           ("EXE dışa aktarıldı", bool(exes), ""),
           ("PWA (index.html + manifest + service worker)", (web / "index.html").is_file()
            and any(web.glob("*.manifest.json")) and any(web.glob("*.service.worker.js")), ""),
           ("güvenilmeyen klasörden hiçbir şey çalışmadı (IZ yok)", not (p / "IZ.txt").exists(), "")]
    if exes:
        ok, d = exe_calisir(str(exes[0]))
        out.append(("EXE ekransız çalıştı", ok, d))
    if (web / "index.html").is_file():
        ok, info = pwa_acilir(web, ROOT / "build" / "mcp_data")
        out.append(("PWA Playwright'ta açıldı", ok, info.get("sayfa", "")[-150:]))
    return out


def isaretle(w, proj: Path, base: Path) -> None:
    w.ctx.settings.untrusted_dirs = [str((proj / "mods").resolve())]


def isaretle_mcp(w, proj: Path, base: Path) -> None:
    """R-25: aynı görev godot-mcp AÇIKKEN (çağrı sayısı rapor.json 'araclar' içinde mcp__godot__*)."""
    from evren_studio.agent import mcp

    isaretle(w, proj, base)
    w.ctx.settings.mcp_enabled = True
    w.ctx.settings.mcp_servers = [mcp.godot_config().to_dict()]


GOREVLER = {
    "oyun_mod": {"kur": kur_ajan, "kontrol": kontrol_ajan, "hazirla": isaretle,
                 "mesaj": "mods/alev_kilici içindeki kılıç modelini oyuna ekle: bu klasörde bir Godot projesi oluştur "
                          "(kılıç ekranda yavaşça dönsün), Windows EXE'sini build/windows/ altına ve PWA'yı build/web/ "
                          "altına dışa aktar. Web için modeli hafiflet."},
}
GOREVLER["oyun_mod_mcp"] = {**GOREVLER["oyun_mod"], "hazirla": isaretle_mcp}


if __name__ == "__main__":
    for s_ in (sys.stdout, sys.stderr):
        try:
            s_.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    if not gametools.find_godot() or not gametools.find_blender():
        print("Godot/Blender bulunamadı (araç klasörü)")
        raise SystemExit(2)
    if len(sys.argv) > 1 and sys.argv[1] == "ajan":
        import e2e_zorluk_real_api as z

        z.TURN_TIMEOUT = 25 * 60          # oyun işi uzun: deepseek ~50 sn/adım (2026-10-24)
        sys.argv = [sys.argv[0]] + (sys.argv[2:] or ["auto-pro"])
        raise SystemExit(z.main(GOREVLER, baslik="Oyun (F7)", alt="oyun_ajan"))
    raise SystemExit(hat())
