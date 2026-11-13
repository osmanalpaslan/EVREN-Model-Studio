"""Döngü bekçisi — dış araçlar için kalıcı çözüm (2026-11-12 uygulama analizi).

Kanıt: kullanıcının gerçek web QA oturumlarında Playwright `browser_navigate` / `browser_console_messages` tekrarları
"arada dosya değişmedi; sonuç aynı olacak" diye YANLIŞ uyarı aldı — masaüstü için 2026-11-06'da yapılan düzeltme
(gözlem cf3c8b0737b8, 13 durdurma) yalnız `mcp__masaustu__`'ya özeldi. Genel kural: dış sunucudaki başarılı eylem o
sunucunun sayaçlarını sıfırlar (eylem eşiği 4/6), başarılı yerel komut tüm dış sayaçları sıfırlar, arada eylem yokken
aynı dış okuma yine 3. kezde döngüdür (R-22: tetiklenen + tetiklenmeyen). Gözlem artık döngünün TÜRÜNÜ ve aracın ADINI
yazar; model değişip tur sürdüyse "durdurdu" denmez. Proje görevinde yürütücünün dosyaları yazılmaz.
"""
from __future__ import annotations

import json

import pytest

from evren_studio import gozlem
from evren_studio.agent import mcp
from evren_studio.agent.runner import PROTECTED_NOTE, AgentEvents, AgentRunner, external_scope
from evren_studio.agent.tools import Workspace
from evren_studio.api.client import ChatResult
from evren_studio.db import Database


class Client:
    def __init__(self, responses):
        self.responses = list(responses)

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, on_reasoning=None, tools=None, **kw):
        return self.responses.pop(0) if self.responses else ChatResult(content="Bitti.", finish_reason="stop")


def call(name, cid, **args):
    return ChatResult(tool_calls=[{"id": cid, "name": name, "arguments": json.dumps(args)}], finish_reason="tool_calls")


class BrowserMcp:
    """Playwright benzeri: okuma araçları (konsol, anlık görüntü) + eylemler (sayfaya git, tıkla)."""
    READ = {"browser_console_messages", "browser_snapshot"}
    ALL = ("browser_console_messages", "browser_snapshot", "browser_navigate", "browser_click")

    def __init__(self, fail=()):
        self.calls, self.fail = [], set(fail)

    def _spec(self, n):
        return mcp.tool_spec("playwright", {"name": n}, n in self.READ)

    def specs(self, read_only_only=False):
        return [self._spec(n) for n in self.ALL]

    def get(self, name):
        n = name.removeprefix("mcp__playwright__")
        return mcp.McpTool("playwright", n, self._spec(n), n in self.READ)

    def call(self, name, arguments):
        self.calls.append(name)
        n = name.removeprefix("mcp__playwright__")
        return ("Hata" if n in self.fail else f"{n} tamam"), n in self.fail

    def servers(self):
        return ["playwright"]


