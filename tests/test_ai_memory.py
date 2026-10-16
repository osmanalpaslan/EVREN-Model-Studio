"""Ortak geliştirici hafızası (docs/ai-memory) denetimi ve araç testleri.

Bu test başarısızsa: AGENTS.md protokolünü uygulayın — eksik bölümleri
doldurun ve `python tools/ai_memory.py indeks` çalıştırın.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("ai_memory", ROOT / "tools" / "ai_memory.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ortak_hafiza_gecerli_ve_guncel():
    errors = _load().check()
    assert not errors, "Ortak hafıza denetimi başarısız (AGENTS.md):\n" + "\n".join(errors)


def test_kayit_ve_oturum_sablonlari(tmp_path, monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "INCIDENTS", tmp_path / "incidents")
    monkeypatch.setattr(m, "SESSIONS", tmp_path / "sessions")
    monkeypatch.setattr(m, "ROOT", tmp_path)
    assert m.main(["kayit", "--baslik", "Örnek hata: ğüşıöç", "--motor", "Test",
                   "--model", "bilinmiyor", "--tarih", "2026-01-02"]) == 0
    path = tmp_path / "incidents" / "2026-01-02-ornek-hata-gusioc.md"
    assert path.exists()
    meta, body = m.parse_doc(path)
    assert meta["id"] == path.stem and meta["durum"] == "acik" and meta["tur"] == "hata"
    secs = m.sections(body)
    assert all(m._section(secs, s) is not None for s in m.INCIDENT_SECTIONS)
    assert not m._meaningful(m._section(secs, "Belirti")), "şablon boş gelmeli"
    # aynı başlık ikinci kez → yeni dosya adı
    m.main(["kayit", "--baslik", "Örnek hata: ğüşıöç", "--motor", "T", "--model", "x",
            "--tarih", "2026-01-02"])
    assert (tmp_path / "incidents" / "2026-01-02-ornek-hata-gusioc-2.md").exists()
    assert m.main(["oturum", "--baslik", "Deneme", "--motor", "Kilo Code", "--model", "glm-5.3",
                   "--tarih", "2026-01-02"]) == 0
    assert (tmp_path / "sessions" / "2026-01-02-kilo-code-deneme.md").exists()


def test_motor_giris_dosyalari_agents_md_ye_yonlendirir():
    m = _load()
    for rel in m.ENTRY_FILES:
        assert "AGENTS.md" in (ROOT / rel).read_text(encoding="utf-8"), rel
