"""F7 oyun araçları (Qt'siz): Godot, Blender ve godot-mcp'nin yeri; ajan istemine dışa aktarma bilgisi.

Kurulum (kullanıcı onayı 2026-10-24, sağlama toplamı doğrulandı): kurulumsuz zip'ler araç klasörüne açılır —
    <araçlar>/godot/Godot_v4.7.2-stable_win64(_console).exe   (+ "._sc_" → kendi kendine yeterli kip: şablonlar
                                                               ve ayarlar exe'nin yanındaki editor_data/ içinde;
                                                               AppData'ya yazılmaz)
    <araçlar>/blender/blender-5.2.3-windows-x64/blender.exe
    <araçlar>/godot-mcp/build/index.js                       (Coding-Solo/godot-mcp, MIT; npm ci + derleme)
Araç klasörü sırası: ayar `tools_dir`, uygulama klasörünün yanındaki `EVREN-Araclar`, kullanıcı klasöründe
`EVREN-Araclar`. PATH'teki godot/blender de bulunur.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

GODOT_VERSION = "4.7.2"
BLENDER_VERSION = "5.2.3"
APP_ROOT = Path(__file__).resolve().parents[3]          # depo/uygulama kökü (src/evren_studio/agent → ../../..)


def tools_dirs(setting: str = "") -> list[Path]:
    out = []
    for d in (setting, str(APP_ROOT.parent / "EVREN-Araclar"), str(Path.home() / "EVREN-Araclar")):
        if d and Path(d).is_dir() and Path(d) not in out:
            out.append(Path(d))
    return out


def _glob_first(dirs: list[Path], patterns: list[str]) -> str | None:
    for d in dirs:
        for pat in patterns:
            hits = sorted(d.glob(pat))
            if hits:
                return str(hits[-1])
    return None


def find_godot(setting: str = "", console: bool = True) -> str | None:
    """Godot çalıştırılabilir dosyası. console=True → ekransız işler için _console.exe (çıktıyı terminale yazar)."""
    pats = (["godot/Godot_v*_win64_console.exe", "Godot_v*_win64_console.exe"] if console else []) + \
        ["godot/Godot_v*_win64.exe", "Godot_v*_win64.exe"]
    return _glob_first(tools_dirs(setting), pats) or shutil.which("godot") or shutil.which("godot4")


def find_blender(setting: str = "") -> str | None:
    return _glob_first(tools_dirs(setting), ["blender/blender-*/blender.exe", "blender-*/blender.exe"]) \
        or shutil.which("blender")


def find_godot_mcp(setting: str = "") -> str | None:
    return _glob_first(tools_dirs(setting), ["godot-mcp/build/index.js"])


def templates_ready(godot: str | None) -> bool:
    """Dışa aktarma şablonları kurulu mu (kendi kendine yeterli kip: exe yanındaki editor_data)."""
    if not godot:
        return False
    base = Path(godot).parent / "editor_data" / "export_templates"
    if any(base.glob(f"{GODOT_VERSION}.stable/windows_release_x86_64.exe")):
        return True
    appdata = Path(os.environ.get("APPDATA", "")) / "Godot" / "export_templates"
    return any(appdata.glob(f"{GODOT_VERSION}.stable/windows_release_x86_64.exe"))


def prompt_section(setting: str = "") -> str:
    """Godot/Blender kuruluysa ajan için kısa kullanım bölümü (oyun rolü veya project.godot olan projede)."""
    godot, blender = find_godot(setting), find_blender(setting)
    if not godot and not blender:
        return ("# Oyun araçları\n- Godot ve Blender kurulu değil. Oyun dışa aktarmak gerekiyorsa kullanıcıya "
                "Ayarlar > MCP'deki oyun araçları kurulumunu söyle; kendin indirmeye çalışma.\n")
    lines = ["# Oyun araçları (kurulu; yolu tırnakla kullan)"]
    if godot:
        lines.append(f'- Godot {GODOT_VERSION}: "{godot}" — dışa aktarma şablonları '
                     + ("kurulu." if templates_ready(godot) else "KURULU DEĞİL (EXE/PWA dışa aktarılamaz; kullanıcıya söyle)."))
        lines.append("- Dışa aktarmak için `godot_export` aracını kullan (içe aktarır, export_presets.cfg yoksa "
                     "yazar, EXE + PWA çıkarır, hataları döndürür). Elle gerekirse: `& \"<godot>\" --headless --path . "
                     '--export-release "Windows Desktop" build/windows/oyun.exe` / `"Web" build/web/index.html`. '
                     "PWA için Web ön ayarında "
                     "progressive_web_app/enabled=true, çizici gl_compatibility. Dışa aktarmadan önce `--headless "
                     "--path . --import` ile içe aktar ve çıktıda ERROR olmadığını kontrol et. Modeller GLB olarak "
                     "assets/ altında olmalı; mod/kaynak klasörlerinde boş .gdignore bulunmalı (Godot onları işlemez).")
    if blender:
        lines.append(f'- Blender {BLENDER_VERSION}: model dönüştürmek/küçültmek için `convert_model` aracını kullan '
                     "(Blender'ı kendin komutla çalıştırma: araç --disable-autoexec ile güvenli çalıştırır).")
    lines.append("- Hazır CC0 model/doku gerekiyorsa `polyhaven_search` ve `polyhaven_download` (Poly Haven).")
    return "\n".join(lines) + "\n"
