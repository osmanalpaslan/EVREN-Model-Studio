"""Windows-MCP başlatıcısı (agent/wmcp_baslatici.py) — askıdaki pencere koruması.

2026-11-05 gerçek deneme: "Yanıt Vermiyor" VS Code ve dwm.exe hayalet penceresi dururken Windows-MCP 0.8.8'in Snapshot'ı
90 sn'de yanıt vermedi; `WINDOWS_MCP_EXCLUDE_PROCESSES` + yeniden başlatma çözmedi (0.8.8 o listeyi pencere listesinde
uygulamıyor). Başlatıcıyla aynı masaüstünde Snapshot 15-19 sn'de doldu. Gerçek Windows-MCP YOK: sahte Desktop/uia."""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import pytest

from evren_studio.agent import mcp, wmcp_baslatici as wb


class FakeUia:
    def __init__(self, fg):
        self.fg = fg

    def GetForegroundWindow(self):
        return self.fg


def fake_desktop(handles):
    class Desktop:
        calls: list = []

        def get_controls_handles(self, optimized=False):
            return set(handles)

        def get_foreground_window(self):
            Desktop.calls.append("uia")             # gerçekte burada UI Automation'a girilir
            return "ön plan"

    return Desktop


def test_askidaki_ve_atlanan_pencereler_listeden_cikar_ön_plana_girilmez():
    hung, names = {2}, {3: "Code.exe", 4: "notepad.exe"}
    skip = wb.make_skip(lambda h: h in hung, lambda: {"code.exe"}, names.get)
    D = fake_desktop({1, 2, 3, 4})
    uia = FakeUia(fg=2)
    assert wb.patch(D, uia, skip) is True
    d = D()
    assert d.get_controls_handles() == {1, 4}
    assert d.get_foreground_window() is None and D.calls == []      # askıdaki ön pencereye UIA çağrısı yok
    uia.fg = 1                                                       # tetiklenmeyen durum (R-22): sağlam pencere
    assert d.get_foreground_window() == "ön plan" and D.calls == ["uia"]
    uia.fg = 0                                                       # ön planda pencere yok: paketin kendi davranışı
    assert d.get_foreground_window() == "ön plan"


def test_askida_pencere_yokken_liste_aynen_kalir():
    skip = wb.make_skip(lambda h: False, lambda: set(), lambda h: "Code.exe")
    D = fake_desktop({1, 2, 3})
    wb.patch(D, FakeUia(fg=1), skip)
    assert D().get_controls_handles() == {1, 2, 3}


def test_denetim_hatasi_pencereyi_atlatmaz():
    def boom(_h):
        raise OSError("erişim yok")

    skip = wb.make_skip(boom, lambda: {"code.exe"}, boom)
    assert skip(5) is False


def test_beklenmeyen_surumde_dokunmadan_calisir():
    class Eski:
        def get_controls_handles(self):
            return {1}

    assert wb.patch(Eski, FakeUia(fg=1), lambda h: True) is False
    assert Eski().get_controls_handles() == {1}
    assert wb.patch(None, None, lambda h: True) is False


def test_baslatici_bagimsiz_ve_sunucu_onunla_acilir(tmp_path):
    """Başlatıcı Windows-MCP'nin Python 3.14 ortamında çalışır: evren_studio içe aktaramaz; `-P` olmadan agent/mcp.py
    paketin `mcp` kütüphanesini gölgelerdi."""
    tree = ast.parse(mcp.WINDOWS_LAUNCHER.read_text(encoding="utf-8"))
    mods = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    mods |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m.startswith(("evren_studio", ".")) for m in mods), mods
    cfg = mcp.windows_config()
    argv = cfg.argv(None, tmp_path)
    assert Path(argv[0]) == mcp.windows_python(tmp_path)
    assert argv[1] == "-P" and Path(argv[2]) == mcp.WINDOWS_LAUNCHER and argv[3] == "serve"
    assert mcp.WINDOWS_LAUNCHER.exists()


def test_eski_surumun_kaydettigi_masaustu_ayari_yeni_baslaticiya_tasinir():
    """R-03/R-14: önceki sürüm komutu `{windows_mcp}` (exe doğrudan) kaydetti; yeni tanım okunmalı, açık/kapalı korunmalı."""
    old = {**mcp.windows_config().to_dict(), "command": "{windows_mcp}",
           "args": ["serve", "--exclude-tools", "PowerShell"], "enabled": False}
    cfg = mcp.configs_from_settings([old])[0]
    assert cfg.command == "{windows_mcp_python}" and "{windows_mcp_baslatici}" in cfg.args
    assert cfg.enabled is False
    own = {**old, "command": "C:/benim/windows-mcp.exe", "enabled": True}       # elle kurulan dokunulmaz
    assert mcp.configs_from_settings([own])[0].command == "C:/benim/windows-mcp.exe"


def test_hazir_sayilmasi_icin_python_da_gerekir(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp.os, "name", "nt")
    scripts = tmp_path / "mcp" / "windows" / "venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "windows-mcp.exe").write_text("", encoding="utf-8")
    (tmp_path / "mcp" / "windows" / "hazir.txt").write_text("x", encoding="utf-8")
    assert not mcp.windows_ready(tmp_path)
    (scripts / "python.exe").write_text("", encoding="utf-8")
    assert mcp.windows_ready(tmp_path)


