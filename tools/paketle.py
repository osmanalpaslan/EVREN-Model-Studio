"""EVREN Studio kurulum paketi yapım hattı (Windows).

Kullanım (depo kökünden):
  .venv\\Scripts\\python.exe tools\\paketle.py sertifika   # kendi imza sertifikası (bir kez; yoksa oluşturur)
  .venv\\Scripts\\python.exe tools\\paketle.py             # tam yapım: önkoşullar → exe → imza → duman testi → kurulum
  .venv\\Scripts\\python.exe tools\\paketle.py --imzasiz   # imzasız (sertifika yokken)

Çıktı: dist\\EVREN-Studio-Kurulum-<sürüm>.exe (+ .sha256). Ayrıntı: docs/ILERIDE_YAPILACAKLAR.md §1, installer/.

Gerekenler: PyInstaller (.venv), Inno Setup 6 (ISCC.exe; `winget install JRSoftware.InnoSetup --scope user`).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "installer"
BUILD = ROOT / "build"
PREREQ_DIR = BUILD / "onkosullar"
PYI_DIST = BUILD / "pyi" / "dist"
APP_DIR = PYI_DIST / "EVREN Studio"
APP_EXE = APP_DIR / "EVREN Studio.exe"
OUT = ROOT / "dist"
CERT_SUBJECT = "CN=EVREN Studio - Osman Alpaslan"
SIGN_PS1 = INSTALLER / "imza.ps1"


def version() -> str:
    text = (ROOT / "src" / "evren_studio" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*"(\d+\.\d+\.\d+)"', text, re.M)
    if not m:
        raise SystemExit("__version__ okunamadı")
    return m.group(1)


def version_file(ver: str) -> str:
    """PyInstaller VSVersionInfo (exe Özellikler > Ayrıntılar)."""
    a, b, c = (int(x) for x in ver.split("."))
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({a}, {b}, {c}, 0), prodvers=({a}, {b}, {c}, 0), mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041F04B0', [
      StringStruct('CompanyName', 'Osman Alpaslan'),
      StringStruct('FileDescription', 'EVREN Studio'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', 'EVREN Studio'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 Osman Alpaslan (MIT)'),
      StringStruct('OriginalFilename', 'EVREN Studio.exe'),
      StringStruct('ProductName', 'EVREN Studio'),
      StringStruct('ProductVersion', '{ver}')])]),
    VarFileInfo([VarStruct('Translation', [0x041F, 1200])])
  ]
)
"""


