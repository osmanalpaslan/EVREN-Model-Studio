"""Madde 2: dosya sohbet alanının her yerine bırakılabilir (yalnız yazma kutusu değil). Ağ yok."""
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
    yield app, w
    w.close()


def _drop(widget, md, pos=None):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QDragEnterEvent, QDropEvent

    p = pos or QPoint(widget.width() // 2, widget.height() // 3)
    enter = QDragEnterEvent(p, Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier)
    widget.dragEnterEvent(enter)
    accepted = enter.isAccepted()
    drop = QDropEvent(QPointF(p), Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier)
    widget.dropEvent(drop)
    return accepted


def test_sohbet_alanına_bırakılan_dosya_ek_olur(win, tmp_path):
    from PySide6.QtCore import QMimeData, QUrl

    app, w = win
    s = w.session
    f = tmp_path / "rapor.txt"
    f.write_text("merhaba", encoding="utf-8")
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(str(f))])
    assert _drop(s, md)
    names = [a.name for a in s.composer.attachments.items()]
    assert "rapor.txt" in names
    assert not s._drop_hint.isVisible()


def test_dosya_olmayan_sürükleme_kabul_edilmez(win):
    from PySide6.QtCore import QMimeData

    _app, w = win
    md = QMimeData()
    md.setText("yalnız metin")
    assert not _drop(w.session, md)
    assert w.session.composer.attachments.items() == []


def test_sürüklerken_ipucu_görünür(win, tmp_path):
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent

    _app, w = win
    s = w.session
    f = tmp_path / "a.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n")
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(str(f))])
    s.dragEnterEvent(QDragEnterEvent(QPoint(50, 50), Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier))
    assert s._drop_hint.isVisible() and s._drop_hint.width() > 100
    s.dragLeaveEvent(QDragLeaveEvent())
    assert not s._drop_hint.isVisible()


def test_konuşma_içindeki_görünüme_bırakılan_dosya_oturuma_ulaşır(win, tmp_path):
    """Salt okunur yanıt/fark görünümleri bırakmayı kabul etmez; Qt olayı üst bileşene (oturuma) iletir.
    Olay en içteki görünüme QApplication üzerinden gönderilir (gerçek dağıtım yolu)."""
    from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent, QDropEvent
    from PySide6.QtWidgets import QApplication

    from evren_studio.ui.markdown_view import MarkdownView
    from evren_studio.ui.transcript import AssistantMessageWidget, DiffView

    app, w = win
    s = w.session
    proj = tmp_path / "p"
    proj.mkdir()
    s.new_session()
    s.welcome._choose(str(proj))
    s._ensure_session("Bırakma denemesi")
    a = AssistantMessageWidget("glm-5.3", True)
    s.transcript.add(a)
    t = a.add_tool("1", "edit_file", {"path": "x.py"})
    t.set_result(True, "düzenlendi", {"diff": "--- a\n+++ b\n@@\n-x\n+y\n", "path": "x.py"})
    a.finalize("Örnek yanıt", None, "stop")
    app.processEvents()
    targets = [v.viewport() for v in s.transcript.findChildren(MarkdownView) + s.transcript.findChildren(DiffView)]
    assert targets
    for i, vp in enumerate(targets):
        f = tmp_path / f"veri{i}.csv"                    # her bırakmada ayrı dosya (aynısı "zaten ekli" uyarısı açar)
        f.write_text("a,b\n1,2\n", encoding="utf-8")
        md = QMimeData()
        md.setUrls([QUrl.fromLocalFile(str(f))])
        enter = QDragEnterEvent(QPoint(5, 5), Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(vp, enter)
        assert s._drop_hint.isVisible(), type(vp.parent()).__name__
        s.dropEvent(QDropEvent(QPointF(5, 5), Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier))
        assert not s._drop_hint.isVisible()
    names = [a.name for a in s.composer.attachments.items()]
    assert all(f"veri{i}.csv" in names for i in range(len(targets)))
