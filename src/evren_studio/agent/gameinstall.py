"""Oyun araçlarını kur (Qt'siz): Godot 4.7.2 + dışa aktarma şablonları, Blender 5.2.3 — resmî kaynaklardan.

Güvenlik: her dosya, 2026-10-24'te resmî sağlama listeleriyle (Godot SHA512-SUMS.txt, Blender .sha256) doğrulanmış
SABİT değerle karşılaştırılır; uyuşmazsa dosya silinir, kurulum durur. Kurulumsuz zip'ler araç klasörüne açılır
(yönetici izni yok, AppData'ya yazılmaz; Godot kendi kendine yeterli kipte: `._sc_`). Arşiv dışına yazan girdi
(zip slip) reddedilir. Arayüz iş parçacığında ÇAĞRILMAZ (R-04). Kullanıcı onayı arayüzde alınır.
"""
from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

GODOT_URL = "https://github.com/godotengine/godot/releases/download/4.7.2-stable/"
BLENDER_URL = "https://download.blender.org/release/Blender5.2/"
USER_AGENT = "EVREN-Studio/1.0 (oyun araclari)"


@dataclass(frozen=True)
class Item:
    key: str
    title: str
    url: str
    size: int                      # bayt (bilgi)
    algo: str                      # sha512 | sha256
    digest: str


ITEMS: dict[str, Item] = {
    "godot": Item("godot", "Godot 4.7.2 düzenleyici (Windows)", GODOT_URL + "Godot_v4.7.2-stable_win64.exe.zip",
                  86_013_866, "sha512",
                  "83decd58fdf67b9d657958a1ae6bf1929c20785315a81effe245874cdc57acb709bf868e00778a96984338c1b29dafdb"
                  "453c6847747694621c6ecf5da2259993"),
    "sablonlar": Item("sablonlar", "Godot 4.7.2 dışa aktarma şablonları (EXE + PWA için)",
                      GODOT_URL + "Godot_v4.7.2-stable_export_templates.tpz", 1_281_349_702, "sha512",
                      "ca4d71c4d7b81dfc15d1a98baa07534aa95b03fdda78a0075b06672e1648d2e5f40980c9adc28d23e1b92e732ee7bf"
                      "3461997aa804af74ec2fcd7a93ccb84079"),
    "blender": Item("blender", "Blender 5.2.3 (Windows, model dönüştürme)",
                    BLENDER_URL + "blender-5.2.3-windows-x64.zip", 405_839_452, "sha256",
                    "723f08a4401502561eb763cdeacf8745b31e5f3f154d287d3830d97cf75dc2fb"),
}
GROUPS = {"godot": ["godot", "sablonlar"], "blender": ["blender"]}


class InstallError(Exception):
    pass


def default_dir() -> Path:
    """Kurulum yeri: uygulama klasörünün yanındaki EVREN-Araclar (yazılamıyorsa kullanıcı klasöründe)."""
    from .gametools import APP_ROOT

    cand = APP_ROOT.parent / "EVREN-Araclar"
    try:
        cand.mkdir(parents=True, exist_ok=True)
        probe = cand / ".yazilabilir"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return cand
    except OSError:
        return Path.home() / "EVREN-Araclar"


def status(setting: str = "") -> dict[str, bool]:
    from . import gametools

    g = gametools.find_godot(setting)
    return {"godot": bool(g), "sablonlar": gametools.templates_ready(g), "blender": bool(gametools.find_blender(setting))}


def total_size(keys: list[str]) -> int:
    return sum(ITEMS[k].size for k in keys)


def download(item: Item, dest: Path, log: Callable[[str], None], cancel=None, client=None) -> Path:
    """İndirir ve sağlama toplamını doğrular; uyuşmazsa siler ve InstallError."""
    import httpx

    dest.mkdir(parents=True, exist_ok=True)
    path = dest / item.url.rsplit("/", 1)[-1]
    h = hashlib.new(item.algo)
    if path.is_file():                                    # önceki yarım/tam indirme: yeniden doğrula
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() == item.digest:
            log(f"{item.title}: daha önce indirilmiş, doğrulandı.")
            return path
        path.unlink()
        h = hashlib.new(item.algo)
    own = client is None
    c = client or httpx.Client(timeout=httpx.Timeout(60.0, read=300.0), follow_redirects=True,
                               headers={"User-Agent": USER_AGENT})
    tmp = path.with_suffix(path.suffix + ".indiriliyor")
    try:
        with c.stream("GET", item.url) as r:
            if r.status_code != 200:
                raise InstallError(f"{item.title}: indirilemedi (HTTP {r.status_code}).")
            total = int(r.headers.get("content-length") or item.size)
            done, last = 0, -10
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    if cancel is not None and getattr(cancel, "cancelled", False):
                        raise InstallError("İptal edildi.")
                    f.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    pct = int(100 * done / max(total, 1))
                    if pct >= last + 10:
                        last = pct
                        log(f"{item.title}: %{pct} ({done // (1024 * 1024)} / {total // (1024 * 1024)} MB)")
    except InstallError:
        tmp.unlink(missing_ok=True)
        raise
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise InstallError(f"{item.title}: bağlantı hatası: {type(exc).__name__}: {exc}"[:300]) from exc
    finally:
        if own:
            c.close()
    if h.hexdigest() != item.digest:
        tmp.unlink(missing_ok=True)
        raise InstallError(f"{item.title}: SAĞLAMA TOPLAMI UYUŞMADI — dosya silindi, kurulum durduruldu. "
                           "İndirilen dosya resmî dosya değil veya bozuk.")
    tmp.replace(path)
    log(f"{item.title}: indirildi ve sağlama toplamı doğrulandı.")
    return path


def _safe_extract(z: zipfile.ZipFile, dest: Path, strip: str = "") -> int:
    root = dest.resolve()
    n = 0
    for info in z.infolist():
        name = info.filename
        if strip:
            if not name.startswith(strip):
                continue
            name = name[len(strip):]
        if not name or name.endswith("/"):
            continue
        out = (dest / name).resolve()
        if root not in out.parents:
            raise InstallError(f"Arşivde güvensiz yol: {info.filename}")
        out.parent.mkdir(parents=True, exist_ok=True)
        with z.open(info) as src, open(out, "wb") as f:
            for chunk in iter(lambda: src.read(1 << 20), b""):
                f.write(chunk)
        n += 1
    return n


def install(keys: list[str], dest: Path | None = None, log: Callable[[str], None] | None = None, cancel=None,
            client=None) -> Path:
    """Seçilen öğeleri indirir, doğrular, açar. Dönüş: araç klasörü."""
    log = log or (lambda _m: None)
    dest = Path(dest) if dest else default_dir()
    dl = dest / "indirilen"
    for key in keys:
        item = ITEMS[key]
        arc = download(item, dl, log, cancel, client)
        log(f"{item.title}: açılıyor…")
        with zipfile.ZipFile(arc) as z:
            if key == "godot":
                _safe_extract(z, dest / "godot")
                (dest / "godot" / "._sc_").write_text("", encoding="utf-8")
            elif key == "sablonlar":
                _safe_extract(z, dest / "godot" / "editor_data" / "export_templates" / "4.7.2.stable", "templates/")
            elif key == "blender":
                _safe_extract(z, dest / "blender")
        log(f"{item.title}: kuruldu.")
    return dest
