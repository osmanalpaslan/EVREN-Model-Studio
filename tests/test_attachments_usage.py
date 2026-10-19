"""Ekler (sürükle-bırak, Ctrl+V, ataç) ve kullanım düğmesi — gerçek ağ yok.

Görsel girdinin gerçek API sonucu: docs/knowledge/MODEL_CAPABILITIES.md
(2026-10-19). Burada biçim, akış ve arayüz davranışı sınanır.
"""
from __future__ import annotations

import base64
import copy
import json
import os
import time

import httpx
import pytest

from evren_studio.agent.runner import MAX_HISTORY_IMAGES, to_api_messages
from evren_studio.api.anthropic_client import to_anthropic
from evren_studio.api.client import ChatResult, EvrenClient, QuotaInfo
from evren_studio.api.images import anthropic_blocks, chat_content, expand_chat_images, responses_content
from evren_studio.api.openai_client import to_responses_input

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


@pytest.fixture()
def png(tmp_path):
    p = tmp_path / "kare.png"
    p.write_bytes(PNG_1PX)
    return str(p)


# ---- API biçimleri ------------------------------------------------------------------


def test_chat_content_ve_eksik_dosya(png, tmp_path):
    parts = chat_content("ne görüyorsun", [png, str(tmp_path / "yok.png")])
    assert parts[0]["type"] == "text" and "ne görüyorsun" in parts[0]["text"]
    assert "bulunamadı: yok.png" in parts[0]["text"]
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert len(parts) == 2


def test_evren_govdesi_image_url_icerir(png):
    seen = []

    def handler(req):
        seen.append(json.loads(req.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "kırmızı"},
                                                      "finish_reason": "stop"}], "usage": {}})

    c = EvrenClient("https://x.test/v1", "evren_llm_TEST", transport=httpx.MockTransport(handler))
    c.chat("auto", [{"role": "user", "content": "renk?", "_images": [png]}])
    msg = seen[0]["messages"][0]
    assert "_images" not in msg and isinstance(msg["content"], list)
    assert msg["content"][1]["type"] == "image_url"


def test_openai_ve_anthropic_bicimleri(png):
    _, items = to_responses_input([{"role": "user", "content": "bak", "_images": [png]}])
    assert [p["type"] for p in items[0]["content"]] == ["input_text", "input_image"]
    _, msgs = to_anthropic([{"role": "user", "content": "bak", "_images": [png]}])
    assert msgs[0]["content"][0]["type"] == "image"
    assert msgs[0]["content"][0]["source"]["media_type"] == "image/png"
    assert anthropic_blocks("", [png])[0]["type"] == "image"
    assert responses_content("x", [])[0] == {"type": "input_text", "text": "x"}


def test_to_api_messages_gorselleri_tasir_ve_sinirlar(png):
    hist = []
    for i in range(MAX_HISTORY_IMAGES + 2):
        hist.append({"role": "user", "content": f"m{i}", "meta": {"images": [png]}})
        hist.append({"role": "assistant", "content": "tamam"})
    msgs = to_api_messages("sys", hist, "native")
    users = [m for m in msgs if m["role"] == "user"]
    with_img = [m for m in users if m.get("_images")]
    assert len(with_img) == MAX_HISTORY_IMAGES and users[-1].get("_images")   # en yeniler
    assert "[ekli görsel: kare.png]" in users[0]["content"]                     # eskiler not
    # özet isteği görsel göndermez
    plain = to_api_messages("sys", hist, "text", images=False)
    assert not any(m.get("_images") for m in plain)
    assert expand_chat_images([{"role": "assistant", "content": "x", "_images": [png]}])[0]["content"] == "x"


# ---- arayüz -------------------------------------------------------------------------


class Client:
    def __init__(self, responses=None, quota=None):
        self.responses = list(responses or [])
        self.calls = []
        self.quota = quota

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, on_reasoning=None,
             tools=None, **kw):
        self.calls.append({"model": model, "messages": copy.deepcopy(messages)})
        r = self.responses.pop(0) if self.responses else ChatResult(content="tamam", finish_reason="stop")
        if on_delta and r.content:
            on_delta(r.content, "")
        return r

    def get_quota(self):
        if self.quota is None:
            raise RuntimeError("kota yok")
        return self.quota

    def close(self):
        pass


