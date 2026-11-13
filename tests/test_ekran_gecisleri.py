"""Ekran geçişlerinde yumuşak animasyon (2026-11-12, kullanıcı onayı).

Eski görünümün anlık görüntüsü üstte saydamlaşarak kaybolur, yeni sayfa birkaç piksel aşağıdan yerine oturur. Sayfa
değişimi ANINDA olur (yalnız görünüm canlanır), katman fare olaylarını geçirir. Animasyon kapalıyken (Windows ayarı,
testler) hiçbir katman oluşmaz. Tetiklenen ve tetiklenmeyen durumlar ayrı sınanır (R-22).
"""
from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from evren_studio.ui import brand, transitions  # noqa: E402


@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.resize(1300, 850)
    w.show()
    app.processEvents()
    yield app, w
    w.close()


@pytest.fixture()
def anim(monkeypatch):
    monkeypatch.setattr(brand, "animations_enabled", lambda: True)


def _overlays(widget) -> list[transitions.Overlay]:
    return [o for o in widget.findChildren(QWidget, transitions.OVERLAY_NAME)]


def _settle(app, cond, timeout=3.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def test_animasyon_kapaliyken_gecis_aninda_ve_katmansiz(win):
    """conftest EVREN_STUDIO_NO_ANIM=1: davranış eskisiyle aynı."""
    app, w = win
    w.show_page("settings")
    assert w.center.currentWidget() is w.pages["settings"] and not _overlays(w.center)
    w.show_sessions()
    assert w.center.currentWidget() is w.session and not _overlays(w.center)


def test_sayfa_gecisi_yumusak_ve_aninda_kullanilir(win, anim):
    app, w = win
    old = w.center.currentWidget()
    w.show_page("settings")
    page = w.pages["settings"]
    assert w.center.currentWidget() is page, "sayfa ANINDA değişir"
    ov = _overlays(w.center)
    assert len(ov) == 1
    assert ov[0].testAttribute(Qt.WA_TransparentForMouseEvents), "tıklamalar yeni sayfaya geçer"
    assert ov[0].geometry() == w.center.rect() and not ov[0].snapshot.isNull() and old is w.session
    assert page.pos() == QPoint(0, transitions.RISE_PX), "yeni sayfa aşağıdan başlar"
    from PySide6.QtCore import QAbstractAnimation, QPropertyAnimation

    fade = ov[0].findChildren(QPropertyAnimation)
    assert fade and fade[0].state() == QAbstractAnimation.Stopped, \
        "canlandırma hemen başlamaz: sayfanın ilk düzeni bitince (ilk kareler kaybolmasın)"
    app.processEvents()
    assert fade[0].state() == QAbstractAnimation.Running
    # Sayfaya geçince sağ panel gizlenir, orta alan genişler: katman da genişler (yarım geçiş olmaz)
    width0 = w.center.width()
    app.processEvents()
    if _overlays(w.center):
        assert w.center.width() >= width0 and _overlays(w.center)[0].geometry() == w.center.rect()
    assert _settle(app, lambda: not _overlays(w.center)), "katman kaybolur ve silinir"
    assert page.pos() == QPoint(0, 0), "sayfa yerine oturur"


def test_ayni_sayfaya_gecis_ve_gizli_yigin_canlanmaz(win, anim):
    """Tetiklenmeyen durumlar: aynı sayfa yeniden açılınca ve yığın görünmezken katman yok."""
    app, w = win
    w.show_page("settings")
    assert _settle(app, lambda: not _overlays(w.center))
    w.show_page("settings")
    assert not _overlays(w.center)
    w.panel.setVisible(False)
    w.panel.show_tab("changes")
    assert not _overlays(w.panel) and w.panel.stack.currentWidget() is w.panel.changes


def test_sag_panel_sekmesi_yumusak_kayma_yok(win, anim):
    app, w = win
    w.show_sessions()
    w.panel.setVisible(True)
    app.processEvents()
    w.panel.show_tab("files")
    assert w.panel.stack.currentWidget() is w.panel.files
    assert len(_overlays(w.panel)) == 1 and w.panel.files.pos() == QPoint(0, 0), "sekmede yalnız çapraz geçiş"
    assert _settle(app, lambda: not _overlays(w.panel))


def test_oturum_degisince_gecis_cizimden_sonra_oynar(win, anim):
    app, w = win
    db = w.ctx.db
    a = db.create_session("m", None, "auto", title="A")
    db.add_session_message(a, "user", "merhaba A")
    b = db.create_session("m", None, "auto", title="B")
    db.add_session_message(b, "user", "merhaba B")
    s = w.session
    s.open_session(a)
    assert _settle(app, lambda: not _overlays(s.stack))
    s.open_session(b)                                     # başka oturum: akış aynı bileşen ama içerik değişir
    ov = _overlays(s.stack)
    assert len(ov) == 1 and s.stack.currentWidget() is s.transcript
    assert _settle(app, lambda: not _overlays(s.stack))
    s.open_session(b)                                     # aynı oturumun yeniden çizimi: titremez
    assert not _overlays(s.stack)


def test_yeni_oturumda_goruntu_akis_temizlenmeden_alinir(win, anim, monkeypatch):
    app, w = win
    db = w.ctx.db
    sid = db.create_session("m", None, "auto", title="dolu")
    db.add_session_message(sid, "user", "bir istek")
    db.add_session_message(sid, "assistant", "bir yanıt", model="m")
    s = w.session
    s.open_session(sid)
    assert _settle(app, lambda: not _overlays(s.stack))
    seen = []
    real = transitions.begin

    def spy(stack):
        lay = s.transcript.lay
        seen.append(sum(1 for i in range(lay.count()) if lay.itemAt(i).widget() is not None))
        return real(stack)

    monkeypatch.setattr(transitions, "begin", spy)
    s.new_session()
    assert len(seen) == 1 and seen[0] >= 2, "görüntü BİR KEZ, mesajlar hâlâ akıştayken alınır (boş ekrandan geçiş olmaz)"
    assert s.stack.currentWidget() is s.welcome_page and len(_overlays(s.stack)) == 1
    assert _settle(app, lambda: not _overlays(s.stack))
