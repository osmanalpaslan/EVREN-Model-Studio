"""Arka plan servisleri, test bekçisi ve QA yazma engeli (2026-10-19; gerçek ağ/model yok)."""
from __future__ import annotations

import socket
import sys

import pytest

from evren_studio.agent import testcheck
from evren_studio.agent.services import ServiceManager, port_open
from evren_studio.agent.tools import ToolBox, ToolError, Workspace
from evren_studio.api.client import ChatResult
from evren_studio.db import Database
from test_agent_runner import FakeClient, Recorder, call, make_runner


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---- servisler ----------------------------------------------------------------------------

def test_servis_baslar_porta_hazir_olur_kayit_okunur_kapanir(tmp_path):
    (tmp_path / "index.html").write_text("merhaba", encoding="utf-8")
    port = _free_port()
    sm = ServiceManager(tmp_path)
    try:
        out = sm.start(f'& "{sys.executable}" -m http.server {port} --bind 127.0.0.1', name="web", port=port,
                       wait_seconds=30)
        assert out.startswith("Servis 'web' çalışıyor") and f"127.0.0.1:{port}" in out
        assert port_open(port) and sm.running() == ["web"]
        with pytest.raises(ToolError, match="zaten çalışıyor"):
            sm.start("python -m http.server", name="web")
        assert "çalışıyor" in sm.logs("web")
        assert sm.stop() == "Servis 'web' kapatıldı."              # tek servis: ad gerekmez
        assert sm.running() == []
    finally:
        sm.stop_all()


def test_hemen_kapanan_servis_cikti_ile_bildirilir(tmp_path):
    sm = ServiceManager(tmp_path)
    out = sm.start(f'& "{sys.executable}" -c "import sys; print(\'patladi\'); sys.exit(3)"', name="kotu",
                   wait_seconds=10)
    assert "hemen sonra kapandı" in out and "patladi" in out


def test_kullanilan_port_ve_servis_siniri(tmp_path):
    busy = socket.socket()
    busy.bind(("127.0.0.1", 0))
    busy.listen(1)
    try:
        with pytest.raises(ToolError, match="kullanımda"):
            ServiceManager(tmp_path).start("python -m http.server", port=busy.getsockname()[1])
    finally:
        busy.close()


def test_port_ciktidan_bulunur(tmp_path):
    port = _free_port()
    sm = ServiceManager(tmp_path)
    try:
        out = sm.start(f'& "{sys.executable}" -m http.server {port} --bind 127.0.0.1', name="h", wait_seconds=30)
        # port verilmedi: "Serving HTTP on 127.0.0.1 port N (http://127.0.0.1:N/)" çıktısından bulunur
        assert sm.services["h"].port == port and "çalışıyor" in out
    finally:
        sm.stop_all()


# ---- test bekçisi -----------------------------------------------------------------------------

def test_test_komutu_algilanir(tmp_path):
    assert testcheck.detect_command(tmp_path) is None
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    cmd = testcheck.detect_command(tmp_path)
    assert cmd and ("pytest" in cmd or "unittest" in cmd)
    node = tmp_path / "n"
    node.mkdir()
    (node / "package.json").write_text('{"scripts": {"test": "echo \\"Error: no test specified\\""}}', encoding="utf-8")
    (node / "node_modules").mkdir()
    assert testcheck.detect_command(node) is None                    # npm init varsayılanı test değil


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    yield d
    d.close()


def _proj(tmp_path, test_body="assert topla(1, 2) == 3"):
    root = tmp_path / "proje"
    (root / "tests").mkdir(parents=True)
    (root / "hesap.py").write_text("def topla(a, b):\n    return a + b\n", encoding="utf-8")
    (root / "tests" / "test_hesap.py").write_text(
        "import sys, unittest\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
        "from hesap import topla\n\n\nclass T(unittest.TestCase):\n    def test_t(self):\n        "
        + test_body.replace("assert ", "self.assertTrue(") + ")\n", encoding="utf-8")
    return root


def _last_user_nudges(client):
    return [m["content"] for c in client.calls for m in c["messages"]
            if m["role"] == "user" and "TEST BEKÇİSİ" in str(m.get("content"))]


