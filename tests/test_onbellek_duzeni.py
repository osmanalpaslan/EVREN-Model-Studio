"""Madde 22 B: önbellek dostu istek düzeni (2026-11-13 ölçümü: EVREN istemin değişmeyen başını önbelleğe alır — aynı başla
4-7 kat hızlı, önbellekten okunan token kotadan düşmez).

Kural: ardışık isteklerde önceki istek (kuyruk notu hariç) sonrakinin AYNEN başı olmalı — adımlar ve turlar arasında,
proje dosyaları değişse ve tura özel ipucu gelip gitse bile. Sabit istem yalnız gerçekten gerektiğinde yenilenir (EVREN.md
düzenlendi, kip değişti, özet). Değişen notlar son mesajın kuyruğunda.
"""
from __future__ import annotations

import json

import pytest

from evren_studio.agent import runner as rmod
from evren_studio.agent import tools
from evren_studio.agent.runner import TAIL_SEPARATOR, AgentEvents, AgentRunner, append_tail
from evren_studio.api.client import ChatResult
from evren_studio.db import Database


class Kayit:
    """Sahte istemci: istekleri kaydeder; her turda önce a.py'yi okur, sonra bitirir."""

    def __init__(self):
        self.istekler: list[list[dict]] = []
        self.n = 0

    def chat(self, model, messages, **kw):
        self.istekler.append(json.loads(json.dumps(messages, ensure_ascii=False, default=str)))
        self.n += 1
        if self.n % 2 == 1:
            return ChatResult(tool_calls=[{"id": f"c{self.n}", "name": "read_file",
                                           "arguments": json.dumps({"path": "a.py"})}], finish_reason="tool_calls")
        return ChatResult(content="Bitti.", finish_reason="stop")

    def close(self):
        pass


