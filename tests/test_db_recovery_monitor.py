"""Veritabanı, kurtarma ve izleme ajanı testleri."""
from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest

from evren_studio.api.client import EvrenClient
from evren_studio.api.errors import ApiError, ErrorKind
from evren_studio.db import Database, ErrorRecord
from evren_studio.monitor import (
    MonitorAgent,
    _hash_content,
    _meaningful_diff,
    _visible_text,
)
from evren_studio.recovery import RecoveryEngine


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    yield database
    database.close()


# ---- veritabanı ------------------------------------------------------------


def test_sohbet_kaydi_ve_disa_aktarma(db):
    cid = db.create_chat("glm-5.3")
    db.rename_chat(cid, "Test sohbeti")
    db.add_message(cid, "user", "Merhaba")
    db.add_message(cid, "assistant", "Selam!", model="glm-5.3")
    msgs = db.get_messages(cid)
    assert len(msgs) == 2
    md = db.export_chat_markdown(cid)
    assert "# Test sohbeti" in md
    assert "Merhaba" in md and "Selam!" in md


def test_sohbet_arama(db):
    db.create_chat("glm-5.3", "Alfa sohbet")
    db.create_chat("glm-5.3", "Beta sohbet")
    assert len(db.list_chats("Alfa")) == 1
    assert len(db.list_chats("")) == 2


def test_sohbet_silme(db):
    cid = db.create_chat("glm-5.3")
    db.add_message(cid, "user", "x")
    db.delete_chat(cid)
    assert db.get_messages(cid) == []
    assert db.list_chats() == []


def test_hata_kaydi_ve_imza_aramasi(db):
    engine = RecoveryEngine(db, "0.1.0")
    err = ApiError(kind=ErrorKind.SERVER_UNAVAILABLE, message="sağlıklı endpoint yok",
                   status=503, operation="chat_completions", model="glm-5.3")
    eid = engine.record_error(err, monitor_state="izleme kapalı")
    db.update_error_fix(eid, "30 sn bekleyip yeniden dendi", "başarılı", "-")

    err2 = ApiError(kind=ErrorKind.SERVER_UNAVAILABLE, message="yine yok",
                    status=503, operation="chat_completions", model="glm-5.3")
    advice = engine.advise(err2)
    assert advice.past_success, "Geçmiş başarılı çözüm bulunmalı"
    assert any("işe yaramış çözüm" in s for s in advice.recommended_steps)
    assert advice.source_guess.startswith("muhtemel sağlayıcı")


def test_basarisiz_cozum_tekrar_onerilmez(db):
    engine = RecoveryEngine(db, "0.1.0")
    err = ApiError(kind=ErrorKind.AUTH, message="401", status=401,
                   operation="chat_completions", model="glm-5.3")
    eid = engine.record_error(err)
    db.update_error_fix(eid, "anahtar yeniden girildi", "başarısız — anahtar geçersiz", "-")

    advice = engine.advise(err)
    assert advice.past_failures, "Başarısız çözüm kaydı görünmeli"
    assert any("tekrar denemeyin" in s for s in advice.recommended_steps)


def test_eski_hata_kayitlari_temizlenir(db):
    from datetime import datetime, timedelta, timezone

    old = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat(
        timespec="seconds"
    )
    db.add_error(ErrorRecord(operation="x", message="eski", created_at=old))
    db.add_error(ErrorRecord(operation="y", message="yeni"))
    n = db.purge_old_errors(90)
    assert n == 1
    assert len(db.list_errors()) == 1


def test_model_sagligi_kaydi(db):
    db.upsert_model_health("glm-5.3", False, 503, "sağlıklı endpoint yok", None)
    db.upsert_model_health("glm-5.3", True, 200, None, 850)
    h = db.get_model_health("glm-5.3")
    assert h["healthy"] == 1
    assert h["latency_ms"] == 850
    assert h["last_error"] is None


# ---- izleme: içerik analizi ---------------------------------------------------


def test_gorunur_metin_cikarma():
    html = ("<html><head><title>Duyurular</title>"
            "<script>var x=1;</script></head>"
            "<body><div>Bakım çalışması 20:00'de</div></body></html>")
    text = _visible_text(html)
    assert "TITLE: Duyurular" in text
    assert "Bakım çalışması" in text
    assert "var x" not in text, "Betik içeriği metne KARIŞMAMALI"


def test_anlamli_fark_tespiti():
    old = "TITLE: EVREN\nBODY: her şey normal"
    new = "TITLE: EVREN\nBODY: bakım duyurusu yayımlandı"
    diff = _meaningful_diff(old, new)
    assert diff is not None
    assert "bakım duyurusu" in diff


def test_fark_yoksa_none():
    assert _meaningful_diff("a b c", "a b c") is None


def test_hash_farkli_icerik_farkli_hash():
    assert _hash_content("x") != _hash_content("y")


# ---- izleme ajanı ----------------------------------------------------------------


class RecordingAgent(MonitorAgent):
    """Ağ yerine kayıtlı sonuçlar üreten test ajanı."""

    def __init__(self, *a, page_html="OK", page_status=200, **kw):
        super().__init__(*a, **kw)
        self._page_html = page_html
        self._page_status = page_status

    def _single_round(self):
        ok = 200 <= self._page_status < 300
        text = _visible_text(self._page_html) if ok else ""
        h = _hash_content(text) if ok else None
        change = False
        summary = None
        if ok and self.last_text is not None and h != self.last_hash:
            summary = _meaningful_diff(self.last_text, text)
            change = bool(summary)
        if ok:
            self.last_text, self.last_hash = text, h
        self._record(type("R", (), {
            "kind": "announcement", "ok": ok,
            "detail": f"HTTP {self._page_status}",
            "content_hash": h, "change_detected": change,
            "change_summary": summary, "checked_at": "",
        })())


