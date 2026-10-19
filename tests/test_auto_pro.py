"""Auto Pro: sağlayıcıya duyarlı yönlendirme ve uygulamanın yapay zekâ işleri (2026-10-19).

Kullanıcı kararları: yalnız anahtarı girilen sağlayıcının motorları görünür; birden fazla
sağlayıcıda "dengeli" dağıtım; uygulamanın kendi yapay zekâ işleri bağlı API'den;
oturum başlığı, hata açıklaması, commit mesajı önerisi. Gerçek ağ yok.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time

import pytest

from evren_studio.agent import project as pj
from evren_studio.agent import router
from evren_studio.api.client import ChatResult
from evren_studio.api.errors import ApiError, ErrorKind

EVREN_IDS = {"deepseek-v4-flash", "qwen3.8-flash-next", "gemma-4-31b", "deepseek-v4.1-flash", "qwen3-vl-30b"}
OPENAI_IDS = {"gpt-6-luna", "gpt-6.1-sol", "gpt-6-astra", "gpt-5.3-codex"}
ANTH_IDS = {"claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"}


def test_zincir_yalniz_evren_yalniz_ucretli_ve_dengeli():
    assert router.chain_for("kod", EVREN_IDS)[0] == "deepseek-v4-flash"
    only_openai = router.chain_for("kod", OPENAI_IDS)
    assert only_openai and all(m in OPENAI_IDS for m in only_openai)          # EVREN yok → EVREN çıkmaz
    mixed = EVREN_IDS | ANTH_IDS
    kod = router.chain_for("kod", mixed)
    assert kod[0] in EVREN_IDS and any(m in ANTH_IDS for m in kod)           # çok token → önce ücretsiz
    plan = router.chain_for("plan", mixed)
    assert plan[0] == "claude-opus-5-5" and plan[-1] in EVREN_IDS            # az token yüksek değer → önce ücretli
    assert router.chain_for("baslik", OPENAI_IDS)[0] == "gpt-6-luna"         # ucuz model
    assert router.chain_for("kod", None) == router.EVREN_ROUTES["kod"]       # geriye uyum
    assert router.choose("kod", available=set()).model == "" or router.chain_for("kod", set()) == []


def test_eski_ad_tasinir():
    from evren_studio.config import migrate_raw

    assert migrate_raw({"default_model": "akilli"})["default_model"] == "auto-pro"
    assert router.normalize_model_id("akilli") == "auto-pro" and router.is_auto_pro("akilli")
    assert router.normalize_model_id("glm-5.3") == "glm-5.3"


# ---- uygulama bağlamı -----------------------------------------------------------------------

@pytest.fixture()
def ctx(tmp_path, monkeypatch, fake_keyring):
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    from evren_studio.config import Settings
    from evren_studio.ui.app_context import AppContext

    c = AppContext(Settings(data_dir=str(tmp_path / "data")))
    c._cached_key = ""
    yield c
    c.db.close()


def test_liste_anahtara_gore(ctx):
    ids = [m.id for m in ctx.chat_models()]
    assert "auto-pro" in ids and "auto" in ids                                # hiç anahtar yok: EVREN gösterilir
    ctx._provider_keys["openai"] = "sk-proj-SAHTE1234567890abcdef"
    ids = [m.id for m in ctx.chat_models()]
    assert ids[0] == "auto-pro" and "auto" not in ids and "glm-5.3" not in ids  # EVREN motorları çıkmaz
    assert "gpt-6-luna" in ids and "claude-haiku-5-5" not in ids
    assert ctx.provider_of("auto-pro") == "openai"
    assert ctx.available_model_ids() <= {c.id for c in ctx.paid_models}
    ctx._cached_key = "evren_llm_SAHTE_123456789"
    ids = [m.id for m in ctx.chat_models()]
    assert "auto" in ids and "gpt-6-luna" in ids and ctx.provider_of("auto-pro") == "evren"


class Client:
    def __init__(self, name, log, fail=None, text="tamam"):
        self.name, self.log, self.fail, self.text = name, log, fail, text

    def chat(self, model, messages, **kw):
        self.log.append(model)
        if self.fail:
            raise self.fail
        return ChatResult(content=self.text, finish_reason="stop",
                          usage={"input_tokens": 1000, "output_tokens": 100})

    def close(self):
        pass


def test_ai_chat_yedege_gecer_butceye_uyar_maliyet_kaydeder(ctx):
    ctx._cached_key = "evren_llm_SAHTE_123456789"
    ctx._provider_keys["anthropic"] = "sk-ant-api03-SAHTE1234567890abcdef"
    log = []
    down = ApiError(kind=ErrorKind.SERVER_UNAVAILABLE, message="bakım", status=503)
    ctx.make_client_for = lambda p, log_sink=None: Client(p, log, fail=down if p == "evren" else None)
    text, model = ctx.ai_chat("kod", [{"role": "user", "content": "x"}])
    assert model in ANTH_IDS and log[0] in EVREN_IDS                           # EVREN çöktü → ücretli yedek
    assert ctx.db.month_spend().get("anthropic", 0) > 0                         # maliyet kaydedildi
    # bütçe dolunca ücretli atlanır; EVREN de çöktüyse hata
    ctx.db.add_usage_cost("anthropic", "claude-haiku-5-5", {}, 99.0)
    log.clear()
    with pytest.raises(Exception):
        ctx.ai_chat("kod", [{"role": "user", "content": "x"}])
    assert all(m in EVREN_IDS for m in log)
    # kota hatasında yedeğe geçilmez (hesap başına)
    ctx.make_client_for = lambda p, log_sink=None: Client(
        p, log, fail=ApiError(kind=ErrorKind.RATE_LIMIT, message="pencere", status=429))
    with pytest.raises(ApiError):
        ctx.ai_chat("baslik", [{"role": "user", "content": "x"}])


# ---- arayüz ------------------------------------------------------------------------------

@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.Ok)
    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
    yield app, w
    w.close()


def _wait(app, cond, timeout=6.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def test_yalniz_ucretli_anahtarla_evren_ekranlari_gizlenir(win):
    app, w = win
    w._apply_providers()
    assert w.sidebar.nav_buttons["monitor"].isVisibleTo(w.sidebar)
    w.ctx._cached_key = ""
    w.ctx._provider_keys["anthropic"] = "sk-ant-api03-SAHTE1234567890abcdef"
    w.show_page("usage")
    w._apply_providers()
    for k in ("models", "usage", "monitor", "connection"):
        assert not w.sidebar.nav_buttons[k].isVisibleTo(w.sidebar), k
    assert w.center.currentWidget() is w.session                            # gizlenen sayfadan çıkıldı
    s = w.session
    s.refresh_models()
    ids = s.composer.model_ids()
    assert ids[0] == "auto-pro" and "auto" not in ids and "claude-sonnet-5-5" in ids
    s.welcome.refresh()
    assert not s.welcome.key_card.isVisibleTo(s.welcome)                     # bir anahtar var → uyarı yok
    s.refresh_usage()
    w.ctx.db.add_usage_cost("anthropic", "claude-haiku-5-5", {}, 0.5)
    s.update_usage_view()
    assert s.composer.usage_btn.text().startswith("$")                      # EVREN kotası yerine harcama


def test_otomatik_oturum_basligi(win, monkeypatch):
    app, w = win
    monkeypatch.delenv("EVREN_STUDIO_NO_AI_TITLE", raising=False)
    calls = []

    class C:
        def chat(self, model, messages, **kw):
            calls.append(messages[0]["content"][:20])
            if "başlık" in messages[0]["content"]:
                return ChatResult(content='"Python Liste Sıralama."', finish_reason="stop")
            return ChatResult(content="Şöyle sıralarsın: sorted(x)", finish_reason="stop")

        def close(self):
            pass

    w.ctx.make_client = lambda log_sink=None: C()
    s = w.session
    s.new_session()
    s.welcome._choose(None)
    s.send("python'da bir listeyi nasıl sıralarım acaba bilmiyorum")
    assert _wait(app, lambda: w.ctx.db.get_session(s.session_id)["title"] == "Python Liste Sıralama")
    # elle değiştirilen başlığa dokunulmaz
    s.new_session()
    s.welcome._choose(None)
    s.send("ikinci soru")
    w.ctx.db.update_session(s.session_id, title="Benim adım")
    assert _wait(app, lambda: not s.running)
    time.sleep(0.3)
    app.processEvents()
    assert w.ctx.db.get_session(s.session_id)["title"] == "Benim adım"


def test_hata_karti_yapay_zeka_aciklamasi(win):
    from evren_studio.ui.transcript import ErrorCard

    app, w = win
    s = w.session
    s.new_session()
    s.welcome._choose(None)
    w.ctx.ai_chat = lambda role, msgs, **kw: ("Sunucu bakımda; birkaç dakika sonra deneyin.", "deepseek-v4-flash")

    class Down:
        def chat(self, *a, **k):
            raise ApiError(kind=ErrorKind.SERVER_UNAVAILABLE, message="bakım", status=503)

        def close(self):
            pass

    w.ctx.make_client = lambda log_sink=None: Down()
    s.send("merhaba")
    assert _wait(app, lambda: s.findChildren(ErrorCard))
    card = s.findChildren(ErrorCard)[-1]
    btn = next(b for b in card.findChildren(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton)
               if "açıkla" in b.text())
    btn.click()
    assert _wait(app, lambda: "Sunucu bakımda" in card.body.text())
    assert "deepseek-v4-flash" in card.body.text()


needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git yok")


@needs_git
def test_commit_mesaji_onerisi(tmp_path):
    from evren_studio.ui.project_ui import clean_commit_message

    assert clean_commit_message('```\nCommit mesajı: "Sıcaklık dönüştürücü eklendi"\n```') == \
        "Sıcaklık dönüştürücü eklendi"
    assert clean_commit_message("") == ""
    env = {**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "T",
           "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q", "-b", "master"], cwd=tmp_path, env=env, check=True)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, env=env, check=True)
    subprocess.run(["git", "-c", "core.hooksPath=", "commit", "-qm", "ilk"], cwd=tmp_path, env=env, check=True)

    def run_task(task, prompt, fallback):
        (tmp_path / "b.txt").write_text("y", encoding="utf-8")
        return pj.TaskRun(stopped="done", summary="yaptım", model="m")

    hooks = pj.ProjectHooks(run_task=run_task, review=lambda m: '{"tamam": true}', run_check=lambda c: (0, ""),
                            save=lambda s: None, commit_message=lambda t, d: "b.txt dosyası eklendi")
    st = pj.ProjectState(goal="g", tasks=[pj.Task(1, "b ekle")])
    pj.ProjectRunner(st, tmp_path, hooks).run()
    log = subprocess.run(["git", "log", "-1", "--format=%B"], cwd=tmp_path, capture_output=True, text=True,
                         encoding="utf-8").stdout
    assert log.startswith("b.txt dosyası eklendi") and "EVREN proje görev 1: b ekle" in log


def test_ai_chat_dusunmeyi_kapatir_bos_yanitta_siradakine_gecer(ctx):
    """2026-10-19 gerçek ölçüm: kısa işlerde düşünen EVREN modelleri BOŞ yanıt veriyordu."""
    ctx._cached_key = "evren_llm_SAHTE_123456789"
    seen = []

    class C:
        def chat(self, model, messages, **kw):
            seen.append((model, kw.get("extra_body")))
            text = "" if len(seen) == 1 else "Kısa Başlık"
            return ChatResult(content=text, finish_reason="stop")

        def close(self):
            pass

    ctx.make_client_for = lambda p, log_sink=None: C()
    text, model = ctx.ai_chat("baslik", [{"role": "user", "content": "x"}], max_tokens=40)
    assert text == "Kısa Başlık" and len(seen) == 2                          # boş → sıradaki model
    assert seen[0] == ("deepseek-v4-flash", {"reasoning_effort": "none"})    # yedek listede de işaretli


def test_yedek_listede_dusunme_yetenegi_isaretli(ctx):
    assert (ctx.model_info("deepseek-v4-flash").capabilities or {}).get("reasoning_effort")
    assert not (ctx.model_info("gemma-4-31b").capabilities or {}).get("reasoning_effort")
