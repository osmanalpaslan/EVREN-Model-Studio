"""2026-11-12 uygulama analizinden çıkan düzeltmeler: tek örnek (ikinci açılış ikinci pencere açmaz → zamanlanmış
görevler iki kez çalışmaz) ve ajanın PowerShell'de bash heredoc denemesi (gerçek kullanım verisinden)."""
from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from evren_studio import app as appmod
from evren_studio.agent import tools

win_only = pytest.mark.skipif(os.name != "nt", reason="Windows'a özgü")


# ---- heredoc ----

@win_only
@pytest.mark.parametrize("cmd", [
    "python - <<'PY'\nprint(1)\nPY",
    'python - <<"EOF"\nimport sys\nEOF',
    "cat <<EOF > a.txt\nmerhaba\nEOF",
    "python <<-SON\nprint(2)\nSON",
])
def test_powershellde_heredoc_calistirilmaz_ne_yapilacagi_soylenir(tmp_path, cmd):
    tb = tools.ToolBox(tools.Workspace(tmp_path))
    with pytest.raises(tools.ToolError, match="heredoc"):
        tb.run_command(cmd)


@win_only
@pytest.mark.parametrize("cmd", [
    'python -c "print(1<<3)"',
    'python -c "x = 2 << 4; print(x)"',
    "Write-Output '<<EOF>> yazısı'",
    'python -c "\nimport sys\nprint(sys.version_info[0])"',      # çok satırlı -c PowerShell'de çalışır
    '$y = 2; python -c "print(1 << 3)"\nWrite-Output y',          # kayma + sonraki satır (bitiş satırı değil)
    'python -c "x, y = 1, 2; print(x << y)"\nWrite-Output 1',     # `<< y` sonrası satır var ama "y" bitiş satırı yok
])
def test_heredoc_olmayan_komut_etkilenmez(tmp_path, cmd):
    assert tools.heredoc_hint(cmd) == ""
    res = tools.ToolBox(tools.Workspace(tmp_path)).run_command(cmd, timeout_seconds=60)
    assert res.exit_code == 0, res.output


# ---- tek örnek ----

def test_ikinci_ornek_mutex_ile_anlasilir(monkeypatch):
    if os.name != "nt":
        assert appmod._hold_mutex() is False
        return
    monkeypatch.setenv("EVREN_STUDIO_INSTANCE", f"EVREN.Test.{uuid.uuid4().hex[:8]}")
    first = appmod._hold_mutex()
    second = appmod._hold_mutex()                    # aynı ad ikinci kez → zaten var
    assert first is False and second is True


@pytest.fixture()
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_calisan_ornek_yoksa_sinyal_basarisiz(qapp, monkeypatch):
    monkeypatch.setenv("EVREN_STUDIO_INSTANCE", f"EVREN.Test.{uuid.uuid4().hex[:8]}")
    assert appmod.signal_existing(timeout_ms=300) is False


def test_ikinci_acilis_calisan_pencereyi_one_getirir(qapp, monkeypatch):
    from PySide6.QtWidgets import QWidget

    monkeypatch.setenv("EVREN_STUDIO_INSTANCE", f"EVREN.Test.{uuid.uuid4().hex[:8]}")
    w = QWidget()
    w.show()
    w.showMinimized()
    server = appmod.listen_for_instances(w)
    assert server is not None and server.isListening()
    ok = {}
    import threading

    t = threading.Thread(target=lambda: ok.setdefault("r", appmod.signal_existing(timeout_ms=3000)))
    t.start()
    end = time.monotonic() + 5
    while time.monotonic() < end and getattr(w, "instance_pings", 0) == 0:
        qapp.processEvents()
        time.sleep(0.02)
    t.join(5)
    assert ok.get("r") is True and w.instance_pings == 1 and not w.isMinimized()
    server.close()
    w.close()


@win_only
def test_gercek_iki_acilis_ikinci_pencere_acmaz(tmp_path):
    """Gerçek süreçlerle: ilk uygulama açıkken ikinci `python -m evren_studio` hemen 0 ile çıkar."""
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "EVREN_STUDIO_DATA_DIR": str(tmp_path / "data"),
           "EVREN_STUDIO_INSTANCE": f"EVREN.Test.{uuid.uuid4().hex[:8]}", "PYTHONPATH": str(root / "src"),
           "EVREN_STUDIO_NO_UPDATE_CHECK": "1", "EVREN_STUDIO_NO_PROBE": "1", "EVREN_GOZLEM": "0"}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    first = subprocess.Popen([sys.executable, "-m", "evren_studio"], env=env, creationflags=flags)
    try:
        time.sleep(6)                                # pencere + yerel sunucu kurulsun
        assert first.poll() is None, "ilk örnek açılmadı"
        t0 = time.monotonic()
        second = subprocess.run([sys.executable, "-m", "evren_studio"], env=env, creationflags=flags, timeout=60)
        assert second.returncode == 0 and time.monotonic() - t0 < 30
        assert first.poll() is None                   # ilk örnek açık kaldı
    finally:
        first.kill()
        first.wait(10)
