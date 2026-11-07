"""Çalışırken tema değişimi (kullanıcı 2026-11-07: "açık modda sağ üstteki düğmeler neredeyse görünmez").

Kök neden: simge ve satır içi renkler bileşen oluşturulurken sabitleniyordu; koyu → açık geçişte koyu temanın açık
gri rengi beyaz zeminde kalıyordu. Artık simgeler rengi her çizimde temadan okur (icons._ThemedEngine), sabit renkli
stiller/etiket resimleri theme.watch ile yeniden boyanır.
"""
from __future__ import annotations

import gc
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize  # noqa: E402
from PySide6.QtGui import QColor, QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from evren_studio.ui import icons, theme  # noqa: E402


@pytest.fixture()
def app():
    a = QApplication.instance() or QApplication([])
    yield a
    theme.apply_theme(a, "koyu")


def _darkest(pm) -> QColor:
    img = pm.toImage()
    best, lum = None, 2.0
    for x in range(img.width()):
        for y in range(img.height()):
            c = img.pixelColor(x, y)
            if c.alpha() > 200:
                v = (c.red() * 299 + c.green() * 587 + c.blue() * 114) / 255000
                if v < lum:
                    best, lum = c, v
    return best


def test_simge_rengi_cizim_aninda_gecerli_temadan(app):
    theme.apply_theme(app, "koyu")
    ic = icons.icon("folder")                                   # tema rolü: varsayılan text_dim
    dark = _darkest(ic.pixmap(QSize(18, 18)))
    theme.apply_theme(app, "açık")
    light = _darkest(ic.pixmap(QSize(18, 18)))                   # AYNI QIcon nesnesi
    assert dark.lightness() > 180 and light.lightness() < 110, (dark.name(), light.name())


def test_rol_ve_sabit_renk_ve_devre_disi(app):
    theme.apply_theme(app, "açık")
    p = theme.current()
    assert icons.resolve("accent") == p.accent and icons.resolve(None) == p.text_dim
    assert icons.resolve("#123456") == "#123456"                # sabit renk aynen kalır
    assert icons.resolve("olmayan_rol") == p.text_dim
    off = icons.icon("check", "accent").pixmap(QSize(16, 16), QIcon.Mode.Disabled)
    assert _darkest(off).name() != QColor(p.accent).name()      # devre dışı: muted


def test_watch_tema_degisince_yeniden_boyar_ve_anahtarla_yerine_gecer(app):
    theme.apply_theme(app, "koyu")
    lab = QLabel()
    theme.style(lab, lambda pal: f"color: {pal.warning};")
    assert theme.DARK.warning in lab.styleSheet()
    theme.apply_theme(app, "açık")
    assert theme.LIGHT.warning in lab.styleSheet()
    n = theme.watcher_count()
    for _ in range(5):                                          # durum değiştikçe yeniden kayıt: birikmez
        icons.set_pixmap(lab, "check", "success", 15)
    assert theme.watcher_count() == n + 1


def test_silinen_bilesenin_kaydi_duser(app):
    lab = QLabel()
    theme.style(lab, lambda pal: f"color: {pal.text};")
    before = theme.watcher_count()
    lab.deleteLater()
    app.processEvents()
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    del lab
    gc.collect()
    theme.notify_changed()                                      # hata vermez, ölü kaydı atar
    assert theme.watcher_count() < before


def test_markdown_ve_baglanti_yeni_temayla(app):
    from evren_studio.ui.markdown_view import MarkdownView

    theme.apply_theme(app, "koyu")
    v = MarkdownView()
    v.set_markdown("Merhaba **dünya** `kod`")
    assert theme.DARK.text.lower() in v.document().defaultStyleSheet().lower()
    theme.apply_theme(app, "açık")
    assert theme.LIGHT.text.lower() in v.document().defaultStyleSheet().lower()
    v.set_plain("düz metin")                                    # düz metin yeniden Markdown'a çevrilmez
    theme.apply_theme(app, "koyu")
    assert v.toPlainText() == "düz metin"


def test_ayarlar_baglantisinda_sabit_renk_yok():
    from evren_studio.ui.settings_page import link

    assert "color" not in link("x", "https://ornek.org")        # renk paletten (Link) gelir
