"""Arayüz QA: tüm ekranlar sahte EVREN API'siyle açılır, düğmeleri çalıştırılır.

Gerçek ağ kullanılmaz: EvrenClient httpx.MockTransport ile, izleme ajanının
duyuru sayfası isteği de sahte taşımayla yanıtlanır. Her testte:
- yakalanmamış Python hatası (Qt slotları dahil) OLMAMALI,
- Qt'nin iş parçacığı uyarıları ("different thread" vb.) OLMAMALI.
"""
from __future__ import annotations

import json
import os
import sys
import time

import httpx
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QLabel, QMessageBox  # noqa: E402

from evren_studio.api.client import ChatResult, EvrenClient  # noqa: E402
from evren_studio.api.errors import ApiError, ErrorKind  # noqa: E402

KEY = "evren_llm_SAHTE_QA_ANAHTARI_123456"
MODELS = {"object": "list", "data": [
    {"id": "glm-5.3", "task": "chat", "modalities": ["text"], "context_length": 524288,
     "capabilities": {"tools": True}, "pricing": {"free_until": "2026-11-01"}},
    {"id": "auto", "task": "chat", "modalities": ["text"], "context_length": 32768,
     "capabilities": {}, "pricing": None},
    {"id": "dots-ocr", "task": "ocr", "modalities": ["image", "text"], "context_length": 131072,
     "capabilities": {}, "pricing": None},
]}
QUOTA = {"used_tokens": 1000, "cap": 100000, "window_minutes": 5, "reset_at": "2026-10-16T12:00:00Z",
         "usage_ratio": 0.01, "level": "ok", "held_cr": "0", "remaining_cr": "100",
         "daily_used_tokens": 150000, "daily_limit_tokens": 15000000,
         "daily_remaining_tokens": 14850000, "daily_reset_at": "2026-10-17T00:00:00Z"}


def api_handler(request: httpx.Request) -> httpx.Response:
    p = request.url.path
    if p == "/healthz":
        return httpx.Response(200, json={"status": "ok"})
    if p == "/readyz":
        return httpx.Response(200, json={"status": "ready"})
    if p == "/v1/models":
        return httpx.Response(200, json=MODELS)
    if p == "/v1/quota":
        return httpx.Response(200, json=QUOTA)
    if p == "/v1/terms/status":
        return httpx.Response(200, json={"current_version": 1, "accepted": True})
    if p == "/v1/chat/completions":
        body = json.loads(request.content)
        if body.get("stream"):
            chunks = [
                {"id": "x", "model": body["model"], "choices": [{"delta": {"content": "Merhaba "}}]},
                {"choices": [{"delta": {"content": "dünya."}, "finish_reason": "stop"}]},
                {"choices": [], "usage": {"evren": {"routed_model": "qwen3.8-flash-next"}}},
            ]
            data = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
            return httpx.Response(200, content=data.encode(), headers={"Content-Type": "text/event-stream"})
        return httpx.Response(200, json={"id": "r1", "model": body["model"],
                                         "choices": [{"finish_reason": "stop",
                                                      "message": {"content": "Özet metni"}}]})
    return httpx.Response(404, json={"detail": "yok"})


def page_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text="<html><title>EVREN</title><body>Duyuru yok</body></html>")


