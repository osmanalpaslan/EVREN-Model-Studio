"""Uygulama yapılandırması.

Ayarlar %LOCALAPPDATA%\\EVREN-Model-Studio\\config.json içinde saklanır.
API anahtarı asla buraya yazılmaz; secrets.py üzerinden Windows Credential
Manager'a gider.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def default_data_dir() -> Path:
    """Uygulama verileri için varsayılan kök dizin."""
    base = os.environ.get("EVREN_STUDIO_DATA_DIR")
    if base:
        return Path(base)
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "EVREN-Model-Studio"


DEFAULT_BASE_URL = "https://evren-llmapi.ssyz.org.tr/v1"
DEFAULT_ANNOUNCEMENT_URL = "https://evren.ssyz.org.tr/"

TASK_LABELS = {
    "chat": "Sohbet",
    "vision_chat": "Görsel Sohbet",
    "embedding": "Metin Vektörü (Embedding)",
    "rerank": "Yeniden Sıralama (Rerank)",
    "ocr": "Görselden Metin (OCR)",
    "audio_transcription": "Ses Yazıya Çevirme (ASR)",
    "guard": "Güvenlik Sınıflandırma",
    "decision": "Karar (choice/score)",
}


SETTINGS_VERSION = 2
# Eski sürümün varsayılanı: kullanıcı değiştirmediyse yeni varsayılana taşınır.
_OLD_DEFAULT_MODEL = "glm-5.3"


def migrate_raw(raw: dict[str, Any]) -> dict[str, Any]:
    """config.json'u güncel sürüme taşır (yalnız eski VARSAYILAN değerleri değiştirir)."""
    version = raw.get("settings_version", 1)
    if not isinstance(version, int):
        version = 1
    if version < 2 and raw.get("default_model", _OLD_DEFAULT_MODEL) == _OLD_DEFAULT_MODEL:
        # Eski sürüm varsayılanı her zaman dosyaya yazıyordu; glm-5.3 bilerek seçilmiş
        # olabilir ama ayırt edilemez. Kullanıcı kararı (2026-10-16): varsayılan auto.
        raw["default_model"] = "auto"
    raw["settings_version"] = max(version, SETTINGS_VERSION)
    return raw


@dataclass
class Settings:
    """Kalıcı uygulama ayarları (API anahtarı HARİÇ)."""

    base_url: str = DEFAULT_BASE_URL
    announcement_url: str = DEFAULT_ANNOUNCEMENT_URL
    # "auto" = EVREN yönlendiricisi her istek için uygun modeli seçer (2026-10-16
    # ölçümü: gemma-4-31b / qwen3.8-flash-next'e yönlendirdi). Kullanıcı model
    # seçiciden veya Ayarlar'dan değiştirebilir.
    default_model: str = "auto"
    task_model_preferences: dict[str, str] = field(default_factory=dict)
    auto_model_switch: bool = False
    timeout_seconds: float = 120.0
    max_retries: int = 3
    stream_responses: bool = True
    theme: str = "koyu"
    font_size: int = 10
    error_log_retention_days: int = 90
    automation_level: str = "onayli"
    monitor_interval_minutes: int = 5
    monitor_duration_minutes: int = 30
    monitor_real_model_test: bool = False
    monitor_test_model: str = "glm-5.3"
    data_dir: str = ""
    code_workdir: str = ""
    # ---- kod ajanı / çalışma alanı ----
    agent_mode: str = "manuel"              # manuel | kabul | plan | auto (eski: onayli/otomatik)
    tool_protocol: str = "otomatik"         # otomatik | yerel | metin
    agent_max_steps: int = 40
    command_timeout_seconds: int = 120
    tool_output_limit: int = 20000
    recent_workspaces: list[str] = field(default_factory=list)
    # Otomatik özet (compaction.py): eşik = min(bağlamın %percent'i, max_tokens)
    auto_compact: bool = True
    auto_compact_percent: int = 75
    auto_compact_max_tokens: int = 100_000
    # Özeti üreten model ("" = oturumun modeli). Ölçüm 2026-10-16: aynı özet
    # glm-5.3 ile 153 sn, deepseek-v4-flash ile 41 sn, kalite eşdeğer.
    auto_compact_model: str = "deepseek-v4-flash"
    # Ücretli sağlayıcılar (OpenAI/Anthropic) için aylık TAHMİNİ bütçe (USD, tüm sağlayıcılar toplamı)
    monthly_budget_usd: float = 5.0
    budget_enforce: bool = True             # sınıra gelince her yeni istekten önce onay iste
    show_reasoning: bool = True
    sidebar_visible: bool = True
    panel_visible: bool = True
    send_with_enter: bool = True
    # Ayar dosyası sürümü (taşıma için). 2: varsayılan model glm-5.3 → auto.
    settings_version: int = SETTINGS_VERSION

    def resolved_data_dir(self) -> Path:
        return Path(self.data_dir) if self.data_dir else default_data_dir()

    def remember_workspace(self, path: str) -> None:
        items = [p for p in self.recent_workspaces if p.lower() != path.lower()]
        self.recent_workspaces = [path] + items[:9]
        self.code_workdir = path


class ConfigStore:
    """config.json okuma/yazma; bozulmuş dosyada güvenli geri dönüş."""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or default_data_dir()
        self.path = self.data_dir / "config.json"

    def load(self) -> Settings:
        if not self.path.exists():
            return Settings()
        try:
            raw: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Bozuk dosya: varsayılanlarla devam, dosyayı olduğu gibi bırak.
            return Settings()
        if not isinstance(raw, dict):
            return Settings()
        raw = migrate_raw(raw)
        known = {f for f in Settings.__dataclass_fields__}
        filtered = {k: v for k, v in raw.items() if k in known}
        return Settings(**filtered)

    def save(self, settings: Settings) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(asdict(settings), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(self.path)
