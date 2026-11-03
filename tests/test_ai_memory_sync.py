"""`ai_memory.py baslangic` GitHub eşitlemesi — geçici git depolarıyla.

Senaryo: kullanıcı A bilgisayarında çalışıp GitHub'a gönderir, B bilgisayarında
motor oturumu açar. B'deki motor bunu kendisi fark etmeli; güvenliyse
kendiliğinden güncellemeli, değilse veri kaybettirmeden uyarmalı.
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git yok")


def _load():
    spec = importlib.util.spec_from_file_location("ai_memory", ROOT / "tools" / "ai_memory.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()


def g(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=t@example.test",
                        "-c", "core.hooksPath=", "-c", "commit.gpgsign=false", *args],
                       cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def commit(repo: Path, name: str, text: str = "x") -> None:
    (repo / name).write_text(text, encoding="utf-8")
    g(repo, "add", name)
    g(repo, "commit", "-q", "-m", f"ekle {name}")


@pytest.fixture()
def repos(tmp_path):
    """origin (çıplak) + a (diğer bilgisayar) + b (bu bilgisayar)."""
    origin = tmp_path / "origin.git"
    g(tmp_path, "init", "-q", "--bare", "-b", "master", str(origin))
    a = tmp_path / "a"
    g(tmp_path, "clone", "-q", str(origin), str(a))
    commit(a, "ilk.txt")
    g(a, "push", "-q", "origin", "master")
    b = tmp_path / "b"
    g(tmp_path, "clone", "-q", str(origin), str(b))
    return origin, a, b


def head(repo: Path) -> str:
    return g(repo, "rev-parse", "HEAD")


def test_esit_kopya(repos):
    _, _, b = repos
    out = m.sync_with_remote(b)
    assert out == ["✓ Yerel kopya GitHub ile eşit ('master')."]


def test_geride_ve_temiz_ise_otomatik_alinir(repos):
    _, a, b = repos
    commit(a, "diger_bilgisayar.txt")
    g(a, "push", "-q", "origin", "master")
    out = m.sync_with_remote(b)
    assert any("1 yeni commit otomatik alındı" in line for line in out), out
    assert head(b) == head(a) and (b / "diger_bilgisayar.txt").exists()


def test_yerel_degisiklik_varsa_dokunulmaz(repos):
    _, a, b = repos
    commit(a, "diger.txt")
    g(a, "push", "-q", "origin", "master")
    (b / "ilk.txt").write_text("yarım iş", encoding="utf-8")
    before = head(b)
    out = m.sync_with_remote(b)
    assert head(b) == before and (b / "ilk.txt").read_text(encoding="utf-8") == "yarım iş"
    assert any("GERİSİNDE" in line and "commit'lenmemiş" in line for line in out), out


def test_ayrismis_dallar_birlestirilmez(repos):
    _, a, b = repos
    commit(a, "a.txt")
    g(a, "push", "-q", "origin", "master")
    commit(b, "b.txt")
    before = head(b)
    out = m.sync_with_remote(b)
    assert head(b) == before
    assert any("ayrışmış" in line for line in out), out


def test_gonderilmemis_commit_uyarisi(repos):
    _, _, b = repos
    commit(b, "yerel.txt")
    out = m.sync_with_remote(b)
    assert any("gönderilmemiş 1 commit" in line for line in out), out


def test_birlesmis_daldan_mastera_gecilir(repos):
    _, a, b = repos
    g(b, "checkout", "-q", "-b", "feat/x")
    commit(b, "ozellik.txt")
    g(b, "push", "-q", "-u", "origin", "feat/x")
    # diğer bilgisayarda (GitHub'da) birleştirildi
    g(a, "fetch", "-q", "origin")
    g(a, "merge", "-q", "--no-ff", "-m", "Merge feat/x", "origin/feat/x")
    g(a, "push", "-q", "origin", "master")
    out = m.sync_with_remote(b)
    assert g(b, "rev-parse", "--abbrev-ref", "HEAD") == "master", out
    assert head(b) == head(a)
    assert any("master'a birleştirilmişti" in line for line in out), out


def test_otomatik_kapaliyken_yalniz_uyarir(repos):
    _, a, b = repos
    commit(a, "yeni.txt")
    g(a, "push", "-q", "origin", "master")
    before = head(b)
    out = m.sync_with_remote(b, auto=False)
    assert head(b) == before and any("GERİSİNDE" in line for line in out)


def test_uzak_depoya_ulasilamazsa_uyarir(repos):
    origin, _, b = repos
    g(b, "remote", "set-url", "origin", str(origin.parent / "olmayan.git"))   # ağ yok taklidi
    out = m.sync_with_remote(b)
    assert len(out) == 1 and "ulaşılamadı" in out[0]


def test_uzak_depo_yoksa(tmp_path):
    g(tmp_path, "init", "-q", "-b", "master")
    assert "origin" in m.sync_with_remote(tmp_path)[0]


def test_git_deposu_degilse_sessiz(tmp_path):
    d = tmp_path / "depo-degil"
    d.mkdir()
    assert m.sync_with_remote(d) == []


# ---- devir: başka bilgisayarda süren çalışma dalı (R-35) ---------------------------------------------

DEVIR = "# DEVİR\n\n## Şu an\n\n- Kaldığı yer: Madde 5 kart arayüzü yarım\n\n## Geliştirme sırası\n\n- x\n"


def test_baska_bilgisayardaki_yeni_calisma_dali_bulunur(repos):
    _, a, b = repos
    g(a, "switch", "-q", "-c", "feat/devam")
    (a / "docs").mkdir()
    commit(a, "docs/DEVIR_NOTU.md", DEVIR)
    g(a, "push", "-q", "-u", "origin", "feat/devam")
    m.sync_with_remote(b)                                       # fetch
    name, subject, now = m.active_work_branch(b)
    assert name == "feat/devam" and "Madde 5 kart arayüzü yarım" in now and "ekle" in subject
    g(b, "switch", "-q", "feat/devam")                           # bu bilgisayar da o dala geçti → uyarı yok
    assert m.active_work_branch(b) is None


def test_birlestirilmis_dal_devam_eden_is_sayilmaz(repos):
    _, a, b = repos
    g(a, "switch", "-q", "-c", "feat/bitti")
    commit(a, "is.txt")
    g(a, "push", "-q", "-u", "origin", "feat/bitti")
    g(a, "switch", "-q", "master")
    g(a, "merge", "-q", "--ff-only", "feat/bitti")
    g(a, "push", "-q", "origin", "master")
    m.sync_with_remote(b)
    assert m.active_work_branch(b) is None


def test_kod_degisen_commit_devir_notu_olmadan_durur(monkeypatch):
    staged = {"v": ""}
    monkeypatch.setattr(m, "git", lambda *a: staged["v"])
    monkeypatch.setattr(m, "check", lambda: [])
    staged["v"] = "src/evren_studio/x.py\ndocs/ai-memory/sessions/s.md"
    assert m.cmd_kanca(None) == 1
    staged["v"] += "\ndocs/DEVIR_NOTU.md"
    assert m.cmd_kanca(None) == 0
    staged["v"] = "tests/test_x.py\ndocs/ai-memory/sessions/s.md"          # yalnız test: devir notu şart değil
    assert m.cmd_kanca(None) == 0