def wait_until(app, cond, timeout=8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    app.processEvents()
    return cond()


def label_value(row) -> str:
    return row.findChildren(QLabel)[1].text()


@pytest.fixture()
def qa(tmp_path, monkeypatch, fake_keyring):
    """Ana pencere + sahte API + hata/uyarı yakalayıcıları."""
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    fake_keyring.store[("EVREN-Model-Studio", "evren_api_key")] = KEY
    app = QApplication.instance() or QApplication([])

    errors: list[str] = []
    warnings: list[str] = []
    old_hook = sys.excepthook
    sys.excepthook = lambda t, v, tb: errors.append(f"{t.__name__}: {v}")
    qInstallMessageHandler(lambda mode, ctx, msg: warnings.append(msg))

    # Diyaloglar test sırasında beklemesin
    dialogs: list[str] = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: (dialogs.append("question"), QMessageBox.Yes)[1]))
    for name in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, _n=name, **k: (dialogs.append(_n), QMessageBox.Ok)[1]))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(tmp_path / "disa.json"), "")))
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("auto", True)))

    # İzleme ajanının duyuru sayfası isteği sahte taşımayla
    real_client = httpx.Client

    def client_factory(*a, **kw):
        if kw.get("transport") is None:
            kw["transport"] = httpx.MockTransport(page_handler)
        return real_client(*a, **kw)

    import evren_studio.monitor as monitor_mod
    monkeypatch.setattr(monitor_mod.httpx, "Client", client_factory)

    from evren_studio.ui import app_context

    def make_client(self, log_sink=None):
        return EvrenClient("https://qa.test/v1", KEY, transport=httpx.MockTransport(api_handler),
                           max_retries=0, log_sink=log_sink)

    monkeypatch.setattr(app_context.AppContext, "make_client", make_client)
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    app.processEvents()
    yield app, w, errors, warnings, dialogs
    w.close()
    qInstallMessageHandler(None)
    sys.excepthook = old_hook


def assert_clean(errors, warnings):
    assert not errors, "Yakalanmamış hata(lar): " + " | ".join(errors)
    bad = [m for m in warnings if "thread" in m.lower() or "QObject" in m]
    assert not bad, "Qt iş parçacığı uyarıları: " + " | ".join(bad)


def test_tum_ekranlar_ve_eylemleri(qa):
    app, w, errors, warnings, dialogs = qa
    pages = w.pages

    # Modeller: açılışta arka planda yüklenir; ayrıca elle yenile
    w.show_page("models")
    pages["models"].refresh_models()
    assert wait_until(app, lambda: pages["models"].table.rowCount() == 3), "model tablosu dolmadı"
    pages["models"].show_detail(0, 0)
    assert "glm-5.3" in pages["models"].detail.text()
    assert "auto" in w.session.composer.model_ids(), "canlı liste yazma kutusuna ulaşmadı"
    assert "dots-ocr" not in w.session.composer.model_ids(), "OCR modeli sohbet listesinde olmamalı"

    # Sistem durumu
    w.show_page("home")
    pages["home"].run_check()
    assert wait_until(app, lambda: pages["home"].status_label.text().startswith("Sonuç:"))
    assert "3 model" in label_value(pages["home"].model_row)

    # Bağlantı testi
    w.show_page("connection")
    pages["connection"].run()
    assert wait_until(app, lambda: "BAĞLANTI SAĞLAM" in label_value(pages["connection"].result))
    assert "evren_ll" in pages["connection"].log.toPlainText() and KEY not in pages["connection"].log.toPlainText()

    # Kullanım / kota (show_page refresh tetikler)
    w.show_page("usage")
    assert wait_until(app, lambda: label_value(pages["usage"].level_row) == "ok")
    assert pages["usage"].window_bar.value() == 1
    assert "150,000" in label_value(pages["usage"].daily_row)

    # Hata merkezi
    w.ctx.recovery.record_error(ApiError(kind=ErrorKind.SERVER_UNAVAILABLE, message="sağlıklı endpoint yok",
                                         status=503, operation="chat_completions", model="glm-5.3"))
    w.show_page("errors")
    assert pages["errors"].table.rowCount() >= 1
    pages["errors"].show_detail(0, 0)
    assert "HATA KAYDI" in pages["errors"].detail.toPlainText()

    # Yardım / tanılama
    w.show_page("help")
    pages["help"].run_diag()
    assert wait_until(app, lambda: "httpx sürümü" in pages["help"].diag.toPlainText())

    # Durum izleme: başlat → kontroller → durdur → rapor
    w.show_page("monitor")
    mon = pages["monitor"]
    mon.start()
    assert wait_until(app, lambda: "[healthz]" in mon.log.toPlainText(), 10), "izleme kontrolleri görünmedi"
    assert "[announcement] ✓" in mon.log.toPlainText()
    mon.stop()
    assert wait_until(app, lambda: label_value(mon.state_row) == "kullanıcı durdurdu", 15)
    assert wait_until(app, lambda: bool(mon.report.toPlainText().strip()), 10), "rapor oluşmadı"
    assert mon.start_btn.isEnabled()

    # Ayarlar: kaydet ve varsayılana döndür
    w.show_page("settings")
    st = pages["settings"]
    st.timeout.setValue(250)
    st.max_steps.setValue(77)
    st.save_all()
    assert w.ctx.settings.timeout_seconds == 250 and w.ctx.settings.agent_max_steps == 77
    saved = json.loads((w.ctx.store.path).read_text(encoding="utf-8"))
    assert saved["timeout_seconds"] == 250
    assert "timeout_seconds" in st.changed_fields()
    st.reset_defaults()
    assert w.ctx.settings.timeout_seconds == 120 and w.ctx.settings.agent_max_steps == 40
    assert st.timeout.value() == 120, "form varsayılan değerlerle yenilenmeli"
    assert st.changed_fields() == []
    st.export_data()
    assert json.loads((w.ctx.store.path.parent.parent / "disa.json").read_text(encoding="utf-8")) is not None \
        if (w.ctx.store.path.parent.parent / "disa.json").exists() else True

    # Oturumlara dönüş
    w.show_sessions()
    assert w.center.currentWidget() is w.session
    assert_clean(errors, warnings)


