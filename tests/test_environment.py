"""Ortam denetimi: proje türünden gereken programlar, kurulum planı, ajan aracı ve
arayüz kartı. Gerçek kurulum YAPILMAZ (conftest kilidi + sahte install)."""
from __future__ import annotations

import json
import os
import time

import pytest

from evren_studio.agent import environment as env
from evren_studio.agent.runner import AgentEvents, AgentRunner, ApprovalRequest
from evren_studio.agent.tools import Workspace
from evren_studio.api.client import ChatResult
from evren_studio.db import Database


# ---- proje türü --------------------------------------------------------------------------


def test_bos_klasorde_gereksinim_yok(tmp_path):
    assert env.detect_requirements(tmp_path) == {}


def test_node_pnpm_python_go_dotnet_tespiti(tmp_path):
    (tmp_path / "package.json").write_text('{"packageManager": "pnpm@9.0.0"}', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "go.mod").write_text("module x\n", encoding="utf-8")
    (tmp_path / "app.csproj").write_text("<Project/>", encoding="utf-8")
    req = env.detect_requirements(tmp_path)
    assert req["node"] == "package.json" and req["pnpm"] == "packageManager: pnpm"
    assert req["python"] == "pyproject.toml" and req["go"] == "go.mod"
    assert req["dotnet"] == "*.csproj"


def test_kilit_dosyasi_yarn(tmp_path):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "yarn.lock").write_text("", encoding="utf-8")
    assert set(env.detect_requirements(tmp_path)) == {"node", "yarn"}


def test_takma_adlar():
    assert env.normalize_tool("npm") == "node"
    assert env.normalize_tool("Cargo") == "rust"
    assert env.normalize_tool("photoshop") is None


def test_istem_bolumu_moda_gore(tmp_path):
    st = [env.ToolStatus("pnpm", "pnpm", "pnpm-lock.yaml", None)]
    oto = env.prompt_section(st, "otomatik")
    man = env.prompt_section(st, "manuel")
    assert "install_program" in oto and "sorulmadan kurulur" in oto and "pnpm ✗ eksik" in oto
    assert "kullanıcıya sorulur" in man


def test_kurulum_plani_once_npm_sonra_winget(monkeypatch):
    monkeypatch.setattr(env.shutil, "which", lambda n: {"npm": r"C:\n\npm.cmd",
                                                         "winget": r"C:\w\winget.exe"}.get(n))
    plans = env.install_plan("pnpm")
    assert plans[0][1:] == ["install", "-g", "pnpm"]
    assert "pnpm.pnpm" in plans[1] and "--scope" in plans[1]
    assert "--accept-package-agreements" in env.install_plan("go")[0]
    assert env.install_plan("node")[0][3] == "OpenJS.NodeJS.LTS"


def test_kurulum_basarili_ve_path_yenilenir(monkeypatch):
    import importlib

    real = importlib.reload(env)            # conftest kilidini bu modül kopyasında kaldır
    state = {"kuruldu": False, "komutlar": []}
    monkeypatch.setattr(real, "find_exe", lambda t: r"C:\go\bin\go.exe" if state["kuruldu"] else None)
    monkeypatch.setattr(real, "tool_version", lambda t, e, timeout=15: "1.24.0")
    monkeypatch.setattr(real, "install_plan", lambda k: [["winget", "install", "--id", "GoLang.Go"]])
    monkeypatch.setattr(real, "refresh_path", lambda: None)

    class P:
        returncode, stdout, stderr = 0, "Başarıyla yüklendi", ""

    def fake_run(cmd, **kw):
        state["komutlar"].append(cmd)
        state["kuruldu"] = True
        return P()

    monkeypatch.setattr(real.subprocess, "run", fake_run)
    r = real._install("go", None, 60, None)
    assert r.ok and r.version == "1.24.0" and state["komutlar"]
    assert real._install("photoshop", None, 60, None).ok is False


def test_gereksinim_once_kurulur(monkeypatch):
    import importlib

    real = importlib.reload(env)
    kurulu: set[str] = set()
    monkeypatch.setattr(real, "find_exe", lambda t: "x" if t.key in kurulu else None)
    monkeypatch.setattr(real, "tool_version", lambda t, e, timeout=15: "")
    monkeypatch.setattr(real, "refresh_path", lambda: None)
    monkeypatch.setattr(real, "install_plan", lambda k: [[k, "kur"]])

    class P:
        returncode, stdout, stderr = 0, "", ""

    sira = []

    def fake_run(cmd, **kw):
        sira.append(cmd[0])
        kurulu.add(cmd[0])
        return P()

    monkeypatch.setattr(real.subprocess, "run", fake_run)
    r = real._install("pnpm", None, 60, None)
    assert r.ok and sira == ["node", "pnpm"] and r.steps == ["node: kuruldu"]


# ---- ajan aracı -----------------------------------------------------------------------------


class Fake:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def chat(self, model, messages, **kw):
        self.requests.append(messages)
        return self.responses.pop(0) if self.responses else ChatResult(content="Bitti.", finish_reason="stop")


class Ev(AgentEvents):
    def __init__(self, decision):
        self.decision = decision
        self.asked = []

    def approval_needed(self, req: ApprovalRequest):
        self.asked.append(req)
        req.resolve(self.decision)


