"""Tek "Sağlayıcılar ve anahtarlar" ekranı (2026-11-12, kullanıcı isteği: OpenAI/Claude için ayrı alanlar yerine Kilo
Code gibi TÜM API anahtarları ve motorlar için genel bir alan).

Ücretli istek YAPILMAZ: istemciler sahte HTTP / sahte list_models ile sınanır (R-17). Anahtar yalnız kasaya
(sahte keyring) yazılır, ayar dosyasına asla. Tetiklenen ve tetiklenmeyen durumlar ayrı (R-22).
"""
from __future__ import annotations

import json
import os
import time

import httpx
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from evren_studio import secrets  # noqa: E402
from evren_studio.api import providers  # noqa: E402
from evren_studio.api.errors import ApiError, ErrorKind  # noqa: E402

SVC = "EVREN-Model-Studio"
OAI = "sk-proj-SAHTE1234567890abcdef"
ANT = "sk-ant-api03-SAHTE1234567890abcdef"
EVR = "evren_llm_SAHTEANAHTAR1234567890"


@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    yield app, w
    w.close()
    providers.unregister_gateways(set())


def _wait(app, cond, timeout=6.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def _models(*ids):
    return [type("M", (), {"id": i})() for i in ids]


# ---- katalog ----------------------------------------------------------------------------------------------------

def test_sablon_katalogu_tum_saglayicilar_tek_listede():
    from evren_studio.ui import connections as cn

    keys = [t.key for t in cn.templates()]
    for k in ("evren", "openai", "anthropic", "gemini", "deepseek", "openrouter", "kilo", "groq", "xai", "mistral",
              "together", "fireworks", "moonshot", "huggingface", "vercel", "ollama", "lmstudio", "openai_uyumlu",
              "tavily"):
        assert k in keys, k
    assert len(keys) == len(set(keys)), "tekrar yok"
    assert [t.key for t in cn.templates() if t.group == "populer"] == list(cn.POPULAR)
    for t in cn.templates():
        if t.gateway and t.key != "openai_uyumlu":
            assert providers.GATEWAY_KINDS[t.key]["base_url"].startswith(("https://", "http://localhost")), t.key
    yerel = {t.key for t in cn.templates() if not t.key_required}
    assert yerel == {"ollama", "lmstudio", "openai_uyumlu"}, "yalnız yerel/özel türler anahtarsız"
    assert {"gw-x"} and providers.KEYLESS_KINDS == yerel


def test_yerel_turler_ucretsiz_kaydedilir():
    providers.register_gateway("gw-test-ollama", "ollama")
    providers.register_gateway("gw-test-gemini", "gemini")
    try:
        assert providers.PROVIDERS["gw-test-ollama"].paid is False
        assert providers.PROVIDERS["gw-test-gemini"].paid is True and not providers.PROVIDERS["gw-test-gemini"].verified
    finally:
        providers.unregister_gateways(set())


# ---- hata nedenleri (Kilo Code gibi satırda) ----------------------------------------------------------------------

@pytest.mark.parametrize("exc,beklenen", [
    (ApiError(ErrorKind.AUTH, "401", status=401), "Anahtar reddedildi"),
    (ApiError(ErrorKind.VALIDATION, "Please pass a valid API key", status=400), "Anahtar reddedildi"),  # Gemini: 400
    (ApiError(ErrorKind.NETWORK, "bağlanamadı"), "ulaşılamadı"),
    (ApiError(ErrorKind.TIMEOUT, "zaman aşımı"), "ulaşılamadı"),
    (ApiError(ErrorKind.NOT_FOUND, "yok", status=404), "Adres bulunamadı"),
    (ApiError(ErrorKind.QUOTA_EXHAUSTED, "kredi", status=402), "Kredi bitti"),
    (ApiError(ErrorKind.RATE_LIMIT, "429", status=429), "Hız sınırı"),
    (ApiError(ErrorKind.SERVER_ERROR, "500", status=500), "Sağlayıcı hatası"),
    (ConnectionRefusedError("refused"), "ulaşılamadı"),
    (ValueError("bozuk json"), "Beklenmeyen yanıt"),
])
def test_hata_nedeni(exc, beklenen):
    from evren_studio.ui.connections import describe_error

    assert beklenen in describe_error(exc)


# ---- bağlantı denemesi doğru istemciye ve adrese gider --------------------------------------------------------------

def test_deneme_dogru_istemci_ve_adres(win, monkeypatch):
    from evren_studio.api.anthropic_client import AnthropicClient
    from evren_studio.api.client import EvrenClient
    from evren_studio.api.compat_client import CompatClient
    from evren_studio.api.openai_client import OpenAIClient
    from evren_studio.ui import connections as cn

    app, w = win
    seen = []
    for cls in (EvrenClient, OpenAIClient, AnthropicClient, CompatClient):
        monkeypatch.setattr(cls, "list_models",
                            lambda self, c=cls: seen.append((c.__name__, self.base_url, self.api_key)) or _models("m1"))
    assert cn.probe(w.ctx, "openai", OAI) == ["m1"]
    assert cn.probe(w.ctx, "anthropic", ANT) == ["m1"]
    assert cn.probe(w.ctx, "evren", EVR) == ["m1"]
    assert cn.probe(w.ctx, "gemini", "AIzaSAHTE") == ["m1"]
    assert cn.probe(w.ctx, "openai_uyumlu", "", "http://localhost:9999/v1") == ["m1"]
    names = [s[0] for s in seen]
    assert names[:2] == ["OpenAIClient", "AnthropicClient"] and seen[0][2] == OAI and seen[1][2] == ANT
    assert seen[2][0] == "EvrenClient" and seen[2][2] == EVR and "evren" in seen[2][1]
    assert seen[3][0] == "CompatClient" and "generativelanguage.googleapis.com" in seen[3][1]
    assert seen[4][1].startswith("http://localhost:9999") and seen[4][2] == "", "anahtarsız yerel sunucu (başlık yok)"


def test_tavily_denemesi_yazilan_anahtarla(win, monkeypatch):
    from evren_studio.agent import websearch
    from evren_studio.ui import connections as cn

    app, w = win
    got = []
    monkeypatch.setattr(websearch, "usage", lambda key="auto", client=None: got.append(key) or (
        {"plan": "x", "used": 1, "limit": 10} if key == "tvly-iyi" else None))
    assert cn.probe(w.ctx, "tavily", "tvly-iyi") == [] and got == ["tvly-iyi"]
    with pytest.raises(ApiError) as e:
        cn.probe(w.ctx, "tavily", "tvly-kotu")
    assert "Anahtar reddedildi" in cn.describe_error(e.value)


# ---- kaydet / kaldır (Qt'siz çekirdek) --------------------------------------------------------------------------------

def test_sabit_yuvalar_kasaya_dogru_adla_ve_onbellek_yenilenir(win, fake_keyring):
    from evren_studio.ui import connections as cn

    app, w = win
    ctx = w.ctx
    assert not ctx.has_api_key()
    for tkey, key, name in (("evren", EVR, "evren_api_key"), ("openai", OAI, "openai_api_key"),
                            ("anthropic", ANT, "anthropic_api_key"), ("tavily", "tvly-SAHTE123", "tavily_api_key")):
        assert cn.save_connection(ctx, tkey, key) == tkey
        stored = {k: v for (s, k), v in fake_keyring.store.items() if s == SVC}
        assert key in stored.values(), tkey
    assert ctx.api_key() == EVR and ctx.provider_key("openai") == OAI and ctx.provider_key("anthropic") == ANT
    conf = (ctx.store.path).read_text(encoding="utf-8") if ctx.store.path.exists() else ""
    for k in (EVR, OAI, ANT, "tvly-SAHTE123"):
        assert k not in conf, "anahtar ayar dosyasına yazılmaz"
    ids = [c.id for c in cn.connections(ctx)]
    assert ids[0] == "evren" and {"openai", "anthropic", "tavily"} <= set(ids)
    for c in cn.connections(ctx):
        assert c.key_mask and all(k not in c.key_mask for k in (EVR, OAI, ANT, "tvly-SAHTE123")), "maskeli"
    cn.remove_connection(ctx, "openai")
    assert ctx.provider_key("openai") is None and "openai" not in [c.id for c in cn.connections(ctx)]
    cn.remove_connection(ctx, "evren")
    assert not ctx.has_api_key()
    first = cn.connections(ctx)[0]
    assert first.id == "evren" and not first.configured, "EVREN anahtarsız da listede (ekle düğmesiyle)"


def test_ag_gecidi_kaydi_anahtarsiz_ayar_modeller_secicide_auto_pro_disi(win, fake_keyring):
    from evren_studio.ui import connections as cn

    app, w = win
    ctx = w.ctx
    pid = cn.save_connection(ctx, "gemini", "AIzaSAHTE123456", models=["gemini-pro-x", "gemini-flash-y"])
    assert pid == "gw-gemini"
    g = ctx.gateways()[0]
    assert g["kind"] == "gemini" and g["base_url"].startswith("https://generativelanguage.googleapis.com")
    assert "AIzaSAHTE" not in json.dumps(ctx.settings.gateways)
    assert fake_keyring.store[(SVC, "gw-gemini_api_key")] == "AIzaSAHTE123456"
    ids = {m.id for m in ctx.chat_models()}
    assert "gw-gemini::gemini-pro-x" in ids and "gw-gemini::gemini-pro-x" not in ctx.available_model_ids()
    pid2 = cn.save_connection(ctx, "gemini", "AIzaIKINCI", models=["m"])
    assert pid2 == "gw-gemini-2", "aynı türden ikinci kayıt ayrı kimlik alır"
    # düzenleme: anahtar boş → eski anahtar korunur, modeller değişir
    cn.save_connection(ctx, "gemini", "", conn_id="gw-gemini", models=["yalniz-bu"])
    assert fake_keyring.store[(SVC, "gw-gemini_api_key")] == "AIzaSAHTE123456"
    assert next(x for x in ctx.gateways() if x["id"] == "gw-gemini")["models"] == ["yalniz-bu"]
    cn.remove_connection(ctx, "gw-gemini")
    assert [x["id"] for x in ctx.gateways()] == ["gw-gemini-2"] and (SVC, "gw-gemini_api_key") not in fake_keyring.store


# ---- pencere akışları ----------------------------------------------------------------------------------------------

def test_secim_sayfasi_arama_ve_gruplar(win):
    from PySide6.QtCore import Qt

    from evren_studio.ui import connections as cn

    app, w = win
    dlg = cn.ConnectionDialog(w.ctx)
    assert dlg.pages.currentIndex() == 0 and set(dlg.tiles) == set(cn.POPULAR)
    dlg.search.setText("groq")
    vis = [dlg.all_list.item(i) for i in range(dlg.all_list.count()) if not dlg.all_list.item(i).isHidden()]
    assert [it.data(Qt.UserRole) for it in vis] == ["", "groq"], "yalnız Groq ve kendi grup başlığı"
    assert not any(b.isVisibleTo(dlg) for b in dlg.tiles.values()), "popüler kutular da süzülür"
    dlg.search.setText("")
    assert all(not dlg.all_list.item(i).isHidden() for i in range(dlg.all_list.count()))
    item = next(dlg.all_list.item(i) for i in range(dlg.all_list.count()) if dlg.all_list.item(i).data(Qt.UserRole) == "ollama")
    dlg.all_list.itemClicked.emit(item)
    assert dlg.pages.currentIndex() == 1 and dlg.tpl.key == "ollama"
    assert dlg.base.isVisibleTo(dlg) and dlg.base.text() == "http://localhost:11434/v1"
    assert "isteğe bağlı" in dlg.key.placeholderText()
    dlg.back_btn.click()
    assert dlg.pages.currentIndex() == 0


def test_openai_ekleme_onek_uyarisi_ve_kayit(win, fake_keyring, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from evren_studio.ui import connections as cn

    app, w = win
    dlg = cn.ConnectionDialog(w.ctx, "openai")
    assert dlg.pages.currentIndex() == 1 and not dlg.models_box.isVisibleTo(dlg), "sabit yuvada model listesi yok"
    dlg.save()
    assert dlg.result_id is None and "yapıştırın" in dlg.status.text(), "anahtarsız kaydedilmez"
    dlg.key.setText("yanlis-onekli-anahtar")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    dlg.save()
    assert dlg.result_id is None and (SVC, "openai_api_key") not in fake_keyring.store, "uyarıda vazgeçildi"
    dlg.key.setText(OAI)
    dlg.save()
    assert dlg.result_id == "openai" and fake_keyring.store[(SVC, "openai_api_key")] == OAI


def test_ozel_saglayici_adres_denetimi_ve_elle_model(win, fake_keyring):
    from evren_studio.ui import connections as cn

    app, w = win
    dlg = cn.ConnectionDialog(w.ctx, "openai_uyumlu")
    dlg.base.setText("localhost:1234")
    dlg.manual.setText("yerel-model-7b")
    dlg._add_manual()
    dlg.save()
    assert dlg.result_id is None and "http" in dlg.status.text()
    dlg.base.setText("http://localhost:1234/v1")
    dlg.name.setText("Ofis sunucusu")
    dlg.save()
    assert dlg.result_id == "gw-openai-uyumlu"
    g = w.ctx.gateways()[0]
    assert g["name"] == "Ofis sunucusu" and g["models"] == ["yerel-model-7b"] and g["base_url"] == "http://localhost:1234/v1"
    assert not any(k == "gw-openai-uyumlu_api_key" for (_s, k) in fake_keyring.store), "anahtarsız: kasaya yazılmaz"


def test_deneme_dugmesi_modelleri_getirir_ve_hatayi_gosterir(win, monkeypatch):
    from evren_studio.api.compat_client import CompatClient, join_model
    from evren_studio.ui import connections as cn

    app, w = win
    dlg = cn.ConnectionDialog(w.ctx, "groq")
    dlg.test()
    assert "yapıştırın" in dlg.status.text(), "anahtar gerekli türde anahtarsız denenmez"
    monkeypatch.setattr(CompatClient, "list_models",
                        lambda self: _models(join_model(self.provider_id, "llama-x"), join_model(self.provider_id, "qwen-y")))
    dlg.key.setText("gsk_SAHTE123")
    dlg.test()
    assert _wait(app, lambda: "Bağlandı" in dlg.status.text())
    assert dlg.models.count() == 2 and "2 model" in dlg.status.text()

    def boom(self):
        raise ApiError(ErrorKind.AUTH, "Invalid API Key", status=401)

    monkeypatch.setattr(CompatClient, "list_models", boom)
    dlg.test()
    assert _wait(app, lambda: "✗" in dlg.status.text()) and "Anahtar reddedildi" in dlg.status.text()
    assert dlg.models.count() == 2, "başarısız denemede önceki liste silinmez"


def test_duzenleme_anahtari_korur_ve_turu_degistirmez(win, fake_keyring):
    from PySide6.QtCore import Qt

    from evren_studio.ui import connections as cn

    app, w = win
    cn.save_connection(w.ctx, "openrouter", "sk-or-ESKI123456", models=["a/b", "c/d"])
    dlg = cn.ConnectionDialog(w.ctx, "openrouter", conn_id="gw-openrouter")
    assert dlg.pages.currentIndex() == 1 and not dlg.back_btn.isVisibleTo(dlg), "düzenlemede seçim sayfasına dönülmez"
    assert "Kayıtlı anahtar" in dlg.key.placeholderText() and "ESKI123456" not in dlg.key.placeholderText()
    assert dlg.checked_models() == ["a/b", "c/d"]
    dlg.models.item(1).setCheckState(Qt.Unchecked)
    dlg.save()
    assert dlg.result_id == "gw-openrouter"
    assert fake_keyring.store[(SVC, "gw-openrouter_api_key")] == "sk-or-ESKI123456"
    assert w.ctx.gateways()[0]["models"] == ["a/b"]


# ---- Ayarlar ile bağlantılar ---------------------------------------------------------------------------------------

def test_ayarlarda_tek_liste_evren_ilk_ve_anahtar_ekle(win, monkeypatch):
    from PySide6.QtWidgets import QDialog, QPushButton

    from evren_studio.ui import connections as cn

    app, w = win
    page = w.pages["settings"]
    sec = page.connections
    assert list(sec.row_widgets)[0] == "evren"
    btns = [b.text() for b in sec.row_widgets["evren"].findChildren(QPushButton)]
    assert btns == ["Anahtar ekle"], "EVREN anahtarsızken tek düğme: Anahtar ekle"
    opened = []

    def fake_exec(dlg):
        opened.append(dlg.tpl.key if dlg.tpl else None)
        dlg.key.setText(EVR)
        dlg.save()
        return QDialog.Accepted

    monkeypatch.setattr(cn.ConnectionDialog, "exec", fake_exec)
    changed = []
    page.settings_saved.connect(lambda: changed.append(1))
    sec.row_widgets["evren"].findChildren(QPushButton)[0].click()
    assert opened == ["evren"] and w.ctx.api_key() == EVR and changed
    btns = [b.text() for b in sec.row_widgets["evren"].findChildren(QPushButton)]
    assert btns == ["Dene", "Düzenle", "Sil"]


def test_karsilama_anahtar_gir_dogrudan_evren_penceresi(win, monkeypatch):
    from PySide6.QtWidgets import QDialog

    from evren_studio.ui import connections as cn

    app, w = win
    opened = []
    monkeypatch.setattr(cn.ConnectionDialog, "exec", lambda dlg: opened.append(dlg.tpl.key) or QDialog.Rejected)
    w.session.welcome.open_settings.emit()
    assert _wait(app, lambda: opened == ["evren"])
    page = w.pages["settings"]
    assert w.center.currentWidget() is page and page.current_category() == "saglayicilar"


def test_anahtarsiz_ucretli_model_secimi_o_saglayicinin_penceresini_acar(win, monkeypatch):
    from PySide6.QtWidgets import QDialog

    from evren_studio.ui import connections as cn

    app, w = win
    opened = []
    monkeypatch.setattr(cn.ConnectionDialog, "exec", lambda dlg: opened.append(dlg.tpl.key) or QDialog.Rejected)
    w.session.set_model("claude-opus-5-5")
    assert _wait(app, lambda: opened == ["anthropic"])
    assert w.session.model != "claude-opus-5-5", "anahtarsız seçim geri alındı"


def test_satir_denemesi_sonucu_gosterir_ve_yenilemede_kalir(win, monkeypatch):
    from evren_studio.ui import connections as cn

    app, w = win
    cn.save_connection(w.ctx, "openai", OAI)
    sec = w.pages["settings"].connections
    sec.refresh()
    monkeypatch.setattr(cn, "probe", lambda ctx, t, k, b="": (_ for _ in ()).throw(
        ApiError(ErrorKind.QUOTA_EXHAUSTED, "insufficient_quota", status=429)))
    sec.test("openai")
    lab = sec.row_widgets["openai"].status_label
    assert _wait(app, lambda: "✗" in lab.text()) and "Kredi bitti" in lab.text()
    sec.refresh()
    assert "Kredi bitti" in sec.row_widgets["openai"].status_label.text(), "durum yenilemede kaybolmaz"


def test_model_secilmeden_ag_gecidi_kaydedilmez(win, fake_keyring):
    from evren_studio.ui import connections as cn

    app, w = win
    dlg = cn.ConnectionDialog(w.ctx, "deepseek")
    dlg.key.setText("sk-SAHTE123456")
    dlg.save()
    assert dlg.result_id is None and "En az bir model" in dlg.status.text()
    assert w.ctx.gateways() == [] and not any(k.startswith("gw-") for (_s, k) in fake_keyring.store)


def test_degistirilmis_adres_ve_kayitli_anahtarla_deneme(win, monkeypatch):
    from evren_studio.api.compat_client import CompatClient
    from evren_studio.ui import connections as cn

    app, w = win
    seen = []
    monkeypatch.setattr(CompatClient, "list_models",
                        lambda self: seen.append((self.base_url, self.api_key)) or _models("gw-gecici::m"))
    assert cn.probe(w.ctx, "openrouter", "sk-or-X", "https://vekil.example/v1") == ["m"]
    assert seen[-1][0].startswith("https://vekil.example"), "kullanıcının verdiği adres kullanılır"
    cn.save_connection(w.ctx, "openrouter", "sk-or-KAYITLI123", base_url="https://vekil.example/v1", models=["m"])
    dlg = cn.ConnectionDialog(w.ctx, "openrouter", conn_id="gw-openrouter")
    assert dlg.base.text() == "https://vekil.example/v1" and dlg.key.text() == ""
    dlg.test()                                            # anahtar yazılmadı → kayıtlı anahtarla denenir
    assert _wait(app, lambda: "Bağlandı" in dlg.status.text())
    # istemci "/v1"i içeride ayırıp yola ekler (istek https://vekil.example/v1/models'e gider)
    assert seen[-1][0].startswith("https://vekil.example") and seen[-1][1] == "sk-or-KAYITLI123"


# ---- anahtarsız yerel/özel sunucular (2026-11-12 bulgusu: modelleri seçicide hiç görünmüyordu) -------------------

def test_anahtarsiz_istekte_kimlik_basligi_gonderilmez():
    """Gerçek denemede Vercel AI Gateway "Bearer yok" başlığını reddetti; başlıksız istek 200 döndü."""
    from evren_studio.api.compat_client import CompatClient

    seen = []

    def handler(req: httpx.Request):
        seen.append(req.headers.get("authorization"))
        return httpx.Response(200, json={"data": [{"id": "m1"}]})

    for key in ("", "sk-gercek-anahtar"):
        CompatClient("http://localhost:11434/v1", key, "gw-ollama", transport=httpx.MockTransport(handler)).list_models()
    assert seen == [None, "Bearer sk-gercek-anahtar"]


def test_anahtarsiz_yerel_sunucu_modelleri_secicide_ve_kullanilir(win, fake_keyring):
    from evren_studio.api.compat_client import CompatClient
    from evren_studio.ui import connections as cn

    app, w = win
    ctx = w.ctx
    pid = cn.save_connection(ctx, "ollama", "", models=["qwen-yerel"])
    assert pid == "gw-ollama" and not ctx.has_provider_key(pid)
    assert pid in ctx.available_providers() and ctx.provider_ready(pid)
    assert "gw-ollama::qwen-yerel" in {m.id for m in ctx.chat_models()}
    assert "gw-ollama::qwen-yerel" not in ctx.available_model_ids(), "Auto Pro'ya yine girmez"
    c = ctx.make_client_for(pid)
    assert isinstance(c, CompatClient) and c.api_key == ""
    assert providers.PROVIDERS[pid].paid is False
    w.session.set_model("gw-ollama::qwen-yerel")
    assert w.session.model == "gw-ollama::qwen-yerel", "anahtar uyarısı çıkmadan seçilir"
    comp = w.session.composer
    w.session.refresh_models()
    comp._show_models()
    texts = [comp.popup.item(i).text() for i in range(comp.popup.count())]
    assert any("qwen-yerel" in t and "yerel · ücretsiz" in t for t in texts), "seçicide ücretli denmez"


def test_anahtar_isteyen_ag_gecidi_anahtarsizken_hazir_degil(win, fake_keyring):
    """Tetiklenmeyen durum: Groq gibi anahtar isteyen türde anahtar yoksa kullanılamaz (habersiz hata olmaz)."""
    app, w = win
    ctx = w.ctx
    ctx.settings.gateways = [{"id": "gw-groq", "kind": "groq", "name": "Groq",
                              "base_url": "https://api.groq.com/openai/v1", "models": ["llama-x"]}]
    ctx.save_settings()
    assert "gw-groq" not in ctx.available_providers() and not ctx.provider_ready("gw-groq")
    with pytest.raises(RuntimeError):
        ctx.make_client_for("gw-groq")