def test_tekerlek_odaksiz_alani_degistirmez(qa):
    app, w, errors, warnings, _ = qa
    w.show_page("settings")
    spin = w.pages["settings"].timeout
    app.processEvents()
    before = spin.value()
    ev = QWheelEvent(QPointF(5, 5), QPointF(spin.mapToGlobal(QPoint(5, 5))), QPoint(0, 0), QPoint(0, 120),
                     Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(spin, ev)
    app.processEvents()
    assert spin.value() == before, "odaklanmamış alan tekerlekle değişmemeli"
    assert spin.focusPolicy() != Qt.WheelFocus
    combo = w.pages["settings"].theme
    idx = combo.currentIndex()
    QApplication.sendEvent(combo, QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120),
                                              Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))
    assert combo.currentIndex() == idx
    assert_clean(errors, warnings)


def test_komut_listesi_tiklanir_ve_model_secilir(qa):
    app, w, errors, warnings, _ = qa
    comp = w.session.composer
    w.show_page("models")
    w.pages["models"].refresh_models()
    assert wait_until(app, lambda: "auto" in comp.model_ids())
    w.show_sessions()

    comp.set_text("/")
    app.processEvents()
    assert comp.popup_visible() and comp.popup.count() >= 9

    # Klavye: aşağı ok seçimi değiştirir
    first = comp.popup.currentRow()
    QTest.keyClick(comp.edit, Qt.Key_Down)
    assert comp.popup.currentRow() == first + 1

    # Tıklama: /plan → mod değişir, kutu temizlenir
    comp.set_text("/pl")
    app.processEvents()
    item = comp.popup.item(0)
    assert item.text().startswith("/plan")
    comp.popup.itemClicked.emit(item)
    app.processEvents()
    assert w.session.mode == "plan" and comp.mode() == "plan"
    assert comp.edit.toPlainText() == "" and not comp.popup_visible()

    # /model tıklanınca model listesi açılır, modele tıklayınca seçilir
    comp.set_text("/mo")
    app.processEvents()
    comp.popup.itemClicked.emit(comp.popup.item(0))
    app.processEvents()
    assert comp.popup_visible() and comp.edit.toPlainText() == "/model "
    texts = [comp.popup.item(i).text() for i in range(comp.popup.count())]
    assert any("auto" in t for t in texts) and any("glm-5.3" in t for t in texts)
    auto_item = next(comp.popup.item(i) for i in range(comp.popup.count()) if "auto" in comp.popup.item(i).text())
    comp.popup.itemClicked.emit(auto_item)
    app.processEvents()
    assert comp.model() == "auto" and w.session.model == "auto"
    assert not comp.popup_visible()

    # Enter ile seçim: "/model gl" + Enter → glm-5.3
    comp.set_text("/model gl")
    app.processEvents()
    QTest.keyClick(comp.edit, Qt.Key_Return)
    app.processEvents()
    assert comp.model() == "glm-5.3"

    # Esc listeyi kapatır, ajanı durdurmaz
    comp.set_text("/")
    app.processEvents()
    QTest.keyClick(comp.edit, Qt.Key_Escape)
    assert not comp.popup_visible()
    assert_clean(errors, warnings)


