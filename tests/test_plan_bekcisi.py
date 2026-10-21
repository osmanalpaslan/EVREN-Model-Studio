"""Plan bekçisi: fazlara ayrılmış işte açık madde varken tur bitmesin (2026-10-21; gerçek ağ yok).

Kullanıcı bildirimi: model planı dosyaya yazıp bir fazı bitirince "Faz 1 tamamlandı" deyip
duruyor, "devam" denince sürdürüyordu. Hem tetiklenmesi hem tetiklenmemesi gereken durumlar (R-22).
"""
from __future__ import annotations

import os

import pytest

from evren_studio.agent import planguard
from evren_studio.api.client import ChatResult
from evren_studio.db import Database
from test_agent_runner import FakeClient, Recorder, call, make_runner

PLAN3 = "# Plan\n- [ ] Faz 1: a.py\n- [ ] Faz 2: b.py\n- [ ] Faz 3: c.py\n"


def test_ayristirici_acik_ve_kapali_maddeler():
    text = ("# Proje\n- [x] Faz 1 kurulum\n- [ ] Faz 2 veritabanı\n* [~] Faz 3 arayüz\n1. [ ] Faz 4 test\n"
            "## Faz 5\nDurum: bekliyor\n## Faz 6\nDurum: tamamlandı\n"
            "| Faz | Durum |\n|---|---|\n| Faz 7 | ⏳ bekliyor |\n| Faz 8 | ✅ bitti |\n")
    items = planguard.open_items_in_text(text)
    assert items == ["Faz 2 veritabanı", "Faz 3 arayüz", "Faz 4 test", "Faz 5", "Faz 7 · ⏳ bekliyor"]
    assert planguard.open_items_in_text("- [x] a\n- [X] b\nDurum: tamamlandı") == []
    assert planguard.is_plan_file("PLAN.md") and planguard.is_plan_file("docs/faz_plani.txt")
    assert not planguard.is_plan_file("README.md") and not planguard.is_plan_file("plan.py")


def test_kaynaklar_yalniz_son_gercek_mesajdan_beri():
    old_todo = {"role": "tool", "name": "update_todos", "meta": {"todos": [{"content": "eski", "status": "pending"}]}}
    hist = [{"role": "user", "content": "ilk"}, old_todo, {"role": "user", "content": "yeni iş"}]
    assert planguard.open_todos(hist) == []                         # eski işin listesi tetiklemez
    hist.append({"role": "user", "content": "devam", "meta": {"auto_continue": True}})
    hist.append({"role": "tool", "name": "update_todos",
                 "meta": {"todos": [{"content": "A", "status": "completed"}, {"content": "B", "status": "pending"}]}})
    assert planguard.open_todos(hist) == ["B"]                      # özet sonrası otomatik devam aynı tur sayılır


def test_cok_asamali_istem_algilama():
    long_phases = "Bu projeyi fazlara ayır ve sırayla işle.\n" + "\n".join(f"{i}. madde {i} " + "x" * 150 for i in range(1, 10))
    assert planguard.looks_multi_phase(long_phases)
    assert not planguard.looks_multi_phase("hesap.py'deki hatayı düzelt")
    assert not planguard.looks_multi_phase("x" * 2000)              # uzun ama aşamasız


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    yield d
    d.close()


@pytest.fixture()
def proj(tmp_path):
    root = tmp_path / "proje"
    root.mkdir()
    return root


def _nudges(client):
    return [m["content"] for c in client.calls for m in c["messages"]
            if m["role"] == "user" and "PLAN BEKÇİSİ" in str(m.get("content"))]