@pytest.mark.skipif(os.name != "nt", reason="Windows")
def test_gercek_win32_askidaki_pencere_denetimi_saglam_pencerede_false():
    """Başlatıcının kullandığı IsHungAppWindow bu sürecin konsol/masaüstü penceresinde askı demez (tetiklenmeyen)."""
    import ctypes

    desk = ctypes.windll.user32.GetDesktopWindow()
    skip = wb.make_skip(lambda h: bool(ctypes.windll.user32.IsHungAppWindow(h)), lambda: set(), lambda h: None)
    assert skip(desk) is False
    assert sys.version_info >= (3, 11)              # `-P` seçeneği 3.11+ (Windows-MCP ortamı 3.14)


# ---- WindowText (8. gerçek deneme: ajan 2+3'ü yaptı ama "Sonuç: 5" etiketini Snapshot'ta göremedi) ----------------

class Rect:
    def __init__(self, l, t, r, b):
        self.left, self.top, self.right, self.bottom = l, t, r, b


class Node:
    def __init__(self, kind, name="", kids=(), rect=(0, 0, 10, 10)):
        self.ControlTypeName, self.Name, self.kids, self.BoundingRectangle = kind, name, list(kids), Rect(*rect)

    def GetChildren(self):
        return self.kids


class Win:
    def __init__(self, name, handle):
        self.name, self.handle = name, handle


def test_pencere_yazilari_yalniz_duz_yazi_konumlu_ve_tekrarsiz():
    root = Node("WindowControl", "EVREN Hesap", [
        Node("EditControl", "Birinci sayı"),
        Node("PaneControl", "", [Node("TextControl", "Sonuç: 5", rect=(100, 200, 140, 220)),
                                 Node("TextControl", "Sonuç: 5", rect=(100, 200, 140, 220))]),
        Node("ButtonControl", "Topla"), Node("TextControl", ""), Node("StatusBarControl", "Hazır")])
    assert wb.collect_texts(root) == ["(120,210) Sonuç: 5", "(5,5) Hazır"]


def test_pencere_yazilari_sinirli_dev_pencerede_takilmaz():
    many = Node("WindowControl", "", [Node("TextControl", f"satır {i}") for i in range(50)])
    assert len(wb.collect_texts(many, limit=10)) == 10
    deep = Node("TextControl", "dip")
    for _ in range(40):
        deep = Node("PaneControl", "", [deep])
    assert wb.collect_texts(deep, max_depth=30) == []                  # derinlik sınırı
    assert len(wb.collect_texts(many, max_visit=5)) == 4                 # ziyaret sınırı (kök + 4)


def test_pencere_secimi_tam_eslesme_once_sonra_icerik():
    ws = [Win("EVREN Hesap Deneme - eski", 1), Win("EVREN Hesap Deneme", 2), Win("Not Defteri", 3)]
    assert wb.pick_window(ws, "evren hesap deneme").handle == 2
    assert wb.pick_window(ws, "not def").handle == 3
    assert wb.pick_window(ws, "") is None and wb.pick_window(ws, "yok") is None


def test_pencere_yoksa_acik_pencereleri_soyler():
    class D:
        def get_windows(self):
            return [Win("Not Defteri", 3)], {3}

    class U:
        def ControlFromHandle(self, h):
            return Node("WindowControl", "x", [Node("TextControl", "merhaba")])

    assert "not found" in wb.window_text(D(), U(), "Hesap") and "Not Defteri" in wb.window_text(D(), U(), "Hesap")
    assert wb.window_text(D(), U(), "Not").endswith("(5,5) merhaba")


def test_arac_sunucu_kaydina_eklenir_ve_masaustu_penceresinden_okur():
    class FakeMcp:
        def __init__(self):
            self.tools = {}

        def tool(self, name, description, annotations=None):
            def deco(fn):
                self.tools[name] = (fn, annotations)
                return fn
            return deco

    class Pkg:
        @staticmethod
        def register_all(mcp, *, get_desktop, get_analytics):
            mcp.tools["Snapshot"] = (None, None)

    class D:
        def get_windows(self):
            return [Win("EVREN Hesap Deneme", 7)], {7}

    class U:
        def ControlFromHandle(self, h):
            assert h == 7
            return Node("WindowControl", "", [Node("TextControl", "Sonuç: 5")])

    assert wb.add_text_tool(Pkg, U()) is True
    m = FakeMcp()
    Pkg.register_all(m, get_desktop=D, get_analytics=lambda: None)
    assert set(m.tools) == {"Snapshot", wb.TEXT_TOOL}
    fn, ann = m.tools[wb.TEXT_TOOL]
    assert "Sonuç: 5" in fn("EVREN Hesap")
    assert ann is None or ann.readOnlyHint is True
    assert wb.add_text_tool(object(), U()) is False                    # beklenmeyen sürüm: dokunmaz


def test_uygulama_araci_sorulmadan_sunar_ve_ajana_anlatir():
    cfg = mcp.windows_config()
    assert wb.TEXT_TOOL in cfg.allowed_tools and wb.TEXT_TOOL in cfg.read_only_tools
    assert wb.TEXT_TOOL not in mcp.WINDOWS_EXCLUDED
    assert "WindowText" in mcp.DESKTOP_PROMPT and "etiket" in mcp.DESKTOP_PROMPT


def test_sunucunun_kendi_pencereleri_taranmaz_digerleri_taranir():
    """2026-11-06: sunucunun AI ışığı katmanlarını kendi içinden okumak Snapshot'ı 15 sn yapıyordu (atlayınca 0,5 sn)."""
    pids = {1: 500, 2: 777, 3: 777, 4: 900}
    check = wb.own_or_hung(pids.get, lambda h: h == 4, 777)
    assert [check(h) for h in (1, 2, 3, 4)] == [False, True, True, True]

    def boom(_h):
        raise OSError("erişim yok")

    assert wb.own_or_hung(boom, lambda h: False, 777)(1) is False        # pid okunamazsa: askı denetimine kalır
