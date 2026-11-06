"""Masaüstü kontrolü ve masaüstü QA (Madde 13, 2026-11-05). Gerçek fare/klavye/masaüstü YOK: Windows-MCP yerine
tests/fake_mcp_server.py ve sahte yönetici. Her otomatik tetik için tetiklenen ve tetiklenmeyen durum (R-22)."""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

import pytest

from evren_studio.agent import mcp, qa
from evren_studio.agent.tools import EXEC, READ

FAKE = str(Path(__file__).with_name("fake_mcp_server.py"))
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


# ---- ne zaman sunulur -------------------------------------------------------------------------------

@pytest.mark.parametrize("mesaj", [
    "Not Defteri'ni aç ve merhaba yaz", "masaüstündeki uygulamayı test et", "dist\\HesapAraci.exe açılınca ne oluyor?",
    "Hesap makinesinde 2+2 yap", "fareyle şu pencereyi büyüt", "MASAÜSTÜ uygulamasını dene"])
def test_masaustu_isi_istenince_sunulur(mesaj):
    ok, why = mcp.needed(mcp.windows_config(), mcp.ProjectProfile(), mesaj)
    assert ok, why


@pytest.mark.parametrize("mesaj", [
    "butona tıkla ve formu gönder", "sayfadaki açılır pencere kapanmıyor", "README'yi güncelle",
    "testleri çalıştır", "web uygulamasının giriş ekranını test et", ""])
def test_masaustu_isi_yokken_sunulmaz(mesaj):
    ok, _why = mcp.needed(mcp.windows_config(), mcp.ProjectProfile(web=True, code_files=50), mesaj)
    assert not ok


# ---- güvenlik yapılandırması ------------------------------------------------------------------------

def test_tam_yetkili_araclar_verilmez_telemetri_kapali():
    cfg = mcp.windows_config()
    for t in ("PowerShell", "FileSystem", "Registry", "Process", "Clipboard"):
        assert t not in cfg.allowed_tools and t in cfg.args[cfg.args.index("--exclude-tools") + 1].split(",")
    assert cfg.env["ANONYMIZED_TELEMETRY"] == "false"
    assert "--control-policy" not in cfg.args                         # 0.8.8'de yok (gerçek deneme 2026-11-05)
    assert set(cfg.read_only_tools) <= set(cfg.allowed_tools)
    for t in ("Click", "Type", "App", "Shortcut", "Move", "MultiEdit"):
        assert t not in cfg.read_only_tools, f"{t} sorulmadan çalışmamalı"
    assert mcp.WINDOWS_MCP_PACKAGE == "windows-mcp==0.8.8"        # sabit sürüm (tedarik zinciri)
    assert cfg.blocked_keys == ["End"]                             # ayarsız kullanımda da End engelli (kullanıcı)


def test_ekran_goruntusu_metin_modeline_sunulmaz_talimat_uydurmayi_yasaklar():
    """2026-11-05 gerçek deneme: model göremediği ekran görüntüsünden "Sonuç: 5 görünüyor" diye uydurdu."""
    cfg = mcp.windows_config()
    assert "Screenshot" not in cfg.allowed_tools and "Screenshot" not in cfg.read_only_tools
    assert "UYDURMA" in mcp.DESKTOP_PROMPT and "doğrulayamadım" in mcp.DESKTOP_PROMPT
    text, _err = mcp.result_text({"content": [{"type": "image", "data": "x", "mimeType": "image/png"}]})
    assert "GÖREMEZSİN" in text and "gördüm" in text
    assert "GİZLİLİK" in mcp.PRESETS["masaustu"]["confirm"] and "EVREN API" in mcp.PRESETS["masaustu"]["confirm"]


@pytest.mark.parametrize("kisayol", ["End", "ctrl+end", "Ctrl + End", "shift+END"])
def test_engelli_tus_kisayolda_calistirilmaz(kisayol):
    """Kullanıcı 2026-11-05: 'End tuşu ekran yakalamayı açıyor, test yarıda kalır'."""
    _args, ret = mcp.desktop_guard("Shortcut", {"shortcut": kisayol}, ["End"])
    assert ret and "engelli" in ret


