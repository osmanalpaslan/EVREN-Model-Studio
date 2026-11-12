"""testcheck: proje türüne göre test komutu ve sonucun sınıflandırılması (2026-11-13 kapsam ölçümü: %72, Node/.NET,
"pytest yoksa unittest", zaman aşımı ve "test yok" yolları hiç sınanmıyordu). Derin Mod doğrulaması artık her proje
türünde bu kodla testleri GERÇEKTEN çalıştırıyor: yanlış "düştü" denetçiye sahte "yüksek" sorun, yanlış "geçti"
kanıtsız onay demektir. Tetiklenen ve tetiklenmeyen durumlar ayrı sınanır (R-22).
"""
from __future__ import annotations

import pytest
from test_derin_kanit import _sub_returning

from evren_studio.agent import deep as dp
from evren_studio.agent import testcheck
from evren_studio.agent.tools import CommandResult


class Box:
    """ToolBox yerine: run_command'ın gerçek sonuç türünü döndürür, çağrıyı kaydeder."""

    def __init__(self, code=None, out="", timed_out=False, cancelled=False):
        self.res = CommandResult(command="x", exit_code=code, output=out, duration=1.0, timed_out=timed_out,
                                 cancelled=cancelled)
        self.calls: list[tuple[str, int | None]] = []

    def run_command(self, command, timeout_seconds=None, cancel=None):
        self.calls.append((command, timeout_seconds))
        return self.res


@pytest.mark.parametrize("kw, durum", [
    ({"code": 0, "out": "3 passed"}, "gecti"),
    ({"code": 1, "out": "1 failed"}, "dustu"),
    ({"code": 5, "out": "collected 0 items"}, "yok"),         # pytest: hiç test yok (yalnız çıkış kodu söyler)
    ({"code": 0, "out": "NO TESTS RAN"}, "yok"),              # unittest: hiç test yok
    ({"timed_out": True}, "yok"),                             # zaman aşımı "düştü" sayılmaz
    ({"cancelled": True}, "yok"),                             # kullanıcı durdurdu
])
def test_sonuc_siniflandirma(kw, durum):
    box = Box(**kw)
    assert testcheck.run(box, "python -m pytest -q", timeout=7)[0] == durum
    assert box.calls == [("python -m pytest -q", 7)]


def test_pytest_yoksa_unittest_ve_dogru_baslangic_klasoru(tmp_path, monkeypatch):
    monkeypatch.setattr(testcheck, "_has_pytest", lambda root: False)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("x = 1\n", encoding="utf-8")
    assert testcheck.detect_command(tmp_path) == "python -m unittest discover -s tests -q"
    duz = tmp_path / "duz"
    duz.mkdir()
    (duz / "a_test.py").write_text("x = 1\n", encoding="utf-8")
    assert testcheck.detect_command(duz) == "python -m unittest discover -s . -q"


def test_pytest_denetimi_calismazsa_kurulu_sayilmaz(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("python yok")
    monkeypatch.setattr(testcheck.subprocess, "run", boom)
    assert testcheck._has_pytest(tmp_path) is False


def test_npm_testi_yalniz_gercek_betik_ve_kurulu_modullerle(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}', encoding="utf-8")
    assert testcheck.detect_command(tmp_path) is None                 # node_modules yok: npm test çalışamaz
    (tmp_path / "node_modules").mkdir()
    assert testcheck.detect_command(tmp_path) == "npm test --silent"
    (tmp_path / "package.json").write_text("{bozuk", encoding="utf-8")
    assert testcheck.detect_command(tmp_path) is None                 # bozuk package.json çökertmez


def test_dotnet_yalniz_test_sdk_li_proje(tmp_path):
    (tmp_path / "Uyg.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"></Project>', encoding="utf-8")
    assert testcheck.detect_command(tmp_path) is None                 # test projesi değil
    t = tmp_path / "Uyg.Tests"
    t.mkdir()
    (t / "Uyg.Tests.csproj").write_text('<PackageReference Include="Microsoft.NET.Test.Sdk" />', encoding="utf-8")
    assert testcheck.detect_command(tmp_path) == "dotnet test --nologo -v q"


def test_projenin_sanal_ortami_kullanilir(tmp_path):
    exe = tmp_path / ".venv" / "Scripts" / "python.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    assert testcheck._python(tmp_path) == str(exe)


def test_derin_dogrulamada_calismayan_test_sorun_sayilmaz_ve_istem_soyler():
    """Zaman aşımı / test yok → "yüksek" sorun EKLENMEZ (tetiklenmeyen); istem testlerin çalışmadığını söyler."""
    sub = _sub_returning([])
    tests = {"komut": "python -m pytest -q", "durum": "yok", "cikis": None, "son": ""}
    assert dp.verify(dp.DeepState(goal="g"), "--- a\n+++ b\n+x\n", sub, tests=tests, with_tests=True) == []
    assert all("çalışmadı" in p for p in sub.prompts)
