"""Test ve araç betiklerinin geçici klasörleri: oluştur, kaydet, çıkışta sil.

Neden (2026-11-11, disk temizliği oturumunun bulgusu): gerçek API betikleri ve okunurluk denetimi `tempfile.mkdtemp`
klasörlerini hiç silmiyordu — Temp'te 21 `evren-masaustu-*` (her biri ~425 MB: Windows-MCP venv + uv önbelleği + Python
kopyası, toplam 8,5 GB) ve 154 `evren-denetim-*` birikmişti.

Kullanım:
    from gecici import klasor          # betik sys.path'e ROOT/tools ekler
    data = klasor("evren-masaustu-")   # çıkışta (atexit) silinir

Saklamak (hata ayıklama): komut satırında `--sakla` ya da ortam değişkeni EVREN_GECICI_SAKLA=1 → silinmez, yolları yazar.
Windows'ta kapanmakta olan bir süreç dosyayı kısa süre kilitleyebilir: birkaç kez kısa bekleyip yeniden dener; git'in salt
okunur nesne dosyaları yazılabilir yapılıp silinir. Silinemeyen kalırsa uyarı yazar (betiği düşürmez).
"""
from __future__ import annotations

import atexit
import os
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path

_dirs: list[Path] = []


def sakla() -> bool:
    return "--sakla" in sys.argv or os.environ.get("EVREN_GECICI_SAKLA") == "1"


def klasor(prefix: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix=prefix))
    _dirs.append(d)
    return d


def _writable(func, path, _exc) -> None:
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def sil(d: Path, tries: int = 4, wait: float = 1.0) -> bool:
    """Klasörü siler; kilitliyse kısa bekleyip yeniden dener. Silindiyse (ya da hiç yoksa) True."""
    for i in range(tries):
        if not d.exists():
            return True
        shutil.rmtree(d, onerror=_writable)
        if not d.exists():
            return True
        time.sleep(wait * (i + 1))
    return not d.exists()


def temizle() -> list[Path]:
    """Kayıtlı tüm klasörleri siler; silinemeyenleri döndürür."""
    kalan = [d for d in reversed(_dirs) if not sil(d)]
    _dirs.clear()
    return kalan


def _cikista() -> None:
    if not _dirs:
        return
    if sakla():
        print("[geçici] SAKLANDI (--sakla): " + ", ".join(str(d) for d in _dirs), file=sys.stderr)
        return
    kalan = temizle()
    if kalan:
        print("[geçici] silinemedi (kilitli): " + ", ".join(str(d) for d in kalan), file=sys.stderr)


atexit.register(_cikista)