@pytest.mark.parametrize("kisayol", ["ctrl+c", "alt+tab", "enter", "ctrl+shift+s"])
def test_engelli_olmayan_kisayol_gecer(kisayol):
    args, ret = mcp.desktop_guard("Shortcut", {"shortcut": kisayol}, ["End"])
    assert ret == "" and args["shortcut"] == kisayol


def test_yazarken_end_gonderilmez_ama_engel_yoksa_dokunulmaz():
    assert mcp.desktop_guard("Type", {"text": "2", "caret_position": "end"}, ["End"])[0]["caret_position"] == "idle"
    assert mcp.desktop_guard("Type", {"text": "2", "caret_position": "end"}, [])[0]["caret_position"] == "end"
    assert mcp.desktop_guard("Type", {"text": "2", "caret_position": "start"}, ["End"])[0]["caret_position"] == "start"
    assert mcp.desktop_guard("Type", {"text": "2", "caret_position": "start"}, ["Home"])[0]["caret_position"] == "idle"
    assert mcp.desktop_guard("Type", {"text": "{End}"}, ["End"])[0]["text"] == "{End}"   # metin kaçışlı yazılır


def test_snapshotta_gorsel_hep_kapali():
    assert mcp.desktop_guard("Snapshot", {"use_vision": True, "use_dom": True}, [])[0] == {"use_vision": False,
                                                                                            "use_dom": True}


def test_bekci_tur_yolunda_uygulanir_ve_reddedilen_cagri_sunucuya_gitmez():
    class Mgr:
        def __init__(self):
            self.calls = []

        def running(self, *_a):
            return object()

        def call(self, cfg, root, tool, args):
            self.calls.append((tool, args))
            return {"content": [{"type": "text", "text": "tamam"}]}

    cfg = mcp.windows_config()
    cfg.blocked_keys = ["End"]
    mgr = Mgr()
    tools = [mcp.McpTool("masaustu", n, mcp.tool_spec("masaustu", {"name": n}, False), False)
             for n in ("Shortcut", "Type", "Snapshot")]
    ts = mcp.McpToolset(tools, mgr, {"masaustu": cfg}, None)
    text, err = ts.call("mcp__masaustu__Shortcut", {"shortcut": "ctrl+end"})
    assert err and "engelli" in text and mgr.calls == []
    ts.call("mcp__masaustu__Type", {"text": "2", "caret_position": "end"})
    ts.call("mcp__masaustu__Snapshot", {"use_vision": True})
    assert mgr.calls == [("Type", {"text": "2", "caret_position": "idle"}), ("Snapshot", {"use_vision": False})]
    # masaüstü olmayan sunucuya bekçi karışmaz (R-22)
    other = mcp.McpServerConfig(name="baska", command="x")
    ts2 = mcp.McpToolset([mcp.McpTool("baska", "Shortcut", mcp.tool_spec("baska", {"name": "Shortcut"}, False), False)],
                         mgr, {"baska": other}, None)
    ts2.call("mcp__baska__Shortcut", {"shortcut": "ctrl+end"})
    assert mgr.calls[-1] == ("Shortcut", {"shortcut": "ctrl+end"})


def test_tiklama_izin_sisteminde_komut_okuma_sorulmaz():
    click = mcp.tool_spec("masaustu", {"name": "Click", "inputSchema": {}}, "Click" in mcp.WINDOWS_READ_ONLY)
    snap = mcp.tool_spec("masaustu", {"name": "Snapshot", "inputSchema": {}}, "Snapshot" in mcp.WINDOWS_READ_ONLY)
    assert click.kind == EXEC and snap.kind == READ
    assert click.name == "mcp__masaustu__Click"


def test_hazir_ayar_ayarlardan_guncel_tanimla_okunur():
    raw = [{**mcp.windows_config().to_dict(), "allowed_tools": ["PowerShell"], "enabled": True}]
    cfg = mcp.configs_from_settings(raw)[0]
    assert "PowerShell" not in cfg.allowed_tools and cfg.when == "masaustu"   # eski/kurcalanmış kayıt yetki açamaz


