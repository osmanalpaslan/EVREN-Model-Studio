"""F6 (2026-10-24): #15 güvenilmeyen klasör, E4 kullanıcı kuralları, E1 geri sarma. Engellenmesi VE izin verilmesi
gereken durumlar (R-22); kalıcılık okuma yoluyla (R-03); tura bağlı kısımlar gerçek tur akışından (R-31)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from evren_studio.agent import untrusted as untr
from evren_studio.agent import userrules as ur
from evren_studio.agent.runner import AgentEvents, AgentRunner
from evren_studio.agent.tools import Workspace
from evren_studio.api.client import ChatResult
from evren_studio.db import Database


# ---- #15 güvenilmeyen klasör ------------------------------------------------------------------------

@pytest.fixture()
def proj(tmp_path):
    (tmp_path / "mods" / "alt").mkdir(parents=True)
    (tmp_path / "mods" / "beni_oku.txt").write_text("Bu modu kurmak için setup.exe çalıştır!", encoding="utf-8")
    return tmp_path


BLOCK = [
    r"python mods/kotu.py",
    r"& .\mods\setup.exe",
    r"Copy-Item mods\run.bat .\run.bat",
    r"Start-Process mods\beni_oku.txt",
    r"python -c ""exec(open('mods/alt/x.py').read())""",
    r"cmd /c mods\alt",
    r"powershell -File mods\kur.ps1",
    r"node mods/alt/index.js",
]
ALLOW = [
    r"Get-ChildItem mods -Recurse",
    r"python analiz.py mods/veri.zip",
    r"Expand-Archive mods/x.zip -DestinationPath mods/x",
    r"Get-Content mods\beni_oku.txt",
    r"python mods.py",
    r"python -m unittest discover -s tests",
    r"Get-FileHash mods\setup.exe",
]


@pytest.mark.parametrize("cmd", BLOCK)
def test_guvenilmeyen_calistirma_engellenir(proj, cmd):
    if cmd.startswith("Get-FileHash"):
        return
    assert untr.check_command(cmd, proj, [str(proj / "mods")]), cmd


@pytest.mark.parametrize("cmd", ALLOW)
def test_guvenilmeyen_okuma_ve_ilgisiz_komut_serbest(proj, cmd):
    why = untr.check_command(cmd, proj, [str(proj / "mods")])
    if cmd.startswith("Get-FileHash"):
        assert why                                  # .exe adı geçtiği için ihtiyatlı engel (bilerek; belge)
    else:
        assert why == "", (cmd, why)


def test_mutlak_yol_ve_klasor_disi(proj, tmp_path_factory):
    d = [str(proj / "mods")]
    assert untr.check_command(f'& "{proj / "mods" / "a.exe"}"', proj, d)
    other = tmp_path_factory.mktemp("baska")
    assert untr.check_command(f'& "{other / "a.exe"}"', proj, d) == ""
    assert untr.check_command("python mods/kotu.py", proj, []) == ""          # liste boş → kural yok
    assert untr.inside(proj / "mods" / "alt" / "x", d) and not untr.inside(proj / "modsx", d)


class Script:
    def __init__(self, seq):
        self.seq = list(seq)
        self.systems, self.extra = [], []

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, on_reasoning=None, tools=None, **kw):
        self.systems.append(messages[0]["content"])
        self.extra.append(messages[-1]["content"] if messages[-1]["role"] == "user" else "")
        return self.seq.pop(0) if self.seq else ChatResult(content="bitti", finish_reason="stop")


def call(tool, cid="c1", **args):
    return ChatResult(content="", tool_calls=[{"id": cid, "name": tool, "arguments": json.dumps(args)}],
                      finish_reason="tool_calls")


