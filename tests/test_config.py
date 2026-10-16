"""Yapılandırma ve varsayılan ayar testleri."""
from __future__ import annotations

import json

from evren_studio.config import ConfigStore, Settings


def test_varsayilan_ayarlar():
    s = Settings()
    assert s.auto_model_switch is False, "Otomatik model değiştirme varsayılan olarak KAPALI olmalı"
    assert s.stream_responses is True
    assert s.timeout_seconds == 120.0
    assert s.max_retries == 3
    assert s.monitor_interval_minutes == 5
    assert s.monitor_duration_minutes == 30
    assert s.base_url == "https://evren-llmapi.ssyz.org.tr/v1"


def test_kaydet_ve_oku(tmp_path):
    store = ConfigStore(tmp_path)
    s = Settings(default_model="auto", timeout_seconds=60.0)
    store.save(s)
    loaded = store.load()
    assert loaded.default_model == "auto"
    assert loaded.timeout_seconds == 60.0


def test_bilinmeyen_alanlar_yoksayilir(tmp_path):
    store = ConfigStore(tmp_path)
    store.save(Settings())
    raw = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    raw["zararli_alan"] = "x"
    raw["default_model"] = "mimo-v2.6-pro"
    (tmp_path / "config.json").write_text(
        json.dumps(raw, ensure_ascii=False), encoding="utf-8"
    )
    loaded = store.load()
    assert loaded.default_model == "mimo-v2.6-pro"
    assert not hasattr(loaded, "zararli_alan")


def test_bozuk_dosya_varsayilana_doner(tmp_path):
    (tmp_path / "config.json").write_text("{bozuk json", encoding="utf-8")
    loaded = ConfigStore(tmp_path).load()
    assert loaded.default_model == Settings().default_model
