"""Uzun işler: saatler süren komutlar tur bitince kapanmaz, bekleme kota harcamaz (2026-10-21)."""
from __future__ import annotations

import sys
import time

import pytest

from evren_studio.agent.jobs import JobManager
from evren_studio.agent.tools import ToolError
from evren_studio.api.client import CancelToken, ChatResult
from evren_studio.db import Database
from test_agent_runner import FakeClient, Recorder, call, make_runner

PY = f'& "{sys.executable}"'


def _script(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return f'{PY} "{p}"'


@pytest.fixture()
def jm(tmp_path):
    m = JobManager(tmp_path / "jobs")
    yield m
    m.stop_all()


def test_is_baslar_beklenir_cikti_dosyaya_yazilir(jm, tmp_path):
    cmd = _script(tmp_path, "t.py", "import time\nfor i in range(3):\n    print('adım', i, 'ğüş', flush=True)\n    time.sleep(0.3)\n")
    job = jm.start(tmp_path, cmd, "testler")
    assert job.running and job.id.startswith("testler-")
    job, why = jm.wait(job.id, max_minutes=1)
    assert why == "bitti" and job.exit_code == 0 and "bitti (başarılı)" in job.state()
    log = job.log_path.read_text(encoding="utf-8")
    assert "adım 2 ğüş" in log and "adım 2" in job.summary()


def test_bekleme_suresi_dolar_is_surer_iptal_edilebilir(jm, tmp_path):
    cmd = _script(tmp_path, "uzun.py", "import time\ntime.sleep(30)\n")
    job = jm.start(tmp_path, cmd)
    _, why = jm.wait(job.id, max_minutes=0.02)                       # ~1 sn
    assert "süresi doldu" in why and job.running
    tok = CancelToken()
    tok.cancel()
    _, why = jm.wait(job.id, cancel=tok)
    assert "durdurdu" in why and job.running
    jm.stop(job.id)
    time.sleep(0.5)
    assert not job.running and job.state() == "durduruldu"


def test_basarisiz_is_ve_bildirim_tek_sefer(jm, tmp_path):
    job = jm.start(tmp_path, _script(tmp_path, "kotu.py", "import sys\nprint('patladı')\nsys.exit(2)\n"))
    jm.wait(job.id, max_minutes=1)
    # PowerShell başarısız programın kodunu 1 olarak bildirir (run_command ile aynı); önemli olan ≠ 0
    assert job.exit_code not in (0, None) and "çıkış kodu" in job.state()
    assert [j.id for j in jm.finished_unnotified()] == [job.id]
    assert jm.finished_unnotified() == []
    with pytest.raises(ToolError):
        jm.get("yok-1")


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    yield d
    d.close()


@pytest.fixture()
def proj(tmp_path):
    root = tmp_path / "proje"
    root.mkdir()
    return root


def test_ajan_uzun_isi_baslatir_bekler_sonucu_alir_tur_bitince_kapanmaz(db, proj, jm, tmp_path):
    cmd = _script(tmp_path, "suite.py", "import time\nprint('12 test geçti', flush=True)\ntime.sleep(0.5)\n")
    long_cmd = _script(tmp_path, "arka.py", "import time\ntime.sleep(20)\n")
    client = FakeClient([
        ChatResult(tool_calls=[call("start_job", cid="s", command=cmd)]),
        ChatResult(tool_calls=[call("wait_job", cid="w", max_minutes=1)]),
        ChatResult(tool_calls=[call("start_job", cid="s2", command=long_cmd)]),
        ChatResult(content="Testler geçti; arka plan işi sürüyor.", finish_reason="stop"),
    ])
    runner, history, _ = make_runner(db, client, proj, mode="auto", jobs=jm)
    out = runner.run(history)
    assert out.stopped == "done"
    tools = [m for m in client.calls[2]["messages"] if m["role"] == "tool"]
    assert "12 test geçti" in tools[-1]["content"] and "bitti (başarılı)" in tools[-1]["content"]
    assert [j.id for j in jm.running()] == ["is-2"]                  # tur bitti, uzun iş KAPANMADI


def test_uzun_is_manuel_modda_onay_ister_araclar_yalniz_yonetici_varken(db, proj, jm):
    ev = Recorder("deny")
    client = FakeClient([ChatResult(tool_calls=[call("start_job", command="python -c 1")]),
                         ChatResult(content="ok", finish_reason="stop")])
    runner, history, _ = make_runner(db, client, proj, events=ev, mode="manuel", jobs=jm)
    runner.run(history)
    assert len(ev.approvals) == 1 and "Uzun iş" in ev.approvals[0].title and jm.jobs == {}
    client2 = FakeClient([ChatResult(content="ok", finish_reason="stop")])
    r2, h2, _ = make_runner(db, client2, proj)
    r2.run(h2)
    names = {t["function"]["name"] for t in client2.calls[0]["tools"]}
    assert not names & {"start_job", "wait_job", "job_status", "stop_job"}
