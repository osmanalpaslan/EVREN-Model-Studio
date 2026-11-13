"""Madde 22 D (2026-11-13): masaüstü hızlı yolu — PencereOgeleri (tek pencere), UIEylem (tek çağrıda çok eylem, önce UIA
kalıpları, desteklenmezse fare/klavye, sonunda pencerenin son hâli) ve kilitli oturumda masaüstü işinin duraklaması.

Ölçüm (önce): "2+3" görevi 43 adım / 714 sn; her Snapshot tüm masaüstünü tarıyordu (~16 sn).
"""
from __future__ import annotations

import json

import pytest
from test_masaustu_otomatik import Mgr, ok_text, toolset

from evren_studio.agent import mcp
from evren_studio.agent import wmcp_baslatici as wb


class Rect:
    left, top, right, bottom = 0, 0, 10, 10


class Value:
    def __init__(self, node):
        self.node, self.IsReadOnly = node, False

    @property
    def Value(self):
        return self.node.value

    def SetValue(self, v):
        self.node.value = v
        self.node.app.recalc()


class Invoke:
    def __init__(self, node):
        self.node = node

    def Invoke(self):
        self.node.app.pressed.append(self.node.Name)
        self.node.app.recalc(press=self.node.Name)


class N:
    """Sahte UIA öğesi: patterns = {"value", "invoke"}; app = hesap makinesi durumu."""

    def __init__(self, app, kind, name="", kids=(), patterns=(), aid="", enabled=True, value=""):
        self.app, self.ControlTypeName, self.Name, self.kids = app, kind, name, list(kids)
        self.patterns, self.AutomationId, self.IsEnabled, self.value = set(patterns), aid, enabled, value
        self.BoundingRectangle = Rect()
        self.clicks = 0
        self.keys: list[str] = []

    def GetChildren(self):
        return self.kids

    def GetValuePattern(self):
        return Value(self) if "value" in self.patterns else None

    def GetInvokePattern(self):
        return Invoke(self) if "invoke" in self.patterns else None

    def GetTogglePattern(self):
        return None

    def GetSelectionItemPattern(self):
        return None

    def Click(self, simulateMove=False, waitTime=0.0):
        self.clicks += 1
        self.app.pressed.append(self.Name + " (fare)")
        self.app.recalc(press=self.Name)

    def SetFocus(self):
        pass

    def SendKeys(self, text, waitTime=0.0):
        self.keys.append(text)


class Hesap:
    def __init__(self, invoke=True):
        self.pressed: list[str] = []
        self.a = N(self, "EditControl", "Sayı 1", patterns={"value"}, aid="sayi1")
        self.b = N(self, "EditControl", "Sayı 2", patterns={"value"}, aid="sayi2")
        self.btn = N(self, "ButtonControl", "Topla", patterns={"invoke"} if invoke else set())
        self.off = N(self, "ButtonControl", "Sil", patterns={"invoke"}, enabled=False)
        self.res = N(self, "TextControl", "Sonuç: -")
        self.root = N(self, "WindowControl", "EVREN Hesap", kids=[self.a, self.b, self.btn, self.off, self.res])

    def recalc(self, press=None):
        if press == "Topla":
            try:
                self.res.Name = f"Sonuç: {int(self.a.value) + int(self.b.value)}"
            except ValueError:
                self.res.Name = "Sonuç: hata"


class Win:
    def __init__(self, name, handle):
        self.name, self.handle = name, handle


def _desk(app):
    class D:
        def get_windows(self):
            return [Win("EVREN Hesap Deneme", 7), Win("Not Defteri", 8)], {7, 8}

    class U:
        def ControlFromHandle(self, h):
            assert h == 7
            return app.root
    return D(), U()


def test_tek_cagrida_yaz_yaz_tikla_ve_son_hal_doner():
    app = Hesap()
    d, u = _desk(app)
    out = wb.ui_actions(d, u, "EVREN Hesap", [{"yaz": "Sayı 1", "metin": "2"}, {"yaz": "sayi2", "metin": "3"},
                                             {"tikla": "Topla"}], sleep=lambda s: None)
    assert "1. yaz #1 'Sayı 1' ← '2' ✓ (UIA)" in out and "2. yaz #2 'Sayı 2' ← '3' ✓ (UIA)" in out
    assert "3. tıkla #3 'Topla' ✓ (UIA)" in out and "Sonuç: 5" in out and "= '2'" in out
    assert app.pressed == ["Topla"] and app.btn.clicks == 0                    # fare kullanılmadı


def test_kalip_yoksa_fareye_duser_ve_ilk_hatada_durur():
    app = Hesap(invoke=False)
    d, u = _desk(app)
    out = wb.ui_actions(d, u, "EVREN Hesap", [{"yaz": "#1", "metin": "4"}, {"yaz": "#2", "metin": "1"},
                                             {"tikla": "Topla"}, {"tikla": "Yok"}, {"tikla": "Topla"}],
                        sleep=lambda s: None)
    assert "3. tıkla #3 'Topla' ✓ (fare)" in out and "4. DURDU: hedef 'Yok' bulunamadı" in out
    assert "5." not in out and app.pressed == ["Topla (fare)"] and "Sonuç: 5" in out


def test_devre_disi_hedef_ve_engelli_tus_durdurur():
    app = Hesap()
    d, u = _desk(app)
    assert "DURDU: #4 'Sil' devre dışı" in wb.ui_actions(d, u, "EVREN Hesap", [{"tikla": "Sil"}], sleep=lambda s: None)
    out = wb.ui_actions(d, u, "EVREN Hesap", [{"tus": "ctrl+a"}, {"tus": "end"}], sleep=lambda s: None)
    assert "1. tuş ctrl+a ✓" in out and "2. DURDU: tuş 'end' desteklenmiyor ya da engelli" in out
    assert app.root.keys == ["{Ctrl}a"]


