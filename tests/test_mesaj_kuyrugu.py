"""Madde 23 a — iş sürerken mesaj: kuyruk, çalışan işe iletme (steer), geri çekme, iş bitince gönderme.

Kullanıcı 2026-11-13: "bir prompt yazdığımda o işlem bitene kadar yeni prompt yazamıyorum. ara cevaplar alarak claude
code'daki gibi işlemlerine devam etsin ... ilettiğim ama işleme alınmamış promtu geri çekebilmeliyim".
"""
from __future__ import annotations

import os
import threading
import time

import pytest

from evren_studio.agent import claims
from evren_studio.agent.inbox import Inbox, merge
from evren_studio.agent.runner import STEER_NOTE
from evren_studio.api.client import ChatResult
from evren_studio.db import Database
from test_agent_runner import FakeClient, Recorder, call, make_runner


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "t.db")
    yield d
    d.close()


@pytest.fixture()
def workspace(tmp_path):
    root = tmp_path / "proje"
    root.mkdir()
    (root / "app.py").write_text("print('merhaba')\n", encoding="utf-8")
    return root

# ---- kuyruk (Qt'siz) --------------------------------------------------------------------------------------------


def test_kuyruk_sirasi_geri_cekme_ve_iletilebilir_onek():
    box, seen = Inbox(), []
    box.on_change = lambda: seen.append(len(box))
    a = box.add("README'yi de düzelt")
    b = box.add("ekli", attachments=["dosya"])          # ekli → iletilmez, iş bitince
    c = box.add("sonra testleri çalıştır")
    assert [p.steerable for p in box.items()] == [True, False, True]
    assert [p.text for p in box.take_steerable()] == [a.text]      # yalnız BAŞTAKİ iletilebilir: c, b'yi sollamaz
    assert [p.id for p in box.items()] == [b.id, c.id]
    assert box.withdraw(a.id) is None                    # alınmış mesaj geri çekilemez
    assert box.withdraw(c.id).text == c.text and [p.id for p in box.items()] == [b.id]
    assert seen and seen[-1] == 1                       # her değişimde bildirim


def test_parti_komut_tek_basina_digerleri_birlikte():
    box = Inbox()
    box.add("bir")
    box.add("iki")
    box.add("/compact")
    box.add("üç")
    assert merge(box.take_batch()) == ("bir\n\niki", [])
    assert [p.text for p in box.take_batch()] == ["/compact"]
    assert [p.text for p in box.take_batch()] == ["üç"]
    assert box.take_batch() == [] and not box
    assert not Inbox().add("/model glm").steerable       # komut çalışan işe iletilmez


def test_ayni_anda_alma_ve_geri_cekme_mesaji_bir_kez_verir():
    # Koşucu (arka plan) alırken kullanıcı geri çekiyor: her mesaj ya alınır ya geri çekilir, ikisi birden asla.
    # İş parçacığı geçişini sıklaştır: kilitsiz bir sürümde yarış görünür olsun.
    import sys

    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        _yaris_turlari()
    finally:
        sys.setswitchinterval(old)


def _yaris_turlari():
    for _ in range(60):
        box = Inbox()
        ids = [box.add(f"m{i}").id for i in range(40)]
        taken, back = [], []
        t = threading.Thread(target=lambda: [taken.extend(p.id for p in box.take_steerable()) for _ in range(20)])
        t.start()
        for i in ids:
            p = box.withdraw(i)
            if p is not None:
                back.append(p.id)
        t.join()
        assert sorted(taken + back) == ids and not set(taken) & set(back)


# ---- koşucu ------------------------------------------------------------------------------------------------------