QUOTA = QuotaInfo(used_tokens=250_000, cap=2_500_000, window_minutes=5, reset_at="2026-10-19T07:51:00+00:00",
                  usage_ratio=0.1, level="ok", held_cr="0.0000", remaining_cr="1020.0000",
                  daily_used_tokens=1_500_000, daily_limit_tokens=15_000_000,
                  daily_remaining_tokens=13_500_000, daily_reset_at="2026-10-20T00:00:00Z")


@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
    yield app, w
    w.close()


def _wait(app, cond, timeout=6.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def _mime_files(paths):
    from PySide6.QtCore import QMimeData, QUrl

    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(p) for p in paths])
    md.setText("\n".join(paths))
    return md


def test_birakilan_dosya_yol_yazmaz_kart_olur(win, tmp_path, png):
    app, w = win
    comp = w.session.composer
    note = tmp_path / "notlar.txt"
    note.write_text("merhaba dünya", encoding="utf-8")
    comp.edit.insertFromMimeData(_mime_files([str(note), png]))
    assert comp.edit.toPlainText() == ""                     # adres metne yazılmadı
    items = comp.attachments.items()
    assert [a.kind for a in items] == ["file", "image"]
    assert items[0].path == str(note)                        # yol arka planda
    assert items[1].path != png and items[1].path.startswith(str(tmp_path / "data"))   # kopya
    assert comp.attachments.isVisibleTo(comp)
    # aynı dosya ikinci kez eklenmez; kaldırma çalışır
    comp.edit.insertFromMimeData(_mime_files([str(note)]))
    assert len(comp.attachments.items()) == 2
    comp.attachments.remove(items[0])
    assert [a.kind for a in comp.attachments.items()] == ["image"]


def test_panodan_gorsel_ve_metin_yapistirma(win):
    from PySide6.QtCore import QMimeData
    from PySide6.QtGui import QColor, QImage

    app, w = win
    comp = w.session.composer
    img = QImage(3000, 1000, QImage.Format_RGB32)
    img.fill(QColor("red"))
    md = QMimeData()
    md.setImageData(img)
    comp.edit.insertFromMimeData(md)
    att = comp.attachments.items()[0]
    assert att.kind == "image" and att.name.startswith("ekran-goruntusu")
    stored = QImage(att.path)
    assert max(stored.width(), stored.height()) <= 1568          # küçültüldü
    text = QMimeData()
    text.setText("düz metin")
    comp.edit.insertFromMimeData(text)
    assert comp.edit.toPlainText() == "düz metin"


def test_gorselli_mesaj_auto_ile_gider_ve_gecmiste_gorunur(win, png):
    app, w = win
    s = w.session
    client = Client()
    w.ctx.make_client = lambda log_sink=None: client
    s.new_session()
    s.welcome._choose(None)
    assert s.model == "auto"
    s.add_files([png])
    s.composer.set_text("bu ne renk?")
    s.composer._submit()
    assert _wait(app, lambda: not s.running and client.calls)
    user = [m for m in client.calls[0]["messages"] if m["role"] == "user"][-1]
    assert user["_images"] and user["content"] == "bu ne renk?"
    assert s.composer.attachments.items() == []
    saved = [m for m in w.ctx.db.get_session_messages(s.session_id) if m["role"] == "user"][0]
    assert saved["meta"]["images"] and saved["meta"]["attachments"][0]["kind"] == "image"
    s.open_session(s.session_id)                               # yeniden çizim: ek şeridi
    from evren_studio.ui.transcript import UserMessageWidget

    ws = [x for x in s.transcript.findChildren(UserMessageWidget)]
    assert ws and ws[-1].attachments and ws[-1].attachments[0].kind == "image"