def _run(tmp_path, monkeypatch, mode, install_mode, decision="deny", name="go"):
    calls = []
    monkeypatch.setattr(env, "find_exe", lambda t: None)
    monkeypatch.setattr(env, "install",
                        lambda key, **k: calls.append(key) or env.InstallResult(key, True, "winget …",
                                                                                "", "1.24.0", "go.exe"))
    db = Database(tmp_path / "t.db")
    sid = db.create_session("m", str(tmp_path), mode)
    db.add_session_message(sid, "user", "görev")
    ev = Ev(decision)
    client = Fake([ChatResult(tool_calls=[{"id": "c1", "name": "install_program",
                                           "arguments": json.dumps({"name": name, "reason": "go.mod var"})}])])
    r = AgentRunner(client, "m", session_id=sid, store=db, events=ev, workspace=Workspace(tmp_path),
                    mode=mode, stream=False, install_mode=install_mode)
    r.run(db.get_session_messages(sid))
    tool = [m for m in db.get_session_messages(sid) if m["role"] == "tool"][0]
    db.close()
    return calls, ev, tool, r, client


def test_otomatik_kurulum_sormaz(tmp_path, monkeypatch):
    calls, ev, tool, r, client = _run(tmp_path, monkeypatch, "manuel", "otomatik")
    assert calls == ["go"] and ev.asked == [] and "kuruldu" in tool["content"]
    assert tool["meta"]["auto_approved"]


def test_manuel_kurulum_sorar_reddedilirse_kurmaz(tmp_path, monkeypatch):
    calls, ev, tool, r, client = _run(tmp_path, monkeypatch, "auto", "manuel", decision="deny")
    assert calls == [] and len(ev.asked) == 1 and ev.asked[0].kind == "install"
    assert "kurulsun mu" in ev.asked[0].title and tool["meta"]["denied"]


def test_manuel_kurulum_onaylanirsa_kurar_ve_oturum_izni(tmp_path, monkeypatch):
    calls, ev, tool, r, client = _run(tmp_path, monkeypatch, "auto", "manuel", decision="allow_session")
    assert calls == ["go"] and r.perms.allow_installs


def test_bilinmeyen_program_kurulmaz(tmp_path, monkeypatch):
    calls, ev, tool, r, client = _run(tmp_path, monkeypatch, "auto", "otomatik", name="photoshop")
    assert calls == [] and "bilinen kurulum listesinde yok" in tool["content"]


def test_plan_modunda_kurulum_engelli(tmp_path, monkeypatch):
    calls, ev, tool, r, client = _run(tmp_path, monkeypatch, "plan", "otomatik")
    assert calls == [] and ev.asked == []


def test_sistem_isteminde_ortam_bolumu(tmp_path, monkeypatch):
    (tmp_path / "go.mod").write_text("module x\n", encoding="utf-8")
    calls, ev, tool, r, client = _run(tmp_path, monkeypatch, "auto", "manuel")
    system = client.requests[0][0]["content"]
    assert "# Ortam denetimi" in system and "go ✗ eksik" in system and "kullanıcıya sorulur" in system


# ---- arayüz kartı ----------------------------------------------------------------------------


@pytest.fixture()
def window(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    yield app, w
    w.close()


def _wait(app, cond, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


@pytest.mark.parametrize("mode", ["manuel", "otomatik"])
def test_arayuz_kurulum_karti(window, tmp_path, monkeypatch, mode):
    from evren_studio.ui.transcript import InstallCard

    app, w = window
    proj = tmp_path / "proje"
    proj.mkdir()
    (proj / "go.mod").write_text("module x\n", encoding="utf-8")
    monkeypatch.setattr(env, "find_exe", lambda t: None)
    monkeypatch.setattr(env, "tool_version", lambda *a, **k: "")
    kurulan = []
    monkeypatch.setattr(env, "install", lambda key, **k: kurulan.append(key) or
                        env.InstallResult(key, True, "winget", "", "1.24.0", "go.exe"))
    w.ctx.settings.install_mode = mode
    w.session.welcome._choose(str(proj))
    w.session._ensure_session("deneme")
    assert _wait(app, lambda: w.session.findChildren(InstallCard))
    card = w.session.findChildren(InstallCard)[0]
    if mode == "manuel":
        assert card.buttons and "Kurulsun mu" in card.title.text() and kurulan == []
        card.install_btn.click()
    assert _wait(app, lambda: "Kurulum tamamlandı" in card.title.text())
    assert kurulan == ["go"] and "✓ Go kuruldu (1.24.0)" in card.body.text()
    if mode == "otomatik":
        assert not card.buttons


def test_kisa_plan(monkeypatch):
    monkeypatch.setattr(env.shutil, "which", lambda n: {"npm": r"C:\n\npm.cmd",
                                                         "winget": r"C:\w\winget.exe"}.get(n))
    assert env.short_plan("go") == "winget install GoLang.Go"
    assert env.short_plan("pnpm") == "npm install -g pnpm"
    monkeypatch.setattr(env.shutil, "which", lambda n: None)
    assert "yok" in env.short_plan("go")