def test_bekci_bozulan_testi_bir_kez_bildirir(db, tmp_path):
    root = _proj(tmp_path)
    client = FakeClient([
        ChatResult(tool_calls=[call("edit_file", path="hesap.py", old_string="a + b", new_string="a - b")]),
        ChatResult(content="Bitti.", finish_reason="stop"),
        ChatResult(content="Kod düzeltildi, testler geçmeli.", finish_reason="stop"),
    ])
    ev = Recorder()
    notes = []
    ev.status = notes.append
    runner, history, _ = make_runner(db, client, root, events=ev, mode="auto", test_check=True)
    out = runner.run(history)
    assert out.stopped == "done"
    nudges = _last_user_nudges(client)
    assert len(client.calls) == 3 and nudges and "DÜŞÜYOR" in nudges[0] and "test dosyalarını" in nudges[0]
    assert any("testler düştü" in n for n in notes)


def test_bekci_gecen_testte_ve_yazma_yokken_sessiz(db, tmp_path):
    root = _proj(tmp_path)
    for responses in (
        [ChatResult(tool_calls=[call("edit_file", path="hesap.py", old_string="a + b", new_string="b + a")]),
         ChatResult(content="Bitti.", finish_reason="stop")],
        [ChatResult(tool_calls=[call("read_file", path="hesap.py")]), ChatResult(content="Okudum.", finish_reason="stop")],
    ):
        client = FakeClient(responses)
        runner, history, _ = make_runner(db, client, root, mode="auto", test_check=True)
        runner.run(history)
        assert not _last_user_nudges(client) and len(client.calls) == 2


def test_bekci_tur_basinda_dusen_testte_sessiz(db, tmp_path):
    root = _proj(tmp_path, "assert topla(1, 2) == 4")                 # zaten düşüyor
    client = FakeClient([
        ChatResult(tool_calls=[call("edit_file", path="hesap.py", old_string="a + b", new_string="(a + b)")]),
        ChatResult(content="Bitti.", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, root, mode="auto", test_check=True)
    runner.run(history)
    assert not _last_user_nudges(client)                             # ilgisiz bozukluğa sürüklemez


def test_bekci_kapaliyken_ve_plan_modunda_calismaz(db, tmp_path):
    root = _proj(tmp_path)
    client = FakeClient([
        ChatResult(tool_calls=[call("edit_file", path="hesap.py", old_string="a + b", new_string="a - b")]),
        ChatResult(content="Bitti.", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, root, mode="auto", test_check=False)
    runner.run(history)
    assert not _last_user_nudges(client)


# ---- QA: yazma yok, servis araçları ----------------------------------------------------------

def test_qa_kipinde_yazma_araclari_sunulmaz_ve_engellenir(db, tmp_path):
    root = _proj(tmp_path)
    client = FakeClient([
        ChatResult(tool_calls=[call("write_file", path="x.txt", content="a")]),
        ChatResult(content="tamam", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, root, mode="auto", no_writes=True,
                                     services=ServiceManager(root))
    runner.run(history)
    names = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert "write_file" not in names and "edit_file" not in names and "start_service" in names
    assert not (root / "x.txt").exists()
    tool = [m for m in client.calls[1]["messages"] if m["role"] == "tool"][0]["content"]
    assert "dosya değiştirilemez" in tool


def test_servis_araclari_yalniz_servis_yoneticisi_varken(db, tmp_path):
    root = _proj(tmp_path)
    client = FakeClient([ChatResult(content="ok", finish_reason="stop")])
    runner, history, _ = make_runner(db, client, root)
    runner.run(history)
    names = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert not names & {"start_service", "service_logs", "stop_service"}


def test_servis_baslatma_manuel_modda_onay_ister(db, tmp_path):
    root = _proj(tmp_path)
    ev = Recorder("deny")
    client = FakeClient([
        ChatResult(tool_calls=[call("start_service", command="python -m http.server 8765")]),
        ChatResult(content="tamam", finish_reason="stop"),
    ])
    sm = ServiceManager(root)
    runner, history, _ = make_runner(db, client, root, events=ev, mode="manuel", services=sm)
    runner.run(history)
    assert len(ev.approvals) == 1 and "Servis" in ev.approvals[0].title and sm.running() == []
