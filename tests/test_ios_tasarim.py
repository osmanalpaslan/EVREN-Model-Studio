"""iOS 27 / Liquid Glass tasarım dili (2026-11-12, kullanıcı isteği "güncel iOS tasarım dili").

Renk belirteçleri yedi zeminde WCAG ile ölçülür (R-33); kullanıcının koyu tema kararları (tüm yazı parlak, vurgu beyaz,
seçili satır nötr gri) ayrıca tests/test_klavye_baglam_tema.py'de korunur. Anahtar (switch), seçim dairesi ve açılır
liste işareti SVG'leri gerçekten yazılır ve palet rengini taşır.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from evren_studio.ui import theme  # noqa: E402

ZEMINLER = ("bg", "sidebar", "panel", "surface", "surface2", "hover", "selected")


def _lum(h: str) -> float:
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def _cr(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


@pytest.mark.parametrize("pal", [theme.LIGHT, theme.DARK], ids=["açık", "koyu"])
def test_yazi_ve_anlam_renkleri_tum_zeminlerde_okunur(pal):
    for fg in ("text", "text_dim", "text_faint", "muted", "success", "danger", "warning", "accent"):
        for bg in ZEMINLER + ("accent_soft", "bubble", "glass_top", "glass_bottom"):
            assert _cr(getattr(pal, fg), getattr(pal, bg)) >= 4.5, (pal.name, fg, bg)
    assert _cr(pal.on_accent, pal.accent) >= 4.5


def test_acik_tema_parlak_beyaz_degil_yumusak_gri():
    """Kullanıcı tercihi (DepoWise'da seçilen dil): zemin parlak beyaz değil; kartlar zeminden açık, kenar çubuğu koyu."""
    lt = theme.LIGHT
    assert _lum(lt.bg) < 0.86, "zemin yumuşak gri"
    assert _lum(lt.surface) > _lum(lt.bg) > _lum(lt.sidebar)
    r, g, b = (int(lt.bg[i:i + 2], 16) for i in (1, 3, 5))
    assert max(r, g, b) - min(r, g, b) <= 10, "nötr gri (renk kaymasız)"


def test_anahtar_kapali_izi_zeminde_gorunur():
    """iOS 27 tanımlı kenar: kapalı anahtarın kenarı açık zeminde ≥ 2,5 ayırt edilir; açık iz yeşil."""
    for pal in (theme.LIGHT, theme.DARK):
        assert _cr(pal.switch_line, pal.surface) >= 2.5 or pal.name == "koyu", pal.name
        r, g, b = (int(pal.switch_on[i:i + 2], 16) for i in (1, 3, 5))
        assert g > r and g > b, "açık iz yeşil (iOS)"
    assert _cr(theme.LIGHT.switch_on, theme.LIGHT.surface) >= 3.0


def _urls(css: str) -> dict[str, str]:
    out = {}
    for sel, url in re.findall(r"([^{}\n]+?)\s*\{[^{}]*?image: url\(\"([^\"]+)\"\)", css):
        out[sel.strip()] = url
    return out


@pytest.mark.parametrize("pal", [theme.LIGHT, theme.DARK], ids=["açık", "koyu"])
def test_qss_gorsel_varliklari_yazilir_ve_palet_rengini_tasir(pal):
    css = theme.build_qss(pal, 10)
    urls = _urls(css)
    need = {"QCheckBox::indicator:unchecked": pal.switch_off, "QCheckBox::indicator:checked": pal.switch_on,
            "QListView::indicator:checked": pal.accent, "QComboBox::down-arrow": pal.text_dim}
    for sel, color in need.items():
        assert sel in urls, sel
        svg = Path(urls[sel]).read_text(encoding="utf-8")
        assert color.lower() in svg.lower(), (sel, color)
    assert 'opacity="0.45"' in Path(urls["QCheckBox::indicator:checked:disabled"]).read_text(encoding="utf-8")
    # Kenar yarıçapları iç içe uyumlu: giriş < düğme < kart < yazma kutusu
    assert theme.R_FIELD < theme.R_BUTTON < theme.R_CARD < theme.R_COMPOSER
    assert f"QFrame#Composer {{ background: qlineargradient" in css and f"border-radius: {theme.R_COMPOSER}px" in css
    assert "QFrame#Segmented QToolButton:checked" in css


def test_renk_degisince_yeni_svg_yazilir():
    a = theme._switch_icon(theme.LIGHT, True)
    b = theme._switch_icon(theme.DARK, True)
    assert a != b and Path(a).is_file() and Path(b).is_file()
    assert theme._switch_icon(theme.LIGHT, True) == a, "aynı içerik aynı dosya"


def test_kucuk_yazilar_ve_hap_secicileri_kenarli():
    """Yazma kutusundaki seçiciler düz yazı gibi görünüyordu: ince kenarlı kapsül olmalı (tetiklenen); simge
    düğmeleri (araç çubuğu) çerçevesiz kalır (tetiklenmeyen)."""
    css = theme.build_qss(theme.LIGHT, 10)
    chip = re.search(r'QToolButton\[variant="chip"\] \{([^}]*)\}', css).group(1)
    assert f"border: 1px solid {theme.LIGHT.border}" in chip
    icon = re.search(r'QToolButton\[variant="icon"\], QPushButton\[variant="icon"\] \{([^}]*)\}', css).group(1)
    assert "border: none" in icon


def test_sag_panel_bolumlu_denetim(tmp_path, monkeypatch, fake_keyring):
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    from PySide6.QtWidgets import QApplication, QFrame

    QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    try:
        seg = w.panel.segments
        assert isinstance(seg, QFrame) and seg.objectName() == "Segmented"
        assert all(b.parent() is seg for b in w.panel._buttons) and len(w.panel._buttons) == 6
        w.panel.show_tab("changes")
        assert [b.isChecked() for b in w.panel._buttons] == [False, True, False, False, False, False]
    finally:
        w.close()


@pytest.mark.parametrize("boy", [600, 900])
def test_komut_listesi_ve_karsilama_yazma_kutusuyla_ust_uste_binmez(boy, tmp_path, monkeypatch, fake_keyring):
    """2026-11-12: karşılamanın en küçük boyu (469 px) yığını, 9 satırlık komut listesi (~420 px) yazma kutusunu
    büyütüyordu; toplam pencereye sığmayınca Qt parçaları üst üste bindiriyordu (liste yazma kutusunun arkasına ve alt
    bilgi yazısının üstüne taşıyordu). Karşılama kaydırılabilir alanda, liste pencereye göre kısalır."""
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.resize(1400, boy)
    w.show()
    try:
        app.processEvents()
        s = w.session
        assert s.minimumSizeHint().height() <= s.height(), "kapalıyken sığar"
        # offscreen'de yazı ölçüleri küçük (satır ~24 px): Windows'ta ölçülen satır yüksekliği (41 px) kullanılır
        monkeypatch.setattr(s.composer.popup, "sizeHintForRow", lambda _r: 41)
        s.composer.edit.setPlainText("/")
        s.composer._on_text()
        app.processEvents()
        c = s.composer
        assert c.popup.isVisible() and c.popup.count() > 3
        # Qt sığmayan düzende pencereyi kendiliğinden UZATIR (ekranı kaplayan pencerede bu olamaz → taşma): liste
        # pencereyi büyütmeden sığmalı
        assert w.height() == boy and w.minimumSizeHint().height() <= boy, "liste pencereyi büyütmez"
        assert c.popup.geometry().bottom() < c.frame.geometry().top(), "liste yazma kutusunun üstünde kalır"
        assert c.geometry().bottom() <= s.height(), "yazma kutusu oturum alanından taşmaz"
        assert c.minimumSizeHint().height() <= c.height(), "yazma kutusu en küçük boyundan sıkıştırılmadı"
    finally:
        w.close()