def test_gorsel_okuyamayan_motorda_uyari(win, png, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    app, w = win
    s = w.session
    client = Client()
    w.ctx.make_client = lambda log_sink=None: client
    s.new_session()
    s.welcome._choose(None)
    s.composer.set_model("glm-5.3", emit=True)
    s.add_files([png])
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    s.composer.set_text("bak")
    s.composer._submit()
    assert client.calls == [] and s.composer.edit.toPlainText() == "bak"
    assert len(s.composer.attachments.items()) == 1          # ek geri kondu
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    s.composer.edit.clear()
    s.composer.set_text("bak")
    s.composer._submit()
    assert _wait(app, lambda: not s.running and client.calls)
    assert s.model == "auto" and client.calls[0]["model"] == "auto"


def test_dosya_eki_icerigi_modele_gider(win, tmp_path):
    app, w = win
    s = w.session
    client = Client()
    w.ctx.make_client = lambda log_sink=None: client
    s.new_session()
    s.welcome._choose(None)
    txt = tmp_path / "rapor.csv"
    txt.write_text("ad,yaş\nAli,30\n", encoding="utf-8")
    binf = tmp_path / "veri.bin"
    binf.write_bytes(b"\x00\x01\x02" * 10)
    s.add_files([str(txt), str(binf)])
    s.composer._submit()                                       # yalnız ek, metin yok
    assert _wait(app, lambda: not s.running and client.calls)
    content = [m for m in client.calls[0]["messages"] if m["role"] == "user"][-1]["content"]
    assert "### rapor.csv" in content and "Ali,30" in content
    assert "### veri.bin" in content and "ikili dosya" in content
    from evren_studio.ui.transcript import UserMessageWidget

    um = s.transcript.findChildren(UserMessageWidget)[-1]
    assert len(um.attachments) == 2 and "📎" not in um.text


def test_duzenlemede_ekler_geri_gelir(win, png):
    app, w = win
    s = w.session
    client = Client()
    w.ctx.make_client = lambda log_sink=None: client
    s.new_session()
    s.welcome._choose(None)
    s.add_files([png])
    s.composer.set_text("ilk")
    s.composer._submit()
    assert _wait(app, lambda: not s.running and client.calls)
    mid = [m for m in w.ctx.db.get_session_messages(s.session_id) if m["role"] == "user"][0]["id"]
    s.edit_message(mid, "ilk")
    assert len(s.composer.attachments.items()) == 1


def test_kullanim_dugmesi_ve_paneli(win):
    from evren_studio.ui.usage_popup import UsageSnapshot, fmt_pct, fmt_time, fmt_tokens

    app, w = win
    s = w.session
    chip = s.composer.usage_btn
    assert chip.text() == "Kullanım"                           # henüz veri yok
    client = Client(quota=QUOTA)
    w.ctx.make_client = lambda log_sink=None: client
    s.refresh_usage()
    assert _wait(app, lambda: chip.snapshot.quota is not None)
    assert chip.text() == "%90" and "13,50 M" in chip.toolTip()
    chip.open_panel()
    texts = " ".join(lab.text() for lab in chip.panel.findChildren(__import__("PySide6.QtWidgets",
                                                                              fromlist=["QLabel"]).QLabel))
    for part in ("Günlük token kotası", "13,50 M", "5 dakikalık hız penceresi", "Kalan: 1.020 cr", "Normal"):
        assert part in texts, part
    chip.panel.hide()
    assert _wait(app, lambda: not s._usage_busy)               # panelin açılış yenilemesi bitti
    # hata durumu
    w.ctx.make_client = lambda log_sink=None: Client(quota=None)
    s.refresh_usage()
    assert _wait(app, lambda: chip.snapshot.error)
    assert chip.snapshot.quota is QUOTA                       # son iyi veri korunur
    assert fmt_tokens(10_060) == "10,1 B" and fmt_tokens(950) == "950" and fmt_pct(0.999) == "%99,9"
    assert fmt_time(None) == "?"
    assert UsageSnapshot().quota is None


def test_kullanim_ucretli_modelde_butce_gosterir(win):
    app, w = win
    s = w.session
    w.ctx._provider_keys["anthropic"] = "sk-ant-api03-SAHTE1234567890abcdef"
    s.composer.set_model("claude-haiku-5-5", emit=True)
    w.ctx.db.add_usage_cost("anthropic", "claude-haiku-5-5", {}, 1.25)
    snap = s._usage_snapshot()
    assert snap.paid_name == "Anthropic" and snap.paid_spent == pytest.approx(1.25) and snap.paid_limit == 5.0
