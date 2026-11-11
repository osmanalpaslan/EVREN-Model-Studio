"""Geçici klasör sızıntısı (2026-11-11, disk temizliği oturumunun bulgusu): Temp'te 21 evren-masaustu-* (~8,5 GB) ve
154 evren-denetim-* birikmişti — betikler tempfile.mkdtemp klasörlerini silmiyordu. tools/gecici.py çıkışta siler."""
from __future__ import annotations

import os
import re
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import gecici  # noqa: E402


def test_kayitli_klasorler_silinir_salt_okunur_dahil(monkeypatch):
    monkeypatch.setattr(gecici, "_dirs", [])
    d = gecici.klasor("evren-test-gecici-")
    (d / "alt").mkdir()
    ro = d / "alt" / "nesne"                  # git nesneleri gibi salt okunur
    ro.write_text("x", encoding="utf-8")
    os.chmod(ro, stat.S_IREAD)
    assert d.exists() and gecici._dirs == [d]
    assert gecici.temizle() == [] and not d.exists() and gecici._dirs == []


def test_sakla_secenegi_silmez(monkeypatch, capsys):
    monkeypatch.setattr(gecici, "_dirs", [])
    monkeypatch.setenv("EVREN_GECICI_SAKLA", "1")
    d = gecici.klasor("evren-test-sakla-")
    try:
        gecici._cikista()
        assert d.exists() and "SAKLANDI" in capsys.readouterr().err
    finally:
        monkeypatch.delenv("EVREN_GECICI_SAKLA")
        gecici.temizle()
    assert not d.exists()


def test_kilitli_dosya_birakilinca_yeniden_denenir(monkeypatch):
    d = gecici.klasor("evren-test-kilit-")
    calls = {"n": 0}
    real = gecici.shutil.rmtree

    def flaky(path, onerror=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return                            # ilk denemede silinemedi (kapanmakta olan süreç kilidi)
        real(path, onerror=onerror)
    monkeypatch.setattr(gecici.shutil, "rmtree", flaky)
    monkeypatch.setattr(gecici.time, "sleep", lambda s: None)
    assert gecici.sil(d) and calls["n"] == 2 and not d.exists()


def test_betikler_gecici_klasoru_silmeden_birakmaz():
    """Bekçi: tests/e2e_*.py ve tools/*.py'de mkdtemp varsa o dosya ya gecici.klasor kullanmalı ya da rmtree ile silmeli."""
    kotu = []
    for f in sorted(list((ROOT / "tests").glob("e2e_*.py")) + list((ROOT / "tools").glob("*.py"))):
        t = f.read_text(encoding="utf-8")
        if re.search(r"tempfile\.mkdtemp\(", t) and "rmtree" not in t and "klasor(" not in t:
            kotu.append(f.name)
    assert not kotu, "Geçici klasör silinmiyor: " + ", ".join(kotu)
    for name in ("e2e_masaustu_real_api.py", "e2e_hiz_auto_karsilastirma_real_api.py", "e2e_ui_real_api.py",
                 "e2e_zamanlayici_real_api.py"):
        assert "tempfile.mkdtemp" not in (ROOT / "tests" / name).read_text(encoding="utf-8"), name
    assert "sil(data)" in (ROOT / "tools" / "ui_denetim.py").read_text(encoding="utf-8")