@pytest.fixture()
def env(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    db = Database(tmp_path / "t.db")
    yield root, db
    db.close()


def _run(env, steps, mcp_obj=None, **kw):
    root, db = env
    sid = db.create_session("m", str(root), "auto")
    db.add_session_message(sid, "user", "sayfayı dene")
    client = Client([call(n, f"c{i}", **a) for i, (n, a) in enumerate(steps)] + [ChatResult(content="Bitti.")])
    recs = []
    r = AgentRunner(client, "m", session_id=sid, store=db, workspace=Workspace(root), mode="auto", stream=False,
                    events=AgentEvents(), mcp=mcp_obj or BrowserMcp(), stats_sink=recs.append, **kw)
    out = r.run(db.get_session_messages(sid))
    tools = [m for m in db.get_session_messages(sid) if m["role"] == "tool"]
    return out, tools, recs


NAV = ("mcp__playwright__browser_navigate", {"url": "http://localhost:5173"})
CONSOLE = ("mcp__playwright__browser_console_messages", {})
CLICK = ("mcp__playwright__browser_click", {"ref": "e12"})
CMD = ("run_command", {"command": "Write-Output yeniden-baslatildi"})


def test_dis_sunucu_kapsami():
    assert external_scope("mcp__playwright__browser_navigate") == "mcp__playwright__"
    assert external_scope("mcp__masaustu__Click") == "mcp__masaustu__"


def test_sayfayi_yeniden_acmak_ve_konsolu_okumak_dongu_degil(env):
    """Gerçek kullanımdaki desen: aç → konsolu oku → (değişiklik) → yeniden aç → konsolu oku … — uyarı YOK."""
    out, tools, _ = _run(env, [NAV, CONSOLE, NAV, CONSOLE, NAV, CONSOLE])
    assert out.stopped == "done"
    assert not any("[Döngü uyarısı]" in t["content"] for t in tools)          # navigate eşiği 4: 3. açılış serbest


def test_yerel_komut_dis_sayaclari_sifirlar(env):
    """Sunucu yeniden başlatılıp (yerel komut) aynı okuma yapılır: dünya değişmiş olabilir → sayılmaz."""
    cmds = [("run_command", {"command": f"Write-Output yeniden-baslatildi-{i}"}) for i in range(3)]
    out, tools, _ = _run(env, [CONSOLE, cmds[0], CONSOLE, cmds[1], CONSOLE, cmds[2], CONSOLE])
    assert out.stopped == "done" and not any("[Döngü uyarısı]" in t["content"] for t in tools)
    out, _, _ = _run(env, [CONSOLE, CMD, CONSOLE, CMD, CONSOLE, CMD, CONSOLE])
    assert out.stopped == "loop"                                               # AYNI yerel komutun 3. tekrarı yine döngü


def test_arada_eylem_yoksa_ayni_dis_okuma_dongu_ve_dogru_uyari(env):
    out, tools, recs = _run(env, [CONSOLE, CONSOLE, CONSOLE])                  # tetiklenen durum (R-22)
    assert out.stopped == "loop"
    warn = next(t["content"] for t in tools if "[Döngü uyarısı]" in t["content"])
    assert "dış aracı" in warn and "dosya değişmedi" not in warn               # yanlış gerekçe yok
    loop = next(r for r in recs if r.get("event") == "loop")
    assert loop["loop_kind"] == "dis_arac_tekrar" and loop["tool"] == "mcp__playwright__browser_console_messages"
    assert loop["result"] == "durdu"


def test_ayni_eylemin_sonsuz_tekrari_yakalanir(env):
    assert _run(env, [CLICK] * 3)[0].stopped == "done"                         # kasıtlı kısa tekrar serbest
    assert _run(env, [CLICK] * 6)[0].stopped == "loop"


def test_basarisiz_eylem_durumu_degistirmez(env):
    out, _, _ = _run(env, [CONSOLE, CLICK, CONSOLE, CLICK, CONSOLE], mcp_obj=BrowserMcp(fail={"browser_click"}))
    assert out.stopped == "loop"


def test_yerel_okuma_kurali_degismedi(env):
    root, _ = env
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    out, tools, recs = _run(env, [("read_file", {"path": "a.py"})] * 3)
    assert out.stopped == "loop"
    assert "dosya değişmedi" in next(t["content"] for t in tools if "[Döngü uyarısı]" in t["content"])
    assert next(r for r in recs if r.get("event") == "loop")["loop_kind"] == "ayni_cagri"


def test_model_degisince_kayit_durdu_demez(env):
    out, _, recs = _run(env, [CONSOLE, CONSOLE, CONSOLE], fallback_models=["yedek-model"])
    loop = next(r for r in recs if r.get("event") == "loop")
    assert loop["result"] == "model_degisti" and loop["model"] == "m"          # döngüye giren model adına
    assert out.stopped == "done"                                               # yedek modelle tur sürdü


# ---- gözlem ----

def test_gozlem_dongu_turunu_ve_araci_yazar_kisisel_veri_yazmaz(monkeypatch):
    seen = {}
    monkeypatch.setattr(gozlem, "kaydet", lambda tur, baslik, **kw: seen.update(tur=tur, baslik=baslik, **kw) or "x")
    gozlem.ajan_olayi({"event": "loop", "model": "m", "role": "kod", "loop_kind": "dis_arac_tekrar",
                       "tool": "mcp__playwright__browser_console_messages", "result": "durdu",
                       "detail": "“C:\\Users\\Osman\\gizli.txt” 3 kez"})
    assert seen["baslik"] == "Döngü bekçisi turu durdurdu" and seen["onem"] == "orta"
    assert seen["ayrinti"]["dongu_turu"] == "dis_arac_tekrar"
    assert seen["ayrinti"]["arac"] == "mcp__playwright__browser_console_messages"
    assert "gizli" not in json.dumps(seen, ensure_ascii=False)                 # ayrıntı metni (yol) gözleme girmez
    seen.clear()
    gozlem.ajan_olayi({"event": "loop", "model": "m", "loop_kind": "uydurma; rm -rf", "tool": "C:\\yol\\x.py",
                       "result": "model_degisti"})
    assert seen["baslik"].startswith("Döngü bekçisi: model değiştirildi") and seen["onem"] == "dusuk"
    assert seen["ayrinti"]["dongu_turu"] is None and seen["ayrinti"]["arac"] is None   # bilinmeyen tür / yol yazılmaz


def test_gozlem_izinli_anahtarlar_gercek_kayitta_suzulur():
    out = gozlem._ayrinti_temizle({"dongu_turu": "ileri_geri", "arac": "edit_file", "detail": "C:\\gizli"})
    assert out == {"dongu_turu": "ileri_geri", "arac": "edit_file"}


# ---- proje yürütücüsünün dosyaları ----

def test_proje_gorevinde_plan_ve_rapor_dosyasi_yazilmaz(env):
    root, _ = env
    steps = [("write_file", {"path": "EVREN_PLAN.md", "content": "- [x] bitti"}),
             ("edit_file", {"path": "./evren_rapor.md", "old_string": "a", "new_string": "b"}),
             ("write_file", {"path": "kod.py", "content": "x = 1\n"})]
    out, tools, _ = _run(env, steps, protected_files=("EVREN_PLAN.md", "EVREN_RAPOR.md"))
    assert PROTECTED_NOTE.format(name="EVREN_PLAN.md") in tools[0]["content"]
    assert "proje yürütücüsüne ait" in tools[1]["content"]                     # büyük/küçük harf ve ./ fark etmez
    assert not (root / "EVREN_PLAN.md").exists() and (root / "kod.py").is_file()


def test_normal_turda_plan_dosyasi_yazilabilir(env):
    root, _ = env
    out, tools, _ = _run(env, [("write_file", {"path": "EVREN_PLAN.md", "content": "- [ ] görev"})])
    assert (root / "EVREN_PLAN.md").is_file() and "proje yürütücüsüne ait" not in tools[0]["content"]