# ---- kurulum ------------------------------------------------------------------------------------------

def test_kurulum_uv_ile_python_314_ve_sabit_surum(tmp_path, monkeypatch):
    calls = []

    def fake_run(argv, timeout, flags):
        calls.append(argv)
        boot = tmp_path / "mcp" / "windows" / "boot" / "Scripts"
        boot.mkdir(parents=True, exist_ok=True)
        (boot / ("uv.exe" if "pip" in argv else "python.exe")).write_text("", encoding="utf-8")

    class R:
        returncode = 0
        stdout = stderr = ""

    def fake_sub(argv, **kw):
        calls.append(argv)
        venv = tmp_path / "mcp" / "windows" / "venv" / "Scripts"
        venv.mkdir(parents=True, exist_ok=True)
        (venv / "python.exe").write_text("", encoding="utf-8")
        if "pip" in argv:
            (venv / "windows-mcp.exe").write_text("", encoding="utf-8")
        assert kw["env"]["UV_PYTHON_INSTALL_DIR"].startswith(str(tmp_path))   # Python veri klasörüne iner
        return R()

    monkeypatch.setattr(mcp, "_run", fake_run)
    monkeypatch.setattr(mcp, "check_windows_flags", lambda exe, help_text=None: [])
    monkeypatch.setattr(mcp.subprocess, "run", fake_sub)
    monkeypatch.setattr(mcp.os, "name", "nt")
    exe = mcp.install_windows_mcp(tmp_path)
    flat = [" ".join(map(str, c)) for c in calls]
    assert any("venv --python 3.14" in c for c in flat)
    assert any("pip install" in c and "windows-mcp==0.8.8" in c for c in flat)
    assert any("uv==" in c for c in flat)
    assert exe.exists() and mcp.windows_ready(tmp_path)


# 0.8.8 `windows-mcp serve --help` çıktısından (2026-11-05, gerçek kurulum) kısaltılmış seçenekler
HELP_088 = ("Usage: windows-mcp serve [OPTIONS]\n  --transport [stdio|sse|streamable-http]\n  --host TEXT\n  --port INTEGER\n"
            "  --debug\n  --config FILE\n  --auth-key TEXT\n  --tools TEXT\n  --exclude-tools TEXT\n  --cors-origins TEXT\n")


def test_secenekler_kurulu_surumle_uyumlu():
    assert mcp.check_windows_flags(Path("x"), HELP_088) == []
    assert mcp.check_windows_flags(Path("x"), HELP_088.replace("--exclude-tools", "--baska")) == ["--exclude-tools"]


def test_uyumsuz_secenekte_kurulum_hazir_sayilmaz(tmp_path, monkeypatch):
    """Belge ile kurulu sürüm ayrışırsa (README'deki --control-policy) kurulum başarılı görünmesin."""
    def fake_run(argv, timeout, flags):
        boot = tmp_path / "mcp" / "windows" / "boot" / "Scripts"
        boot.mkdir(parents=True, exist_ok=True)
        (boot / ("uv.exe" if "pip" in argv else "python.exe")).write_text("", encoding="utf-8")

    class R:
        returncode = 0
        stdout = stderr = ""

    def fake_sub(argv, **kw):
        venv = tmp_path / "mcp" / "windows" / "venv" / "Scripts"
        venv.mkdir(parents=True, exist_ok=True)
        for n in ("python.exe", "windows-mcp.exe"):
            (venv / n).write_text("", encoding="utf-8")
        return R()

    monkeypatch.setattr(mcp, "_run", fake_run)
    monkeypatch.setattr(mcp.subprocess, "run", fake_sub)
    monkeypatch.setattr(mcp.os, "name", "nt")
    monkeypatch.setattr(mcp, "check_windows_flags", lambda exe, help_text=None: ["--control-policy"])
    with pytest.raises(mcp.McpError, match="--control-policy"):
        mcp.install_windows_mcp(tmp_path)
    assert not mcp.windows_ready(tmp_path)


