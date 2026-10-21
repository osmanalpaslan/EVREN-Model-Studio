"""Kenar çubuğu sürükleyince kaybolmasın (2026-10-21; önceki "düzeldi" kaydı sürüklemeyi denememişti).

Kök neden: QStackedWidget'ın en küçük boyut ipucu tüm sayfaların en büyüğüydü (kaydırmasız uzun
açıklamalar → 1728 px, offscreen'de daha da büyük); QSplitter sürüklemede taşanı soldan kesip
kenar çubuğunu eksi x'e itiyordu. Hata TEK fare hareketiyle tetiklenmiyor: test, gerçek kullanıcı
gibi çok adımlı sürükleme yapar ve mutlak piksel değil DEĞİŞMEZLER denetler (R-05: offscreen ölçüleri farklı).
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    yield app, w
    w.close()


def _drag(app, w, handle_index: int, dx: int, steps: int = 10) -> None:
    """Tutamacı splitter koordinatında MUTLAK konumlarla çok adımda sürükler."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    sp = w.splitter
    h = sp.handle(handle_index)
    start = h.mapTo(sp, QPoint(h.width() // 2, h.height() // 2))
    QTest.mousePress(h, Qt.LeftButton, Qt.NoModifier, QPoint(h.width() // 2, h.height() // 2))
    for i in range(1, steps + 1):
        target = start + QPoint(int(dx * i / steps), 0)
        QTest.mouseMove(h, h.mapFrom(sp, target))
        app.processEvents()
    end = start + QPoint(dx, 0)
    QTest.mouseRelease(h, Qt.LeftButton, Qt.NoModifier, h.mapFrom(sp, end))
    app.processEvents()


def _assert_on_screen(w) -> None:
    sp = w.splitter
    sizes = sp.sizes()
    # (tutamaç 1 px; handle().width() Qt'nin 5 px yakalama alanını verir, toplama katılmaz)
    assert sum(sizes) <= sp.width(), f"sütunlar pencereyi aşıyor: {sizes} > {sp.width()}"
    assert w.sidebar.geometry().x() >= 0, f"kenar çubuğu soldan dışarı itildi: x={w.sidebar.geometry().x()}"
    assert not w.sidebar.visibleRegion().isEmpty(), "kenar çubuğu görünmez oldu"
    if w.panel.isVisible():
        assert w.panel.geometry().right() <= sp.width() + 1, "sağ panel sağdan dışarı itildi"


@pytest.mark.parametrize("size", [(1440, 900), (1000, 700)])
@pytest.mark.parametrize("dx", [60, 180, 500])
def test_kenar_cubugu_genisletince_ekranda_kalir(win, size, dx):
    app, w = win
    w.resize(*size)
    w.show()
    app.processEvents()
    before = w.splitter.sizes()[0]
    _drag(app, w, 1, dx)
    _assert_on_screen(w)
    after = w.splitter.sizes()[0]
    assert after >= before                                        # genişletme gerçekten işliyor
    assert 220 <= after <= 420 and w.ctx.settings.sidebar_visible is True


def test_ayar_sayfasinda_ve_sag_panelde_de_tasmaz(win):
    app, w = win
    w.resize(1440, 900)
    w.show()
    app.processEvents()
    _drag(app, w, 2, -400)                                        # sağ paneli genişlet
    _assert_on_screen(w)
    w.show_page("settings")
    app.processEvents()
    _drag(app, w, 1, 300)
    _assert_on_screen(w)


def test_genislik_hatirlanir_ve_acilista_uygulanir(win, tmp_path):
    app, w = win
    w.resize(1440, 900)
    w.show()
    app.processEvents()
    assert w.splitter.sizes()[0] == 264                            # istenen açılış genişliği uygulanıyor
    _drag(app, w, 1, 80)
    width = w.splitter.sizes()[0]
    assert w.ctx.settings.sidebar_width == width
    w.close()
    from evren_studio.ui.main_window import MainWindow

    w2 = MainWindow()                                             # kaydedilen ayar açılışta okunur (R-03)
    try:
        w2.resize(1440, 900)
        w2.show()
        app.processEvents()
        assert w2.splitter.sizes()[0] == width
    finally:
        w2.close()


def test_en_kucuk_pencerede_ucu_sigar(win):
    app, w = win
    w.resize(w.minimumWidth(), 700)
    w.show()
    app.processEvents()
    _drag(app, w, 1, 200)
    _assert_on_screen(w)
