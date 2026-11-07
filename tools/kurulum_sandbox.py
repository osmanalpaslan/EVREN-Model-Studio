"""Kurulum dosyasını TEMİZ bir Windows'ta (Windows Sandbox) otomatik dener — docs/ILERIDE_YAPILACAKLAR.md §1.7.

    .venv\\Scripts\\python.exe tools\\kurulum_sandbox.py [dist\\EVREN-Studio-Kurulum-<sürüm>.exe]

Sandbox'ta Python, Git, Node.js ve GitHub CLI YOKTUR. Betik:
  1. kurulum dosyasını salt okunur, sonuç klasörünü yazılabilir olarak bağlayan bir .wsb yapılandırması yazar,
  2. Sandbox açılınca içerde kurulumu sessizce TÜM eksik programlarla çalıştırır (/TASKS=...dev\\python,...),
  3. kurulan programları (python/git/node/gh --version, yeni PATH ile), uygulamanın duman testini
     (`--duman-testi`: pencere, betikler, sistem Python'u, anahtar deposu, SSL) ve kurulum günlüğünü sonuç klasörüne yazar,
  4. içerde iş bitince Sandbox kapanır; betik sonucu okuyup özetler.
Gereken: Windows 10/11 Pro, "Windows Sandbox" özelliği açık (bir kez yönetici izni + yeniden başlatma).
Sandbox'ta oturum kullanıcısı yöneticidir: Node.js / GitHub CLI MSI'larının yönetici izni penceresi çıkmaz (gerçek
bilgisayarda kullanıcı kapsamlı kurulumda çıkar — ayrıca elle denenmeli).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "sandbox_deneme"
SANDBOX = Path(r"C:\Windows\System32\WindowsSandbox.exe")
TASKS = "desktopicon,dev,dev\\python,dev\\git,dev\\node,dev\\gh"

INNER_PS1 = r'''$ErrorActionPreference = 'Continue'
$out = 'C:\sonuc'
"basladi $(Get-Date -Format o)" | Out-File -Encoding utf8 "$out\ilerleme.txt"
$setup = Get-ChildItem 'C:\kurulum\EVREN-Studio-Kurulum-*.exe' | Select-Object -First 1
# kurulumdan ÖNCE: temiz makinede ne var (Store python yer tutucusu dahil)
$once = @{}
foreach ($c in 'python','git','node','gh') { $once[$c] = (Get-Command $c -ErrorAction SilentlyContinue).Source }
$once | ConvertTo-Json | Out-File -Encoding utf8 "$out\once.json"
$t0 = Get-Date
$p = Start-Process $setup.FullName -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CURRENTUSER',
     '/TASKS="__TASKS__"',"/LOG=$out\kurulum.log" -Wait -PassThru
"kurulum cikis $($p.ExitCode) sure $([int]((Get-Date)-$t0).TotalSeconds) sn" | Out-File -Append -Encoding utf8 "$out\ilerleme.txt"
# kurulumdan SONRA: kayıt defterindeki yeni PATH ile
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
$sonra = @{}
foreach ($c in 'python','git','node','gh') {
  $src = (Get-Command $c -ErrorAction SilentlyContinue).Source
  $ver = ''
  if ($src) { try { $ver = (& $c --version 2>&1 | Select-Object -First 1) -join '' } catch { $ver = "HATA $_" } }
  $sonra[$c] = @{ yol = $src; surum = "$ver" }
}
$sonra | ConvertTo-Json -Depth 3 | Out-File -Encoding utf8 "$out\sonra.json"
$exe = Join-Path $env:LOCALAPPDATA 'Programs\EVREN Studio\EVREN Studio.exe'
"uygulama var: $(Test-Path $exe)" | Out-File -Append -Encoding utf8 "$out\ilerleme.txt"
if (Test-Path $exe) {
  $env:EVREN_STUDIO_DATA_DIR = "$env:TEMP\evren-duman"
  $a = Start-Process $exe -ArgumentList '--duman-testi',"$out\duman.txt" -PassThru
  if (-not $a.WaitForExit(120000)) { $a.Kill(); "duman testi zaman asimi" | Out-File -Append -Encoding utf8 "$out\ilerleme.txt" }
  if (Test-Path "$env:EVREN_STUDIO_DATA_DIR\logs\crash.log") { Copy-Item "$env:EVREN_STUDIO_DATA_DIR\logs\crash.log" "$out\crash.log" }
}
$lnk = @{ baslat = Test-Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\EVREN Studio.lnk";
          masaustu = Test-Path "$env:USERPROFILE\Desktop\EVREN Studio.lnk" }
$lnk | ConvertTo-Json | Out-File -Encoding utf8 "$out\kisayol.json"
"bitti $(Get-Date -Format o)" | Out-File -Append -Encoding utf8 "$out\ilerleme.txt"
'TAMAM' | Out-File -Encoding utf8 "$out\BITTI.txt"
shutdown.exe /s /t 5
'''


def wsb(setup_dir: Path, out: Path) -> str:
    return f"""<Configuration>
  <Networking>Disable</Networking>
  <MappedFolders>
    <MappedFolder><HostFolder>{setup_dir}</HostFolder><SandboxFolder>C:\\kurulum</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>{out}</HostFolder><SandboxFolder>C:\\sonuc</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder>
  </MappedFolders>
  <LogonCommand><Command>powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\\sonuc\\icerde.ps1</Command></LogonCommand>
  <MemoryInMB>4096</MemoryInMB>
