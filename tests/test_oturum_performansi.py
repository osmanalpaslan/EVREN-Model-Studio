"""Oturum açma performansı (2026-11-12, kullanıcının gerçek 716 mesajlık oturumunun ölçümü):

1. Geçmiş penceresi tek bir uzun ajan turunda tüm turu çiziyordu (pencere 40, çizilen 144 mesaj).
2. Her yanıt baloncuğu boş bir Markdown görünümü + gizli düşünme bloğu + gizli canlı yıldız taşıyordu; kapalı araç
   kartları fark/çıktı görünümlerini hemen kuruyordu (66 mesaj → 2265 bileşen, +80 MB).
3. Sağ panelin Değişiklikler sekmesi her açılışta ve ajanın HER dosya değişikliğinde tüm farkları baştan hesaplıyordu.

Tetiklenen ve tetiklenmeyen durumlar ayrı sınanır (R-22).
"""
from __future__ import annotations

import json
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
    w.show()
    w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
    yield app, w
    w.close()


def _flush(app):
    from PySide6.QtCore import QCoreApplication, QEvent

    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def _top_widgets(s):
    lay = s.transcript.lay
    return [lay.itemAt(i).widget() for i in range(lay.count()) if lay.itemAt(i).widget() is not None]


def _long_turn_session(db, steps: int = 100):
    """Tek kullanıcı isteği + `steps` araçlı adım (gerçek oturumdaki uzun ajan turu gibi)."""
    sid = db.create_session("m", None, "auto", title="uzun tur")
    db.add_session_message(sid, "user", "büyük iş")
    for i in range(steps):
        db.add_session_message(sid, "assistant", "", model="m", meta={"duration_s": 2.0},
                               tool_calls=[{"id": f"c{i}", "name": "read_file",
                                            "arguments": json.dumps({"path": f"d{i}.py"})}])
        db.add_session_message(sid, "tool", "x" * 50, tool_call_id=f"c{i}", name="read_file",
                               meta={"summary": f"Okundu d{i}.py", "output": "satır\n" * 30})
    db.add_session_message(sid, "assistant", "Bitti.", model="m", meta={"duration_s": 1.0})
    return sid


def test_uzun_tek_tur_pencereyi_asmaz(win):
    from evren_studio.ui import session_view as sv
    from evren_studio.ui.transcript import AssistantMessageWidget, NoteWidget, UserMessageWidget

    app, w = win
    sid = _long_turn_session(w.ctx.db)
    s = w.session
    s.open_session(sid)
    _flush(app)
    asst = [x for x in _top_widgets(s) if isinstance(x, AssistantMessageWidget)]
    assert 0 < len(asst) <= sv.HISTORY_WINDOW // 2 + 2, len(asst)          # 201 mesajın tamamı DEĞİL
    assert not [x for x in _top_widgets(s) if isinstance(x, UserMessageWidget)], "turun başı gizli"
    assert not [x for x in _top_widgets(s) if isinstance(x, NoteWidget)], "araç sonucu kartından kopmadı"
    assert all(tw.finished for tw in s.tool_widgets.values()), "her araç kartı sonucunu aldı"
    # Yarım turun toplamı eksik olurdu: yazılmaz
    assert "tur toplamı" not in asst[-1].footer.text()
    # "Önceki mesajlar" düğmesi en üstte; tıklanınca bir sayfa daha açılır
    from PySide6.QtWidgets import QPushButton

    btn = [b for b in s.findChildren(QPushButton) if b.text().startswith("Önceki ")]
    assert btn
    btn[0].click()
    _flush(app)
    asst2 = [x for x in _top_widgets(s) if isinstance(x, AssistantMessageWidget)]
    assert len(asst) < len(asst2)


def test_normal_oturum_kullanici_mesajindan_baslar(win):
    """Tetiklenmeyen durum: kısa turlarda pencere yine bir kullanıcı mesajından başlar, tur toplamı yazılır."""
    from evren_studio.ui.transcript import AssistantMessageWidget, UserMessageWidget

    app, w = win
    db = w.ctx.db
    sid = db.create_session("m", None, "auto", title="kısa turlar")
    for i in range(40):
        db.add_session_message(sid, "user", f"istek {i}")
        db.add_session_message(sid, "assistant", "", model="m", meta={"duration_s": 2.0},
                               tool_calls=[{"id": f"c{i}", "name": "read_file",
                                            "arguments": json.dumps({"path": "a.py"})}])
        db.add_session_message(sid, "tool", "x", tool_call_id=f"c{i}", name="read_file", meta={"summary": "Okundu"})
        db.add_session_message(sid, "assistant", f"yanıt {i}", model="m", meta={"duration_s": 1.0})
    w.session.open_session(sid)
    _flush(app)
    msgs = [x for x in _top_widgets(w.session) if isinstance(x, (UserMessageWidget, AssistantMessageWidget))]
    assert isinstance(msgs[0], UserMessageWidget)
    assert "tur toplamı" in msgs[-1].footer.text()


