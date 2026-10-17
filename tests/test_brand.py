"""Ay-yıldız simgesi (Türk Bayrağı Kanunu oranları), tema renkleri, .ico ve canlı gösterge."""
from __future__ import annotations

import os
import struct

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from evren_studio.ui import brand, theme  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def app():
    return QApplication.instance() or QApplication([])


def test_bayrak_oranlari():
    g = brand._G
    assert brand._R_OUT * 2 / g == pytest.approx(0.5)       # dış ay çapı 0,5 G
    assert brand._R_IN * 2 / g == pytest.approx(0.4)        # iç ay çapı 0,4 G
    assert brand._IN_DX / g == pytest.approx(1 / 16)        # iç ay merkezi 1/16 G sağda
    assert brand._R_STAR * 2 / g == pytest.approx(0.25)     # yıldız dairesi çapı 1/4 G
    assert (brand._STAR_CX - brand._R_STAR) / g == pytest.approx(1 / 3)   # dış ay merkezi → yıldız dairesi


def test_hilal_ici_bos_yildiz_dolu():
    size = 480.0
    path = brand.crescent_star_path(size, margin=0.0)
    k = size / (brand._STAR_CX + brand._R_STAR + brand._R_OUT)
    ox, oy = brand._R_OUT * k, size / 2
    assert path.contains(QPointF(ox - brand._R_OUT * k * 0.9, oy)), "hilalin sol kalın kısmı dolu"
    assert not path.contains(QPointF(ox + brand._IN_DX * k, oy)), "iç ay dairesi boş (hilal)"
    assert path.contains(QPointF(ox + brand._STAR_CX * k, oy)), "yıldızın merkezi dolu"
    assert not path.contains(QPointF(2, 2)), "köşeler boş (arka plan yok)"


def test_yildizin_bir_ucu_hilale_bakar():
    p = brand.star_path(0, 0, 10)
    first = p.elementAt(0)
    assert (round(first.x, 6), round(first.y, 6)) == (-10, 0)


def test_tema_renkleri():
    assert brand.brand_color(theme.DARK) == brand.FLAG_WHITE    # koyu: bayraktaki gibi beyaz
    assert brand.brand_color(theme.LIGHT) == brand.FLAG_RED     # açık: bayrak kırmızısı


def test_simge_saydam_zeminli():
    img = brand.pixmap(64, brand.FLAG_RED, ratio=1.0).toImage()
    assert img.pixelColor(0, 0).alpha() == 0 and img.pixelColor(63, 63).alpha() == 0
    assert img.hasAlphaChannel()


def test_ico_tum_boyutlar(tmp_path):
    path = tmp_path / "e.ico"
    assert brand.save_ico(str(path))
    data = path.read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind, count) == (0, 1, len(brand.ICO_SIZES))
    sizes = [data[6 + 16 * i] or 256 for i in range(count)]
    assert sizes == list(brand.ICO_SIZES)


def test_canli_gosterge_ilerler():
    star = brand.BusyStar(14)
    a0 = star._angle
    star._advance()
    star._advance()
    assert star._angle != a0
    star.start()
    assert star.running
    star.stop()
    assert not star.running
    assert star.focusPolicy() == Qt.NoFocus
