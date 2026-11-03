"""web_search aracı (agent/websearch.py): sağlayıcı zinciri, kota bitince yedeğe geçiş, hiçbiri yokken işin
durmaması, izin modları ve tur başı hatırlatmasının tetiklenen/tetiklenmeyen durumları (R-22, R-31)."""
from __future__ import annotations

import json

import httpx
import pytest

from evren_studio import secrets
from evren_studio.agent import websearch
from evren_studio.agent.runner import AgentEvents, AgentRunner
from evren_studio.agent.tools import SPEC_BY_NAME, Workspace
from evren_studio.api.client import ChatResult
from evren_studio.db import Database

TAVILY_OK = {"answer": "PySide6 6.12 en yeni sürüm.",
             "results": [{"title": "PySide6 · PyPI", "url": "https://pypi.org/project/PySide6/",
                          "published_date": "2026-10-20", "content": "PySide6 6.12.0 yayımlandı."}]}
DDG_HTML = """
<div class="result results_links results_links_deep result--ad"><h2 class="result__title">
<a rel="nofollow" class="result__a" href="https://duckduckgo.com/y.js?ad=1">Reklam</a></h2></div>
<div class="result results_links results_links_deep web-result "><h2 class="result__title">
<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fdoc.qt.io%2Fpyside6&amp;rut=x">Qt &amp; Python</a>
</h2><a class="result__snippet" href="x"><b>PySide6</b> belgeleri</a></div>
"""


@pytest.fixture(autouse=True)
def _temiz(monkeypatch):
    monkeypatch.setattr(websearch, "_key_blocked_until", 0.0)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)


def client(tavily_key_status=200, keyless_status=200, ddg_status=200, seen=None):
    def handler(req: httpx.Request):
        if seen is not None:
            seen.append((req.url.host, req.headers.get("authorization", ""), req.headers.get("x-tavily-access-mode")))
        if req.url.host == "api.tavily.com":
            keyed = req.headers.get("authorization", "").startswith("Bearer ")
            status = tavily_key_status if keyed else keyless_status
            return httpx.Response(status, json=TAVILY_OK if status == 200 else {"detail": "x"})
        if req.url.host == "html.duckduckgo.com":
            return httpx.Response(ddg_status, text=DDG_HTML if ddg_status == 200 else "")
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_anahtarla_tavily_ve_parametreler():
    seen: list = []
    bodies: list = []

    def handler(req):
        bodies.append(json.loads(req.content))
        seen.append(req.headers.get("authorization"))
        return httpx.Response(200, json=TAVILY_OK)
    c = httpx.Client(transport=httpx.MockTransport(handler))
    res = websearch.search("PySide6 sürüm", guncel=True, max_results=20, key="tvly-test-ANAHTAR", client=c)
    assert res.provider == "tavily" and res.answer and res.results[0]["url"].startswith("https://pypi")
    assert seen == ["Bearer tvly-test-ANAHTAR"]
    assert bodies[0]["search_depth"] == "advanced" and bodies[0]["time_range"] == "year"
    assert bodies[0]["max_results"] == websearch.MAX_RESULTS                     # üst sınır
    websearch.search("deprem", haber=True, key="tvly-test-ANAHTAR", client=c)
    assert bodies[1]["topic"] == "news" and bodies[1]["search_depth"] == "basic"


def test_kota_dolunca_anahtarsiza_gecer_ve_anahtari_bir_sure_denemez():
    seen: list = []
    c = client(tavily_key_status=432, seen=seen)
    res = websearch.search("x", key="tvly-test-ANAHTAR", client=c)
    assert res.provider == "tavily-anahtarsız" and "kota doldu" in res.notes[0]
    seen.clear()
    res = websearch.search("y", key="tvly-test-ANAHTAR", client=c)
    assert all(not a for _h, a, _m in seen)                                       # anahtar ikinci kez gönderilmedi
    assert "bitmiş görünüyor" in res.notes[0]