def test_adim_arasinda_ara_mesaj_kayda_girer_ve_kuyruk_notuyla_gider(db, workspace):
    queue = [[], [{"content": "Bu arada README'ye de bir satır ekle.", "meta": {"shown": "README'ye ekle"}}]]
    client = FakeClient([
        ChatResult(tool_calls=[call("read_file", path="app.py")]),
        ChatResult(content="Tamam, ikisini de yaptım.", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, workspace, mode="auto")
    runner.steer_source = lambda: queue.pop(0) if queue else []
    out = runner.run(history)
    assert out.stopped == "done" and len(client.calls) == 2
    roles = [m["role"] for m in history]
    i = roles.index("tool")
    steer = history[i + 1]
    assert steer["role"] == "user" and steer["meta"]["steer"] and steer["meta"]["shown"] == "README'ye ekle"
    last = client.calls[1]["messages"][-1]
    assert last["role"] == "user" and "README'ye de bir satır" in str(last["content"]) and STEER_NOTE in str(last["content"])
    first_texts = [str(m.get("content")) for m in client.calls[0]["messages"]]
    assert not any(STEER_NOTE in t for t in first_texts)            # ara mesaj yokken not da yok (R-22)
    assert "# Kullanıcıdan ara mesaj" in last["content"]
    saved = [m for m in db.get_session_messages(runner.session_id) if m["role"] == "user"]
    assert saved[-1]["meta"].get("steer")                           # kalıcı kayıt (oturum yeniden açılınca görünür)


def test_yanit_bitince_bekleyen_ara_mesajla_ayni_turda_surer(db, workspace):
    pending = [{"content": "Bir de kısa özet yaz.", "meta": {}}]
    client = FakeClient([ChatResult(content="Bitti.", finish_reason="stop"),
                         ChatResult(content="Özet: ...", finish_reason="stop")])
    runner, history, _ = make_runner(db, client, workspace, mode="auto")
    taken = []

    def source():
        taken.append(1)
        return [pending.pop()] if pending and len(taken) >= 2 else []   # ilk adımda yok, yanıt bitince var
    runner.steer_source = source
    out = runner.run(history)
    assert out.stopped == "done" and len(client.calls) == 2 and out.last_text == "Özet: ..."


def test_ara_mesaj_yoksa_ya_da_kaynak_hata_verirse_davranis_aynı(db, workspace):
    for source in (None, lambda: [], lambda: (_ for _ in ()).throw(RuntimeError("kuyruk bozuk"))):
        client = FakeClient([ChatResult(content="Bitti.", finish_reason="stop")])
        runner, history, _ = make_runner(db, client, workspace, mode="auto")
        runner.steer_source = source
        assert runner.run(history).stopped == "done" and len(client.calls) == 1
        assert not [m for m in history if (m.get("meta") or {}).get("steer")]


def test_iptalde_ara_mesaj_alinmaz(db, workspace):
    ev = Recorder()
    client = FakeClient([ChatResult(content="Bitti.", finish_reason="stop")])
    runner, history, _ = make_runner(db, client, workspace, events=ev, mode="auto")
    runner.steer_source = lambda: [{"content": "x", "meta": {}}]
    runner.cancel = type("C", (), {"cancelled": True})()
    out = runner.run(history)
    assert out.stopped == "cancelled" and not [m for m in history if (m.get("meta") or {}).get("steer")]


def test_iddia_bekcisi_turu_ara_mesajla_bolunmez():
    hist = [{"role": "user", "content": "düzelt"},
            {"role": "tool", "content": "Çalıştırıldı (çıkış 0)"},
            {"role": "user", "content": "bir de README", "meta": {"steer": True}},
            {"role": "assistant", "content": "tamam"}]
    assert claims.current_turn(hist) == hist[1:]                    # kanıt (test koşusu) ara mesajdan önce kalır


# ---- arayüz (R-31: gerçek send → koşucu → _on_done yolu) ---------------------------------------------------------


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
    w.session.inbox.take_all()
    w.close()


def _wait(app, cond, timeout=8.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def _held_client(first: ChatResult, *rest: ChatResult):
    """İlk yanıt `gate` açılana kadar bekler (iş sürüyor); sonra sırayla diğerleri."""
    gate = threading.Event()

    def held(_tools):
        gate.wait(10)
        return first
    client = FakeClient([held, *rest])
    client.close = lambda: None
    return client, gate


def _users(w):
    return [m for m in w.ctx.db.get_session_messages(w.session.session_id) if m["role"] == "user"]


def test_arayuz_calisirken_gonderilen_mesaj_siraya_alinir_ve_ise_iletilir(win):
    app, w = win
    client, gate = _held_client(ChatResult(content="İlk yanıt.", finish_reason="stop"),
                                ChatResult(content="Ek isteği de yaptım.", finish_reason="stop"))
    w.ctx.make_client = lambda log_sink=None: client
    w.session.welcome._choose(None)
    w.session.send("ilk soru")
    assert _wait(app, lambda: w.session.running and len(client.calls) == 1)
    w.session.composer.set_text("bir de şunu ekle")
    w.session.composer._submit()                         # iş sürerken Enter: reddedilmez
    assert _wait(app, lambda: w.session.composer.queue_count() == 1)
    assert w.session.composer.queue_bar.isVisibleTo(w.session.composer)
    assert w.session.composer.edit.toPlainText() == ""
    note = w.session.composer._queue_rows[0].findChildren(type(w.session.composer.run_hint))
    assert any(lbl.text() == "çalışan işe iletilecek" for lbl in note)
    gate.set()
    assert _wait(app, lambda: not w.session.running)
    assert len(client.calls) == 2 and "bir de şunu ekle" in str(client.calls[1]["messages"][-1]["content"])
    assert [bool((m.get("meta") or {}).get("steer")) for m in _users(w)] == [False, True]
    assert w.session.composer.queue_count() == 0 and not w.session.composer.queue_bar.isVisibleTo(w.session.composer)


def test_arayuz_islenmemis_mesaj_geri_cekilir_ve_gonderilmez(win):
    app, w = win
    client, gate = _held_client(ChatResult(content="İlk yanıt.", finish_reason="stop"))
    w.ctx.make_client = lambda log_sink=None: client
    w.session.welcome._choose(None)
    w.session.send("ilk soru")
    assert _wait(app, lambda: w.session.running and len(client.calls) == 1)
    w.session.send("vazgeçeceğim mesaj")
    assert _wait(app, lambda: w.session.composer.queue_count() == 1)
    w.session.composer.set_text("yarım yazı")
    item = w.session.inbox.items()[0]
    w.session.composer.withdraw_requested.emit(item.id)  # "Geri çek" düğmesi
    assert _wait(app, lambda: w.session.composer.queue_count() == 0)
    assert w.session.composer.edit.toPlainText() == "yarım yazı\n\nvazgeçeceğim mesaj"   # kutudaki yazı korunur
    gate.set()
    assert _wait(app, lambda: not w.session.running)
    time.sleep(0.8)
    app.processEvents()
    assert len(client.calls) == 1 and len(_users(w)) == 1   # geri çekilen gönderilmedi
    assert not w.session.running


def test_arayuz_akis_surerken_mesaj_bekler_bitince_yeni_tur_olur(win):
    # QA/Proje/Derin akışı (koşucu yokken de "meşgul") → ara mesaj iletilmez, akış bitince yeni tur.
    app, w = win
    client = FakeClient([ChatResult(content="Sıradaki mesajın yanıtı.", finish_reason="stop")])
    client.close = lambda: None
    w.ctx.make_client = lambda log_sink=None: client
    w.session.welcome._choose(None)
    w.session.project.active = True
    try:
        w.session.send("proje bitince şunu yap")
        assert _wait(app, lambda: w.session.composer.queue_count() == 1)
        labels = w.session.composer._queue_rows[0].findChildren(type(w.session.composer.run_hint))
        assert any(lbl.text() == "iş bitince gönderilecek" for lbl in labels)
        first_id = w.session.inbox.items()[0].id
        w.session.composer.set_text("yazmakta olduğum")
        end = time.monotonic() + 1.0
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.02)
        assert not client.calls                          # akış sürerken gönderilmez
        assert w.session.composer.edit.toPlainText() == "yazmakta olduğum"    # yazılan yazıya dokunulmaz
        assert [p.id for p in w.session.inbox.items()] == [first_id]           # sıra yerinde (yeniden eklenmedi)
        w.session.composer.set_text("")
    finally:
        w.session.project.active = False
    assert _wait(app, lambda: len(client.calls) == 1 and not w.session.running)
    assert "proje bitince şunu yap" in str(client.calls[0]["messages"][-1]["content"])
    assert w.session.composer.queue_count() == 0


def test_arayuz_durdurma_komutu_ve_oturum_degisimi_sirayi_kutuya_dondurur(win, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)   # oturumsuz not = açılır pencere
    app, w = win
    s = w.session
    s.welcome._choose(None)
    s.project.active = True                              # akış sürüyor (koşucu yok) → mesaj sırada bekler
    try:
        s.send("bekleyen bir")
        assert s.composer.queue_count() == 1
        s.send("/derin-durdur")                          # durdurma komutu: kendiliğinden gönderilmesin
        assert not s.inbox and s.composer.edit.toPlainText() == "bekleyen bir"
        s.composer.set_text("")
        s.send("bekleyen iki")
        assert s.composer.queue_count() == 1
        s.new_session()                                  # başka oturuma gitmesin
        assert not s.inbox and s.composer.edit.toPlainText() == "bekleyen iki"
        a = w.ctx.db.create_session("auto", None)
        b = w.ctx.db.create_session("auto", None)
        s.open_session(a)
        s.composer.set_text("")
        s.send("bekleyen üç")
        assert s.composer.queue_count() == 1
        s.open_session(b)                                # var olan başka oturuma geçiş de
        assert not s.inbox and s.composer.edit.toPlainText() == "bekleyen üç"
    finally:
        s.project.active = False


def test_arayuz_gorev_turuna_ara_mesaj_iletilmez_normal_tura_iletilir(win):
    # Proje/QA/Derin görev turunu yürütücüsü yönetir: koşucuya ara mesaj kaynağı VERİLMEZ (model_override / tur kancası)
    app, w = win
    s = w.session
    client, gate = _held_client(ChatResult(content="tamam", finish_reason="stop"),
                                ChatResult(content="tamam", finish_reason="stop"))
    w.ctx.make_client = lambda log_sink=None: client
    s.welcome._choose(None)
    s.send("ilk")
    assert _wait(app, lambda: s.running)
    assert s.runner.steer_source is not None             # normal tur
    gate.set()
    assert _wait(app, lambda: not s.running)
    client2, gate2 = _held_client(ChatResult(content="görev tamam", finish_reason="stop"))
    w.ctx.make_client = lambda log_sink=None: client2
    s._turn_hook = lambda outcome, exc: None
    s.start_run(model_override=("auto", [], "kod"))
    assert _wait(app, lambda: len(client2.calls) == 1)  # görev turu çalışıyor (yanıt bekletiliyor)
    assert s.running and s.runner is not None and s.runner.steer_source is None
    gate2.set()
    assert _wait(app, lambda: not s.running)


def test_arayuz_durdurunca_sira_kutuya_doner(win):
    app, w = win
    client, gate = _held_client(ChatResult(content="İlk yanıt.", finish_reason="stop"))
    w.ctx.make_client = lambda log_sink=None: client
    w.session.welcome._choose(None)
    w.session.send("ilk soru")
    assert _wait(app, lambda: w.session.running and len(client.calls) == 1)
    w.session.send("sıradaki")
    assert _wait(app, lambda: w.session.composer.queue_count() == 1)
    w.session.stop()                                     # Esc
    assert w.session.composer.queue_count() == 0 and w.session.composer.edit.toPlainText() == "sıradaki"
    gate.set()
    assert _wait(app, lambda: not w.session.running)
    time.sleep(0.8)
    app.processEvents()
    assert len(client.calls) == 1                        # durdurulan işten sonra kendiliğinden gönderilmedi