def test_kurulum_windows_disinda_reddedilir(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp.os, "name", "posix")
    with pytest.raises(mcp.McpError):
        mcp.install_windows_mcp(tmp_path)


# ---- tur akışı: not ve istem ------------------------------------------------------------------------

def _fake_desktop_cfg():
    return mcp.McpServerConfig(name="masaustu", command=sys.executable, args=[FAKE], when="masaustu",
                               read_only_tools=["topla"])


def test_masaustu_sunulunca_kullaniciya_guvenlik_notu_ve_modele_talimat(tmp_path):
    mgr = mcp.McpManager(tmp_path)
    try:
        ts = mgr.toolset([_fake_desktop_cfg()], tmp_path, "Not Defteri'ni aç")
        assert mcp.DESKTOP_NOTE in ts.notes
        assert "Ctrl+Alt+Shift+Backspace" in mcp.DESKTOP_NOTE
        section = mcp.prompt_section(ts.specs(), ts.hints)
        assert "mcp__masaustu__" in section and "Parola" in section and "Snapshot" in section
        none = mgr.toolset([_fake_desktop_cfg()], tmp_path, "README'yi güncelle")
        assert mcp.DESKTOP_NOTE not in none.notes and not none.specs()
    finally:
        mgr.close_all()


# ---- masaüstü görsel göz -----------------------------------------------------------------------------

class _Mgr:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def call(self, cfg, root, tool, args):
        self.calls.append(tool)
        return self.result


class _Call:
    def __init__(self, name="visual_check", **args):
        self.name, self.arguments = name, args


def test_gorsel_goz_ekran_goruntusunu_kaydeder_ve_gorsel_modele_sorar(tmp_path):
    asked = []
    mgr = _Mgr({"content": [{"type": "image", "data": base64.b64encode(PNG).decode(), "mimeType": "image/png"}]})
    tools = qa.DesktopQaTools(mgr, mcp.windows_config(), tmp_path, lambda q, p: asked.append((q, p)) or "evet",
                              tmp_path / "shots")
    assert [s.name for s in tools.specs()] == ["visual_check"]
    res = tools.run(_Call(question="Kaydet düğmesi görünüyor mu?"))
    assert res.ok and "evet" in res.content and mgr.calls == ["Screenshot"]
    assert Path(asked[0][1]).read_bytes() == PNG


def test_gorsel_goz_goruntu_yoksa_hata_gorsel_model_yoksa_sunulmaz(tmp_path):
    mgr = _Mgr({"content": [{"type": "text", "text": "ekran yok"}]})
    tools = qa.DesktopQaTools(mgr, mcp.windows_config(), tmp_path, lambda q, p: "x", tmp_path / "s")
    tools._sleep = lambda s: None
    res = tools.run(_Call(question="?"))
    assert not res.ok and "görsel döndürmedi" in res.content
    assert "ekran yok" in res.content and mgr.calls == ["Screenshot", "Screenshot"]   # neden söylenir, bir kez yeniden


def test_gorsel_goz_ilk_denemede_gorsel_gelmezse_ikincide_alir(tmp_path):
    img = {"content": [{"type": "image", "data": base64.b64encode(PNG).decode(), "mimeType": "image/png"}]}

    class Seq(_Mgr):
        def call(self, cfg, root, tool, args):
            self.calls.append(tool)
            return {"content": [{"type": "text", "text": "meşgul"}]} if len(self.calls) == 1 else img

    mgr = Seq(None)
    tools = qa.DesktopQaTools(mgr, mcp.windows_config(), tmp_path, lambda q, p: "evet", tmp_path / "s")
    tools._sleep = lambda s: None
    res = tools.run(_Call(question="?"))
    assert res.ok and mgr.calls == ["Screenshot", "Screenshot"]
    assert qa.DesktopQaTools(mgr, None, tmp_path, None, tmp_path).specs() == []
    assert not qa.save_mcp_image({"content": [{"type": "image", "data": ""}]}, tmp_path / "x.png")
    assert not qa.save_mcp_image({"content": [{"type": "image", "data": "===="}]}, tmp_path / "y.png")  # boş çözülür
    assert not (tmp_path / "y.png").exists()