def test_yanit_baloncugu_agir_parcalari_gerekince_kurar(win):
    """Canlı akış: yıldız beklerken, düşünme bloğu düşünce gelince, gövde metin gelince kurulur ve görünür."""
    from evren_studio.ui.brand import BusyStar
    from evren_studio.ui.markdown_view import MarkdownView
    from evren_studio.ui.transcript import AssistantMessageWidget, ThinkingBlock

    app, w = win
    a = AssistantMessageWidget("m", True)
    w.session.transcript.add(a)
    assert not a.findChildren(MarkdownView) and not a.findChildren(ThinkingBlock) and not a.findChildren(BusyStar)
    a.stop_waiting()                                   # kurulmamış yıldızda hata vermez
    a.start_waiting()
    assert a.busy.isVisibleTo(a) and len(a.findChildren(BusyStar)) == 1
    assert a._status_lay.indexOf(a.busy) == 0, "yıldız durum yazısının solunda"
    a.append_reasoning("düşünüyorum")
    assert a.thinking.isVisibleTo(a) and "düşünüyorum" in a.thinking.text.text()
    a.append_text("Merhaba")
    a._render()
    assert a.body.isVisibleTo(a) and "Merhaba" in a.body.toPlainText()
    assert not a.busy.isVisibleTo(a), "metin gelince bekleme yıldızı gizlenir"
    # Sıra korunur: düşünme bloğu gövdeden önce, gövde durum satırından önce
    lay = a.layout()
    order = [lay.indexOf(a._think_slot), lay.indexOf(a._body_slot), lay.indexOf(a.status_row)]
    assert order == sorted(order) and -1 not in order
    b = AssistantMessageWidget("m", True)
    w.session.transcript.add(b)
    b.finalize("", None, "stop")                       # boş yanıt: gövde kurulmaz
    assert not b.findChildren(MarkdownView) and not b.findChildren(ThinkingBlock)


def test_gecmiste_gorunmez_bilesen_kurulmaz(win):
    from evren_studio.ui.brand import BusyStar
    from evren_studio.ui.markdown_view import MarkdownView
    from evren_studio.ui.transcript import CodeView, ThinkingBlock

    app, w = win
    sid = _long_turn_session(w.ctx.db, steps=30)
    w.session.open_session(sid)
    _flush(app)
    t = w.session.transcript
    assert len(t.findChildren(MarkdownView)) == 1, "yalnız metni olan yanıtın gövdesi"
    assert not t.findChildren(ThinkingBlock) and not t.findChildren(BusyStar)
    assert not t.findChildren(CodeView), "kapalı kartların çıktı görünümü kurulmaz"
    card = next(iter(w.session.tool_widgets.values()))
    assert card.expand.isVisibleTo(card), "ayrıntı oku görünür (içerik var)"
    card.toggle_details(True)
    views = card.findChildren(CodeView)
    assert views and "satır" in views[0].toPlainText()


def test_arac_karti_ayrintisi_acilinca_kurulur(win):
    from evren_studio.ui.transcript import AssistantMessageWidget, CodeView, DiffView, QLabel

    app, w = win
    a = AssistantMessageWidget("m", True)
    w.session.transcript.add(a)
    t = a.add_tool("1", "edit_file", {"path": "x.py"})
    t.set_result(True, "düzenlendi", {"diff": "--- a\n+++ b\n@@\n-x\n+y\n", "path": "x.py"})
    assert not t.findChildren(DiffView) and t.expand.isVisibleTo(t)
    t.toggle_details(True)
    diffs = t.findChildren(DiffView)
    assert len(diffs) == 1 and "+y" in diffs[0].toPlainText()
    t.toggle_details(False)
    t.toggle_details(True)
    _flush(app)
    assert len(t.findChildren(DiffView)) == 1, "yeniden açınca kopya kurulmaz"
    # Hata metni de açılınca görünür
    e = a.add_tool("2", "read_file", {"path": "yok.py"})
    e.set_result(False, "Okunamadı", {"error_text": "Dosya bulunamadı: yok.py"})
    assert not [lb for lb in e.details.findChildren(QLabel) if "bulunamadı" in lb.text()]
    e.toggle_details(True)
    assert [lb for lb in e.details.findChildren(QLabel) if "bulunamadı" in lb.text()]
    # İçerik yoksa ayrıntı oku görünmez
    n = a.add_tool("3", "list_files", {"path": "."})
    n.set_result(True, "Listelendi", {})
    assert not n.expand.isVisibleTo(n) and not n.findChildren(CodeView)


