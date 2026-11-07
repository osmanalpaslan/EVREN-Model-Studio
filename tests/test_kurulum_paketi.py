"""Kurulum paketi (Madde 16, 2026-11-07): paketli çalışma, gömülü programlar, kaldırma, sürüm tek kaynak."""
from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path

import pytest

from evren_studio import __version__, app, secrets
from evren_studio.agent import environment, mcp

ROOT = Path(__file__).resolve().parents[1]
ISS = (ROOT / "installer" / "evren_studio.iss").read_text(encoding="utf-8")
SPEC = (ROOT / "installer" / "evren_studio.spec").read_text(encoding="utf-8")
PREREQS = json.loads((ROOT / "installer" / "prereqs.json").read_text(encoding="utf-8"))["items"]
sys.path.insert(0, str(ROOT / "tools"))
import paketle  # noqa: E402


# ---- Microsoft Store'un sahte python.exe'si gerçek Python sayılmaz -----------------------------------------------

def test_store_python_yer_tutucusu_kurulu_sayilmaz(monkeypatch):
    stub = r"C:\Users\x\AppData\Local\Microsoft\WindowsApps\python.exe"
    assert environment.is_store_stub(stub)
    assert environment.is_store_stub(stub.replace("python.exe", "python3.exe"))
    assert not environment.is_store_stub(r"C:\Users\x\AppData\Local\Microsoft\WindowsApps\winget.exe")
    assert not environment.is_store_stub(r"C:\Users\x\AppData\Local\Programs\Python\Python312\python.exe")
    paths = {"python": stub, "py": r"C:\Windows\py.exe"}
    monkeypatch.setattr(environment.shutil, "which", paths.get)
    assert environment.find_exe(environment.KNOWN_TOOLS["python"]) == r"C:\Windows\py.exe"
    monkeypatch.setattr(environment.shutil, "which", {"python": stub}.get)
    assert environment.find_exe(environment.KNOWN_TOOLS["python"]) is None          # yalnız yer tutucu → yok


# ---- paketli (frozen) çalışmada Serena / masaüstü kontrolü kurulumu sistem Python'unu kullanır ------------------