# ---- masaüstü QA istemleri ve durum -------------------------------------------------------------------

def _state(target):
    return qa.QaState(goal="hesap", target=target, run_hint="python app.py",
                      scenarios=[qa.Scenario(1, "Toplama", ["2 ve 3 yaz", "Hesapla'ya bas"], "5 görünür")])


def test_masaustu_istemleri_masaustu_aracini_acar_tarayiciyi_acmaz():
    st = _state("masaustu")
    plan = qa.planning_prompt("hesap aracı", target="masaustu")
    sc = qa.scenario_prompt(st, st.scenarios[0], [])
    for text in (plan, sc):
        assert mcp.needed(mcp.windows_config(), mcp.ProjectProfile(), text)[0]
        assert not mcp.needed(mcp.playwright_config(), mcp.ProjectProfile(), text)[0]
    assert "<qa_plan>" in plan and "<qa_sonuc>" in sc and "mcp__masaustu__Snapshot" in sc


def test_web_istemleri_masaustu_aracini_acmaz():
    st = _state("web")
    for text in (qa.planning_prompt("site", target="web"), qa.scenario_prompt(st, st.scenarios[0], [])):
        assert not mcp.needed(mcp.windows_config(), mcp.ProjectProfile(), text)[0]
        assert "mcp__masaustu" not in text


def test_hedef_kaydedilir_eski_kayit_web_sayilir():
    st = _state("masaustu")
    assert qa.QaState.from_json(st.to_json()).target == "masaustu"
    import json

    old = json.loads(_state("web").to_json())
    old.pop("target")
    assert qa.QaState.from_json(json.dumps(old)).target == "web"
    web = _state("web")
    for s in (st, web):
        s.scenarios[0].status = "kaldi"
    assert "masaüstünde" in qa.fix_goal(st) and "tarayıcıda" in qa.fix_goal(web)


# ---- arayüz --------------------------------------------------------------------------------------------

@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    # Ayarlar'ı kaydeden test "Kaydedildi" kutusu açar; kapatılmazsa görünmez pencerede sonsuza kadar bekler
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
    yield app, w
    w.close()


def test_masaustu_qa_on_kosullari(win, tmp_path):
    app, w = win
    qc = w.session.qa
    proj = tmp_path / "uyg"
    proj.mkdir()
    w.session.welcome._choose(str(proj))
    assert "Masaüstü kontrolünü kur" in qc.precheck("masaustu")
    assert "Playwright" in qc.precheck("web")
    w.ctx.settings.mcp_enabled = True
    w.ctx.settings.mcp_servers = [mcp.windows_config().to_dict()]
    assert qc.precheck("masaustu") == ""
    assert "Playwright" in qc.precheck("web")                      # web QA için masaüstü yetmez


def test_engelli_tuslar_ayardan_gelir_kaydedilir_ve_acilista_okunur(win):
    app, w = win
    s = w.ctx.settings
    assert s.desktop_blocked_keys == ["End"]                            # varsayılan (kullanıcının bilgisayarı)
    page = w.pages["settings"]
    page.desktop_blocked.setText("End, PrintScreen")
    page.save_all()
    from evren_studio.config import ConfigStore

    assert ConfigStore(w.ctx.store.data_dir).load().desktop_blocked_keys == ["End", "PrintScreen"]   # R-03
    s.mcp_enabled = True
    s.mcp_servers = [mcp.windows_config().to_dict()]
    cfg = next(c for c in w.ctx.mcp_configs() if c.name == "masaustu")
    assert cfg.blocked_keys == ["End", "PrintScreen"]


def test_ayarlarda_masaustu_satiri_ve_komut_listesi(win):
    app, w = win
    card = w.pages["settings"].mcp_card
    row = card.rows["masaustu"]
    assert row["install"].text() == "Masaüstü kontrolünü kur"
    assert not row["toggle"].isEnabled()                            # kurulmadan etkinleştirilemez
    from evren_studio.ui.composer import SLASH_COMMANDS

    assert "/qa-masaustu" in SLASH_COMMANDS