def test_tavily_yoksa_duckduckgo_reklamsiz_ve_yonlendirme_cozulmus():
    res = websearch.search("pyside", key=None, client=client(keyless_status=429))
    assert res.provider == "duckduckgo" and len(res.results) == 1
    assert res.results[0]["url"] == "https://doc.qt.io/pyside6" and res.results[0]["title"] == "Qt & Python"
    assert "PySide6 belgeleri" in res.results[0]["snippet"]


def test_hicbiri_yoksa_aramayapilamaz_ve_bos_sorgu():
    with pytest.raises(websearch.SearchUnavailable):
        websearch.search("x", key="tvly-a-bcdefgh", client=client(500, 429, 503))
    with pytest.raises(ValueError):
        websearch.search("  ", key=None, client=client())


def test_cikti_guvenilmez_uyarisi_ve_kaynak():
    res = websearch.search("x", key="tvly-test-ANAHTAR", client=client())
    out = websearch.format_result("x", res)
    assert out.startswith(websearch.UNTRUSTED_NOTE) and "https://pypi.org/project/PySide6/" in out
    assert "2026-10-20" in out and "kaynağın adresini belirt" in out


def test_anahtar_kasadan_okunur_ve_maskelenir():
    class Kasa:
        d: dict = {}

        def set_password(self, s, n, v): self.d[(s, n)] = v
        def get_password(self, s, n): return self.d.get((s, n))
    secrets._set_backend(Kasa())
    try:
        secrets.save_api_key("tvly-dev-GIZLIANAHTAR123", "tavily")
        assert websearch.load_key() == "tvly-dev-GIZLIANAHTAR123"
        assert "GIZLIANAHTAR" not in secrets.mask_secret("anahtar tvly-dev-GIZLIANAHTAR123 sızdı")
    finally:
        secrets._set_backend(None)


def test_kota_okuma():
    def handler(req):
        assert req.headers["authorization"] == "Bearer tvly-test-ANAHTAR"
        return httpx.Response(200, json={"account": {"current_plan": "Researcher", "plan_usage": 12,
                                                     "plan_limit": 1000}})
    c = httpx.Client(transport=httpx.MockTransport(handler))
    assert websearch.usage("tvly-test-ANAHTAR", client=c) == {"plan": "Researcher", "used": 12, "limit": 1000}
    assert websearch.usage(None) is None


@pytest.mark.parametrize("metin,beklenen", [
    ("PySide6'nın en son sürümünü kullan", True),
    ("bunu internette araştır", True),
    ("İNTERNETTEN bul", True),
    ("pazar araştırması yap", True),
    ("dolar fiyatı ne", True),
    ("webde ara", True),
    ("dosyayı güncelle", False),            # "güncel" kelimesi "güncelle" içinde tetiklememeli
    ("requests kur ve test et", False),
    ("web sitesi yap", False),
    ("hatanın nedenini araştır", False),     # kod içi inceleme
    ("sürüm notlarına yaz", False),
])
def test_web_ihtiyaci_sezgisi(metin, beklenen):
    assert websearch.needs_web(metin) is beklenen


# ---- koşucu ----------------------------------------------------------------------------------------

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


def run(db, proj, seq, text="görev", mode="auto", events=None):
    proj.mkdir(exist_ok=True)
    sid = db.create_session("m", str(proj))
    db.add_session_message(sid, "user", text)
    c = Script(seq)
    r = AgentRunner(c, "m", session_id=sid, store=db, events=events or Ev(), workspace=Workspace(proj), mode=mode,
                    stream=False)
    r.run(db.get_session_messages(sid))
    tools = [m for m in db.get_session_messages(sid) if m["role"] == "tool"]
    return c, tools


@pytest.fixture()
def sahte_arama(monkeypatch):
    calls: list = []

    def fake(query, guncel=False, haber=False, max_results=5, **kw):
        calls.append((query, guncel, haber, max_results))
        return websearch.SearchResult("tavily", "cevap", [{"title": "T", "url": "https://a.org", "date": "",
                                                           "snippet": "ozet"}])
    monkeypatch.setattr(websearch, "search", fake)
    return calls


