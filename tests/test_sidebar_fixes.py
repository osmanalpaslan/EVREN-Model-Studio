"""Kenar çubuğu düzeltmeleri (2026-10-19).

Kullanıcı uygulamanın kendi ajanıyla kenar çubuğuna "Developed by Osman Alpaslan"
ekletmişti; yazı ad ile gizleme düğmesi arasına sıkışıp kesiliyordu. Ajan sorunu
splitter'da arayıp main_window'a Windows'ta çöken bir hata ayıklama günlüğü
(`time.strftime('%f')`) ekledi ve uygulama açılmaz oldu. Ayrıca Ctrl+K kenar
çubuğunu açarken ayarı güncellemiyordu.
"""
from __future__ import annotations

import os
import time

import pytest


@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    app.processEvents()
    yield app, w
    w.close()


def test_gelistirici_satiri_sigar_ve_kesilmez(win):
    app, w = win
    sb = w.sidebar
    assert sb.credit.text() == "Developed by Osman Alpaslan"
    # Kendi satırında: ad/gizleme düğmesi satırının ALTINDA ve tam genişlikte (sıkışıp kesilmez).
    # Piksel genişliği ekransız modda ölçülemez (yazı tipi yok); gerçek pencerede 199 ≤ 220
    # olduğu ekran görüntüsüyle doğrulandı (R-05).
    assert sb.credit.y() >= sb.logo.y() + sb.logo.height() - 2
    assert sb.credit.width() >= sb.width() - 30
    assert sb.credit.contentsMargins().left() > 0         # ad hizasında (logonun sağında)
    assert sb.credit.height() < 40                        # boş alanı doldurup uzamaz


def test_ctrl_k_kenar_cubugunu_ayarla_birlikte_acar(win):
    app, w = win
    w.toggle_sidebar()                                    # kapat
    assert not w.sidebar.isVisible() and w.ctx.settings.sidebar_visible is False
    w.focus_session_search()                              # Ctrl+K
    app.processEvents()
    assert w.sidebar.isVisible()
    assert w.ctx.settings.sidebar_visible is True         # ayar da güncel (yeniden açılışta kapanmaz)
    assert not w.session.sidebar_btn.isVisibleTo(w.session)   # başlıktaki "göster" düğmesi gizlendi
    w.focus_session_search()                              # açıkken kapatmaz
    assert w.sidebar.isVisible()


def test_strftime_yuzde_f_kaynakta_yok():
    """time.strftime('%f') Windows'ta ValueError verir (uygulamayı açılmaz yapmıştı)."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src"
    bad = []
    for p in root.rglob("*.py"):
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "strftime" and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "time" and node.args
                    and isinstance(node.args[0], ast.Constant) and "%f" in str(node.args[0].value)):
                bad.append(f"{p.name}:{node.lineno}")
    assert not bad, f"time.strftime ile %f kullanımı (Windows'ta ValueError): {bad}"
    assert time.strftime("%H:%M:%S")                     # sanity


def test_kendi_kaynak_klasoru_uyarisi(win, tmp_path):
    from pathlib import Path

    import evren_studio
    from evren_studio.ui.transcript import NoteWidget

    app, w = win
    s = w.session
    root = str(Path(evren_studio.__file__).resolve().parents[2])
    s.new_session()
    s._warn_self_source(str(tmp_path))                     # başka klasör: uyarı yok
    assert not any("kendi kaynak kodu" in getattr(n, "text", lambda: "")() if callable(getattr(n, "text", None))
                   else False for n in s.transcript.findChildren(NoteWidget))
    before = len(s.transcript.findChildren(NoteWidget))
    s._warn_self_source(root)
    s._warn_self_source(root)                              # oturumda bir kez
    assert len(s.transcript.findChildren(NoteWidget)) == before + 1
