"""Ajan araçları: proje sınırı, okuma/yazma/düzenleme, geri alma, komut."""
from __future__ import annotations

import os

import pytest

from evren_studio.agent.tools import (
    ToolBox,
    ToolError,
    Workspace,
    revert_file,
    validate_todos,
)


@pytest.fixture()
def ws(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def a():\n    return 1\n\ndef b():\n    return 1\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Proje\nAçıklama satırı\n", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "gizli.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    return Workspace(tmp_path)


@pytest.fixture()
def tb(ws):
    return ToolBox(ws, command_timeout=30)


# ---- proje sınırı -----------------------------------------------------------


def test_proje_disina_cikis_engellenir(ws, tmp_path):
    with pytest.raises(ToolError):
        ws.resolve("../disari.txt")
    with pytest.raises(ToolError):
        ws.resolve(str(tmp_path.parent / "baska.txt"))
    assert ws.resolve("src/app.py").name == "app.py"


def test_git_klasorune_yazilamaz(ws, tb):
    with pytest.raises(ToolError):
        ws.resolve(".git/config", for_write=True)
    with pytest.raises(ToolError):
        tb.prepare_write(".git/hooks/pre-commit", "kötü")


def test_git_dali_okunur(ws):
    assert ws.git_branch() == "main"


def test_proje_hafizasi(ws, tmp_path):
    assert ws.project_memory() == (None, "")
    (tmp_path / "CLAUDE.md").write_text("yalnız claude", encoding="utf-8")
    assert ws.project_memory()[0] == "CLAUDE.md"
    (tmp_path / "EVREN.md").write_text("Testler: pytest", encoding="utf-8")
    name, text = ws.project_memory()
    assert name == "EVREN.md" and "pytest" in text
    (tmp_path / "AGENTS.md").write_text("Önce tools/ai_memory.py baslangic", encoding="utf-8")
    name, text = ws.project_memory()
    assert name == "EVREN.md + AGENTS.md"
    assert "pytest" in text and "ai_memory" in text and "yalnız claude" not in text


# ---- okuma -------------------------------------------------------------------


def test_listeleme_gereksiz_klasorleri_atlar(tb):
    out = tb.list_files(".", 3)
    assert "src/" in out and "app.py" in out
    assert ".venv" not in out and ".git" not in out


def test_dosya_okuma_satir_numarali_ve_aralik(tb):
    out = tb.read_file("src/app.py")
    assert "1\tdef a():" in out and "(5 satır)" in out
    part = tb.read_file("src/app.py", 4, 5)
    assert "4\tdef b():" in part and "def a" not in part


def test_ikili_dosya_okunmaz(tb, tmp_path):
    (tmp_path / "x.bin").write_bytes(b"\x00\x01\x02")
    with pytest.raises(ToolError):
        tb.read_file("x.bin")


def test_arama_ve_glob(tb):
    out = tb.search_files("return 1")
    assert out.count("src/app.py:") == 2
    assert "gizli.py" not in tb.search_files("x = 1")
    assert tb.search_files("yok-boyle-bir-sey") == "Eşleşme bulunamadı."
    assert "src/app.py" in tb.find_files("**/*.py")
    assert "README.md" in tb.find_files("*.md")
    # geçersiz regex düz metin olarak aranır
    assert "Eşleşme" in tb.search_files("(((")


# ---- yazma / düzenleme ----------------------------------------------------------


def test_duzenleme_tekil_olmali(tb):
    with pytest.raises(ToolError, match="2 kez"):
        tb.prepare_edit("src/app.py", "return 1", "return 2")
    with pytest.raises(ToolError, match="bulunamadı"):
        tb.prepare_edit("src/app.py", "olmayan", "x")
    ch = tb.prepare_edit("src/app.py", "def b():\n    return 1", "def b():\n    return 2")
    assert ch.stats == (1, 1)
    tb.apply_change(ch)
    assert "return 2" in (tb.ws.root / "src" / "app.py").read_text(encoding="utf-8")


def test_replace_all(tb):
    ch = tb.prepare_edit("src/app.py", "return 1", "return 3", replace_all=True)
    tb.apply_change(ch)
    assert (tb.ws.root / "src" / "app.py").read_text(encoding="utf-8").count("return 3") == 2


def test_crlf_ve_bom_korunur(tb, tmp_path):
    raw = b"\xef\xbb\xbfsat\xc4\xb1r1\r\nsatir2\r\n"
    (tmp_path / "w.txt").write_bytes(raw)
    ch = tb.prepare_edit("w.txt", "satir2", "satir3")
    tb.apply_change(ch)
    data = (tmp_path / "w.txt").read_bytes()
    assert data.startswith(b"\xef\xbb\xbf")
    assert data.endswith(b"satir3\r\n") and b"\r\n" in data


def test_yeni_dosya_ve_onay_sirasinda_degisiklik(tb, tmp_path):
    ch = tb.prepare_write("yeni/modul.py", "print('merhaba')\n")
    assert ch.is_new and "+print" in ch.diff
    tb.apply_change(ch)
    assert (tmp_path / "yeni" / "modul.py").exists()
    # Onay beklenirken dosya dışarıdan değişirse üzerine yazılmaz
    ch2 = tb.prepare_edit("README.md", "Açıklama", "Yeni açıklama")
    (tmp_path / "README.md").write_text("başkası değiştirdi\n", encoding="utf-8")
    with pytest.raises(ToolError, match="değişmiş"):
        tb.apply_change(ch2)


def test_ayni_icerik_yazilmaz(tb):
    with pytest.raises(ToolError):
        tb.prepare_write("README.md", "# Proje\nAçıklama satırı\n")


# ---- geri alma -----------------------------------------------------------------


def test_geri_alma(tb, tmp_path):
    ch = tb.prepare_edit("README.md", "Açıklama", "Değişti")
    tb.apply_change(ch)
    revert_file(tmp_path, ch.rel_path, ch.before, ch.after)
    assert "Açıklama" in (tmp_path / "README.md").read_text(encoding="utf-8")


def test_geri_alma_yeni_dosyayi_siler(tb, tmp_path):
    ch = tb.prepare_write("gecici.txt", "x\n")
    tb.apply_change(ch)
    revert_file(tmp_path, ch.rel_path, None, ch.after)
    assert not (tmp_path / "gecici.txt").exists()


def test_geri_alma_sonradan_degismisse_onay_ister(tb, tmp_path):
    ch = tb.prepare_edit("README.md", "Açıklama", "Değişti")
    tb.apply_change(ch)
    (tmp_path / "README.md").write_text("elle düzenlendi\n", encoding="utf-8")
    with pytest.raises(ToolError):
        revert_file(tmp_path, ch.rel_path, ch.before, ch.after)
    revert_file(tmp_path, ch.rel_path, ch.before, ch.after, force=True)
    assert "Açıklama" in (tmp_path / "README.md").read_text(encoding="utf-8")


# ---- görevler ve komut ----------------------------------------------------------


def test_gorev_listesi_dogrulama():
    out = validate_todos([{"content": "A", "status": "completed"}, {"content": "B", "status": "x"}])
    assert out[1]["status"] == "pending"
    with pytest.raises(ToolError):
        validate_todos("liste değil")


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gerekir")
def test_komut_calisir_ve_cikti_doner(tb):
    lines = []
    res = tb.run_command("Write-Output 'merhaba dünya'", on_output=lines.append)
    assert res.exit_code == 0 and "merhaba dünya" in res.output
    assert lines
    assert "Çıkış kodu: 0" in res.to_text()


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gerekir")
def test_komut_zaman_asimi(tb):
    res = tb.run_command("Start-Sleep -Seconds 20", timeout_seconds=1)
    assert res.timed_out and res.duration < 15


def test_proje_sanal_ortami_path_basina_eklenir(tmp_path):
    from evren_studio.agent.tools import find_project_venv, project_env

    assert find_project_venv(tmp_path) is None
    scripts = tmp_path / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").write_bytes(b"")
    assert find_project_venv(tmp_path) == scripts
    env = project_env(tmp_path)
    assert env["PATH"].startswith(str(scripts)) and env["VIRTUAL_ENV"].endswith(".venv")


@pytest.mark.skipif(os.name != "nt", reason="PowerShell gerekir")
def test_komut_proje_klasorunde_calisir(tb, tmp_path):
    res = tb.run_command("(Get-Location).Path")
    assert os.path.normcase(str(tmp_path.resolve())) in os.path.normcase(res.output)