def test_bekle_sinirli_ve_anlasilmayan_eylem():
    app = Hesap()
    d, u = _desk(app)
    waits = []
    out = wb.ui_actions(d, u, "EVREN Hesap", [{"bekle": 60}, {"zıpla": "x"}], sleep=waits.append)
    assert waits[0] == 5.0 and "2. DURDU: eylem anlaşılmadı" in out


def test_pencere_yoksa_acik_pencereleri_soyler_ve_listeleme_salt_okunur():
    app = Hesap()
    d, u = _desk(app)
    assert "not found" in wb.ui_actions(d, u, "Hesap Makinesi X", [{"tikla": "Topla"}]) and app.pressed == []
    listing = wb.window_controls(d, u, "EVREN Hesap")
    assert "#1 Edit 'Sayı 1' [id sayi1]" in listing and "#4 Button 'Sil' (disabled)" in listing
    assert "texts: Sonuç: -" in listing and app.pressed == []


def test_hedef_bulma_sirasi():
    app = Hesap()
    ctrls, _t = wb.collect_controls(app.root)
    assert wb.find_target(ctrls, "#3")[1]["ad"] == "Topla"
    assert wb.find_target(ctrls, "SAYI 2")[1]["kimlik"] == "sayi2"            # Türkçe büyük harf (I ↔ ı)
    assert wb.find_target(ctrls, "Sayi 2")[1]["kimlik"] == "sayi2"            # ASCII yazım
    assert wb.find_target(ctrls, "sayi1")[1]["ad"] == "Sayı 1"               # kimlik
    assert wb.find_target(ctrls, "Topl")[1]["ad"] == "Topla"                 # içerik
    assert wb.find_target(ctrls, "#99") is None and wb.find_target(ctrls, "") is None
    ikiz = [(None, {"no": 1, "ad": "Kaydet", "kimlik": "", "etkin": False}),
            (None, {"no": 2, "ad": "Kaydet", "kimlik": "", "etkin": True})]
    assert wb.find_target(ikiz, "Kaydet")[1]["no"] == 2                      # aynı ad: etkin olan seçilir


@pytest.mark.parametrize("spec, out", [("enter", "{Enter}"), ("ctrl+s", "{Ctrl}s"), ("alt+f4", "{Alt}{F4}"),
                                       ("shift+tab", "{Shift}{Tab}"), ("End", None), ("ctrl+end", None),
                                       ("hyper+x", None), ("ctrl+ğ", None), ("", None)])
def test_tus_cevirisi(spec, out):
    assert wb.uia_keys(spec) == out


def test_araclar_kayda_eklenir_ve_ajana_anlatilir():
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
        def register_all(mcp_, *, get_desktop, get_analytics):
            mcp_.tools["Snapshot"] = (None, None)

    app = Hesap()
    d, u = _desk(app)
    assert wb.add_ui_tools(Pkg, u) is True
    m = FakeMcp()
    Pkg.register_all(m, get_desktop=lambda: d, get_analytics=lambda: None)
    assert {wb.CONTROLS_TOOL, wb.ACTION_TOOL} <= set(m.tools)
    assert "Sonuç: 5" in m.tools[wb.ACTION_TOOL][0]("EVREN Hesap", [{"yaz": "#1", "metin": "2"},
                                                                    {"yaz": "#2", "metin": "3"}, {"tikla": "Topla"}])
    assert wb.add_ui_tools(object(), u) is False
    cfg = mcp.windows_config()
    assert {wb.CONTROLS_TOOL, wb.ACTION_TOOL} <= set(cfg.allowed_tools)
    assert wb.CONTROLS_TOOL in cfg.read_only_tools and wb.ACTION_TOOL not in cfg.read_only_tools
    assert "UIEylem" in mcp.DESKTOP_PROMPT and "PencereOgeleri" in mcp.DESKTOP_PROMPT


# ---- D4 kilitli oturum --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("desk, logon, beklenen", [(False, True, True), (True, True, False), (False, False, False),
                                                  (None, True, False)])
def test_kilit_iki_belirtiyle(monkeypatch, desk, logon, beklenen):
    monkeypatch.setattr(mcp.os, "name", "nt")
    monkeypatch.setattr(mcp, "_input_desktop_is_default", lambda: desk)
    monkeypatch.setattr(mcp, "_process_running", lambda exe: logon and exe == "LogonUI.exe")
    assert mcp.session_locked() is beklenen


def test_kilit_denetimi_hata_verirse_engellemez(monkeypatch):
    monkeypatch.setattr(mcp.os, "name", "nt")

    def boom():
        raise OSError("erişim yok")
    monkeypatch.setattr(mcp, "_input_desktop_is_default", boom)
    assert mcp.session_locked() is False


def test_kilitliyken_masaustu_cagrisi_yapilmaz_tur_duraklar(monkeypatch):
    mgr = Mgr({"Click": [ok_text("tıklandı")]})
    ts, notes, _c = toolset(mgr)
    monkeypatch.setattr(mcp, "session_locked", lambda: True)
    text, err = ts.call("mcp__masaustu__Click", {"loc": [1, 2]})
    assert err and text == mcp.LOCKED_TEXT and mgr.calls == [] and ts.user_paused
    assert any("kilitli" in n for n in notes)
    monkeypatch.setattr(mcp, "session_locked", lambda: False)
    ts.user_paused = False
    text, err = ts.call("mcp__masaustu__Click", {"loc": [1, 2]})
    assert not err and "tıklandı" in text and mgr.calls == [("Click", {"loc": [1, 2]})]