def test_ekranda_okunmayacak_programlar_varsayilan_kayit_ve_sunucuya_gecer(win):
    """Kullanıcı 2026-11-06: ekran kullanımı başlayınca birkaç dakika sonra VS Code yanıt vermiyor, tıklayınca
    kapanıyor (olay kaydı: 5 askı, hepsi masaüstü testlerinde). VS Code taramada hiç okunmaz."""
    app, w = win
    s = w.ctx.settings
    assert s.desktop_skip_processes == ["Code.exe", "Cursor.exe", "Windsurf.exe"]
    s.mcp_enabled = True
    s.mcp_servers = [mcp.windows_config().to_dict()]
    cfg = next(c for c in w.ctx.mcp_configs() if c.name == "masaustu")
    assert cfg.env[mcp.EXCLUDE_ENV] == "Code.exe,Cursor.exe,Windsurf.exe"
    assert mcp.EXCLUDE_ENV not in mcp.windows_config().env                       # hazır ayarın kendisi kirlenmez
    page = w.pages["settings"]
    page.desktop_skip.setText("Code.exe, Teams.exe")
    page.save_all()
    from evren_studio.config import ConfigStore

    assert ConfigStore(w.ctx.store.data_dir).load().desktop_skip_processes == ["Code.exe", "Teams.exe"]   # R-03
    s.mcp_enabled, s.mcp_servers = True, [mcp.windows_config().to_dict()]     # save_all MCP listesini de yazar
    cfg = next(c for c in w.ctx.mcp_configs() if c.name == "masaustu")
    assert cfg.env[mcp.EXCLUDE_ENV] == "Code.exe,Teams.exe"
    page.desktop_skip.setText("")                                               # boş: hiçbir program atlanmaz (R-22)
    page.save_all()
    s.mcp_enabled, s.mcp_servers = True, [mcp.windows_config().to_dict()]
    cfg = next(c for c in w.ctx.mcp_configs() if c.name == "masaustu")
    assert mcp.EXCLUDE_ENV not in cfg.env
    other = [c for c in w.ctx.mcp_configs() if c.name != "masaustu"]
    assert all(mcp.EXCLUDE_ENV not in c.env for c in other)


def test_masaustu_qa_istemi_adimlari_birlestirir_dogrulugu_korur():
    """Gerçek QA 2026-11-06: senaryo başına 16-21 adım — her senaryo dosyaları yeniden okuyor, her yazmadan sonra ayrı
    Snapshot alıyor, yazıyı görsel modele soruyordu. Hız kuralları; doğruluk kuralları (okuduğunu yaz) korunur."""
    st = qa.QaState(goal="Topla", run_hint="python hesap.py", target="masaustu",
                    scenarios=[qa.Scenario(idx=1, title="2+3", steps=["2 yaz", "3 yaz", "Topla"], expected="5")])
    p = qa.desktop_scenario_prompt(st, st.scenarios[0], [])
    assert "TEK yanıtta" in p and "WindowText" in p and "yeniden OKUMA" in p
    assert "YALNIZ\n  görünüm sorunu" in p or "YALNIZ görünüm sorunu" in p.replace("\n  ", " ")
    assert "her önemli\n  adımdan sonra yeniden Snapshot" not in p
    assert "Varsayım yapma" in p and "<qa_sonuc>" in p                          # doğruluk ve sonuç bloğu korunur
    assert "Denemeler ARASINDA Snapshot alma" in p
    plan = qa.desktop_planning_prompt("Topla işlevini test et")
    assert "TEK konuyu" in plan and f"en fazla {qa.MAX_TRIES} deneme" in plan
    assert "TEK konuyu" in qa.planning_prompt("giriş formunu test et")              # web planında da
    assert "TEK yanıtta" in mcp.DESKTOP_PROMPT and "WindowText" in mcp.DESKTOP_PROMPT
    assert "Her önemli adımdan sonra yeniden" not in mcp.DESKTOP_PROMPT