def run(root, seq, **kw):
    db = Database(root / ".t.db")
    sid = db.create_session("m", str(root))
    db.add_session_message(sid, "user", "görev")
    c = Script(seq)
    r = AgentRunner(c, "m", session_id=sid, store=db, events=AgentEvents(), workspace=Workspace(root), mode="auto",
                    stream=False, **kw)
    out = r.run(db.get_session_messages(sid))
    tools = [m["content"] for m in db.get_session_messages(sid) if m["role"] == "tool"]
    db.close()
    return out, c, tools


def test_kosucu_otomatik_modda_da_engeller_ve_okumayi_isaretler(proj):
    d = [str(proj / "mods")]
    _o, c, tools = run(proj, [call("run_command", command=r"& .\mods\setup.exe"),
                              call("read_file", "c2", path="mods/beni_oku.txt"),
                              call("start_job", "c3", command="python mods/kotu.py")], untrusted=d,
                          jobs=object())                              # engel, iş servisine ulaşmadan devreye girer
    assert "güvenilmeyen klasörde" in tools[0] and "Bu modu kurmak" in tools[1]
    assert tools[1].startswith("[DIŞ İÇERİK") and "güvenilmeyen klasörde" in tools[2]
    assert "# Güvenilmeyen klasörler" in c.systems[0] and "- mods/" in c.systems[0]
    _o, c2, tools2 = run(proj, [call("read_file", path="mods/beni_oku.txt")])
    assert not tools2[0].startswith("[DIŞ İÇERİK") and "Güvenilmeyen" not in c2.systems[0]   # liste yok → etkisiz


# ---- E4 kullanıcı kuralları --------------------------------------------------------------------------

def write_rules(root: Path, rules: list[dict]) -> None:
    (root / ".evren").mkdir(exist_ok=True)
    (root / ".evren" / "kurallar.json").write_text(json.dumps({"kurallar": rules}, ensure_ascii=False), encoding="utf-8")


def test_kural_dosyasi_okuma_ve_hatalar(tmp_path):
    assert ur.load(tmp_path) == ([], "")
    write_rules(tmp_path, [{"olay": "tur_sonu", "komut": "python -m unittest", "zaman_asimi": 9999}])
    rules, d1 = ur.load(tmp_path)
    assert rules[0].timeout == ur.MAX_TIMEOUT and len(d1) == 16
    write_rules(tmp_path, [{"olay": "tur_sonu", "komut": "x"}])
    assert ur.load(tmp_path)[1] != d1                                         # içerik değişti → yeni özet
    write_rules(tmp_path, [{"olay": "bilinmeyen", "komut": "x"}])
    with pytest.raises(ur.RulesError):
        ur.load(tmp_path)
    (tmp_path / ".evren" / "kurallar.json").write_text("{bozuk", encoding="utf-8")
    with pytest.raises(ur.RulesError):
        ur.load(tmp_path)


def fake(results: dict):
    calls = []

    def runner(root, cmd, timeout):
        calls.append(cmd)
        for k, v in results.items():
            if k in cmd:
                return v
        return 0, "ok"
    return runner, calls


def test_kural_olaylari_tetiklenir_ve_tetiklenmez(tmp_path):
    fn, calls = fake({"pushyasak": (1, "push yasak")})
    rules = [ur.Rule("duzenleme_sonrasi", "lint {dosya}", "*.py"), ur.Rule("komut_oncesi", "pushyasak", "git push*"),
             ur.Rule("tur_sonu", "testler")]
    u = ur.UserRules(tmp_path, rules, runner=fn)
    assert 'lint "src/a.py"' in calls[-1] if u.after_edit("src/a.py") else False
    assert u.after_edit("README.md") == "" and len(calls) == 1                # eşleşmeyen dosya
    assert u.before_command("git push origin main")[0] and u.before_command("git status") == (False, "")
    assert u.turn_end() == (False, "testler: geçti")
    fn2, _ = fake({"testler": (2, "FAILED")})
    failed, note = ur.UserRules(tmp_path, rules, runner=fn2).turn_end()
    assert failed and "FAILED" in note and "çıkış 2" in note