def test_tek_tur_kayitlari(db):
    agent = RecordingAgent(db, "https://ornek.test/")
    sid = agent.start()
    agent.stop("stopped_by_user")
    checks = db.list_monitor_checks(sid)
    assert len(checks) == 1
    assert checks[0]["kind"] == "announcement"
    assert checks[0]["ok"] == 1


def test_icerik_degisikligi_tespit_edilir(db):
    agent = RecordingAgent(db, "https://ornek.test/",
                           page_html="<title>Duyuru</title><body>durum: normal</body>")
    sid = agent.start()
    agent._page_html = "<title>Duyuru</title><body>durum: BAKIM VAR</body>"
    agent._single_round()
    agent.stop("stopped_by_user")
    checks = db.list_monitor_checks(sid)
    assert len(checks) == 2
    assert checks[0]["change_detected"] == 0, "İlk kontrolde değişiklik olmaz"
    assert checks[1]["change_detected"] == 1
    assert "BAKIM" in checks[1]["change_summary"]


def test_ayni_icerik_yeni_olay_yazmaz(db):
    agent = RecordingAgent(db, "https://ornek.test/", page_html="<title>A</title>")
    sid = agent.start()
    agent._single_round()  # aynı içerik
    agent._single_round()  # aynı içerik
    agent.stop("stopped_by_user")
    checks = db.list_monitor_checks(sid)
    assert len(checks) == 3
    assert all(c["change_detected"] == 0 for c in checks), \
        "Değişmeyen duyuru yeni olay olarak yazılmamalı (yalnız kayıt edilir)"


def test_sayfa_erisilemezse_guvenli_davranis(db):
    agent = RecordingAgent(db, "https://ornek.test/", page_status=503)
    sid = agent.start()
    agent.stop("stopped_by_user")
    checks = db.list_monitor_checks(sid)
    assert checks[0]["ok"] == 0
    assert "503" in checks[0]["detail"]


def test_kapanma_sonrasi_devam_secenegi(db):
    agent = RecordingAgent(db, "https://ornek.test/")
    sid = agent.start()
    # Uygulama kapanmış simülasyonu: oturum 'running' kalır
    open_row = db.get_open_monitor_session()
    assert open_row is not None
    assert open_row["id"] == sid
    agent.stop("app_closed")
    assert db.get_open_monitor_session() is None


def test_dongu_30_dakika_planina_uyar(db):
    """interval=5dk/duration=30dk → 7 tur planı; hızlandırılmış simülasyon."""
    agent = RecordingAgent(db, "https://ornek.test/")
    assert agent.interval_seconds == 5 * 60
    assert agent.duration_seconds == 30 * 60
    # Hızlandır: 0.05 sn aralıkla 0.3 sn sürsün → ~7 tur
    agent.interval_seconds = 0.05
    agent.duration_seconds = 0.3
    sid = agent.start()
    deadline = time.monotonic() + 5
    while agent.is_running() and time.monotonic() < deadline:
        time.sleep(0.05)
    agent.stop("completed")
    checks = db.list_monitor_checks(sid)
    assert 5 <= len(checks) <= 9, \
        f"30 dk / 5 dk planı ~7 kontrol üretmeli (başlangıç dahil); {len(checks)} oldu"
    session = db.conn.execute(
        "SELECT * FROM monitor_sessions WHERE id=?", (sid,)
    ).fetchone()
    assert session["status"] in ("completed", "stopped_by_user")


def test_rapor_icerigi(db):
    agent = RecordingAgent(db, "https://ornek.test/",
                           page_html="<title>EVREN</title><body>normal</body>")
    agent.start()
    agent._page_html = "<title>EVREN</title><body>BAKIM DUYURUSU</body>"
    agent._single_round()
    report = agent.build_report()
    md = agent.report_markdown(report)
    assert "EVREN Durum İzleme Raporu" in md
    assert "İzlenen sayfa" in md
    assert any("BAKIM" in c for c in report.changes)
    assert "Kesin Bulgular" in md
    assert "Tahmine Dayalı Bulgular" in md
    assert "Önerilen Sonraki Adım" in md
    agent.stop("stopped_by_user")


# ---- gerçek izleme turları (sahte HTTP) ---------------------------------------------


def test_gercek_tur_sahte_http_ile(db):
    """_single_round gerçek httpx taşınmasına gider: duyuru + healthz."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "ornek.test" in str(request.url):
            return httpx.Response(200, text="<html><title>Sayfa</title></html>")
        if request.url.path == "/healthz":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/readyz":
            return httpx.Response(200, json={"status": "ready"})
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"object": "list", "data": []})
        raise AssertionError(f"beklenmeyen istek: {request.url}")

    transport = httpx.MockTransport(handler)
    # Duyuru sayfası httpx'e doğrudan gider; agent bunu kendi client'ıyla
    # değil ayrı istemciyle yapar → monkeypatch ile transport takılır.
    import evren_studio.monitor as mon

    original_client_init = httpx.Client.__init__

    def patched_init(self, *a, **kw):
        kw.setdefault("transport", transport)
        original_client_init(self, *a, **kw)

    httpx.Client.__init__ = patched_init
    try:
        client = EvrenClient("https://api.test/v1", "k", transport=transport)
        agent = MonitorAgent(db, "https://ornek.test/", interval_minutes=5,
                             duration_minutes=30, client=client)
        sid = agent.start()
        agent._single_round()
        agent.stop("stopped_by_user")
    finally:
        httpx.Client.__init__ = original_client_init

    checks = db.list_monitor_checks(sid)
    kinds = {c["kind"] for c in checks}
    assert kinds == {"announcement", "healthz", "readyz", "models"}
    assert all(c["ok"] == 1 for c in checks)