def test_faz_bitince_durmaz_siradakine_gecer(db, proj):
    ev = Recorder()
    notes = []
    ev.status = notes.append
    client = FakeClient([
        ChatResult(tool_calls=[call("write_file", cid="p", path="PLAN.md", content=PLAN3)]),
        ChatResult(tool_calls=[call("write_file", cid="a", path="a.py", content="a = 1\n")]),
        ChatResult(tool_calls=[call("edit_file", cid="p1", path="PLAN.md", old_string="- [ ] Faz 1", new_string="- [x] Faz 1")]),
        ChatResult(content="Faz 1 tamamlandı. Sıradaki adım: Faz 2.", finish_reason="stop"),   # eskiden burada bitiyordu
        ChatResult(tool_calls=[call("write_file", cid="b", path="b.py", content="b = 2\n")]),
        ChatResult(tool_calls=[call("edit_file", cid="p2", path="PLAN.md", old_string="- [ ] Faz 2", new_string="- [x] Faz 2")]),
        ChatResult(content="Faz 2'ye geçeyim mi?", finish_reason="stop"),                      # soru ile durma
        ChatResult(tool_calls=[call("write_file", cid="c", path="c.py", content="c = 3\n")]),
        ChatResult(tool_calls=[call("edit_file", cid="p3", path="PLAN.md", old_string="- [ ] Faz 3", new_string="- [x] Faz 3")]),
        ChatResult(content="Tüm fazlar bitti.", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, proj, events=ev, mode="auto", plan_guard=True)
    out = runner.run(history)
    assert out.stopped == "done" and out.open_plan_items == []
    assert all((proj / f).exists() for f in ("a.py", "b.py", "c.py"))
    assert len(_nudges(client)) == 2 and "Faz 2: b.py" in _nudges(client)[0]
    assert any("Plan bekçisi" in n for n in notes)


def test_ilerleme_yoksa_sinirli_dener_sonra_durur(db, proj):
    ev = Recorder()
    notes = []
    ev.status = notes.append
    client = FakeClient([ChatResult(tool_calls=[call("write_file", path="PLAN.md", content=PLAN3)])]
                        + [ChatResult(content=f"Özet {i}: işler iyi gidiyor.", finish_reason="stop") for i in range(10)])
    runner, history, _ = make_runner(db, client, proj, events=ev, mode="auto", plan_guard=True)
    out = runner.run(history)
    assert out.stopped == "done" and len(out.open_plan_items) == 3
    assert len(_nudges(client)) == 2                                 # ilerleme yok: sonsuz döngü yok
    assert any("ilerleme göstermiyor" in n for n in notes)


def test_engel_yazinca_durur(db, proj):
    client = FakeClient([
        ChatResult(tool_calls=[call("write_file", path="PLAN.md", content=PLAN3)]),
        ChatResult(content="ENGEL: Faz 2 için veritabanı parolası gerekiyor.", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, proj, mode="auto", plan_guard=True)
    runner.run(history)
    assert _nudges(client) == [] and len(client.calls) == 2


@pytest.mark.parametrize("text, plan_only", [
    ("Kütüphane sistemi yapacağız. Henüz KOD YAZMA. Sadece EVREN_PLAN.md dosyasına görev planı yaz.", True),
    ("Yalnızca bir plan çıkar, dosyalara dokunma.", True),
    ("Just write a plan, don't implement anything.", True),
    ("PLAN.md'deki fazları sırayla uygula.", False),
    ("Kod yazmayı bilen biri gibi hesap.py'yi düzelt.", False),
    ("Fazlara ayır, plan dosyasına yaz ve hepsini uygula.", False),
])
def test_yalniz_plan_istegi_algilama(text, plan_only):
    assert planguard.plan_only_request([{"role": "user", "content": text}]) is plan_only


def test_yalniz_plan_isteginde_plan_dosyasi_tetiklemez(db, proj):
    """R-22: kullanıcı yalnız plan istediyse plandaki açık maddeler istenen sonuçtur; bekçi dürtmez."""
    client = FakeClient([
        ChatResult(tool_calls=[call("write_file", path="EVREN_PLAN.md", content=PLAN3)]),
        ChatResult(content="Plan yazıldı.", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, proj, mode="auto", plan_guard=True)
    history[-1]["content"] = "Henüz KOD YAZMA. Sadece EVREN_PLAN.md dosyasına görev planı yaz."
    out = runner.run(history)
    assert _nudges(client) == [] and len(client.calls) == 2 and out.open_plan_items == []
    assert not (proj / "a.py").exists()


def test_projede_eski_plan_dosyasi_tetiklemez(db, proj):
    (proj / "TODO.md").write_text("- [ ] eski iş 1\n- [ ] eski iş 2\n", encoding="utf-8")
    client = FakeClient([
        ChatResult(tool_calls=[call("read_file", path="TODO.md")]),
        ChatResult(tool_calls=[call("write_file", path="x.py", content="x = 1\n")]),
        ChatResult(content="İstediğin değişiklik yapıldı.", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, proj, mode="auto", plan_guard=True)
    runner.run(history)
    assert _nudges(client) == []                                     # kapsam: istenmeyen işe sürüklemez (R-20)


def test_gorev_listesi_acikken_devam_kapaninca_biter(db, proj):
    client = FakeClient([
        ChatResult(tool_calls=[call("update_todos", todos=[{"content": "A", "status": "in_progress"},
                                                           {"content": "B", "status": "pending"}])]),
        ChatResult(tool_calls=[call("write_file", path="a.py", content="a = 1\n")]),
        ChatResult(content="A bitti.", finish_reason="stop"),
        ChatResult(tool_calls=[call("write_file", path="b.py", content="b = 1\n")]),
        ChatResult(tool_calls=[call("update_todos", todos=[{"content": "A", "status": "completed"},
                                                           {"content": "B", "status": "completed"}])]),
        ChatResult(content="Hepsi bitti.", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, proj, mode="auto", plan_guard=True)
    out = runner.run(history)
    assert len(_nudges(client)) == 1 and "B" in _nudges(client)[0] and out.open_plan_items == []


@pytest.mark.parametrize("kw", [dict(plan_guard=False), dict(plan_guard=True, mode="plan"),
                                dict(plan_guard=True, no_writes=True), dict(plan_guard=True, final_marker="<x>")])
def test_kapali_oldugu_durumlar(db, proj, kw):
    (proj / "PLAN.md").write_text(PLAN3, encoding="utf-8")
    client = FakeClient([
        ChatResult(tool_calls=[call("update_todos", todos=[{"content": "A", "status": "pending"}])]),
        ChatResult(content="tamam <x>", finish_reason="stop"),
    ])
    kw = {"mode": "auto", **kw}
    runner, history, _ = make_runner(db, client, proj, **kw)
    runner.run(history)
    assert _nudges(client) == []


def test_sistem_isteminde_acik_maddeler(db, proj):
    client = FakeClient([
        ChatResult(tool_calls=[call("write_file", path="PLAN.md", content=PLAN3)]),
        ChatResult(content="ENGEL: dur", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, proj, mode="auto", plan_guard=True)
    runner.run(history)
    system = client.calls[1]["messages"][0]["content"]
    assert "# Açık plan maddeleri (PLAN.md)" in system and "Faz 3: c.py" in system


# ---- arayüz: Proje ajanı önerisi ----------------------------------------------------------------

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


def test_uzun_cok_asamali_istemde_proje_onerisi(win, tmp_path, monkeypatch):
    _app, w = win
    from evren_studio.ui.transcript import ChoiceCard

    sv = w.session
    sv.welcome._choose(str(tmp_path))
    started, planned = [], []
    monkeypatch.setattr(sv, "start_run", lambda *a, **k: started.append(1))
    monkeypatch.setattr(sv.project, "command", lambda c, a: planned.append((c, a)))
    text = "Bu uygulamayı fazlara ayırıp sırayla geliştir.\n" + "\n".join(f"{i}. özellik {i} " + "a" * 160 for i in range(1, 10))
    sv.send(text)
    cards = sv.findChildren(ChoiceCard)
    assert cards and started == []                                   # mesaj gönderilmedi, karar bekleniyor
    cards[-1].buttons[0].click()
    assert planned == [("/proje", text)]
    # aynı metin tekrar gönderilince ikinci kez sorulmaz
    sv.send(text)
    assert started == [1]
    # kısa istemde öneri yok
    sv.send("hesap.py'deki hatayı düzelt")
    assert len(sv.findChildren(ChoiceCard)) == 1


def test_oneri_ayardan_kapatilabilir(win, tmp_path, monkeypatch):
    _app, w = win
    from evren_studio.ui.transcript import ChoiceCard

    sv = w.session
    sv.welcome._choose(str(tmp_path))
    w.ctx.settings.suggest_project = False
    monkeypatch.setattr(sv, "start_run", lambda *a, **k: None)
    sv.send("Fazlara ayır.\n" + "\n".join(f"{i}. iş " + "b" * 170 for i in range(1, 10)))
    assert sv.findChildren(ChoiceCard) == []