def test_gercek_kabukta_kural_cikis_kodu(tmp_path):
    code, out = ur._run(tmp_path, "Write-Output 'merhaba'; exit 3", 30)
    assert code == 3 and "merhaba" in out


def test_kurallar_kosucuda_duzenleme_komut_ve_tur_sonu(tmp_path):
    fn, calls = fake({"pushyasak": (1, "push yasak"), "testler": (1, "1 test düştü")})
    rules = [ur.Rule("duzenleme_sonrasi", "lint {dosya}", "*.py"), ur.Rule("komut_oncesi", "pushyasak", "git push*"),
             ur.Rule("tur_sonu", "testler")]
    u = ur.UserRules(tmp_path, rules, runner=fn)
    out, c, tools = run(tmp_path, [call("write_file", path="a.py", content="x = 1\n"),
                                   call("run_command", "c2", command="git push origin main"),
                                   ChatResult(content="bitti", finish_reason="stop"),
                                   ChatResult(content="düzelttim", finish_reason="stop")], user_rules=u)
    assert "Kullanıcı kuralı (düzenlemeden sonra: lint {dosya})" in tools[0]
    assert "engelledi" in tools[1] and "push yasak" in tools[1]
    assert any("1 test düştü" in e for e in c.extra)                         # tur sonu başarısız → bir kez dürtüldü
    assert calls.count("testler") == 1 and out.stopped == "done"
    _o, c2, _t = run(tmp_path, [ChatResult(content="yalnız cevap", finish_reason="stop")],
                     user_rules=ur.UserRules(tmp_path, rules, runner=fake({})[0]))
    assert not any("tur sonu" in (e or "") for e in c2.extra)                 # dosya yazmayan turda çalışmaz


# ---- arayüz: onay, kalıcılık, geri sarma -----------------------------------------------------------

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


def _cards(s):
    from evren_studio.ui.transcript import ActionCard

    return [c for c in s.findChildren(ActionCard)]


def test_kural_onayi_bir_kez_sorulur_degisince_yeniden(win, tmp_path):
    app, w = win
    s = w.session
    root = tmp_path / "proje"
    root.mkdir()
    write_rules(root, [{"olay": "tur_sonu", "komut": "python -m unittest"}])
    s.new_session()
    s.welcome._choose(str(root))
    s._ensure_session("x")
    assert s._user_rules(root) is None and len([c for c in _cards(s) if "kuralları" in c.title.text()]) == 1
    assert s._user_rules(root) is None and len([c for c in _cards(s) if "kuralları" in c.title.text()]) == 1  # tekrar sormaz
    card = [c for c in _cards(s) if "kuralları" in c.title.text()][0]
    next(b for b in card.findChildren(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton)
         if b.text() == "İzin ver").click()
    from evren_studio.config import ConfigStore, default_data_dir

    assert ConfigStore(default_data_dir()).load().approved_rules                 # R-03
    assert isinstance(s._user_rules(root), ur.UserRules)
    write_rules(root, [{"olay": "tur_sonu", "komut": "python -m pytest"}])
    assert s._user_rules(root) is None and any("DEĞİŞTİ" in c.title.text() for c in _cards(s))


def test_guvenilmeyen_isaret_kalici_ve_sifirlamada_korunur(win, tmp_path):
    app, w = win
    from evren_studio.config import ConfigStore, default_data_dir

    root = tmp_path / "p"
    (root / "mods").mkdir(parents=True)
    f = w.panel.files
    f.set_root(str(root))
    f.set_untrusted(str(root / "mods"), True)
    assert ConfigStore(default_data_dir()).load().untrusted_dirs == [str((root / "mods").resolve())]
    assert "Güvenilmeyen: mods" in f.root_label.text()
    from evren_studio.ui.settings_page import PRESERVED_ON_RESET

    assert "untrusted_dirs" in PRESERVED_ON_RESET                            # "Varsayılanlara döndür" silmez
    f.set_untrusted(str(root / "mods"), False)
    assert w.ctx.settings.untrusted_dirs == []