@pytest.fixture()
def ortam(tmp_path, monkeypatch):
    from evren_studio.agent import projectmap

    monkeypatch.setattr(rmod, "FREEZE_SYSTEM", True)
    # küçük projede gerçek harita boş kalır → dosya adlarını listeleyen harita (değişince görünür olsun)
    monkeypatch.setattr(projectmap, "prompt_section",
                        lambda root: "# Proje haritası\n" + ", ".join(sorted(p.name for p in root.iterdir())))
    rmod._FROZEN_SYSTEM.clear()
    root = tmp_path / "p"
    root.mkdir()
    (root / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    db = Database(tmp_path / "t.db")
    sid = db.create_session("m", str(root), "auto")
    c = Kayit()

    def tur(metin, mode="auto"):
        db.add_session_message(sid, "user", metin)
        AgentRunner(c, "m", session_id=sid, store=db, workspace=tools.Workspace(root), mode=mode, stream=False,
                    events=AgentEvents(), project_map=True).run(db.get_session_messages(sid))
    yield root, db, sid, c, tur
    db.close()
    rmod._FROZEN_SYSTEM.clear()


def _kuyruksuz(msgs: list[dict]) -> list[dict]:
    out = [dict(m) for m in msgs]
    last = out[-1]
    if isinstance(last.get("content"), str) and TAIL_SEPARATOR in last["content"]:
        last["content"] = last["content"].split(TAIL_SEPARATOR)[0]
    return out


def test_istek_basi_adimlar_ve_turlar_boyunca_aynen_korunur(ortam):
    root, db, sid, c, tur = ortam
    tur("ayarlar.yaml dosyasındaki değeri değiştir")          # olmayan dosya → tura özel ipucu (kuyrukta)
    (root / "yeni_modul.py").write_text("def g():\n    return 2\n", encoding="utf-8")   # harita değişirdi
    tur("şimdi a.py'yi oku ve özetle")                         # ipucu yok
    assert len(c.istekler) == 4
    assert len({json.dumps(r[0]) for r in c.istekler}) == 1, "sistem istemi oturum boyunca aynı"
    assert "a.py" in c.istekler[-1][0]["content"] and "yeni_modul" not in c.istekler[-1][0]["content"], \
        "harita oturum başında donduruldu (eski düzende her tur yeniden hesaplanıp tüm geçmişin önbelleğini bozardı)"
    assert "BULUNAMADI: `ayarlar.yaml`" in c.istekler[0][-1]["content"]          # ipucu kuyrukta
    assert "BULUNAMADI" not in c.istekler[0][0]["content"]
    for k in range(1, 4):
        onceki = _kuyruksuz(c.istekler[k - 1])
        assert c.istekler[k][:len(onceki)] == onceki, f"istek {k + 1} öncekinin başını aynen taşımıyor"


def test_proje_hafizasi_duzenlenince_ve_kip_degisince_yenilenir(ortam):
    root, db, sid, c, tur = ortam
    tur("a.py'yi oku")
    (root / "EVREN.md").write_text("Her yanıtta KURAL-777 uygula.\n", encoding="utf-8")
    tur("tekrar oku")
    assert "KURAL-777" not in c.istekler[0][0]["content"] and "KURAL-777" in c.istekler[2][0]["content"]
    tur("planla", mode="plan")
    assert c.istekler[4][0]["content"] != c.istekler[2][0]["content"], "kip değişince sabit istem yenilenir"


def test_ayni_aracli_kip_degisince_de_yenilenir_kalici_talimat_sistemde_kalir(ortam):
    """Otomatik ↔ Düzenlemeleri kabul et: araç listesi aynı ama kip satırı farklı → sabit istem yenilenir. Kalıcı
    rol/profil talimatı (extra_hint) sabit istemde, kuyruğa KOPYALANMAZ (her adımda yeniden gönderilip önbellek dışı
    kalırdı)."""
    root, db, sid, c, tur = ortam
    db.add_session_message(sid, "user", "a.py'yi oku")
    for mode in ("auto", "kabul"):
        AgentRunner(c, "m", session_id=sid, store=db, workspace=tools.Workspace(root), mode=mode, stream=False,
                    events=AgentEvents(), extra_hint="PROFIL-TALIMATI-42").run(db.get_session_messages(sid))
    assert "Otomatik" in c.istekler[0][0]["content"] and "Düzenlemeleri kabul et" in c.istekler[2][0]["content"]
    assert all("PROFIL-TALIMATI-42" in r[0]["content"] for r in c.istekler)
    assert all("PROFIL-TALIMATI-42" not in str(r[-1]["content"]) for r in c.istekler)


def test_ozetten_sonra_yenilenir_ve_kurulumda_gecersizlenir(ortam, monkeypatch):
    root, db, sid, c, tur = ortam
    r = AgentRunner(c, "m", session_id=sid, store=db, workspace=tools.Workspace(root), mode="auto", stream=False,
                    events=AgentEvents(), project_map=True)
    r._summary_anchor = 1
    ilk = r._system()
    (root / "yeni.py").write_text("x = 1\n", encoding="utf-8")
    r._map_section = None
    assert r._system() == ilk and "yeni.py" not in ilk               # aynı imza → dondurulmuş
    r._summary_anchor = 99                                          # özet: geçmiş yeni baştan başlıyor
    assert "yeni.py" in r._system(), "özetten sonra sabit istem (harita) yenilenir"
    anahtar = r._frozen_key()
    assert anahtar in rmod._FROZEN_SYSTEM
    r._invalidate_frozen()
    assert anahtar not in rmod._FROZEN_SYSTEM


def test_eski_duzen_ipucunu_sistem_istemine_koyar(tmp_path, monkeypatch):
    """A/B için EVREN_STUDIO_ONBELLEK_ESKI=1 (FREEZE_SYSTEM=False): eski davranış aynen."""
    monkeypatch.setattr(rmod, "FREEZE_SYSTEM", False)
    root = tmp_path / "p"
    root.mkdir()
    db = Database(tmp_path / "t.db")
    sid = db.create_session("m", str(root), "auto")
    db.add_session_message(sid, "user", "ayarlar.yaml dosyasındaki değeri değiştir")
    c = Kayit()
    AgentRunner(c, "m", session_id=sid, store=db, workspace=tools.Workspace(root), mode="auto", stream=False,
                events=AgentEvents()).run(db.get_session_messages(sid))
    db.close()
    assert "BULUNAMADI: `ayarlar.yaml`" in c.istekler[0][0]["content"]
    assert TAIL_SEPARATOR not in str(c.istekler[0][-1]["content"])


def test_kuyruk_notu_ekleme_bicimleri():
    m = [{"role": "system", "content": "s"}, {"role": "user", "content": "soru"}]
    append_tail(m, "")
    assert m[-1]["content"] == "soru"                                # boş not eklenmez
    append_tail(m, "NOT")
    assert m[-1]["content"] == "soru" + TAIL_SEPARATOR + "NOT" and len(m) == 2
    g = [{"role": "user", "content": [{"type": "text", "text": "resim"}]}]
    append_tail(g, "NOT")
    assert g[0]["content"][-1] == {"type": "text", "text": TAIL_SEPARATOR + "NOT"}
    a = [{"role": "system", "content": "s"}, {"role": "assistant", "content": "x"}]
    append_tail(a, "NOT")
    assert a[-1] == {"role": "user", "content": "NOT"}
    t = [{"role": "tool", "tool_call_id": "1", "content": "çıktı"}]
    append_tail(t, "NOT")
    assert t[0]["content"].endswith("NOT") and t[0]["tool_call_id"] == "1"
