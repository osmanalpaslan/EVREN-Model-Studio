"""F7 Godot proje şablonu (Qt'siz): EXE + PWA dışa aktarmaya hazır en küçük proje.

`yeni_proje(kok, ad, model=None)` → project.godot, main.tscn (kamera, ışık, isteğe bağlı GLB modeli döndüren betik),
export_presets.cfg (Windows Desktop → build/windows/<ad>.exe, Web + PWA → build/web/index.html). Ajan aynı içeriği
istemden (gametools.prompt_section) bilir; bu modül uçtan uca testin ve "Godot oyun" şablonunun kaynağıdır.
Dışa aktarma: `godot --headless --path <kök> --import` sonra `--export-release "<ön ayar>" <yol>`.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

PROJECT = """; Engine configuration file.
config_version=5

[application]
config/name="{ad}"
run/main_scene="res://main.tscn"
config/features=PackedStringArray("4.7")

[rendering]
renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
"""
# gl_compatibility: Web/PWA dışa aktarmasının desteklediği tek çizici (WebGL 2) — EXE de aynı görünür.

MAIN_TSCN = """[gd_scene load_steps={steps} format=3]

[ext_resource type="Script" path="res://dondur.gd" id="1"]
{model_res}
[node name="Ana" type="Node3D"]

[node name="Kamera" type="Camera3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 0.94, 0.34, 0, -0.34, 0.94, 0, 2, 6)

[node name="Isik" type="DirectionalLight3D" parent="."]
transform = Transform3D(0.7, -0.5, 0.5, 0, 0.7, 0.7, -0.7, -0.5, 0.5, 0, 4, 0)

[node name="Model" type="Node3D" parent="."]
script = ExtResource("1")
{model_node}"""

DONDUR = """extends Node3D

func _process(delta: float) -> void:
\trotate_y(delta * 0.8)
"""

PRESETS = """[preset.0]

name="Windows Desktop"
platform="Windows Desktop"
runnable=true
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path="build/windows/{ad}.exe"

[preset.0.options]

binary_format/embed_pck=true

[preset.1]

name="Web"
platform="Web"
runnable=true
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path="build/web/index.html"

[preset.1.options]

variant/thread_support=false
progressive_web_app/enabled=true
progressive_web_app/offline_page=""
"""


def safe_name(ad: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", ad).strip("_") or "oyun"


def yeni_proje(kok: Path, ad: str = "oyun", model: str | None = None) -> Path:
    """Proje dosyalarını yazar. `model`: proje köküne göre .glb yolu (ör. "assets/kilic.glb")."""
    kok = Path(kok)
    kok.mkdir(parents=True, exist_ok=True)
    ad = safe_name(ad)
    (kok / "project.godot").write_text(PROJECT.format(ad=ad), encoding="utf-8")
    (kok / "dondur.gd").write_text(DONDUR, encoding="utf-8")
    if model:
        res = f'[ext_resource type="PackedScene" path="res://{model}" id="2"]\n'
        node = '\n[node name="Varlik" parent="Model" instance=ExtResource("2")]\n'
        steps = 3
    else:
        res, node, steps = "", '\n[node name="Kutu" type="CSGBox3D" parent="Model"]\n', 2
    (kok / "main.tscn").write_text(MAIN_TSCN.format(steps=steps, model_res=res, model_node=node), encoding="utf-8")
    (kok / "export_presets.cfg").write_text(PRESETS.format(ad=ad), encoding="utf-8")
    return kok


def presets_yaz(kok: Path, ad: str = "oyun") -> bool:
    """export_presets.cfg YOKSA şablondan yazar (varsa kullanıcınınkine dokunmaz). Dönüş: yazıldı mı."""
    p = Path(kok) / "export_presets.cfg"
    if p.exists():
        return False
    p.write_text(PRESETS.format(ad=safe_name(ad)), encoding="utf-8")
    return True


def hata_satirlari(log: str) -> list[str]:
    return [ln.strip() for ln in log.splitlines() if "ERROR" in ln or "SCRIPT ERROR" in ln][:12]


def calistir(godot: str, kok: Path, *args: str, timeout: int = 600) -> tuple[int, str]:
    r = subprocess.run([godot, "--headless", "--path", str(kok), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.returncode, ((r.stdout or "") + (r.stderr or ""))[-3000:]


def disa_aktar(godot: str, kok: Path, ad: str = "oyun", hedef: str = "ikisi") -> dict:
    """İçe aktar + EXE ve/veya Web/PWA. hedef: "windows" | "web" | "ikisi".
    Dönüş: {"import": kod, "exe": yol|None, "web": yol|None, "log": {...}}."""
    kok = Path(kok)
    ad = safe_name(ad)
    out = {"log": {}, "exe": None, "web": None}
    out["import"], out["log"]["import"] = calistir(godot, kok, "--import")
    if hedef in ("windows", "ikisi"):
        (kok / "build" / "windows").mkdir(parents=True, exist_ok=True)
        c1, out["log"]["exe"] = calistir(godot, kok, "--export-release", "Windows Desktop", f"build/windows/{ad}.exe")
        exe = kok / "build" / "windows" / f"{ad}.exe"
        out["exe"] = str(exe) if c1 == 0 and exe.is_file() else None
    if hedef in ("web", "ikisi"):
        (kok / "build" / "web").mkdir(parents=True, exist_ok=True)
        c2, out["log"]["web"] = calistir(godot, kok, "--export-release", "Web", "build/web/index.html")
        web = kok / "build" / "web" / "index.html"
        out["web"] = str(web) if c2 == 0 and web.is_file() else None
    return out
