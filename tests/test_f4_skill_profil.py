"""F4 (2026-10-24): skill'ler (7.2 + read_skill), ajan profilleri (E5), iş şablonları (#10), skill denetçisi (#13),
betikleştir (#14). Kalıcılık okuma yoluyla sınanır (R-03); her otomatik davranışın tetiklenmeyen durumu da (R-22)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from evren_studio.agent import skills as sk
from evren_studio.agent.runner import AgentEvents, AgentRunner
from evren_studio.agent.tools import Workspace
from evren_studio.api.client import ChatResult
from evren_studio.db import Database


def make_skill(root: Path, name="hesap-kapama", desc="Hesap kapama raporu üretir.", checker: str | None = None,
               frontmatter=True) -> Path:
    d = root / name
    (d / "references").mkdir(parents=True)
    head = f"---\nname: {name}\ndescription: >\n  {desc}\n  İkinci satır.\n" + (f"denetci: {checker}\n" if checker else "") + "---\n"
    (d / "SKILL.md").write_text((head if frontmatter else "") + "# Kurallar\n\nKural 1: Log önce gelir.\n",
                                encoding="utf-8")
    (d / "references" / "sutunlar.md").write_text("İş ID, Müşteri", encoding="utf-8")
    if checker:
        (d / checker).parent.mkdir(parents=True, exist_ok=True)
        (d / checker).write_text("import sys\nprint('denetim', sys.argv[1:])\nsys.exit(0)\n", encoding="utf-8")
    return d


# ---- çekirdek -----------------------------------------------------------------------------------

def test_on_bilgi_aciklama_ve_denetci(tmp_path):
    d = make_skill(tmp_path, checker="scripts/kontrol.py")
    name, desc, checker = sk.describe_folder(d)
    assert name == "hesap-kapama" and desc.startswith("Hesap kapama raporu üretir. İkinci satır.")
    assert checker == "scripts/kontrol.py"
    d2 = make_skill(tmp_path / "b", name="duz", frontmatter=False)
    (d2 / "denetle.py").write_text("pass", encoding="utf-8")
    name, desc, checker = sk.describe_folder(d2)
    assert name == "duz" and desc == "Kural 1: Log önce gelir." and checker == "denetle.py"   # varsayılan ad
    d3 = make_skill(tmp_path / "c", name="denetcisiz")
    assert sk.describe_folder(d3)[2] == ""                                                    # tetiklenmemeli
    with pytest.raises(sk.SkillError):
        sk.describe_folder(tmp_path)


def test_ekleme_kopyalar_ad_cakismasi_ve_yenileme(tmp_path):
    src = make_skill(tmp_path / "kaynak")
    root = tmp_path / "data" / "skills"
    a = sk.install(src, root)
    b = sk.install(tmp_path / "kaynak", root)                     # tek alt klasör içeren üst klasör de olur
    assert a.slug == "hesap-kapama" and b.slug == "hesap-kapama-2"
    assert (root / "hesap-kapama" / "references" / "sutunlar.md").is_file()
    (src / "SKILL.md").write_text("---\nname: hesap-kapama\ndescription: Yeni açıklama\n---\n", encoding="utf-8")
    a.enabled, a.scope = False, "secili"
    sk.refresh(a)
    assert a.description == "Yeni açıklama" and a.enabled is False and a.scope == "secili"   # ayarlar korunur
    a.source = str(tmp_path / "yok")
    with pytest.raises(sk.SkillError):
        sk.refresh(a)


def test_kapsam(tmp_path):
    s = sk.Skill("x", "x", "", str(tmp_path))
    p1, p2 = str(tmp_path / "p1"), str(tmp_path / "p2")
    assert s.applies_to(p1) and not s.applies_to(None)            # tüm projeler; klasörsüz sohbette yok
    s.scope, s.projects = "secili", [p1]
    assert s.applies_to(p1) and s.applies_to(p1.upper()) and not s.applies_to(p2)
    s.scope = "hicbiri"
    assert not s.applies_to(p1)
    s.scope, s.enabled = "tum", False
    assert not s.applies_to(p1)


def test_okuma_liste_ve_disari_cikamama(tmp_path):
    d = make_skill(tmp_path)
    s = sk.Skill("hesap-kapama", "hesap-kapama", "", str(d))
    assert "Kural 1" in sk.read(s) and "İş ID" in sk.read(s, "references/sutunlar.md")
    assert "references/sutunlar.md" in sk.read(s, "?")
    for bad in ("../../x.txt", "..\\..\\x.txt"):
        with pytest.raises(sk.SkillError):
            sk.read(s, bad)
    (d / "veri.xlsx").write_bytes(b"PK\x03\x04\x00\x00")
    with pytest.raises(sk.SkillError, match="İkili"):
        sk.read(s, "veri.xlsx")


def test_istem_bolumu_yalniz_ad_ve_kisa_aciklama():
    s = sk.Skill("a", "uzun", "x" * 1000, "/tmp")
    sec = sk.prompt_section([s])
    assert "- uzun: " in sec and len(sec) < 900 and "…" in sec
    assert sk.prompt_section([]) == ""


# ---- koşucu: read_skill --------------------------------------------------------------------------

class Script:
    def __init__(self, seq):
        self.seq = list(seq)
        self.systems, self.tools = [], []

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, on_reasoning=None, tools=None, **kw):
        self.systems.append(messages[0]["content"])
        self.tools.append([t["function"]["name"] for t in tools or []])
        return self.seq.pop(0) if self.seq else ChatResult(content="bitti", finish_reason="stop")


def call(tool, **args):
    return ChatResult(content="", tool_calls=[{"id": "c1", "name": tool, "arguments": json.dumps(args)}],
                      finish_reason="tool_calls")


def run(tmp_path, seq, skills=None, mode="auto"):
    proj = tmp_path / "p"
    proj.mkdir(parents=True, exist_ok=True)
    db = Database(tmp_path / "t.db")
    sid = db.create_session("m", str(proj))
    db.add_session_message(sid, "user", "rapor üret")
    c = Script(seq)
    r = AgentRunner(c, "m", session_id=sid, store=db, events=AgentEvents(), workspace=Workspace(proj), mode=mode,
                    stream=False, skills=skills)
    r.run(db.get_session_messages(sid))
    tools = [m["content"] for m in db.get_session_messages(sid) if m["role"] == "tool"]
    db.close()
    return r, c, tools


def test_read_skill_yalniz_skill_varken_sunulur_ve_okur(tmp_path):
    s = sk.Skill("hesap-kapama", "hesap-kapama", "Hesap kapama raporu.", str(make_skill(tmp_path / "sk")))
    r, c, tools = run(tmp_path, [call("read_skill", name="hesap-kapama"),
                                 call("read_skill", name="hesap-kapama", path="references/sutunlar.md")], [s])
    assert "read_skill" in c.tools[0] and "# Skill'ler" in c.systems[0] and "- hesap-kapama: Hesap" in c.systems[0]
    assert "Kural 1" in tools[0] and "İş ID" in tools[1] and r.used_skills == ["hesap-kapama"]
    r2, c2, tools2 = run(tmp_path / "b", [call("read_skill", name="x")])
    assert "read_skill" not in c2.tools[0] and "# Skill'ler" not in c2.systems[0]          # skill yok → araç yok
    assert "etkin değil" in tools2[0] and "(yok)" in tools2[0] and r2.used_skills == []
    _r3, c3, _t = run(tmp_path / "c", [], [s], mode="plan")
    assert "read_skill" in c3.tools[0]                                                    # Plan modunda da okunur


def test_baska_projenin_skilli_okunamaz(tmp_path):
    s = sk.Skill("a", "a", "", str(make_skill(tmp_path / "sk", name="a")))
    _r, _c, tools = run(tmp_path, [call("read_skill", name="baska")], [s])
    assert "etkin değil" in tools[0] and "Etkin skill'ler: a" in tools[0]


# ---- arayüz: kalıcılık, profil, denetçi, betikleştir, şablon -----------------------------------

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


def _wait(app, cond, timeout=8.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def test_skill_kalici_kapsam_ve_kaldirma_kaynaga_dokunmaz(win, tmp_path):
    _app, w = win
    ctx = w.ctx
    src = make_skill(tmp_path / "kaynak")
    s = ctx.add_skill(src)
    p1 = str(tmp_path / "proje1")
    s.scope, s.projects = "secili", [p1]
    ctx.save_skill(s)
    db2 = Database(ctx.data_dir() / "evren.db")                    # R-03: yeniden açılan veritabanından okuma
    row = next(r for r in db2.list_skills() if r["slug"] == s.slug)
    db2.close()
    back = sk.Skill.from_row(row)
    assert back.scope == "secili" and back.projects == [p1] and Path(back.folder).is_dir()
    assert [x.name for x in ctx.skills_for(p1)] == ["hesap-kapama"] and ctx.skills_for(str(tmp_path / "p2")) == []
    ctx.remove_skill(s.slug)
    assert not Path(s.folder).exists() and (src / "SKILL.md").is_file() and ctx.skills() == []


def test_profil_filtresi_uygulama_ve_oturumda_kalicilik(win, tmp_path):
    app, w = win
    ctx = w.ctx
    ctx.add_skill(make_skill(tmp_path / "k1", name="rapor"))
    ctx.add_skill(make_skill(tmp_path / "k2", name="web"))
    ctx.db.save_profile("Raporcu", "auto-pro", "plan", json.dumps(["rapor"]), "Sayıları 1.234,50 biçiminde yaz.")
    ctx.db.save_profile("Hepsi", None, None, None, "")
    proj = str(tmp_path / "proje")
    assert [s.name for s in ctx.skills_for(proj, "Raporcu")] == ["rapor"]
    assert sorted(s.name for s in ctx.skills_for(proj, "Hepsi")) == ["rapor", "web"]
    assert sorted(s.name for s in ctx.skills_for(proj, None)) == ["rapor", "web"]
    s = w.session
    s.new_session()
    Path(proj).mkdir()
    s.welcome._choose(proj)
    s.apply_profile("Raporcu")
    assert s.profile == "Raporcu" and s.model == "auto-pro" and s.mode == "plan"
    assert "Sayıları 1.234,50" in s._profile_hint()
    sid = s._ensure_session("ilk")
    assert w.ctx.db.get_session(sid)["profile"] == "Raporcu"
    s.new_session()
    assert s.profile is None and s._profile_hint() == ""
    s.open_session(sid)
    assert s.profile == "Raporcu"                                                         # R-03
    s.apply_profile("yok-boyle")
    assert s.profile == "Raporcu"
    s.apply_profile(None)
    assert w.ctx.db.get_session(sid)["profile"] is None
    w.ctx.db.save_profile("Raporcu2", None, None, None, "")
    w.ctx.db.delete_profile("Raporcu")
    assert w.ctx.profile("Raporcu") is None


def test_tur_skill_ve_profil_talimatini_ajana_verir(win, tmp_path):
    app, w = win
    ctx = w.ctx
    ctx.add_skill(make_skill(tmp_path / "k", name="rapor"))
    ctx.db.save_profile("P", None, "auto", None, "PROFİL-TALİMATI-123")
    systems = []

    class C:
        def chat(self, model, messages, **kw):
            systems.append(messages[0]["content"])
            return ChatResult(content="tamam", finish_reason="stop")

        def close(self):
            pass
    ctx.make_client = lambda log_sink=None: C()
    ctx.make_client_for = lambda provider, log_sink=None: C()
    s = w.session
    proj = tmp_path / "proje"
    proj.mkdir()
    s.new_session()
    s.welcome._choose(str(proj))
    s.composer.set_model("deepseek-v4.1-flash", emit=True)
    s.apply_profile("P")
    s.send("rapor hazırla")
    assert _wait(app, lambda: not s.running and systems)
    assert "- rapor: Hesap" in systems[0] and "PROFİL-TALİMATI-123" in systems[0]
    systems.clear()
    s.apply_profile(None)
    s.send("tekrar")
    assert _wait(app, lambda: not s.running and systems)
    assert "PROFİL-TALİMATI-123" not in systems[0] and "- rapor:" in systems[0]          # skill profilsiz de açık


def test_skill_denetcisi_otomatikte_calisir_digerinde_sorar_yoksa_hicbir_sey(win, tmp_path):
    app, w = win
    from evren_studio.ui.transcript import ActionCard

    ctx = w.ctx
    ctx.add_skill(make_skill(tmp_path / "k", name="rapor", checker="denetle.py"))
    ctx.add_skill(make_skill(tmp_path / "k2", name="denetcisiz"))
    s = w.session
    proj = tmp_path / "proje"
    proj.mkdir()
    s.new_session()
    s.welcome._choose(str(proj))
    s._ensure_session("x")

    def titles():
        return [c.title.text() for c in s.findChildren(ActionCard)]
    s._skill_check(["denetcisiz"])
    s._skill_check([])
    assert not any("denetçi" in t.lower() for t in titles())                            # tetiklenmemeli
    s.mode = "manuel"
    s._skill_check(["rapor"])
    assert any("çalıştırılsın mı" in t for t in titles())
    s.mode = "auto"
    s._skill_check(["rapor"])
    assert _wait(app, lambda: any("denetçisi geçti" in t for t in titles()), 20)
    (Path(ctx.skills()[1].folder if ctx.skills()[1].name == "rapor" else ctx.skills()[0].folder) / "denetle.py") \
        .write_text("import sys\nprint('Sütun eksik: İş ID')\nsys.exit(3)\n", encoding="utf-8")
    s._skill_check(["rapor"])
    assert _wait(app, lambda: any("sorun buldu" in t and "çıkış 3" in t for t in titles()), 20)


def test_betiklestir_ve_sablon(win, tmp_path, monkeypatch):
    app, w = win
    from PySide6.QtWidgets import QMessageBox

    boxes = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: boxes.append(a[2])))
    sent = []
    s = w.session
    s.send = lambda text, *a, **k: sent.append(text)
    s.new_session()
    s.scriptify("")
    assert sent == [] and "proje klasörlü" in boxes[-1]                                    # oturum/klasör yok
    proj = tmp_path / "proje"
    proj.mkdir()
    s.welcome._choose(str(proj))
    s._ensure_session("iş")
    s.scriptify("aylik_rapor")
    assert "scripts/aylik_rapor.py" in sent[-1] and "argüman" in sent[-1]
    s._command("/betiklestir rapor.py")
    assert sent[-1].count("`rapor.py`") == 1
    w.ctx.db.save_profile("Raporcu", None, "kabul", None, "")
    w._use_template("Şablon istemi [dosya]", "Raporcu")
    assert s.composer.edit.toPlainText() == "Şablon istemi [dosya]" and s.profile == "Raporcu" and s.session_id is None


def test_sayfa_acilir_ve_listeler(win, tmp_path):
    app, w = win
    w.ctx.add_skill(make_skill(tmp_path / "k", name="rapor", checker="denetle.py"))
    w.ctx.db.save_profile("Raporcu", "auto-pro", None, None, "")
    w.ctx.db.add_template("Benim şablonum", "istem", None)
    w.show_page("skills")
    page = w.pages["skills"]
    from PySide6.QtWidgets import QLabel

    texts = " ".join(lab.text() for lab in page.findChildren(QLabel))
    assert "Denetçi: denetle.py" in texts and "Raporcu" in texts and "Benim şablonum" in texts
    assert "Excel/CSV raporu" in texts
