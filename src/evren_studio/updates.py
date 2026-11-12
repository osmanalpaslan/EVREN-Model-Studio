"""Güncelleme denetimi (Madde 20 C2, 2026-11-12; Qt'siz).

GitHub Releases'teki son sürüm (herkese açık depo, kimlik gerekmez; saatte 60 istek sınırı) uygulamanın sürümünden
yeniyse bilgi döner. Uygulama yalnız BİLDİRİR: indirip kurmaz (kullanıcı "İndir"e basınca sürüm sayfası tarayıcıda
açılır; kurulum dosyası kendi imzalıdır). Günde en çok bir kez, arka planda, kısa zaman aşımıyla; ağ yoksa sessizce
geçilir. Taslak (draft) ve ön sürüm (prerelease) önerilmez. Kullanıcı bir sürümü "atla" derse o sürüm bir daha
gösterilmez.
"""
from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

REPO = "osmanalpaslan/EVREN-Model-Studio"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGE = f"https://github.com/{REPO}/releases/latest"
INTERVAL_H = 24
TIMEOUT_S = 8


@dataclass
class UpdateInfo:
    version: str
    url: str                 # sürüm sayfası (tarayıcıda açılır)
    asset_url: str = ""      # kurulum dosyası (Kurulum-*.exe) doğrudan bağlantı
    notes: str = ""          # sürüm notlarının ilk kısmı


def parse_version(text: str) -> tuple[int, ...] | None:
    m = re.match(r"\s*v?(\d+(?:\.\d+){0,3})\s*$", text or "")
    if not m:
        return None
    return tuple(int(x) for x in m.group(1).split("."))


def newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    if a is None or b is None:
        return False
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def due(last_iso: str, now: datetime | None = None, hours: int = INTERVAL_H) -> bool:
    if not last_iso:
        return True
    try:
        last = datetime.fromisoformat(last_iso)
    except ValueError:
        return True
    now = now or datetime.now(timezone.utc)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return now - last >= timedelta(hours=hours) or last > now + timedelta(minutes=5)   # saat geri alındıysa da


def _fetch(url: str = API, timeout: float = TIMEOUT_S) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "EVREN-Studio-update-check"})
    with urllib.request.urlopen(req, timeout=timeout) as r:            # noqa: S310 (sabit https adresi)
        return json.loads(r.read(1_000_000).decode("utf-8"))


def check(current: str, fetch: Callable[[], dict] = _fetch, skipped: str = "") -> UpdateInfo | None:
    """Yeni sürüm varsa bilgisi; yoksa / ağ hatasında / atlanan sürümde None."""
    try:
        data = fetch()
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    tag = str(data.get("tag_name") or "")
    if not newer(tag, current):
        return None
    version = ".".join(str(x) for x in parse_version(tag) or ())
    if skipped and parse_version(skipped) == parse_version(version):
        return None
    asset = next((a.get("browser_download_url", "") for a in data.get("assets") or []
                  if str(a.get("name", "")).lower().endswith(".exe") and "kurulum" in str(a.get("name", "")).lower()),
                 "")
    page = str(data.get("html_url") or PAGE)
    if not page.startswith(f"https://github.com/{REPO}/"):
        page = PAGE                                                     # yalnız kendi deposunun sayfası açılır
    if asset and not asset.startswith(f"https://github.com/{REPO}/releases/download/"):
        asset = ""
    return UpdateInfo(version=version, url=page, asset_url=asset, notes=str(data.get("body") or "")[:600])