def test_kosucuda_otomatik_modda_sormadan_arar(db, tmp_path, sahte_arama):
    ev = Ev()
    c, tools = run(db, tmp_path / "p", [call("web_search", query="flask sürüm", guncel="true")], events=ev)
    assert "web_search" in c.tool_names[0] and SPEC_BY_NAME["web_search"].kind == "exec"
    assert not ev.asked and sahte_arama == [("flask sürüm", True, False, 5)]
    assert "https://a.org" in tools[0]["content"] and websearch.UNTRUSTED_NOTE in tools[0]["content"]


def test_kosucuda_plan_modunda_sorulmadan_arar_manuel_sorar_ret(db, tmp_path, sahte_arama):
    # 2026-11-01: Plan modu araştırma içindir; arama dosyaya dokunmaz → sorulmadan çalışır, araç sunulur
    ev0 = Ev()
    c, tools = run(db, tmp_path / "p", [call("web_search", query="x")], mode="plan", events=ev0)
    assert "web_search" in c.tool_names[0] and "https://a.org" in tools[0]["content"] and not ev0.asked
    assert "write_file" not in c.tool_names[0] and "run_command" not in c.tool_names[0]   # plan yine salt okunur
    sahte_arama.clear()
    ev = Ev(allow=False)
    _c, tools = run(db, tmp_path / "p", [call("web_search", query="x")], mode="manuel", events=ev)
    assert ev.asked == ["İnternette arama yapılsın mı?"] and "izin vermedi" in tools[0]["content"]
    assert not sahte_arama


def test_arama_yapilamazsa_is_durmaz(db, tmp_path, monkeypatch):
    def yok(*a, **k):
        raise websearch.SearchUnavailable("Tavily: kota doldu; DuckDuckGo: sonuç yok")
    monkeypatch.setattr(websearch, "search", yok)
    c, tools = run(db, tmp_path / "p", [call("web_search", query="x")])
    assert "yapılamıyor" in tools[0]["content"] and "devam et" in tools[0]["content"]
    assert len(c.systems) == 2                                     # tur sürdü: model sonraki adımı attı


def test_tur_basi_hatirlatma_tetiklenir_ve_tetiklenmez(db, tmp_path):
    c, _t = run(db, tmp_path / "p", [], text="Flask'ın en son sürümünü internette araştır ve requirements'a yaz")
    assert "# Web araması (bu tur)" in c.systems[0]
    c, _t = run(db, tmp_path / "q", [], text="app.py'deki hatayı düzelt ve testleri güncelle")
    assert "# Web araması" not in c.systems[0]


# ---- Ayarlar: Tavily kartı -------------------------------------------------------------------------

def test_ayarlar_tavily_kaydet_kota_sil(tmp_path, monkeypatch, fake_keyring):
    import os
    import time as _t

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.settings_page import SettingsPage
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    page = w.pages["settings"]
    assert isinstance(page, SettingsPage)
    val = page.tavily_row.findChildren(QLabel)[1]
    assert val.text().startswith("yok")
    page.tavily_input.setText("tvly-dev-SAHTEANAHTAR123456")
    page.save_tavily_key()
    assert fake_keyring.store[("EVREN-Model-Studio", "tavily_api_key")] == "tvly-dev-SAHTEANAHTAR123456"
    assert "SAHTEANAHTAR" not in val.text() and val.text().startswith("tvly-dev")      # maskeli
    monkeypatch.setattr(websearch, "usage", lambda: {"plan": "Researcher", "used": 40, "limit": 1000})
    page.show_tavily_usage()
    end = _t.monotonic() + 5
    while "kalan" not in page.tavily_status.text() and _t.monotonic() < end:
        app.processEvents()
    assert "kalan 960" in page.tavily_status.text()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    page.delete_tavily_key()
    assert ("EVREN-Model-Studio", "tavily_api_key") not in fake_keyring.store and val.text().startswith("yok")
    w.close()
