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
    assert brand._R_OUT * 2 / g == pytest.approx(0.5)       # B: dış ay çapı 0,5 G
    assert brand._R_IN * 2 / g == pytest.approx(0.4)        # D: iç ay çapı 0,4 G
    assert brand._IN_DX / g == pytest.approx(1 / 16)        # C: iç ay merkezi 1/16 G sağda
    assert brand._R_STAR * 2 / g == pytest.approx(0.25)     # F: yıldız dairesi çapı 1/4 G
    # E: yıldız dairesinin ay iç dairesinden uzaklığı 1/3 G (iç dairenin sol kenarı → yıldız dairesinin sol kenarı)
    inner_left = brand._IN_DX - brand._R_IN
    star_left = brand._STAR_CX - brand._R_STAR
    assert (star_left - inner_left) / g == pytest.approx(1 / 3)


def test_yildiz_wikimedia_resmi_cizimiyle_ayni_yerde():
    """2026-11-12 düzeltmesi: Wikimedia 'Flag of Turkey' SVG'si (G = 60000; uçkurluk şeridi hariç): dış ay merkezi
    x=30000 (A = 1/2 G), iç ay merkezi 33750, yıldızın aya bakan ucu (41750, 0). Eski kod yıldızı 0,1375 G uzağa
    koyuyordu (E'yi dış ay merkezinden ölçüyordu)."""
    scale = 60000 / brand._G
    outer_cx = 30000
    assert outer_cx + brand._IN_DX * scale == pytest.approx(33750)
    assert outer_cx + (brand._STAR_CX - brand._R_STAR) * scale == pytest.approx(41750)
    assert (outer_cx + brand._STAR_CX * scale) / 60000 == pytest.approx(0.8208, abs=1e-4)   # uçkurluktan 0,8208 G


def test_hilal_ici_bos_yildiz_dolu():
    size = 480.0
    path = brand.crescent_star_path(size, margin=0.0)
    k = size / (brand._STAR_CX + brand._R_STAR + brand._R_OUT)
    ox, oy = brand._R_OUT * k, size / 2
    assert path.contains(QPointF(ox - brand._R_OUT * k * 0.9, oy)), "hilalin sol kalın kısmı dolu"
    assert not path.contains(QPointF(ox + brand._IN_DX * k, oy)), "iç ay dairesi boş (hilal)"
    assert path.contains(QPointF(ox + brand._STAR_CX * k, oy)), "yıldızın merkezi dolu"
    assert not path.contains(QPointF(ox + (brand._STAR_CX - brand._R_STAR) * k - 2, oy)), "yıldız aya değmez"
    assert not path.contains(QPointF(2, 2)), "köşeler boş (arka plan yok)"


def test_animasyon_basinda_halka_sonunda_yasal_hilal():
    """Karşılama animasyonu: iç ay dış ayın tam içindeyken HALKA (içi boş), son hâl yasal hilal + yıldız."""
    k = 10.0
    ring = brand.mark_path(0, 0, k, inner_dx=0.0, star_scale=0.0)
    assert not ring.contains(QPointF(0, 0)), "halkanın ortası boş (eski 'winding' kuralı dolduruyordu)"
    assert ring.contains(QPointF(-(brand._R_OUT - 1.2) * k, 0)) and ring.contains(QPointF((brand._R_OUT - 1.2) * k, 0))
    final = brand.mark_path(0, 0, k)
    ref = brand.mark_path(0, 0, k, inner_dx=brand._IN_DX, star_scale=1.0, star_rot=0.0)
    assert final.boundingRect() == ref.boundingRect()
    mark = brand.BrandMark(80)
    st = mark.state(mark.INTRO_MS)
    assert st["inner_dx"] == pytest.approx(brand._IN_DX) and st["star_scale"] == pytest.approx(1.0)
    assert st["star_rot"] == pytest.approx(0.0) and st["scale"] == pytest.approx(1.0) and st["opacity"] == 1.0
    early = mark.state(300)
    assert early["inner_dx"] < brand._R_OUT - brand._R_IN, "başta iç ay dış ayın içinde (halka)"
    assert early["star_scale"] == 0.0
    mid = mark.state(700)
    assert 0 < mid["star_scale"] and -72.0 < mid["star_rot"] < 0.0


def test_karsilama_logosu_animasyon_kapaliyken_son_hali_cizer(monkeypatch):
    monkeypatch.setenv("EVREN_STUDIO_NO_ANIM", "1")
    mark = brand.BrandMark(80)
    mark.show()
    assert mark.intro_done and not mark.running, "erişilebilirlik: hareket yok, zamanlayıcı çalışmaz"
    mark.replay()
    assert mark.intro_done and not mark.running
    mark.close()