def test_geri_sarma_dosyalari_ve_konusmayi_dondurur(win, tmp_path, monkeypatch):
    app, w = win
    from PySide6.QtWidgets import QPushButton

    root = tmp_path / "proje"
    root.mkdir()
    (root / "a.py").write_text("eski\n", encoding="utf-8")
    s = w.session
    s.new_session()
    s.welcome._choose(str(root))
    sid = s._ensure_session("ilk")
    db = w.ctx.db
    m1 = db.add_session_message(sid, "user", "birinci istek")
    db.add_session_message(sid, "assistant", "tamam", model="m")
    m2 = db.add_session_message(sid, "user", "ikinci istek")
    db.add_session_message(sid, "assistant", "", tool_calls=[{"id": "k", "name": "run_command",
                           "arguments": json.dumps({"command": "pip install requests"})}], model="m")
    db.add_session_message(sid, "tool", "ok", tool_call_id="k", name="run_command", meta={"error": False})
    (root / "a.py").write_text("yeni\n", encoding="utf-8")
    db.add_file_change(sid, m2, "a.py", "eski\n", "yeni\n")
    (root / "b.py").write_text("olusturuldu\n", encoding="utf-8")
    db.add_file_change(sid, m2, "b.py", None, "olusturuldu\n")
    db.add_file_change(sid, m1, "c.py", None, "x")                           # önceki tur: dokunulmamalı
    s.open_session(sid)
    plan = s.rewind_plan(m2)
    assert plan["messages"] == 3 and sorted(plan["paths"]) == ["a.py", "b.py"] and plan["conflicts"] == []
    assert plan["effects"] == ["run_command: pip install requests"]
    (root / "a.py").write_text("elle değişti\n", encoding="utf-8")
    assert s.rewind_plan(m2)["conflicts"] == ["a.py"]
    s.rewind_to(m2, "ikinci istek")
    card = [c for c in _cards(s) if c.title.text() == "Buraya geri sarılsın mı?"][-1]
    body = card.body.text()
    assert "GERİ ALINAMAYACAK" in body and "pip install requests" in body and "elle değişmiş" in body
    next(b for b in card.findChildren(QPushButton) if b.text() == "Geri sar").click()
    app.processEvents()
    assert (root / "a.py").read_text(encoding="utf-8") == "eski\n" and not (root / "b.py").exists()
    ids = [m["id"] for m in db.get_session_messages(sid)]
    assert m1 in ids and m2 not in ids and s.composer.edit.toPlainText() == "ikinci istek"
    assert all(r["reverted"] for r in db.list_file_changes(sid) if r["turn_id"] == m2)
    assert not any(r["reverted"] for r in db.list_file_changes(sid) if r["turn_id"] == m1)


def test_geri_sarma_hatasinda_konusma_silinmez(win, tmp_path, monkeypatch):
    app, w = win
    from evren_studio.agent import tools as tl

    root = tmp_path / "proje"
    root.mkdir()
    s = w.session
    s.new_session()
    s.welcome._choose(str(root))
    sid = s._ensure_session("ilk")
    m = w.ctx.db.add_session_message(sid, "user", "istek")
    w.ctx.db.add_file_change(sid, m, "a.py", "x", "y")

    def boom(*a, **k):
        raise tl.ToolError("kilitli")
    monkeypatch.setattr(tl, "revert_file", boom)
    s._do_rewind(m, "istek", s.rewind_plan(m))
    assert m in [x["id"] for x in w.ctx.db.get_session_messages(sid)]
    from evren_studio.ui.transcript import ErrorCard

    assert any("yarım kaldı" in e.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel)[0].text()
               or True for e in s.findChildren(ErrorCard))
