"""F3 ajan verimliliği (2026-10-24): #1 tablo aracı, #2 ortam paketleri, #3 görevler arası okuma paylaşımı,
E2 proje haritası, E6 proje hafızası önerisi, E8 web_fetch. Her otomatik ekleme için tetiklenen VE tetiklenmeyen
durum (R-22). Gerçek ağ yok."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import httpx
import pytest

from evren_studio.agent import environment, learnings, project as pj, projectmap, tables, webfetch
from evren_studio.agent.runner import AgentEvents, AgentRunner
from evren_studio.agent.tools import SPEC_BY_NAME, Workspace
from evren_studio.api.client import ChatResult
from evren_studio.db import Database


# ---- #1 tablo aracı -----------------------------------------------------------------------------

def make_xlsx(path: Path, sheets: dict[str, list[list]], date_cell: bool = False) -> None:
    """openpyxl olmadan küçük bir xlsx (paylaşılan metinler + sayılar + isteğe bağlı tarih stili)."""
    sst: list[str] = []

    def si(v):
        if v not in sst:
            sst.append(v)
        return sst.index(v)
    wb = ['<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
    rels = ['<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    with zipfile.ZipFile(path, "w") as z:
        for n, (name, rows) in enumerate(sheets.items(), 1):
            wb.append(f'<sheet name="{name}" sheetId="{n}" r:id="rId{n}"/>')
            rels.append(f'<Relationship Id="rId{n}" Target="worksheets/sheet{n}.xml" '
                        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>')
            xml = ['<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
            for r, row in enumerate(rows, 1):
                xml.append(f'<row r="{r}">')
                for c, v in enumerate(row):
                    ref = chr(65 + c) + str(r)
                    if isinstance(v, str):
                        xml.append(f'<c r="{ref}" t="s"><v>{si(v)}</v></c>')
                    elif v is not None:
                        style = ' s="1"' if (date_cell and c == 0 and r > 1) else ""
                        xml.append(f'<c r="{ref}"{style}><v>{v}</v></c>')
                xml.append("</row>")
            xml.append("</sheetData></worksheet>")
            z.writestr(f"xl/worksheets/sheet{n}.xml", "".join(xml))
        wb.append("</sheets></workbook>")
        rels.append("</Relationships>")
        z.writestr("xl/workbook.xml", "".join(wb))
        z.writestr("xl/_rels/workbook.xml.rels", "".join(rels))
        z.writestr("xl/sharedStrings.xml",
                   '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                   + "".join(f"<si><t>{s}</t></si>" for s in sst) + "</sst>")
        z.writestr("xl/styles.xml",
                   '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cellXfs>'
                   '<xf numFmtId="0"/><xf numFmtId="14"/></cellXfs></styleSheet>')


def test_xlsx_sayfa_baslik_tarih_ve_satir_sayisi(tmp_path):
    f = tmp_path / "İşler.xlsx"
    make_xlsx(f, {"Açık İşler": [["Tarih", "Müşteri", "Tutar"], [46000, "Ayşe Ltd.", 12.5], [46001, "Ömer AŞ", 3]],
                  "Boş": []}, date_cell=True)
    out = tables.describe(f)
    assert "2 sayfa: Açık İşler, Boş" in out and "3 dolu satır, 3 sütun" in out
    assert "Ayşe Ltd." in out and "2025-12-09" in out                     # Excel seri 46000 → tarih
    assert "(boş sayfa)" in out
    one = tables.describe(f, sheet="Açık İşler", max_rows=2)
    assert "Ömer AŞ" not in one and "1 satır daha" in one
    with pytest.raises(tables.TableError):
        tables.describe(f, sheet="Yok")


def test_csv_ayirici_kodlama_ve_turkce_ondalik(tmp_path):
    f = tmp_path / "satis.csv"
    f.write_bytes("bölge;tutar\nEge;1.234,50\nMarmara;99,00\n".encode("cp1254"))
    out = tables.describe(f)
    assert "noktalı virgül" in out and "cp1254" in out and "3 dolu satır" in out and "Ege" in out
    assert "ondalık ayırıcı virgül" in out
    g = tmp_path / "b.csv"
    g.write_text("a,b\n1,2\n", encoding="utf-8")
    assert "ondalık" not in tables.describe(g)                            # tetiklenmemeli


def test_desteklenmeyen_ve_eski_xls(tmp_path):
    (tmp_path / "eski.xls").write_bytes(b"\xd0\xcf\x11\xe0")
    with pytest.raises(tables.TableError, match="xls"):
        tables.describe(tmp_path / "eski.xls")
    (tmp_path / "bozuk.xlsx").write_bytes(b"degil")
    with pytest.raises(tables.TableError, match="açılamadı"):
        tables.describe(tmp_path / "bozuk.xlsx")


# ---- koşucu: read_table, web_fetch, ortam, harita -------------------------------------------------

class Script:
    def __init__(self, seq):
        self.seq = list(seq)
        self.systems: list[str] = []
        self.tool_names: list[list[str]] = []

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, on_reasoning=None, tools=None, **kw):
        self.systems.append(messages[0]["content"])
        self.tool_names.append([t["function"]["name"] for t in tools or []])
        return self.seq.pop(0) if self.seq else ChatResult(content="bitti", finish_reason="stop")


class Ev(AgentEvents):
    def __init__(self, allow=True):
        self.allow = allow
        self.asked: list[str] = []

    def approval_needed(self, request):
        self.asked.append(request.title)
        request.resolve(request.ALLOW if self.allow else request.DENY)


def call(name, **args):
    return ChatResult(content="", tool_calls=[{"id": "c1", "name": name, "arguments": json.dumps(args)}],
                      finish_reason="tool_calls")


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "t.db")
    yield d
    d.close()


def run(db, proj, seq, mode="auto", events=None, **kw):
    sid = db.create_session("m", str(proj))
    db.add_session_message(sid, "user", "görev")
    c = Script(seq)
    r = AgentRunner(c, "m", session_id=sid, store=db, events=events or Ev(), workspace=Workspace(proj), mode=mode,
                    stream=False, **kw)
    out = r.run(db.get_session_messages(sid))
    tools = [m for m in db.get_session_messages(sid) if m["role"] == "tool"]
    return out, c, tools


def test_read_table_araci_kosucuda(db, tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    make_xlsx(proj / "veri.xlsx", {"S1": [["a", "b"], [1, 2]]})
    _o, c, tools = run(db, proj, [call("read_table", path="veri.xlsx")])
    assert "read_table" in c.tool_names[0] and "S1 — 2 dolu satır" in tools[0]["content"]
    _o, _c, tools = run(db, proj, [call("read_table", path="yok.xlsx")])
    assert "bulunamadı" in tools[0]["content"]


def test_web_fetch_plan_modunda_okunur_manuelde_sorulur(db, tmp_path, monkeypatch):
    proj = tmp_path / "p"
    proj.mkdir()
    monkeypatch.setattr(webfetch, "fetch", lambda url, max_chars=20000, client=None: "[DIŞ İÇERİK]\nmerhaba")
    _o, _c, tools = run(db, proj, [call("web_fetch", url="https://ornek.com/a")], mode="plan")
    assert "merhaba" in tools[0]["content"]                                  # Plan: araştırma serbest (2026-11-01)
    ev = Ev(allow=False)
    _o, _c, tools = run(db, proj, [call("web_fetch", url="https://ornek.com/a")], mode="manuel", events=ev)
    assert ev.asked and "ornek.com" in ev.asked[0] and "izin vermedi" in tools[0]["content"]
    ev2 = Ev(allow=True)
    _o, _c, tools = run(db, proj, [call("web_fetch", url="https://ornek.com/a")], mode="manuel", events=ev2)
    assert "merhaba" in tools[0]["content"]
    _o, _c, tools = run(db, proj, [call("web_fetch", url="file:///c:/gizli.txt")])
    assert "http" in tools[0]["content"]                                     # yalnız http(s)


def test_web_fetch_html_metin_yonlendirme_ve_ikili_red():
    page = ("<html><head><title>Başlık &amp; Test</title><script>kotu()</script></head><body><nav>menü</nav>"
            "<main><h1>Ana</h1><p>" + "içerik " * 60 + "</p><ul><li>bir</li><li>iki</li></ul></main></body></html>")

    def handler(req):
        if req.url.path == "/eski":
            return httpx.Response(301, headers={"location": "https://ornek.com/yeni"})
        if req.url.path == "/pdf":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, content=page.encode())
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    out = webfetch.fetch("https://ornek.com/eski", client=client)
    assert out.startswith(webfetch.UNTRUSTED_NOTE) and "Başlık & Test" in out and "(yönlendirildi)" in out
    assert "kotu()" not in out and "menü" not in out and "- bir" in out and "# Ana" in out
    with pytest.raises(webfetch.FetchError, match="Metin olmayan"):
        webfetch.fetch("https://ornek.com/pdf", client=client)
    assert "kısaltıldı" in webfetch.fetch("https://ornek.com/a", max_chars=50, client=client)


def test_ortam_paketleri_istemde(db, tmp_path, monkeypatch):
    proj = tmp_path / "p"
    proj.mkdir()
    monkeypatch.setattr(environment, "python_packages", lambda exe=None, timeout=15.0: {"openpyxl": True, "pandas": False})
    _o, c, _t = run(db, proj, [ChatResult(content="bitti", finish_reason="stop")])
    assert "kurulu: openpyxl; KURULU DEĞİL: pandas" in c.systems[0]
    monkeypatch.setattr(environment, "python_packages", lambda exe=None, timeout=15.0: {})
    _o, c2, _t = run(db, proj, [ChatResult(content="bitti", finish_reason="stop")])
    assert "Python paketleri" not in c2.systems[0]                          # python yok → satır yok


def test_proje_haritasi_istemde_yalniz_ayar_acikken_ve_yeterli_dosyada(db, tmp_path):
    proj = tmp_path / "p"
    (proj / "pkg").mkdir(parents=True)
    (proj / "pkg" / "hesap.py").write_text("class Kasa:\n    def topla(self):\n        pass\n\ndef bol(a, b):\n"
                                           "    return a / b\n\ndef _gizli():\n    pass\n", encoding="utf-8")
    (proj / "app.js").write_text("export function baslat() {}\nconst durdur = () => 1\n", encoding="utf-8")
    (proj / "README.md").write_text("# x\n", encoding="utf-8")
    (proj / "node_modules").mkdir()
    (proj / "node_modules" / "dev.js").write_text("function x(){}", encoding="utf-8")
    m = projectmap.build(proj)
    assert "pkg/hesap.py: class Kasa(topla), bol()" in m and "_gizli" not in m
    assert "app.js: baslat, durdur" in m and "node_modules" not in m
    _o, c, _t = run(db, proj, [ChatResult(content="bitti", finish_reason="stop")], project_map=True)
    assert "# Proje haritası" in c.systems[0]
    _o, c2, _t = run(db, proj, [ChatResult(content="bitti", finish_reason="stop")])
    assert "# Proje haritası" not in c2.systems[0]                          # ayar kapalı
    small = tmp_path / "kucuk"
    small.mkdir()
    (small / "a.py").write_text("x=1\n", encoding="utf-8")
    assert projectmap.build(small) == ""                                     # 3 dosyadan az → gereksiz


def test_proje_haritasi_sinir_ve_onbellek(tmp_path):
    for i in range(400):
        (tmp_path / f"modul_{i:03d}.py").write_text("\n".join(f"def f{j}(): pass" for j in range(15)), encoding="utf-8")
    m = projectmap.build(tmp_path, max_chars=3000)
    assert len(m) <= 3200 and "kısaltıldı" in m
    assert projectmap.build(tmp_path, max_chars=3000) is m                   # değişmedi → önbellek
    (tmp_path / "yeni.py").write_text("def g(): pass", encoding="utf-8")
    assert projectmap.build(tmp_path, max_chars=3000) is not m


# ---- #3 görevler arası okuma paylaşımı ----------------------------------------------------------

def test_onceki_gorevde_okunan_guncel_dosya_sonraki_goreve_eklenir(tmp_path):
    (tmp_path / "SKILL.md").write_text("Kural: Log önce gelir.", encoding="utf-8")
    (tmp_path / ".env").write_text("SIFRE=1", encoding="utf-8")
    (tmp_path / "buyuk.txt").write_text("x" * (pj.SHARED_FILE_LIMIT + 10), encoding="utf-8")
    st = pj.ProjectState(goal="g", tasks=[pj.Task(1, "a"), pj.Task(2, "b")])
    assert pj.shared_reads(st, tmp_path) == ""                               # okuma yok → ek yok
    st.reads = {"SKILL.md": 2, ".env": 1, "buyuk.txt": 1, "../disari.txt": 1, "silinmis.md": 1}
    out = pj.shared_reads(st, tmp_path)
    assert "--- SKILL.md ---\nKural: Log önce gelir." in out
    assert "SIFRE" not in out and "buyuk.txt" not in out and "disari" not in out
    (tmp_path / "SKILL.md").write_text("Kural: değişti.", encoding="utf-8")
    assert "değişti" in pj.shared_reads(st, tmp_path)                        # her zaman güncel içerik
    assert "Kural: değişti." in pj.task_prompt(st, st.tasks[1], shared=pj.shared_reads(st, tmp_path))
    eski = pj.ProjectState.from_json(json.dumps({"goal": "g", "tasks": []}))  # eski kayıt: reads alanı yok
    assert eski.reads == {}


def test_proje_kosucusu_okumalari_biriktirir(tmp_path):
    (tmp_path / "SKILL.md").write_text("kural", encoding="utf-8")
    prompts = []

    def run_task(task, prompt, fallback):
        prompts.append(prompt)
        return pj.TaskRun(stopped="done", summary="tamam", model="m", reads=["SKILL.md", "SKILL.md"])
    hooks = pj.ProjectHooks(run_task=run_task, review=lambda m: '{"tamam": true, "neden": "ok"}', run_check=lambda c: (0, ""),
                            save=lambda s: None, status=lambda t: None, task_changed=lambda s: None,
                            quota_wait=lambda: (0, ""))
    st = pj.ProjectState(goal="g", tasks=[pj.Task(1, "a"), pj.Task(2, "b")], status="calisiyor")
    pj.ProjectRunner(st, tmp_path, hooks, use_git=False).run()
    assert "--- SKILL.md ---" not in prompts[0] and "--- SKILL.md ---" in prompts[1]
    assert st.reads == {"SKILL.md": 2}                                       # görev başına bir kez sayılır


# ---- E6 proje hafızası ---------------------------------------------------------------------------

def _tur(cmds):
    msgs, i = [], 0
    for name, args, ok in cmds:
        i += 1
        msgs.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": f"c{i}", "name": name, "arguments": json.dumps(args)}]})
        msgs.append({"role": "tool", "tool_call_id": f"c{i}", "content": "çıktı", "meta": {"error": not ok}})
    return msgs


def test_ders_sinyali_tetiklenir_ve_tetiklenmez():
    assert learnings.signals(_tur([("run_command", {"command": "pytest"}, False),
                                   ("run_command", {"command": "python -m unittest"}, True)]))
    assert learnings.signals(_tur([("install_program", {"name": "node"}, True)])) == ["program kuruldu"]
    assert learnings.signals([], ["test_break"]) == ["testler değişiklikten sonra düştü"]
    # sıradan turlar: başarılı komutlar, aynı komutun tekrarı, yalnız okuma → sinyal YOK (model çağrılmaz)
    assert learnings.signals(_tur([("run_command", {"command": "python a.py"}, True)])) == []
    assert learnings.signals(_tur([("run_command", {"command": "x"}, False), ("run_command", {"command": "x"}, True)])) == []
    assert learnings.signals(_tur([("read_file", {"path": "a"}, True)]), ["loop"]) == []


def test_ders_ayristirma():
    assert learnings.parse("YOK") == [] and learnings.parse("  yok.  ") == [] and learnings.parse("") == []
    items = learnings.parse("Dersler:\n- Testler `python -m unittest` ile koşuyor\n2) satis.csv cp1254 kodlu\n- a\n- b")
    assert items[:2] == ["Testler `python -m unittest` ile koşuyor", "satis.csv cp1254 kodlu"] and len(items) == 3


def test_evren_md_ogrenilenler_bolumu(tmp_path):
    p = learnings.append(tmp_path, ["bir"])
    assert p.read_text(encoding="utf-8").startswith("# EVREN proje notları\n\n## Öğrenilenler\n- bir")
    (tmp_path / "EVREN.md").write_bytes(b"# Proje\r\nKurallar\r\n\r\n## Diger\r\nx\r\n")
    learnings.append(tmp_path, ["iki", "iki"])
    learnings.append(tmp_path, ["iki", "üç"])
    raw = (tmp_path / "EVREN.md").read_bytes()
    t = raw.decode("utf-8")
    assert not raw.startswith(b"\xef\xbb\xbf") and "\r\n" in t and "\n" not in t.replace("\r\n", "")  # CRLF korundu
    assert t.count("- iki") == 1 and "- üç" in t and "## Diger\r\nx" in t
    learnings.append(tmp_path, [f"m{i}" for i in range(40)][:3])
    for i in range(15):
        learnings.append(tmp_path, [f"d{i}a", f"d{i}b", f"d{i}c"])
    body = (tmp_path / "EVREN.md").read_text(encoding="utf-8").split("## Öğrenilenler")[1].split("## Diger")[0]
    assert body.count("\n- ") == learnings.MAX_LINES and "- d14c" in body and "- iki" not in body


def test_ders_icin_model_yalniz_sinyalde_cagrilir(tmp_path, monkeypatch, fake_keyring):
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("EVREN_STUDIO_NO_LEARNINGS", raising=False)
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow
    from evren_studio.ui.transcript import ActionCard

    w = MainWindow()
    try:
        calls = []
        w.ctx.ai_chat = lambda role, msgs, **kw: (calls.append(role) or ("- Testler unittest ile koşuyor", "m"))
        s = w.session
        proj = tmp_path / "proje"
        proj.mkdir()
        s.new_session()
        s.welcome._choose(str(proj))
        s._ensure_session("ders")
        sid = s.session_id
        tid = w.ctx.db.add_session_message(sid, "user", "testleri çalıştır")
        s._suggest_learnings(tid, [])
        assert calls == []                                                    # sinyal yok → çağrı yok
        w.ctx.db.add_session_message(sid, "assistant", "", tool_calls=[{"id": "a", "name": "install_program",
                                                                         "arguments": "{}"}])
        w.ctx.db.add_session_message(sid, "tool", "kuruldu", tool_call_id="a", name="install_program",
                                     meta={"error": False})
        s._suggest_learnings(tid, [])
        import time
        end = time.monotonic() + 5
        while time.monotonic() < end and not s.findChildren(ActionCard):
            app.processEvents()
            time.sleep(0.02)
        cards = [c for c in s.findChildren(ActionCard) if "öğrenilenler" in c.title.text()]
        assert calls == ["ozet"] and cards
        assert not (proj / "EVREN.md").exists()                               # onaysız yazılmaz
        w.ctx.settings.learnings_suggest = False
        s._suggest_learnings(tid, [])
        assert calls == ["ozet"]                                              # ayar kapalı
    finally:
        w.close()


def test_spec_tanimlari():
    assert SPEC_BY_NAME["read_table"].kind == "read" and SPEC_BY_NAME["web_fetch"].kind == "exec"
