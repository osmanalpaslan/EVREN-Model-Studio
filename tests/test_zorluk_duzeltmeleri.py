"""Zorluk paketinin (tests/e2e_zorluk_real_api.py) bulduğu sorunların düzeltmeleri.

- Büyük dosyada model, kısaltılmış read_file çıktısından görmediği satırlar için
  kesin sayı uydurdu → kısaltma uyarısı açık; search_files toplam sayıyı verir.
- İstenen dosya yokken model benzer başka dosyayı sormadan değiştirdi → kural.
"""
from __future__ import annotations

from evren_studio.agent import prompts
from evren_studio.agent.tools import MAX_READ_LINES, ToolBox, Workspace


def _ws(tmp_path):
    (tmp_path / "uygulama.log").write_text(
        "\n".join(("ERROR x" if i % 137 == 0 else "INFO y") + f" #{i}" for i in range(1, 3001)) + "\n",
        encoding="utf-8")
    return ToolBox(Workspace(tmp_path))


def test_kisaltilmis_okuma_acik_uyari_verir(tmp_path):
    out = _ws(tmp_path).read_file("uygulama.log")
    assert "⚠ KISALTILDI" in out
    assert f"{MAX_READ_LINES + 1}-3000 GÖRÜLMEDİ" in out
    assert f"start_line={MAX_READ_LINES + 1}" in out and "search_files" in out


def test_tam_okumada_uyari_yok(tmp_path):
    out = _ws(tmp_path).read_file("uygulama.log", start_line=2990)
    assert "KISALTILDI" not in out and "3000\tINFO y #3000" in out


def test_arama_toplam_sayiyi_basta_verir(tmp_path):
    out = _ws(tmp_path).search_files("ERROR")
    first = out.split("\n", 1)[0]
    assert first == "Toplam 21 eşleşen satır (1 dosyada):"
    assert "uygulama.log:137: ERROR x #137" in out


def test_arama_sinir_ustu_de_sayilir(tmp_path):
    from evren_studio.agent import tools

    (tmp_path / "cok.txt").write_text("hata\n" * (tools.MAX_SEARCH_RESULTS + 25), encoding="utf-8")
    out = ToolBox(Workspace(tmp_path)).search_files("hata", glob="cok.txt")
    assert out.startswith(f"Toplam {tools.MAX_SEARCH_RESULTS + 25} eşleşen satır (1 dosyada); "
                          f"ilk {tools.MAX_SEARCH_RESULTS} gösteriliyor:")
    assert out.count("cok.txt:") == tools.MAX_SEARCH_RESULTS


def test_eslesme_yoksa_eski_metin(tmp_path):
    assert _ws(tmp_path).search_files("YOKBOYLE") == "Eşleşme bulunamadı."


def test_kurallar_istemde():
    assert "onun yerine DEĞİŞTİRME" in prompts.AGENT_RULES
    assert "⚠ KISALTILDI" in prompts.AGENT_RULES


# ---- adı geçen ama olmayan dosya denetimi ------------------------------------------------

def test_metinden_dosya_adlari():
    from evren_studio.agent.scope import mentioned_files

    assert mentioned_files("ayarlar.yaml dosyasındaki timeout değerini 30 yap.") == ["ayarlar.yaml"]
    assert mentioned_files("README.md'deki yazım hatasını düzelt") == ["README.md"]
    assert mentioned_files("src/app.py ve tests/test_x.py; os.path, self.model, sürüm 3.12, "
                           "https://a.com/b.json") == ["src/app.py", "tests/test_x.py"]
    assert mentioned_files("hesapla_kdv adını değiştir") == []


def test_olmayan_dosya_bulunur(tmp_path):
    from evren_studio.agent.scope import missing_mentions

    (tmp_path / "ayar.ini").write_text("x", encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "app.py").write_text("x", encoding="utf-8")
    assert missing_mentions("ayarlar.yaml'daki timeout'u değiştir", tmp_path) == ["ayarlar.yaml"]
    assert missing_mentions("app.py ve ayar.ini'ye bak", tmp_path) == []      # ad ile alt klasörde bulunur
    assert missing_mentions("selam", tmp_path) == []


def test_kosucu_tur_uyarisini_sisteme_ekler(tmp_path):
    from evren_studio.agent.runner import AgentRunner
    from evren_studio.agent.tools import Workspace
    from evren_studio.api.client import ChatResult
    from evren_studio.db import Database

    (tmp_path / "ayar.ini").write_text("[genel]\n", encoding="utf-8")
    seen = []

    class C:
        def chat(self, model, messages, **kw):
            seen.append(messages[0]["content"])
            return ChatResult(content="ayarlar.yaml bulunamadı; ayar.ini'yi mi kastettiniz?", finish_reason="stop")

    db = Database(tmp_path / "t.db")
    try:
        sid = db.create_session("auto", str(tmp_path))
        db.add_session_message(sid, "user", "ayarlar.yaml dosyasındaki timeout değerini 30 yap.")
        AgentRunner(C(), "auto", session_id=sid, store=db, workspace=Workspace(tmp_path),
                    stream=False).run(db.get_session_messages(sid))
        assert "BULUNAMADI: `ayarlar.yaml`" in seen[0]
        db.add_session_message(sid, "user", "ayar.ini'yi kullan")
        seen.clear()
        AgentRunner(C(), "auto", session_id=sid, store=db, workspace=Workspace(tmp_path),
                    stream=False).run(db.get_session_messages(sid))
        assert "BULUNAMADI" not in seen[0]                      # yalnız son mesaja bakılır
    finally:
        db.close()


