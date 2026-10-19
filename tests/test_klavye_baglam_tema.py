"""Alt+Enter yeni satır, Auto Pro bağlam penceresi/özet göstergesi, koyu tema okunurluğu (2026-10-19).

Kullanıcı bildirimi: Alt+Enter mesajı gönderiyordu; bağlam "%10"da özetleniyor gibi görünüyordu
(Auto Pro'ya sabit 1M pencere yazılıydı, özet 100k'de); koyu temada bazı yazılar okunmuyordu.
"""
from __future__ import annotations

import os

import pytest

from evren_studio.agent import router
from evren_studio.agent.compaction import CompactPolicy
from evren_studio.ui import theme


@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
    yield app, w
    w.close()


# ---- Alt+Enter ---------------------------------------------------------------------------

def _press(edit, mods):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    QTest.keyClick(edit, Qt.Key_Return, mods)


def test_alt_shift_ctrl_enter_yeni_satir_enter_gonderir(win):
    from PySide6.QtCore import Qt

    _app, w = win
    edit = w.session.composer.edit
    sent = []
    edit.submit.connect(lambda: sent.append(edit.toPlainText()))
    edit.send_with_enter = True
    edit.setPlainText("a")
    edit.moveCursor(edit.textCursor().MoveOperation.End)
    for mods in (Qt.AltModifier, Qt.ShiftModifier, Qt.ControlModifier):
        _press(edit, mods)
    assert sent == [] and edit.toPlainText() == "a\n\n\n"          # üçü de yeni satır, gönderim yok
    _press(edit, Qt.NoModifier)
    assert len(sent) == 1                                          # düz Enter gönderir


def test_enter_ile_gonderme_kapaliyken_ctrl_enter_gonderir(win):
    from PySide6.QtCore import Qt

    _app, w = win
    edit = w.session.composer.edit
    sent = []
    edit.submit.connect(lambda: sent.append(1))
    edit.send_with_enter = False
    edit.setPlainText("")
    _press(edit, Qt.NoModifier)
    _press(edit, Qt.AltModifier)
    assert sent == [] and edit.toPlainText() == "\n\n"
    _press(edit, Qt.ControlModifier)
    assert sent == [1]


# ---- bağlam ------------------------------------------------------------------------------

def test_auto_pro_penceresi_secilecek_modelden_gelir_1m_degil(win):
    _app, w = win
    s = w.session
    s.model = router.AUTO_PRO_ID
    window, model = s._window([])
    assert model in router.EVREN_ROUTES["sohbet"]
    chain = [s._route([]).model, *s._route([]).fallbacks]
    expected = min(i.context_length for m in chain if (i := w.ctx.model_info(m)) and i.context_length)
    assert window == expected and window < 1_000_000              # yedeklerin en küçüğü (gemma 262k)


def test_somut_modelde_pencere_kendi_degeri(win):
    _app, w = win
    s = w.session
    s.model = "deepseek-v4-flash"
    window, model = s._window([])
    assert model == "deepseek-v4-flash"
    assert window == w.ctx.model_info("deepseek-v4-flash").context_length


def test_gosterge_yuzdesi_ozet_esigine_gore(win):
    _app, w = win
    c = w.session.composer
    policy = CompactPolicy(enabled=True, percent=75, max_tokens=100_000)
    c.set_context(50_000, 1_048_576, policy.soft_limit(1_048_576), model="auto-pro")
    assert "/ 100k (50%)" in c.context_label.text()               # eskiden "/ 1048k (4%)"
    tip = c.context_label.toolTip()
    assert "Auto Pro penceresi 1M" in tip and "Ayarlar" in tip
    c.set_context(50_000, 262_144, None, model="gemma-4-31b")     # özet kapalı → pencereye göre
    assert "/ 262k (19%)" in c.context_label.text()
    assert "kapalı" in c.context_label.toolTip()


# ---- koyu tema ---------------------------------------------------------------------------

def _lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_koyu_temada_tum_yazilar_gorevler_kadar_parlak():
    d = theme.DARK
    assert d.text_dim == d.text and d.text_faint == d.text
    for bg in (d.bg, d.sidebar, d.panel, d.surface, d.surface2, d.hover, d.selected):
        assert _contrast(d.text, bg) >= 7, bg                         # WCAG AAA
        assert _contrast(d.muted, bg) >= 4.5, bg                      # yer tutucu/devre dışı da okunur
    assert d.muted != d.text                                          # devre dışı öğe etkin sanılmasın
    # Düğmeler mavi değil, yazılarla aynı beyaz; üzerindeki yazı koyu ve okunur
    assert d.accent == d.text
    assert _contrast(d.on_accent, d.accent) >= 7
    r, g, b = (int(d.accent_soft[i:i + 2], 16) for i in (1, 3, 5))
    assert max(r, g, b) - min(r, g, b) <= 16                          # seçili satır nötr gri, mavi değil


def test_stil_yer_tutucu_ve_devre_disi_icin_muted_kullanir():
    css = theme.build_qss(theme.DARK, 10)
    assert f"QPushButton:disabled, QToolButton:disabled {{ color: {theme.DARK.muted};" in css
    assert f"QMenu::item:disabled {{ color: {theme.DARK.muted}; }}" in css