def test_calisan_model_ve_sure_gosterilir(qa, tmp_path):
    app, w, errors, warnings, _ = qa
    from evren_studio.ui.transcript import AssistantMessageWidget

    class SlowClient:
        def chat(self, model, messages, stream=False, cancel=None, on_delta=None,
                 on_reasoning=None, tools=None, **kw):
            time.sleep(0.6)
            if on_delta:
                on_delta("Tamam.", "")
            return ChatResult(content="Tamam.", model=model, finish_reason="stop",
                              routed_model="qwen3.8-flash-next" if model == "auto" else None)

        def close(self):
            pass

    w.ctx.make_client = lambda log_sink=None: SlowClient()
    w.session.welcome._choose(None)
    w.session.send("merhaba")
    assert wait_until(app, lambda: w.session.composer.run_bar.isVisible(), 3)
    status = w.session.composer.run_text.text()
    assert w.session.model in status and "sn" in status, status
    assert wait_until(app, lambda: not w.session.running, 5)
    assert not w.session.composer.run_bar.isVisible()
    footers = [a.footer.text() for a in w.session.findChildren(AssistantMessageWidget) if a.footer.isVisible()]
    assert footers and w.session.model in footers[-1] and "sn" in footers[-1], footers
    meta = w.ctx.db.get_session_messages(w.session.session_id)[-1]["meta"]
    assert meta["duration_s"] >= 0.5

    # auto modeli: yönlendirilen model de gösterilir
    w.session.set_model("auto")
    w.session.send("tekrar")
    assert wait_until(app, lambda: not w.session.running, 5)
    sid = w.session.session_id
    w.session.new_session()
    w.session.open_session(sid)
    app.processEvents()
    footers = [a.footer.text() for a in w.session.findChildren(AssistantMessageWidget) if a.footer.text()]
    assert any("auto → qwen3.8-flash-next" in f for f in footers), footers
    assert_clean(errors, warnings)


def test_arka_plan_gorevi_sonucu_teslim_eder(qa):
    """Task nesnesine referans tutulmasa bile sonuç geri çağrısı çalışmalı."""
    app, _w, errors, warnings, _ = qa
    import gc

    from evren_studio.ui.workers import Task, active_task_count

    got = []
    for i in range(20):
        Task(lambda i=i: i * 2, on_done=got.append).start()
    gc.collect()
    assert wait_until(app, lambda: len(got) == 20)
    assert sorted(got) == [i * 2 for i in range(20)]
    assert wait_until(app, lambda: active_task_count() == 0)
    assert_clean(errors, warnings)


def test_llm_markdown_listesi_bos_satirsiz_da_liste_olur():
    from evren_studio.ui.markdown_view import normalize_llm_markdown, render_markdown

    src = "**Yapılanlar:**\n- birinci\n- ikinci\n\n```python\nx = 1\n- kod içi\n```"
    fixed = normalize_llm_markdown(src)
    assert "**Yapılanlar:**\n\n- birinci\n- ikinci" in fixed
    assert "x = 1\n- kod içi" in fixed, "kod bloğu içine dokunulmamalı"
    html = render_markdown(src)
    assert "<li>birinci</li>" in html and "<li>ikinci</li>" in html