# ---- test dosyası koruması ---------------------------------------------------------------

def test_test_niyeti_ve_yol_tanima():
    from evren_studio.agent.scope import is_test_path, user_allows_test_edits

    assert not user_allows_test_edits("`python -m unittest` testlerinin hepsi geçecek şekilde hesap.py'yi düzelt.")
    assert not user_allows_test_edits("Testlerden biri başarısız. Hatayı bul ve düzelt; testleri çalıştır.")
    assert user_allows_test_edits("sil komutu için test ekle")
    assert user_allows_test_edits("testleri de güncelle")
    assert user_allows_test_edits("yanlış olan testi düzelt")
    assert is_test_path("tests/test_hesap.py") and is_test_path("src/a.spec.ts") and is_test_path("pkg/x_test.go")
    assert not is_test_path("hesap.py") and not is_test_path("src/latest.py")


def _guard_run(tmp_path, user_text, responses):
    import json as _json

    from evren_studio.agent.runner import AgentRunner
    from evren_studio.agent.tools import Workspace
    from evren_studio.api.client import ChatResult
    from evren_studio.db import Database

    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "test_h.py").write_text("assert f() == 90\nassert f() == 80\n", encoding="utf-8")
    seen = []

    class C:
        def __init__(self):
            self.rs = list(responses)

        def chat(self, model, messages, **kw):
            seen.append(messages)
            if not self.rs:
                return ChatResult(content="bitti", finish_reason="stop")
            old, new = self.rs.pop(0)
            return ChatResult(content="", finish_reason="tool_calls", tool_calls=[{
                "id": f"c{len(seen)}", "name": "edit_file",
                "arguments": _json.dumps({"path": "tests/test_h.py", "old_string": old, "new_string": new})}])

    db = Database(tmp_path / "t.db")
    try:
        sid = db.create_session("auto", str(tmp_path))
        db.add_session_message(sid, "user", user_text)
        out = AgentRunner(C(), "auto", session_id=sid, store=db, workspace=Workspace(tmp_path), mode="auto",
                          stream=False).run(db.get_session_messages(sid))
        tools_out = [m["content"] for m in db.get_session_messages(sid) if m["role"] == "tool"]
        return out, tools_out
    finally:
        db.close()


def test_istenmeden_test_degisirse_uyari_ve_tur_notu(tmp_path):
    out, tools_out = _guard_run(tmp_path, "testler geçecek şekilde kodu düzelt",
                                [("== 80", "== 90")])
    assert "⚠ Var olan bir TEST dosyasını değiştirdin (tests/test_h.py)" in tools_out[0]
    assert out.test_edits == ["tests/test_h.py"]


def test_geri_alinirsa_tur_notu_yok(tmp_path):
    out, tools_out = _guard_run(tmp_path, "testler geçecek şekilde kodu düzelt",
                                [("== 80", "== 90"), ("assert f() == 90\nassert f() == 90", "assert f() == 90\nassert f() == 80")])
    assert out.test_edits == []


def test_kullanici_isterse_uyari_yok(tmp_path):
    out, tools_out = _guard_run(tmp_path, "yanlış olan testi düzelt: 80 olmalı değil", [("== 80", "== 90")])
    assert "TEST dosyasını" not in tools_out[0] and out.test_edits == []


def test_olusturulacak_dosya_icin_uyari_yok(tmp_path):
    """2026-10-19 ölçümü: oluşturma isteğinde uyarı, zayıf modelleri soru sormaya itti."""
    from evren_studio.agent.scope import missing_mentions, wants_creation

    assert wants_creation("Yalnız standart kütüphaneyle kelime_say.py yaz: python kelime_say.py", "kelime_say.py")
    assert wants_creation("Sadece EVREN_PLAN.md dosyasına uygulanabilir bir görev planı yaz", "EVREN_PLAN.md")
    assert wants_creation("yeni bir rapor.md oluştur", "rapor.md")
    assert not wants_creation("ayarlar.yaml dosyasındaki timeout değerini 30 yap.", "ayarlar.yaml")
    assert missing_mentions("README.md dosyasına kurulum bölümü ekle", tmp_path) == []
    assert missing_mentions("config.json dosyasını oku ve port değerini söyle", tmp_path) == ["config.json"]
