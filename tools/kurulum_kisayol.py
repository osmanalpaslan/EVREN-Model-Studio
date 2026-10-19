"""Masaüstü ve Başlat menüsü kısayolu oluşturur (kurulum.bat çağırır).

Kısayol, sanal ortamın pythonw.exe'si ile `-m evren_studio` çalıştırır (konsol
penceresi açılmaz), simge assets/evren.ico. Yollar PowerShell'e ortam
değişkeniyle geçirilir; kullanıcı adında boşluk veya Türkçe harf olsa da bozulmaz.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PS = r"""
$ws = New-Object -ComObject WScript.Shell
foreach ($dir in @($env:EVREN_DESKTOP, $env:EVREN_STARTMENU)) {
  if (-not $dir) { continue }
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $lnk = $ws.CreateShortcut((Join-Path $dir 'EVREN Studio.lnk'))
  $lnk.TargetPath = $env:EVREN_TARGET
  $lnk.Arguments = '-m evren_studio'
  $lnk.WorkingDirectory = $env:EVREN_ROOT
  $lnk.IconLocation = $env:EVREN_ICON
  $lnk.Description = 'EVREN Studio - EVREN LLM kod ajani ve sohbet'
  $lnk.Save()
}
"""


def main() -> int:
    target = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    if not target.is_file():
        print("Kısayol oluşturulamadı: .venv bulunamadı.")
        return 1
    desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "[Environment]::GetFolderPath('Desktop')"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout.strip():
            desktop = Path(out.stdout.strip())       # OneDrive'a taşınmış masaüstü
    except (OSError, subprocess.TimeoutExpired):
        pass
    start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    if os.environ.get("EVREN_KISAYOL_KLASORU"):       # test: gerçek masaüstüne dokunma
        desktop = start_menu = Path(os.environ["EVREN_KISAYOL_KLASORU"])
    env = {**os.environ, "EVREN_DESKTOP": str(desktop), "EVREN_STARTMENU": str(start_menu),
           "EVREN_TARGET": str(target), "EVREN_ROOT": str(ROOT), "EVREN_ICON": str(ROOT / "assets" / "evren.ico")}
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", PS],
                       env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print("Kısayol oluşturulamadı:", (r.stderr or r.stdout).strip()[:300])
        return 1
    print(f"Kısayol oluşturuldu: {desktop / 'EVREN Studio.lnk'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
