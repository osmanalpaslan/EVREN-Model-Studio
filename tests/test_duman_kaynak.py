"""Duman testi yolu (`--duman-testi <dosya>`) kaynaktan da çalışmalı.

2026-11-14: c824b26 açılışı hızlandırırken `app.main` içindeki QTimer içe aktarmasını kaldırdı; `--duman-testi` yolu
NameError ile çöküyordu. Tam takım bu yolu hiç çalıştırmadığı için yalnız paketleme (tools/paketle.py) duman testi
yakaladı — yani hata ancak kurulum dosyası yapılırken görüldü. Bu test aynı yolu ayrı süreçte, ekransız çalıştırır.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_kaynakta_tanimsiz_ad_yok():
    # Aynı sınıf hata (kaldırılan içe aktarmanın kalan kullanımı) nadir çalışan HER yolda olabilir: ruff F821 tümünü bulur
    import shutil

    ruff = shutil.which("ruff", path=str(Path(sys.executable).parent)) or shutil.which("ruff")
    if ruff is None:
        import pytest

        pytest.skip("ruff kurulu değil")
    r = subprocess.run([ruff, "check", "--select", "F821", "--output-format", "concise", str(ROOT / "src")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, r.stdout[-2000:]


def test_duman_testi_yolu_kaynaktan_tamam_yazar(tmp_path):
    out = tmp_path / "duman.txt"
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "EVREN_STUDIO_DATA_DIR": str(tmp_path / "data"),
           "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, "-m", "evren_studio", "--duman-testi", str(out)], cwd=str(tmp_path),
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    text = out.read_text(encoding="utf-8") if out.exists() else ""
    assert r.returncode == 0, (r.stderr or r.stdout)[-1500:]
    assert text.rstrip().endswith("TAMAM") and "surum=" in text and "pencere=True" in text, text[-800:]