def test_canli_komut_ciktisi_hemen_islenir(win):
    """Tetiklenmeyen durum: açık (canlı) komut kartında çıktı ve çıkış kodu beklemeden görünür."""
    from evren_studio.ui.transcript import AssistantMessageWidget

    app, w = win
    a = AssistantMessageWidget("m", True)
    w.session.transcript.add(a)
    t = a.add_tool("1", "run_command", {"command": "python -V"})
    t.set_running()
    t.append_output("Python 3.12.10\n")
    t.set_result(True, "Komut bitti", {"output": "Python 3.12.10", "exit_code": 0, "duration": 0.4})
    assert "Python 3.12.10" in t._output_view.toPlainText() and t.details.isVisibleTo(t)
    assert "çıkış 0" in t.state.text()
    # Akışta hiç çıktı gelmediyse sonuçtaki çıktı açık kartta HEMEN görünür
    q = a.add_tool("4", "run_command", {"command": "python -c pass"})
    q.set_running()
    q.set_result(True, "Komut bitti", {"output": "tamam", "exit_code": 0})
    assert q._output_view.toPlainText() == "tamam"
    # Açık bırakılmış düzenleme kartı: fark sonuç gelir gelmez kurulur
    from evren_studio.ui.transcript import DiffView

    d = a.add_tool("5", "edit_file", {"path": "x.py"})
    d.toggle_details(True)
    d.set_result(True, "düzenlendi", {"diff": "--- a\n+++ b\n@@\n-x\n+y\n"})
    assert len(d.findChildren(DiffView)) == 1
    # Geçmişten (kapalı) komut kartı: çıktı açılınca gelir, çıkış kodu hemen
    h = a.add_tool("2", "run_command", {"command": "dir"})
    h.set_result(True, "Komut bitti", {"output": "a.txt", "exit_code": 1})
    assert h._output_view is None and "çıkış 1" in h.state.text()
    h.toggle_details(True)
    assert h._output_view is not None and h._output_view.toPlainText() == "a.txt"


def test_degisiklikler_sekmesi_gorunurken_doldurulur_ve_onbellekli(win, monkeypatch):
    from evren_studio.ui import side_panel

    app, w = win
    db = w.ctx.db
    sid = db.create_session("m", None, "auto", title="değişiklik")
    db.add_file_change(sid, None, "a.py", "x\ny\n", "x\nz\nw\n")
    db.add_file_change(sid, None, "b.py", None, "yeni\n")
    tab = w.panel.changes
    calls = []
    real = side_panel.make_diff
    monkeypatch.setattr(side_panel, "make_diff", lambda *a, **k: calls.append(a[2]) or real(*a, **k))
    w.panel.show_tab("todos")                         # sekme görünmüyor
    tab.set_session(sid, None)
    assert len(tab.rows) == 2 and tab.list.count() == 0 and calls == [], "görünmezken fark hesaplanmaz"
    assert "before_text" not in tab.rows[0].keys(), "panel dosya içeriklerini bellekte tutmaz"
    assert "2 dosya, 2 değişiklik" in tab.summary.text()
    w.panel.setVisible(True)
    w.panel.show_tab("changes")
    app.processEvents()
    labels = [tab.list.item(i).text() for i in range(tab.list.count())]
    assert labels[0].startswith("a.py   +2 −1") and labels[1].startswith("b.py   +1 −0") and "(yeni)" in labels[1]
    n = len(calls)
    db.add_file_change(sid, None, "c.py", "1\n", "2\n")
    tab.refresh()                                     # ajanın yeni değişikliği
    stat_calls = [c for c in calls[n:] if c != "c.py"]
    # yalnız yeni kaydın istatistiği + seçili satırın farkı hesaplanır; eskiler önbellekten
    assert calls[n:].count("c.py") >= 1 and stat_calls == [], calls[n:]
    assert tab.list.count() == 3
