"""Zorluk paketi denetleyicileri bilinen DOĞRU ve bilinen YANLIŞ cevaplarla sınanır (R-25) + girdi ipucu (2026-11-12).

"girdi" görevi 2026-11-06'da (gözlem 2983bc967976) gemma'nın doğru açıklamasını "giriş/isim" kelimeleri listede
olmadığı için KALDI saymıştı — denetleyicinin yanlış alarmı. Uygulama tarafında da: girdi bekleyen program girdisiz
çalışınca ajana durum açıkça söylenir (tools.stdin_hint; tetiklenen + tetiklenmeyen, R-22).
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

from evren_studio.agent import tools
from evren_studio.agent.runner import AgentEvents, AgentRunner
from evren_studio.api.client import ChatResult
from evren_studio.db import Database

ROOT = Path(__file__).resolve().parents[1]


def _zorluk():
    spec = importlib.util.spec_from_file_location("e2e_zorluk_mod", ROOT / "tests" / "e2e_zorluk_real_api.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("e2e_zorluk_mod", mod)
    spec.loader.exec_module(mod)
    return mod


GERCEK_GEMMA = ("`oyun.py` dosyası kullanıcıdan isim girişi beklediği için doğrudan çalıştırdığımda hata verdi. Ancak "
                "örnek bir giriş (\"Kullanıcı\") sağlayarak çalıştırdığımda çıktı şu şekilde oldu:\n\n**Çıktı:**\n"
                "`Merhaba Kullanıcı`")


@pytest.mark.parametrize("yanit", [
    GERCEK_GEMMA,                                                           # 2026-11-06'da yanlışlıkla KALDI sayılan
    "Program `Adınız:` diye klavyeden girdi bekliyor; stdin kapalı olduğu için EOFError verdi.",
    "oyun.py ÇALIŞTIRILINCA İSİM GİRİŞİ BEKLİYOR, bu yüzden çıktı vermedi.",  # Türkçe büyük harf
    "The script waits for INPUT, so it raised EOFError.",
])
def test_girdi_denetleyicisi_dogru_aciklamayi_kabul_eder(yanit):
    assert _zorluk().kontrol_girdi(Path("."), {}, yanit)[0][1] is True


@pytest.mark.parametrize("yanit", [
    "Çıktı: Merhaba Ali",                                                   # uydurma girdiyle sessizce çalıştırmış
    "Program çalıştı ama ekrana bir şey yazmadı.",
    "Bitti.",
])
def test_girdi_denetleyicisi_aciklamasiz_cevabi_reddeder(yanit):
    assert _zorluk().kontrol_girdi(Path("."), {}, yanit)[0][1] is False


# ---- uygulama: girdi ipucu ----

@pytest.mark.parametrize("cikti", [
    "Traceback (most recent call last):\n  File \"oyun.py\", line 1\nEOFError: EOF when reading a line",
    "Read-Host : PowerShell is in NonInteractive mode. Read and Prompt functionality is not available.",
])
def test_girdi_ipucu_tetiklenir(cikti):
    assert tools.stdin_hint(cikti) == tools.STDIN_HINT


@pytest.mark.parametrize("cikti", [
    "SyntaxError: unexpected EOF while parsing",                            # başka bir EOF: sözdizimi hatası
    "FAILED (failures=1)",
    "",
])
def test_girdi_ipucu_tetiklenmez(cikti):
    assert tools.stdin_hint(cikti) == ""


def _run(tmp_path, command):
    root = tmp_path / "p"
    root.mkdir()
    (root / "oyun.py").write_text("ad = input('Adınız: ')\nprint(f'Merhaba {ad}')\n", encoding="utf-8")
    db = Database(tmp_path / "t.db")
    sid = db.create_session("m", str(root), "auto")
    db.add_session_message(sid, "user", "oyun.py'yi çalıştır")

    class Client:
        n = 0

        def chat(self, model, messages, **kw):
            Client.n += 1
            if Client.n == 1:
                return ChatResult(tool_calls=[{"id": "c1", "name": "run_command",
                                               "arguments": json.dumps({"command": command})}],
                                  finish_reason="tool_calls")
            return ChatResult(content="Bitti.", finish_reason="stop")
    r = AgentRunner(Client(), "m", session_id=sid, store=db, workspace=tools.Workspace(root), mode="auto",
                    stream=False, events=AgentEvents())
    r.run(db.get_session_messages(sid))
    out = next(m["content"] for m in db.get_session_messages(sid) if m["role"] == "tool")
    db.close()
    return out


@pytest.mark.skipif(os.name != "nt", reason="PowerShell")
def test_gercek_komut_girdi_bekleyen_programda_ipucu_verir(tmp_path):
    out = _run(tmp_path, "python oyun.py")
    assert "EOFError" in out and "[İpucu] Program klavyeden girdi bekledi" in out


@pytest.mark.skipif(os.name != "nt", reason="PowerShell")
def test_gercek_powershell_read_host_cikis_0_olsa_da_ipucu_verir(tmp_path):
    out = _run(tmp_path, "$ad = Read-Host 'Adiniz'; Write-Output \"Merhaba $ad\"")
    assert "Çıkış kodu: 0" in out and "[İpucu] Program klavyeden girdi bekledi" in out


@pytest.mark.skipif(os.name != "nt", reason="PowerShell")
def test_gercek_komut_girdi_verilince_ipucu_yok(tmp_path):
    out = _run(tmp_path, "'Ali' | python oyun.py")
    assert "Merhaba Ali" in out and "[İpucu]" not in out
