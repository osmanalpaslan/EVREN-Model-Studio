"""Auto Pro uyarlanabilir model sırası (kullanıcı kararı 2026-11-01): kullanıcının sırası varsayılan kalır; öndeki
model son saatlerde yedeğinden 2 kattan fazla yavaşsa o gün yedek öne alınır. Ölçüm: 2026-11-01'de
deepseek-v4.1-flash 14,4 sn/100 token, qwen3.8-flash-next 3,7 (21 Ekim'de tersiydi). Tetiklenen/tetiklenmeyen
durumlar ve gerçek tur akışı (R-22, R-31)."""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import pytest

from evren_studio.agent import modelstats, router
from evren_studio.api.client import ChatResult


def rows(model, n, out, dur, **kw):
    return [{"model": model, "ok": 1, "out_tokens": out, "duration_s": dur, "first_chunk_s": 2.0, **kw}
            for _ in range(n)]


def test_etkili_hiz_ilk_parca_dahil_kisa_ve_az_ornek_sayilmaz():
    sp = modelstats.effective_speeds(rows("a", 6, 300, 30) + rows("b", 6, 300, 10) + rows("c", 3, 300, 10)
                                     + rows("d", 6, 50, 1) + rows("e", 6, 300, 1, role=modelstats.PROBE_ROLE))
    assert sp == {"a": 10.0, "b": 30.0}                     # c az örnek, d kısa yanıt, e yoklama


def test_ondeki_belirgin_yavassa_hizli_yedek_one_alinir():
    chain = router.chain_for("kod")
    first, second = chain[0], chain[1]
    r = router.choose("kod", speeds={first: 8.0, second: 30.0})
    assert r.model == second and first in r.fallbacks and "öne alındı" in r.reason


@pytest.mark.parametrize("speeds", [
    {},                                                      # ölçüm yok → kullanıcının sırası
    "esit",                                                  # 2 kattan az fark → değişmez
    "yalniz_ilk",                                            # yedeğin ölçümü yok → değişmez
])
def test_tetiklenmeyen_durumlar_sirayi_degistirmez(speeds):
    chain = router.chain_for("kod")
    first, second = chain[0], chain[1]
    sp = {"esit": {first: 20.0, second: 30.0}, "yalniz_ilk": {first: 5.0}}.get(speeds, speeds) \
        if isinstance(speeds, str) else speeds
    r = router.choose("kod", speeds=sp)
    assert r.model == first and "öne alındı" not in r.reason


def test_sagliksiz_veya_cezali_hizli_model_one_alinmaz():
    chain = router.chain_for("kod")
    first, second = chain[0], chain[1]
    now = datetime.now(timezone.utc)
    health = {second: {"healthy": 0, "last_test_at": now.isoformat()}}
    assert router.choose("kod", speeds={first: 5.0, second: 50.0}, health=health).model == first
    assert router.choose("kod", speeds={first: 5.0, second: 50.0}, penalties={second: "👎"}).model == first


# ---- gerçek tur akışı: kayıtlı çağrılardan hız → koşucunun modeli ------------------------------------

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
    yield app, w, tmp_path
    w.close()


MESAJ = "hesap.py içindeki fonksiyonu düzelt ve testleri çalıştır, iki dosyayı birlikte güncelle"


def _hazirla(w, tmp):
    used: list[str] = []

    class C:
        def chat(self, model, messages, **kw):
            used.append(model)
            return ChatResult(content="tamam", finish_reason="stop")

        def get_quota(self):
            return None

        def close(self):
            pass
    w.ctx.make_client = lambda log_sink=None: C()
    w.ctx.make_client_for = lambda provider, log_sink=None: C()
    s = w.session
    proj = tmp / "proje"
    proj.mkdir(exist_ok=True)
    s.new_session()
    s.welcome._choose(str(proj))
    s.composer.set_model(router.AUTO_PRO_ID, emit=True)
    s.set_mode("auto")
    # klasörlü ajan turu "kod" rolündedir (klasör oturuma ilk mesajda bağlanır; _route'u önceden çağırmak sohbet sayar)
    chain = router.chain_for("kod", w.ctx.available_model_ids() or None)
    return used, router.Route(chain[0], "kod", "", chain[1:])


def _gonder(app, w, used):
    s = w.session
    s.send(MESAJ)
    end = time.monotonic() + 8
    while (s.running or not used) and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)
    return used


def test_tur_akisinda_bugun_yavas_olan_geri_alinir(win):
    app, w, tmp = win
    used, route = _hazirla(w, tmp)
    first, alt = route.model, route.fallbacks[0]
    for _ in range(6):
        w.ctx.db.add_model_call(first, ok=True, duration_s=40.0, first_chunk_s=8.0, out_tokens=300)
        w.ctx.db.add_model_call(alt, ok=True, duration_s=10.0, first_chunk_s=2.0, out_tokens=300)
    _gonder(app, w, used)
    assert used and used[0] == alt, (first, alt, used)


def test_tur_akisinda_olcum_yoksa_kullanici_sirasi(win):
    app, w, tmp = win
    used, route = _hazirla(w, tmp)
    _gonder(app, w, used)
    assert used and used[0] == route.model
