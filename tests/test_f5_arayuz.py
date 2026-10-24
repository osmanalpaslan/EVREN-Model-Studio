"""F5 arayüz (2026-10-24): #12 yazı boyutu/sıkışık, #11 sade görünüm, E10 komut paleti, #16 veri klasörü/yedek,
#9 çıktı önizleme, #8 zaman özeti, #7 canlı iş paneli, #5 tahmin, #6 geçmişi sayfa sayfa yükleme. Ağ yok."""
from __future__ import annotations

import json
import os
import sqlite3
import time
import zipfile
from pathlib import Path

import pytest

from evren_studio.agent import estimate as est
from evren_studio.agent import tables
from evren_studio.api.client import ChatResult
from evren_studio.ui.command_palette import Action, match, norm


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
    from evren_studio.ui import transcript

    transcript.VIEW["simple"] = False


def _wait(app, cond, timeout=8.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


# ---- E10 komut paleti ----------------------------------------------------------------------------

def test_palet_turkce_arama_ve_siralama():
    acts = [Action("Ayarlar", "Git", lambda: None), Action("Otomatik mod", "Mod", lambda: None, "/otomatik"),
            Action("İş şablonları", "Git", lambda: None), Action("Sade görünüm", "Görünüm", lambda: None, "gizle")]
    assert norm("İŞ Şablon") == "is sablon"
    assert [a.title for a in match(acts, "otom")] == ["Otomatik mod"]
    assert [a.title for a in match(acts, "is sab")] == ["İş şablonları"]
    assert [a.title for a in match(acts, "gizle")] == ["Sade görünüm"]
    assert match(acts, "") == acts and match(acts, "yokboyle") == []


def test_palet_eylemleri_ve_calistirma(win):
    app, w = win
    w.ctx.db.save_profile("Raporcu", None, None, None, "")
    titles = [a.title for a in w.palette_actions()]
    for t in ("Ayarlar", "Otomatik mod", "Profil uygula: Raporcu", "Şablon: Excel/CSV raporu", "Oturumları yedekle…",
              "Sade görünüm (araç adımlarını gizle)"):
        assert t in titles, t
    sade = next(a for a in w.palette_actions() if a.title.startswith("Sade görünüm"))
    sade.run()
    assert w.ctx.settings.simple_view is True
    git = next(a for a in w.palette_actions() if a.title == "Skill'ler ve Profiller")
    git.run()
    assert w.center.currentWidget() is w.pages["skills"]


# ---- #12 yazı boyutu, sıkışık · #11 sade görünüm --------------------------------------------------

def test_yazi_boyutu_kisayolu_sinirlari_ve_kaliciligi(win):
    app, w = win
    from evren_studio.config import ConfigStore, default_data_dir

    w.zoom(0)
    w.zoom(+1)
    assert w.ctx.settings.font_size == 11
    for _ in range(10):
        w.zoom(+1)
    assert w.ctx.settings.font_size == 16
    for _ in range(20):
        w.zoom(-1)
    assert w.ctx.settings.font_size == 8
    assert ConfigStore(default_data_dir()).load().font_size == 8                     # R-03
    w.zoom(0)
    assert w.ctx.settings.font_size == 10


def test_sikisik_gorunum(win):
    app, w = win
    w.toggle_compact_view()
    assert w.ctx.settings.compact_view and w.session.transcript.lay.spacing() == 10
    assert "padding: 3px 9px" in app.styleSheet()
    w.toggle_compact_view()
    assert w.session.transcript.lay.spacing() == 18 and "padding: 3px 9px" not in app.styleSheet()


def test_sade_gorunum_biten_kartlari_gizler_calisan_ve_hatali_kalir(win):
    app, w = win
    from evren_studio.ui import transcript as tr

    a = tr.AssistantMessageWidget("m", True)
    a.append_reasoning("düşünüyorum")
    w.session.transcript.add(a)
    ok = a.add_tool("1", "read_file", {"path": "a.py"})
    ok.set_result(True, "Okundu: a.py", {})
    bad = a.add_tool("2", "run_command", {"command": "x"})
    bad.set_result(False, "Hata", {})
    run = a.add_tool("3", "run_command", {"command": "y"})          # bitmemiş (çalışıyor/onay)
    app.processEvents()
    w.toggle_simple_view()
    app.processEvents()
    assert not ok.isVisibleTo(a) and bad.isVisibleTo(a) and run.isVisibleTo(a)
    assert a.tool_summary.isVisibleTo(a) and "1 araç adımı gizli" in a.tool_summary.text()
    assert not a.thinking.isVisibleTo(a)
    late = a.add_tool("4", "read_file", {"path": "b.py"})
    late.set_result(True, "Okundu", {})
    app.processEvents()
    assert not late.isVisibleTo(a) and "2 araç adımı" in a.tool_summary.text()      # sonradan biten de gizlenir
    w.toggle_simple_view()
    assert ok.isVisibleTo(a) and a.thinking.isVisibleTo(a) and not a.tool_summary.isVisibleTo(a)


# ---- #16 veri klasörü / yedek ---------------------------------------------------------------------

def test_yedek_zip_tutarli_ve_anahtarsiz(win, tmp_path):
    app, w = win
    from evren_studio.backup import backup

    sid = w.ctx.db.create_session("m", None)
    w.ctx.db.add_session_message(sid, "user", "merhaba Ğ")
    sk = w.ctx.data_dir() / "skills" / "x"
    sk.mkdir(parents=True)
    (sk / "SKILL.md").write_text("# x", encoding="utf-8")
    w.ctx.save_settings()
    info = backup(w.ctx.db.path, w.ctx.data_dir(), w.ctx.store.path, tmp_path / "out" / "yedek")
    z = zipfile.ZipFile(info["yol"])
    names = z.namelist()
    assert info["yol"].endswith(".zip") and "evren.db" in names and "skills/x/SKILL.md" in names
    assert info["oturum"] >= 1 and info["mesaj"] >= 1
    assert "SAHTE_ANAHTAR" not in z.read("config.json").decode("utf-8")              # anahtar yedekte yok
    z.extract("evren.db", tmp_path / "ac")
    c = sqlite3.connect(tmp_path / "ac" / "evren.db")
    assert c.execute("SELECT content FROM session_messages WHERE session_id=?", (sid,)).fetchone()[0] == "merhaba Ğ"
    c.close()


# ---- #9 çıktı önizleme ------------------------------------------------------------------------------

def test_tablo_onizleme_ve_dosyalar_sekmesi(win, tmp_path):
    app, w = win
    from PySide6.QtGui import QColor, QImage

    from test_f3_verimlilik import make_xlsx

    proj = tmp_path / "p"
    proj.mkdir()
    make_xlsx(proj / "r.xlsx", {"Özet": [["a", "b"], [1, 2]], "Liste": [["x"]]})
    (proj / "s.csv").write_text("a;b\n1;2\n3;4\n", encoding="utf-8")
    img = QImage(40, 20, QImage.Format_RGB32)
    img.fill(QColor("red"))
    img.save(str(proj / "g.png"))
    (proj / "n.txt").write_text("düz metin", encoding="utf-8")
    d = tables.preview(proj / "r.xlsx")
    assert d["sheets"] == ["Özet", "Liste"] and d["rows"][1] == ["1", "2"] and d["total"] == 2
    assert tables.preview(proj / "r.xlsx", "Liste")["rows"] == [["x"]]
    assert tables.preview(proj / "s.csv")["total"] == 3
    f = w.panel.files
    f.set_root(str(proj))
    for name, idx in (("r.xlsx", 1), ("g.png", 2), ("n.txt", 0), ("s.csv", 1)):
        f._open(f.model.index(str(proj / name)))
        assert f.view_stack.currentIndex() == idx, name
    f._open(f.model.index(str(proj / "r.xlsx")))
    assert f.sheet_combo.isVisibleTo(f) and f.table.rowCount() == 2 and not f.edit_btn.isEnabled()


# ---- #8 zaman özeti ---------------------------------------------------------------------------------

def test_zaman_ozeti_yalniz_uzun_turda():
    from evren_studio.ui.timesummary import breakdown

    msgs = [{"role": "assistant", "meta": {"duration_s": 20}}, {"role": "tool", "name": "run_command",
             "meta": {"duration_s": 30, "error": True}}] * 3
    assert breakdown(msgs, 30.0) is None                                     # kısa tur
    assert breakdown(msgs[:2], 120.0) is None                                # az adım
    d = breakdown(msgs, 200.0, switches=1)
    assert d["model"] == 60 and d["tools"] == 90 and d["wait"] == 50 and d["failed"] == 3
    assert d["top"] == [("run_command", 90)] and d["switches"] == 1


def test_kosucu_arac_suresini_kaydeder_ve_tur_sonu_islerini_runner_silinmeden_yapar(win, tmp_path):
    """2026-10-24 hatası: _on_done, _finish runner'ı sildikten sonra used_skills okuyordu → denetçi hiç çalışmıyordu."""
    app, w = win
    from evren_studio.ui.transcript import ActionCard
    from test_f4_skill_profil import make_skill

    w.ctx.add_skill(make_skill(tmp_path / "k", name="rapor", checker="denetle.py"))
    seq = [ChatResult(content="", tool_calls=[{"id": "c1", "name": "read_skill",
                                                "arguments": json.dumps({"name": "rapor"})}],
                      finish_reason="tool_calls"),
           ChatResult(content="bitti", finish_reason="stop")]

    class C:
        def chat(self, model, messages, **kw):
            return seq.pop(0) if seq else ChatResult(content="bitti", finish_reason="stop")

        def close(self):
            pass
    w.ctx.make_client = lambda log_sink=None: C()
    w.ctx.make_client_for = lambda provider, log_sink=None: C()
    s = w.session
    proj = tmp_path / "proje"
    proj.mkdir()
    s.new_session()
    s.welcome._choose(str(proj))
    s.composer.set_model("deepseek-v4.1-flash", emit=True)
    s.set_mode("auto")
    s.send("rapor hazırla")
    assert _wait(app, lambda: not s.running)
    tool = next(m for m in w.ctx.db.get_session_messages(s.session_id) if m["role"] == "tool")
    assert "duration_s" in (tool.get("meta") or {})
    assert _wait(app, lambda: any("denetçisi geçti" in c.title.text() for c in s.findChildren(ActionCard)), 20)


# ---- #7 canlı iş paneli · #5 tahmin · #6 geçmiş sayfaları --------------------------------------------

def test_calisma_paneli(win):
    app, w = win
    wt = w.panel.work
    wt.update_state(None)
    assert wt.empty.isVisibleTo(wt) and not wt.info.isVisibleTo(wt)
    wt.update_state({"title": "Ajan çalışıyor", "model": "qwen", "role": "veri", "elapsed": "12 sn", "step": 3,
                     "activity": "araç çalıştırıyor", "flow": "Proje 2/5", "progress": "1/5 görev bitti",
                     "steps": ["✓ Okundu: a.py · 0,1 sn"], "tokens": 12345})
    assert "qwen (veri)" in wt.info.text() and "Proje 2/5" in wt.info.text() and "12.345" in wt.info.text()
    assert "Okundu: a.py" in wt.steps.text()
    assert w.session._work_state() is None                                   # çalışmıyorken boş


def test_tahmin():
    e = est.estimate(4, [60.0] * 4, [], [])
    assert "varsayılan" in e.basis and e.low_s == 4 * 120                    # az geçmiş → kullanılmaz
    e = est.estimate(4, [60.0, 120.0, 90.0, 100.0, 80.0], [], [10_000] * 6)
    assert "geçmiş 5 görev" in e.basis and 4 * 60 <= e.low_s <= e.high_s <= 4 * 120
    assert e.tokens == 4 * est.CALLS_PER_TASK * 10_000
    e = est.estimate(2, [], [10.0] * 6, [])
    assert "model çağrısı" in e.basis and e.low_s == 2 * est.CALLS_PER_TASK * 10
    t = est.estimate(2, [], [], []).text(daily_remaining=1_000_000)
    assert "kaba tahmin" in t and "kalan kotanın" in t
    assert est.task_seconds([json.dumps({"tasks": [{"status": "bitti", "seconds": 50},
                                                    {"status": "takildi", "seconds": 900}]})]) == [50.0]


def test_gecmis_sayfa_sayfa_yuklenir(win, tmp_path):
    app, w = win
    from evren_studio.ui import session_view as sv
    from evren_studio.ui.transcript import UserMessageWidget

    sid = w.ctx.db.create_session("m", None, title="uzun")
    for i in range(150):
        w.ctx.db.add_session_message(sid, "user", f"istek {i}")
        w.ctx.db.add_session_message(sid, "assistant", f"yanıt {i}", model="m")
    s = w.session
    s.open_session(sid)
    from PySide6.QtCore import QCoreApplication, QEvent

    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    n0 = len(s.findChildren(UserMessageWidget))
    assert n0 <= sv.HISTORY_WINDOW // 2 + 1
    s._show_full_history()
    from PySide6.QtCore import QCoreApplication, QEvent

    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)       # eski çizimin widget'ları silinsin
    app.processEvents()
    n1 = len(s.findChildren(UserMessageWidget))
    assert n0 < n1 <= n0 + sv.HISTORY_PAGE // 2 + 1                         # hepsi değil, bir sayfa daha