def wizard_images() -> tuple[str, str]:
    """Kurulum sihirbazının sol (büyük) ve sağ üst (küçük) resimleri — uygulama logosundan (ui/brand.py), %100 ve
    %200 ölçek. Yoksa sihirbaz Inno Setup'ın kendi resmini gösterir (kullanıcı 2026-11-07: "setupta logo yok")."""
    os.environ["QT_QPA_PLATFORM"] = "windows"        # offscreen kipte yazılar kutucuk çıkar (R-05)
    sys.path.insert(0, str(ROOT / "src"))
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter
    from PySide6.QtWidgets import QApplication

    from evren_studio.ui import brand

    _app = QApplication.instance() or QApplication([])
    red = QColor(brand.FLAG_RED)                    # brand_color() koyu temada beyaz döner
    out_large, out_small = [], []
    for scale in (1, 2):
        # Büyük: 164×314 kırmızı zemin, beyaz ay-yıldız + ad
        w, h = 164 * scale, 314 * scale
        img = QImage(w, h, QImage.Format_RGB32)
        img.fill(red)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        size = 120 * scale
        p.translate((w - size) / 2, 70 * scale)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("white"))
        p.drawPath(brand.crescent_star_path(size))
        p.resetTransform()
        p.setPen(QColor("white"))
        f = QFont("Segoe UI", 15)
        f.setBold(True)
        f.setPixelSize(22 * scale)
        p.setFont(f)
        p.drawText(QRectF(0, 205 * scale, w, 40 * scale), Qt.AlignCenter, "EVREN Studio")
        p.end()
        large = BUILD / f"sihirbaz_buyuk_{scale * 100}.bmp"
        img.save(str(large), "BMP")
        out_large.append(str(large))
        # Küçük: 58×58 beyaz zemin, kırmızı ay-yıldız
        s = 58 * scale
        img = QImage(s, s, QImage.Format_RGB32)
        img.fill(QColor("white"))
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(red)
        p.drawPath(brand.crescent_star_path(s))
        p.end()
        small = BUILD / f"sihirbaz_kucuk_{scale * 100}.bmp"
        img.save(str(small), "BMP")
        out_small.append(str(small))
    return ",".join(out_large), ",".join(out_small)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ps(command: str, timeout: float = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def signer_of(path: Path) -> tuple[str, str]:
    """(durum, imzalayan CN) — Authenticode."""
    r = ps(f"$s = Get-AuthenticodeSignature -LiteralPath '{path}'; "
           "Write-Output ($s.Status.ToString() + '|' + $s.SignerCertificate.Subject)")
    status, _, subject = (r.stdout or "").strip().partition("|")
    m = re.search(r'CN="?([^",]+)', subject)
    return status, (m.group(1) if m else "")


def prereqs() -> list[dict]:
    """Gömülecek yükleyicileri indirir/doğrular (SHA256 + Authenticode imzalayanı)."""
    items = json.loads((INSTALLER / "prereqs.json").read_text(encoding="utf-8"))["items"]
    PREREQ_DIR.mkdir(parents=True, exist_ok=True)
    for it in items:
        f = PREREQ_DIR / it["file"]
        if not f.is_file() or sha256(f) != it["sha256"]:
            print(f"indiriliyor: {it['file']}")
            tmp = f.with_suffix(f.suffix + ".part")
            urllib.request.urlretrieve(it["url"], tmp)
            tmp.replace(f)
        got = sha256(f)
        if got != it["sha256"]:
            f.unlink(missing_ok=True)
            raise SystemExit(f"SHA256 UYUŞMUYOR: {it['file']} ({got}) — indirme bozuk ya da değiştirilmiş")
        status, signer = signer_of(f)
        if status != "Valid" or it["signer"].casefold() not in signer.casefold():
            raise SystemExit(f"İMZA GEÇERSİZ: {it['file']} ({status}, {signer!r}; beklenen {it['signer']!r})")
        print(f"tamam: {it['file']} · sha256 eşleşti · imza {signer}")
    return items


def cert_thumbprint() -> str:
    r = ps(f"Get-ChildItem Cert:\\CurrentUser\\My -CodeSigningCert | Where-Object {{ $_.Subject -eq '{CERT_SUBJECT}' "
           "-and $_.NotAfter -gt (Get-Date) } | Sort-Object NotAfter -Descending | Select-Object -First 1 "
           "-ExpandProperty Thumbprint")
    return (r.stdout or "").strip()


def make_cert() -> str:
    """Kendi (self-signed) kod imzalama sertifikası: 5 yıl, Cert:\\CurrentUser\\My. Ortak anahtar build\\ altına."""
    thumb = cert_thumbprint()
    if thumb:
        print(f"sertifika zaten var: {thumb}")
    else:
        r = ps(f"$c = New-SelfSignedCertificate -Type CodeSigningCert -Subject '{CERT_SUBJECT}' "
               "-CertStoreLocation Cert:\\CurrentUser\\My -KeyAlgorithm RSA -KeyLength 3072 -HashAlgorithm SHA256 "
               "-KeyExportPolicy Exportable -NotAfter (Get-Date).AddYears(5); $c.Thumbprint")
        thumb = (r.stdout or "").strip()
        if not thumb:
            raise SystemExit(f"sertifika oluşturulamadı: {r.stderr.strip()[-400:]}")
        print(f"sertifika oluşturuldu: {thumb}")
    cer = BUILD / "EVREN-Studio-imza.cer"
    BUILD.mkdir(exist_ok=True)
    ps(f"Export-Certificate -Cert Cert:\\CurrentUser\\My\\{thumb} -FilePath '{cer}' | Out-Null")
    print(f"ortak sertifika (paylaşılabilir): {cer}")
    return thumb


def sign(path: Path) -> None:
    r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SIGN_PS1),
                        "-Dosya", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=180)
    if r.returncode != 0:
        raise SystemExit(f"imza başarısız: {path.name}\n{(r.stderr or r.stdout).strip()[-600:]}")
    print((r.stdout or "").strip())


