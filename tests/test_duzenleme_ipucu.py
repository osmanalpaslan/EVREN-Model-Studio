"""edit_file "old_string bulunamadı" → dosyadaki EN YAKIN bölüm ipucu (2026-11-12, analiz önerisi; kullanıcı onayı).

Gerçek kullanımda düzenlemelerin %2,3'ü bu hatayla düştü; ajan dosyayı yeniden okumak için bir adım (EVREN'de 15-80 sn)
daha harcıyordu. Tetiklenen (girinti farkı, küçük yazım farkı) ve tetiklenmeyen (ilgisiz metin, çok büyük dosya)
durumlar ayrı sınanır (R-22); ipucu gerçek araç akışından modele de ulaşır (R-31).
"""
from __future__ import annotations

import json
import time

import pytest

from evren_studio.agent import tools
from evren_studio.agent.runner import AgentEvents, AgentRunner
from evren_studio.api.client import ChatResult
from evren_studio.db import Database

KOD = ("def hesapla(items, tax_rate):\n"
       "    total = compute_total(items, tax_rate)\n"
       "    if total < 0:\n"
       "        raise ValueError('negatif')\n"
       "    return round(total, 2)\n")


def _box(tmp_path, text=KOD, name="a.py"):
    (tmp_path / name).write_text(text, encoding="utf-8")
    return tools.ToolBox(tools.Workspace(tmp_path))


def _err(box, old, path="a.py"):
    with pytest.raises(tools.ToolError) as e:
        box.prepare_edit(path, old, "YENI")
    return str(e.value)


def test_girinti_farki_acikca_soylenir_ve_gercek_satirlar_gosterilir(tmp_path):
    msg = _err(_box(tmp_path), "    total = compute_total(items, tax_rate)\n  if total < 0:\n")
    assert "boşluk/girinti farklı" in msg and "satır 2-3" in msg
    assert "    2|     total = compute_total(items, tax_rate)" in msg and "    3|     if total < 0:" in msg


def test_kucuk_yazim_farkinda_en_yakin_bolum(tmp_path):
    msg = _err(_box(tmp_path), "    total = compute_totl(items, tax_rate)\n    if total < 0:\n")
    assert "en yakın bölüm" in msg.lower() and "satır 2-3" in msg and "compute_total(items, tax_rate)" in msg


def test_ilgisiz_metinde_ipucu_uydurulmaz(tmp_path):
    msg = _err(_box(tmp_path), "class Muz:\n    renk = 'sari'\n")
    assert msg.endswith("okuyup metni birebir (girinti dahil) kopyalayın.") and "```" not in msg


def test_tekrarli_veri_blogunda_yakin_bolum_bulunur(tmp_path):
    """Yalnız sık karakterlerden oluşan 200-600 karakterlik blok (matris/tablo): difflib'in autojunk'u açıkken benzerlik
    %16'ya düşüyor, ipucu hiç verilmiyordu (ölçüm 2026-11-13: kapalıyken %99,6)."""
    rows = "".join("    [" + ", ".join("1" if (r * c) % 3 == 1 else "0" for c in range(8)) + "],\n" for r in range(8))
    msg = _err(_box(tmp_path, "TABLO = [\n" + rows + "]\n"), rows.replace("1", "0", 1))
    assert "en yakın bölüm" in msg.lower() and "satır 2-9" in msg


def test_buyuk_dosyada_hizli(tmp_path):
    big = "".join(f"satir_{i} = {i}\n" for i in range(15000)) + KOD
    box = _box(tmp_path, big)
    t0 = time.perf_counter()
    msg = _err(box, "    total = compute_totl(items, tax_rate)\n")
    assert time.perf_counter() - t0 < 3.0 and "compute_total" in msg


def test_cok_buyuk_dosyada_arama_yapilmaz(tmp_path):
    huge = "".join(f"x{i} = {i}\n" for i in range(tools.NEAREST_MAX_LINES + 10))
    msg = _err(_box(tmp_path, huge), "x5 = 6\n")
    assert "```" not in msg


def test_ipucu_uzun_bolumde_kisaltilir(tmp_path):
    long_text = "".join(f"    deger_{i} = hesapla_uzun_bir_ad({i}, 'metin {i}')\n" for i in range(150))
    old = long_text.replace("hesapla_uzun_bir_ad(7,", "hesapla_uzun_bir_ad(77,")
    msg = _err(_box(tmp_path, long_text), old)
    assert len(msg) < 2200 and "kısaltıldı" in msg


def test_ipucu_gercek_arac_akisindan_modele_ulasir(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    (root / "a.py").write_text(KOD, encoding="utf-8")
    db = Database(tmp_path / "t.db")
    sid = db.create_session("m", str(root), "auto")
    db.add_session_message(sid, "user", "a.py'de if satırını düzelt")

    class Client:
        n = 0

        def chat(self, model, messages, **kw):
            Client.n += 1
            if Client.n == 1:
                # satır içi boşluk farkı ("<  0"): dosyada parça olarak da geçmez, düzenleme gerçekten bulunamaz
                args = {"path": "a.py", "old_string": "    if total <  0:", "new_string": "    if total <= 0:"}
                return ChatResult(tool_calls=[{"id": "c1", "name": "edit_file", "arguments": json.dumps(args)}],
                                  finish_reason="tool_calls")
            return ChatResult(content="Bitti.", finish_reason="stop")
    r = AgentRunner(Client(), "m", session_id=sid, store=db, workspace=tools.Workspace(root), mode="auto",
                    stream=False, events=AgentEvents())
    r.run(db.get_session_messages(sid))
    out = next(m["content"] for m in db.get_session_messages(sid) if m["role"] == "tool")
    db.close()
    assert "boşluk/girinti farklı" in out and "    3|     if total < 0:" in out