</Configuration>
"""


def main(argv: list[str]) -> int:
    if not SANDBOX.is_file():
        print("Windows Sandbox kurulu değil ya da bilgisayar henüz yeniden başlatılmadı (özellik: Containers-DisposableClientVM).")
        return 2
    setups = [Path(a) for a in argv if a.lower().endswith(".exe")] or sorted((ROOT / "dist").glob("EVREN-Studio-Kurulum-*.exe"))
    if not setups:
        print("Kurulum dosyası yok: önce tools\\paketle.py")
        return 2
    setup = setups[-1].resolve()
    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "kurulum").mkdir(parents=True)
    (OUT / "sonuc").mkdir()
    shutil.copy2(setup, OUT / "kurulum" / setup.name)       # yalnız bu dosya bağlanır (dist/'in tamamı değil)
    (OUT / "sonuc" / "icerde.ps1").write_text(INNER_PS1.replace("__TASKS__", TASKS), encoding="utf-8-sig")
    cfg = OUT / "deneme.wsb"
    cfg.write_text(wsb(OUT / "kurulum", OUT / "sonuc"), encoding="utf-8")
    print(f"Sandbox açılıyor: {setup.name} (internet KAPALI — kurulum çevrimdışı olmalı)")
    subprocess.Popen([str(SANDBOX), str(cfg)])
    done = OUT / "sonuc" / "BITTI.txt"
    t0 = time.monotonic()
    while not done.exists() and time.monotonic() - t0 < 30 * 60:
        time.sleep(10)
    res = OUT / "sonuc"
    print((res / "ilerleme.txt").read_text(encoding="utf-8-sig", errors="replace") if (res / "ilerleme.txt").exists()
          else "ilerleme yok")
    for name in ("once.json", "sonra.json", "kisayol.json", "duman.txt", "crash.log"):
        f = res / name
        if f.exists():
            print(f"--- {name}\n{f.read_text(encoding='utf-8-sig', errors='replace').strip()}")
    if not done.exists():
        print("ZAMAN AŞIMI: Sandbox içi iş 30 dk'da bitmedi")
        return 1
    try:
        after = json.loads((res / "sonra.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        after = {}
    missing = [k for k in ("python", "git", "node", "gh") if not (after.get(k) or {}).get("yol")]
    smoke = (res / "duman.txt").read_text(encoding="utf-8", errors="replace") if (res / "duman.txt").exists() else ""
    ok = not missing and "TAMAM" in smoke
    print("SONUÇ:", "GEÇTİ" if ok else f"KALDI (eksik: {missing or '-'}; duman: {'var' if smoke else 'yok'})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
