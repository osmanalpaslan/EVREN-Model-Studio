"""Okunurluk (kontrast) bekçisi: her ekran, iki tema — hiçbir etkin yazı/düğme/simge WCAG 3:1 altında olmamalı.

Kullanıcı bildirimi (2026-11-01): açık modda bazı düğmeler neredeyse görünmüyor, Ayarlar'daki
sabit yazılar tema yüzünden okunmuyor. Ölçüm aracı: tools/ui_denetim.py (pencere görüntüsünden
yazı ile arka plan arasındaki oran). Bir tema rengi veya bileşen stili bu sınırı bozarsa test düşer.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]


def _arac():
    spec = importlib.util.spec_from_file_location("ui_denetim", ROOT / "tools" / "ui_denetim.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_kontrast_olcumu_bilinen_renklerle():
    m = _arac()
    assert m.contrast((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0, rel=1e-3)
    assert m.contrast((0x90, 0x95, 0xA0), (0xFB, 0xFB, 0xFA)) < 3.0, "eski soluk renk yakalanmalı"
    assert m.contrast((0x64, 0x69, 0x74), (0xFB, 0xFB, 0xFA)) > 4.5


@pytest.mark.parametrize("tema", ["açık", "koyu"])
def test_tum_ekranlarda_okunmayan_bilesen_yok(tema, tmp_path, monkeypatch, fake_keyring):
    m = _arac()
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    bulgular = m.denetle(tema, tmp_path, goruntu=False)
    hatalar = [f"{b['ekran']} · {b['tur']} · {b['oran']} · {b['metin'][:50]!r} ({b['ad']}, ön {b['on']} / arka {b['arka']})"
               for b in bulgular if b["duzey"] == "HATA"]
    assert not hatalar, "Okunmayan bileşenler:\n" + "\n".join(hatalar)