def test_karsilama_logosu_oynar_ve_gizlenince_durur(monkeypatch):
    monkeypatch.delenv("EVREN_STUDIO_NO_ANIM", raising=False)
    monkeypatch.setattr(brand, "animations_enabled", lambda: True)
    mark = brand.BrandMark(80)
    mark.show()
    assert mark.running and not mark.intro_done
    assert mark._timer.interval() == int(1000 / mark.INTRO_FPS)
    mark._t0 -= 2.0                                      # 2 sn ilerlet: giriş biter, sakin ışımaya geçer
    mark._tick()
    assert mark.intro_done and mark._timer.interval() == int(1000 / mark.IDLE_FPS)
    mark.hide()
    assert not mark.running, "görünmezken işlemci harcamaz"
    mark.replay()                                        # gizliyken yeniden oynatma zamanlayıcı başlatmaz
    assert not mark.running and mark._ms == 0.0
    mark.show()
    assert mark.running
    mark.close()


def test_cam_karo_simgesi():
    """Uygulama simgesi: süperelips köşeleri saydam, zemin bayrak kırmızısı çevresinde, ay-yıldız beyaz."""
    img = brand.tile_pixmap(128, ratio=1.0).toImage()
    assert img.pixelColor(0, 0).alpha() == 0 and img.pixelColor(127, 127).alpha() == 0, "köşeler saydam"
    k = 128 * 0.64 / brand._MARK_W
    ox = (128 - brand._MARK_W * k) / 2 + brand._R_OUT * k
    body = img.pixelColor(int(ox - brand._R_OUT * k * 0.85), 64)          # hilalin kalın kısmı
    hollow = img.pixelColor(int(ox + brand._IN_DX * k), 64)               # iç ay (zemin görünür)
    star = img.pixelColor(int(ox + brand._STAR_CX * k), 64)
    assert body.red() > 240 and body.green() > 240 and body.blue() > 240, "hilal beyaz"
    assert star.red() > 240 and star.green() > 240, "yıldız beyaz"
    assert hollow.red() > 180 and hollow.green() < 60 and hollow.blue() < 70, "zemin kırmızı"
    assert brand.tile_pixmap(128, ratio=1.0) is brand.tile_pixmap(128, ratio=1.0), "önbellekli"


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


def test_calisma_yildizi_72_derece_adimla_parildar():
    """Her adım 72° (yıldızın simetrisi): adım sonunda yıldız yine yasal yönde, duruşta parıltı sıfır."""
    cyc = brand.BusyStar.STEP_S + brand.BusyStar.HOLD_S
    a_hold, g_hold = brand.BusyStar.pose(brand.BusyStar.STEP_S + 0.1)
    assert a_hold == pytest.approx(72.0) and g_hold == 0.0
    a_mid, g_mid = brand.BusyStar.pose(brand.BusyStar.STEP_S / 2)
    assert 0 < a_mid < 72 and g_mid == pytest.approx(1.0)
    assert brand.BusyStar.pose(4 * cyc + 0.95 * cyc)[0] == pytest.approx(0.0, abs=1e-6), "5. adımdan sonra tam tur"
    angles = [brand.BusyStar.pose(i * 0.03)[0] for i in range(int(brand.BusyStar.STEP_S / 0.03))]
    assert angles == sorted(angles), "adım içinde geri dönmez"


def test_calisma_yildizi_animasyon_kapaliyken_donmez(monkeypatch):
    monkeypatch.setenv("EVREN_STUDIO_NO_ANIM", "1")
    star = brand.BusyStar(14)
    star.start()
    assert not star.running


def test_canli_gosterge_ilerler(monkeypatch):
    monkeypatch.delenv("EVREN_STUDIO_NO_ANIM", raising=False)
    monkeypatch.setattr(brand, "animations_enabled", lambda: True)
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


def test_karsilama_ekrani_canli_logo_ve_yeni_oturumda_yeniden_olusur(tmp_path, monkeypatch, fake_keyring):
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    try:
        logo = w.session.welcome.logo
        assert isinstance(logo, brand.BrandMark)
        calls = []
        monkeypatch.setattr(logo, "replay", lambda: calls.append(1))
        w.session.new_session()
        assert calls == [1]
        side = w.sidebar.logo.pixmap()
        assert side is not None and side.width() == 48, "kenar çubuğunda 24 px cam karo (2x)"
    finally:
        w.close()
