"""Açılış hızı (Madde 17E) ve Derin Mod paralelliği (Madde 17C), 2026-11-07.

- Ayarlar'daki gözlem kartı durumunu git'e sorarak hesaplıyordu (~0,5 sn) — açılışta, kart görünmeden. Artık ilk
  gösterilişte doldurulur (tetiklenmeyen + tetiklenen, R-22).
- EVREN aynı anahtarla 3 eşzamanlı isteği bekletmiyor (CHALLENGE_RESULTS "auto ↔ Auto Pro") → Derin Mod varsayılan
  paralellik 3: "anla" aşamasının 3 incelemesi tek turda biter. Yalnız eski VARSAYILAN (2) taşınır.
"""
from __future__ import annotations

import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from evren_studio import gozlem  # noqa: E402
from evren_studio.agent import deep  # noqa: E402
from evren_studio.config import Settings, migrate_raw  # noqa: E402


def test_gozlem_karti_acilista_git_e_sormaz_gosterilince_sorar(monkeypatch):
    from PySide6.QtWidgets import QApplication

    from evren_studio.ui.gozlem_card import GozlemCard

    app = QApplication.instance() or QApplication([])
    calls = []
    monkeypatch.setattr(gozlem, "durum", lambda *a, **k: calls.append(1) or
                        {"toplam": 2, "bekleyen": 1, "son_gonderim": "", "son_hata": "", "depo": "x"})
    card = GozlemCard(ctx=None)
    card.refresh()                                         # görünmezken dışarıdan çağrı: ertelenir
    assert calls == []
    card.show()
    app.processEvents()
    assert calls == [1] and "2 gözlem" in card.status.text()
    card.refresh()                                         # görünürken: hemen
    assert calls == [1, 1]
    card.close()


def test_derin_paralellik_varsayilan_3_ve_goc():
    assert Settings().deep_parallel == 3
    assert migrate_raw({"deep_parallel": 2, "settings_version": 5})["deep_parallel"] == 3
    assert migrate_raw({"deep_parallel": 1, "settings_version": 5})["deep_parallel"] == 1      # kullanıcı seçimi
    assert migrate_raw({"deep_parallel": 2, "settings_version": 6})["deep_parallel"] == 2      # bir kez taşınır


def test_uc_inceleme_tek_turda_calisir():
    """3 iş, paralellik 3 → aynı anda; 2 → iki tur (Derin "anla" aşaması: ANGLES 3 tane)."""
    assert len(deep.ANGLES) == 3
    for par, expected in ((3, 3), (2, 2)):
        active, peak = [0], [0]
        lock = threading.Lock()

        def job():
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.05)
            with lock:
                active[0] -= 1
            return 1
        assert deep.run_parallel([job, job, job], None, par) == [1, 1, 1]
        assert peak[0] == expected