def iscc() -> Path:
    for p in (Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
              Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"), Path(r"C:\Program Files\Inno Setup 6\ISCC.exe")):
        if p.is_file():
            return p
    found = shutil.which("ISCC")
    if found:
        return Path(found)
    raise SystemExit("Inno Setup 6 bulunamadı: winget install --id JRSoftware.InnoSetup -e --scope user")


def smoke(exe: Path, timeout: float = 90) -> list[str]:
    """Paketli exe'yi boş bir veri klasörüyle açıp kapatır; açılış raporunu döndürür (app.smoke_report)."""
    data = Path(tempfile.mkdtemp(prefix="evren-duman-"))
    out = data / "duman.txt"
    env = {**os.environ, "EVREN_STUDIO_DATA_DIR": str(data)}
    env.pop("QT_QPA_PLATFORM", None)
    proc = subprocess.Popen([str(exe), "--duman-testi", str(out)], env=env)
    t0 = time.monotonic()
    while proc.poll() is None and time.monotonic() - t0 < timeout:
        time.sleep(0.5)
    if proc.poll() is None:
        proc.kill()
        raise SystemExit("DUMAN TESTİ: uygulama zamanında kapanmadı")
    lines = out.read_text(encoding="utf-8").splitlines() if out.is_file() else []
    crash = data / "logs" / "crash.log"
    if crash.is_file():
        raise SystemExit("DUMAN TESTİ: çökme günlüğü yazıldı:\n" + crash.read_text(encoding="utf-8")[-1500:])
    shutil.rmtree(data, ignore_errors=True)
    return lines


def check_smoke(lines: list[str]) -> list[str]:
    """Duman raporundaki sorunlar (boş liste = geçti)."""
    kv = dict(line.split("=", 1) for line in lines if "=" in line)
    problems = []
    if "TAMAM" not in lines:
        problems.append("rapor tamamlanmadı (uygulama açılmadı ya da erken çöktü)")
    if kv.get("frozen") != "True":
        problems.append("paketli çalışmıyor (frozen=False)")
    if kv.get("pencere") != "True":
        problems.append("ana pencere görünmedi")
    for k in ("wmcp_baslatici", "blender_donustur"):
        if kv.get(k) != "var":
            problems.append(f"{k}.py pakette YOK")
    if kv.get("belge") != "var":
        problems.append(f"PDF/Word/PowerPoint okuma pakette eksik: belge={kv.get('belge')}")
    if kv.get("ruff") != "var":
        problems.append("ruff pakette YOK (hata bekçisi Python'da yalnız sözdizimine bakar)")
    if kv.get("json_repair") != "var":
        problems.append("json_repair pakette YOK (bozuk JSON onarımı çalışmaz)")
    if kv.get("harita_dilleri") != "11":
        problems.append(f"proje haritası dil çözümleyicileri eksik: harita_dilleri={kv.get('harita_dilleri')} (11 olmalı)")
    if kv.get("keyring") != "WinVaultKeyring":
        problems.append(f"anahtar deposu (Credential Manager) yok: keyring={kv.get('keyring')}")
    if not kv.get("tls", "").startswith("tamam"):
        problems.append(f"güvenli bağlantı (SSL) kurulamadı: tls={kv.get('tls')} (internet yoksa tekrar deneyin)")
    return problems


def build(signed: bool) -> Path:
    ver = version()
    print(f"== EVREN Studio {ver} ==")
    prereqs()
    BUILD.mkdir(exist_ok=True)
    (BUILD / "surum_bilgisi.txt").write_text(version_file(ver), encoding="utf-8")
    if signed and not cert_thumbprint():
        raise SystemExit("imza sertifikası yok: önce `tools\\paketle.py sertifika` (ya da --imzasiz)")
    shutil.rmtree(PYI_DIST, ignore_errors=True)
    r = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
                        "--distpath", str(PYI_DIST), "--workpath", str(BUILD / "pyi" / "work"),
                        str(INSTALLER / "evren_studio.spec")], cwd=ROOT)
    if r.returncode != 0 or not APP_EXE.is_file():
        raise SystemExit("PyInstaller başarısız")
    if signed:
        sign(APP_EXE)
    lines = smoke(APP_EXE)
    print("duman testi:", " · ".join(lines))
    problems = check_smoke(lines)
    if problems:
        raise SystemExit("DUMAN TESTİ KALDI: " + "; ".join(problems))
    OUT.mkdir(exist_ok=True)
    large, small = wizard_images()
    args = [str(iscc()), f"/DAppVersion={ver}", f"/DSourceDir={APP_DIR}", f"/DPrereqDir={PREREQ_DIR}",
            f"/DOutDir={OUT}", f"/DWizImage={large}", f"/DWizSmallImage={small}", "/Q"]
    if signed:
        args += ["/DSignToolName=evrenimza",
                 # Inno'da tırnak = $q (gerçek " subprocess'te \" olur, ISCC yolu böler); $f = imzalanacak dosya
                 f"/Sevrenimza=powershell.exe -NoProfile -ExecutionPolicy Bypass -File $q{SIGN_PS1}$q -Dosya $f"]
    r = subprocess.run(args + [str(INSTALLER / "evren_studio.iss")], cwd=INSTALLER)
    setup = OUT / f"EVREN-Studio-Kurulum-{ver}.exe"
    if r.returncode != 0 or not setup.is_file():
        raise SystemExit("Inno Setup derlemesi başarısız")
    digest = sha256(setup)
    (setup.with_name(setup.name + ".sha256")).write_text(f"{digest}  {setup.name}\n", encoding="utf-8")
    status, signer = signer_of(setup)
    size = setup.stat().st_size / 1e6
    print(f"KURULUM: {setup} · {size:.0f} MB · sha256 {digest} · imza: {status} {signer}")
    return setup


def main(argv: list[str]) -> int:
    if os.name != "nt":
        print("Yalnız Windows'ta çalışır.")
        return 1
    if argv[:1] == ["sertifika"]:
        make_cert()
        return 0
    if argv[:1] == ["onkosullar"]:
        prereqs()
        return 0
    build(signed="--imzasiz" not in argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