def test_paketli_uygulamada_temel_python_exe_degil_sistem_pythonu(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(environment, "refresh_path", lambda: None)
    monkeypatch.setattr(environment, "find_exe", lambda tool: r"C:\Py312\python.exe")
    assert mcp._base_python() == r"C:\Py312\python.exe"
    monkeypatch.setattr(environment, "find_exe", lambda tool: None)
    with pytest.raises(mcp.McpError, match="Python 3.11"):
        mcp._base_python()


def test_kaynaktan_calisirken_eski_davranis(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    called = []
    monkeypatch.setattr(environment, "find_exe", lambda tool: called.append(tool) or "X")
    assert Path(mcp._base_python()).name.lower().startswith("python")
    assert called == []                                       # sistem araması yalnız paketliyken


# ---- paket içeriği -------------------------------------------------------------------------------------------------

def test_ayri_ortamda_calisan_betikler_pakete_dosya_olarak_girer():
    for name in ("wmcp_baslatici.py", "blender_donustur.py"):
        assert name in SPEC and (ROOT / "src" / "evren_studio" / "agent" / name).is_file()
    assert "LICENSE" in SPEC and "console=False" in SPEC and "upx=False" in SPEC
    for mod in ("fenced_code", "tables", "sane_lists"):                 # markdown_view.py adla yükler
        assert f"markdown.extensions.{mod}" in SPEC
    assert "keyring.backends.Windows" in SPEC


def test_gomulu_programlar_sabit_surum_ve_ozetli_kurulumla_ayni_dosyalar():
    keys = {it["key"] for it in PREREQS}
    assert keys == {"python", "git", "node", "gh"}
    for it in PREREQS:
        assert re.fullmatch(r"[0-9a-f]{64}", it["sha256"]), it["file"]
        assert it["url"].startswith("https://") and it["url"].endswith(it["file"])
        assert f'"{it["file"]}"' in ISS                                   # iss #define ile aynı dosya adı
        assert it["signer"]


def test_kurulum_eksik_olani_sorar_ve_yalniz_onu_kurar():
    for task, check in (("dev\\python", "NeedPython"), ("dev\\git", "NeedGit"), ("dev\\node", "NeedNode"),
                        ("dev\\gh", "NeedGh")):
        assert re.search(rf'Name: "{re.escape(task)}";.*Check: {check}', ISS)
        assert f"WizardIsTaskSelected('{task}')" in ISS
    assert "WINDOWSAPPS" in ISS                                           # Store yer tutucusu kurulu sayılmaz
    assert "InstallAllUsers=0" in ISS and "/CURRENTUSER" in ISS          # Python ve Git yönetici izni istemez


def test_kurulum_kimligi_kilit_adi_lisans_ve_kapsam():
    assert f"AppMutex={app.MUTEX_NAME}" in ISS
    m = re.search(r"AppId=\{\{([0-9A-F-]{36})\}", ISS)
    assert m and uuid.UUID(m.group(1))                                    # sabit, geçerli GUID
    assert "LicenseFile=..\\LICENSE" in ISS and (ROOT / "LICENSE").read_text(encoding="utf-8").startswith("MIT")
    assert "PrivilegesRequired=lowest" in ISS                             # yönetici izni gerekmez
    assert "{localappdata}\\EVREN-Model-Studio" in ISS                    # veri yeri değişmez


def test_kaldirici_veriyi_yalniz_onayla_ve_sessiz_kaldirmada_hic_silmez():
    block = ISS[ISS.index("procedure CurUninstallStepChanged"):]
    assert "(not UninstallSilent())" in block and "MB_DEFBUTTON2" in block   # varsayılan HAYIR
    assert "if DeleteUserData then" in block and "--anahtarlari-sil" in block
    assert block.index("usUninstall") < block.index("--anahtarlari-sil") < block.index("usPostUninstall")


def test_surum_tek_kaynak():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in pyproject and 'attr = "evren_studio.__version__"' in pyproject
    assert not re.search(r'^version\s*=\s*"', pyproject, re.M)
    assert paketle.version() == __version__
    assert f"filevers=({__version__.replace('.', ', ')}, 0)" in paketle.version_file(__version__)


# ---- duman testi değerlendirmesi ----------------------------------------------------------------------------------

GOOD = ["surum=0.3.0", "frozen=True", "pencere=True", "wmcp_baslatici=var", "blender_donustur=var",
        r"python=C:\Py\python.exe", "keyring=WinVaultKeyring", "tls=tamam 401", "TAMAM"]


def test_duman_testi_eksikleri_yakalar():
    assert paketle.check_smoke(GOOD) == []
    for bad, word in (("frozen=False", "frozen"), ("pencere=False", "pencere"), ("wmcp_baslatici=YOK", "wmcp"),
                      ("blender_donustur=YOK", "blender"), ("keyring=fail.Keyring", "anahtar deposu"),
                      ("tls=HATA ConnectError", "SSL")):
        key = bad.split("=")[0]
        lines = [x for x in GOOD if not x.startswith(key + "=")] + [bad]
        assert any(word in p for p in paketle.check_smoke(lines)), bad
    assert paketle.check_smoke(GOOD[:-1])                                 # TAMAM yok = açılmadı/çöktü


def test_duman_raporu_kaynaktan_da_uretilir(monkeypatch):
    import httpx
    from PySide6.QtWidgets import QApplication, QWidget

    _app = QApplication.instance() or QApplication([])
    urls = []
    monkeypatch.setattr(httpx, "get", lambda url, timeout: urls.append(url) or type("R", (), {"status_code": 401})())
    w = QWidget()
    w.show()
    try:
        kv = dict(x.split("=", 1) for x in app.smoke_report(w))
    finally:
        w.close()
        w.deleteLater()
    assert kv["surum"] == __version__ and kv["pencere"] == "True"
    assert kv["wmcp_baslatici"] == "var" and kv["blender_donustur"] == "var"
    assert kv["tls"] == "tamam 401" and urls and urls[0].endswith("/models")
    assert "keyring" in kv


# ---- kaldırırken anahtarlar: yalnız bu uygulamanınkiler ----------------------------------------------------------

@pytest.mark.skipif(sys.platform != "win32", reason="Credential Manager yalnız Windows")
def test_anahtar_silme_yalniz_uygulama_kayitlarini_siler(monkeypatch):
    import keyring

    svc = f"EVREN-Kaldirma-Testi-{uuid.uuid4().hex[:8]}"
    other = f"Baska-Uygulama-{uuid.uuid4().hex[:8]}"
    keyring.set_password(svc, "evren_api_key", "deneme-1")
    keyring.set_password(svc, "gw-kilo_api_key", "deneme-2")
    keyring.set_password(other, "evren_api_key", "dokunulmamali")
    try:
        monkeypatch.setattr(secrets, "SERVICE_NAME", svc)
        names = {t for t, _k in secrets.windows_credentials()}
        assert names and all(svc in n for n in names)
        assert secrets.delete_all_api_keys() == len(names)
        assert secrets.windows_credentials() == []
        assert keyring.get_password(other, "evren_api_key") == "dokunulmamali"
    finally:
        for s, u in ((svc, "evren_api_key"), (svc, "gw-kilo_api_key"), (other, "evren_api_key")):
            try:
                keyring.delete_password(s, u)
            except keyring.errors.PasswordDeleteError:
                pass


def test_anahtarlari_sil_secenegi_pencere_acmadan_siler(monkeypatch):
    calls = []
    monkeypatch.setattr(secrets, "delete_all_api_keys", lambda: calls.append(1) or 2)
    monkeypatch.setattr(sys, "argv", ["EVREN Studio.exe", "--anahtarlari-sil"])
    assert app.main() == 0 and calls == [1]
