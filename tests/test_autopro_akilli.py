"""Auto Pro akıllı seçim (F2, 2026-10-24): A6 zorluk, A7 iş türü rolleri, A10 tutarlılık, A11 kota, A5 kalite puanı,
A8 yoklama, A13 planlayan + yazan. Her otomatik kural için tetiklenmesi VE tetiklenmemesi gereken durum (R-22).
Gerçek ağ yok."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest

from evren_studio.agent import architect, modelstats, router
from evren_studio.agent.quota import QuotaGate
from evren_studio.agent.runner import AgentEvents, AgentRunner
from evren_studio.agent.tools import Workspace
from evren_studio.api.client import ChatResult
from evren_studio.api.errors import ApiError, ErrorKind
from evren_studio.db import Database

# ---- A6 zorluk ----------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "metin.py dosyasındaki selamda “Merhaba” kelimesini “Günaydın” yap. Başka hiçbir şeyi değiştirme.",
    "README.md'deki yazım hatasını düzelt.",
    "ayar.json'da ağ portunu 8080 yap ve en üst düzeye \"debug\": false ekle.",
    "app.py'yi incele",
])
def test_kisa_tek_dosyalik_is_kolay(text):
    assert modelstats.difficulty(text)[0] == "kolay"


@pytest.mark.parametrize("text", [
    "hesapla_kdv fonksiyonunun adını projenin her yerinde kdv_hesapla yap, sonra testleri çalıştır.",
    "`python -m unittest discover -s tests` testlerinin hepsi geçecek şekilde hesap.py'yi düzelt.",
    "Testlerden biri başarısız. Hatayı bul ve düzelt; testleri çalıştırıp geçtiğini göster.",
    "Bu klasörde Python ile bir kütüphane yönetim sistemi yapacağız: kitap ve üye kaydı, ödünç verme.",
    "a.py, b.py ve c.py dosyalarındaki logger çağrılarını değiştir",
    "oyun.py'yi çalıştır ve çıktısını bana söyle.",            # program çalıştırmak kolay sayılmaz
    "x" * 800,
])
def test_cok_dosyali_test_veya_uzun_is_kolay_degil(text):
    assert modelstats.difficulty(text)[0] != "kolay"


def test_zor_is_ve_proje_gorevi():
    assert modelstats.difficulty("Projeyi baştan yaz")[0] == "zor"
    assert modelstats.difficulty("a.py, b.py ve c.py dosyalarında düzenle")[0] == "zor"
    assert modelstats.difficulty("kısa", project_task=True) == ("zor", "proje görevi")
    assert modelstats.difficulty("selam.py'deki yazıyı değiştir")[0] != "zor"


def test_sikayet_algilama():
    assert modelstats.is_complaint("olmadı, hâlâ aynı hata")
    assert modelstats.is_complaint("yine çalışmıyor")
    assert not modelstats.is_complaint("teşekkürler, şimdi başlığı da büyüt")
    assert not modelstats.is_complaint("olmadı " + "x" * 400)          # uzun yeni istek şikâyet sayılmaz


# ---- A7 iş türü ---------------------------------------------------------------------------------

@pytest.mark.parametrize("text,kind", [
    ("satislar.xlsx dosyasından aylık rapor çıkar", "veri"),
    ("Bu CSV'deki müşterileri bölgeye göre özetle", "veri"),
    ("Basit bir platform oyunu yap, karakter zıplasın", "oyun"),
    ("Godot sahnesine düşman ekle", "oyun"),
    ("Ürünler için bir web sayfası yap, form doğrulaması olsun", "web"),
    ("index.html'deki CSS'i karanlık temaya çevir", "web"),
])
def test_is_turu_tetiklenir(text, kind):
    assert modelstats.task_kind(text, agentic=True)[0] == kind


@pytest.mark.parametrize("text", [
    "oyun.py'yi çalıştır ve çıktısını bana söyle.",       # dosya adı iş türü değildir
    "hesap.py'deki bölme hatasını düzelt",
    "web sayfası için csv dışa aktarma ekle",               # karışık iş → genel kod rolü
    "README.md'deki yazım hatasını düzelt.",
])
def test_is_turu_tetiklenmez(text):
    assert modelstats.task_kind(text, agentic=True)[0] == ""


def test_is_turu_proje_dosyalarindan_ama_kod_projesinde_csv_veri_yapmaz():
    assert modelstats.task_kind("aylık toplamları hesapla", agentic=True, files=["satis.xlsx", "ocak.csv"])[0] == "veri"
    assert modelstats.task_kind("aylık toplamları hesapla", agentic=True,
                                files=["app.py", "tests", "ornek.csv"])[0] == ""
    assert modelstats.task_kind("düşman ekle", agentic=True, files=["project.godot", "main.gd"])[0] == "oyun"
    assert modelstats.task_kind("başlığı değiştir", agentic=True, files=["index.html", "style.css"])[0] == "web"


def test_metin_rolu_yalniz_klasorsuz_sohbette():
    assert modelstats.task_kind("Müşteriye nazik bir e-posta yaz", agentic=False)[0] == "metin"
    assert modelstats.task_kind("Python'da liste nasıl sıralanır?", agentic=False)[0] == ""
    assert modelstats.task_kind("Müşteriye nazik bir e-posta yaz", agentic=True)[0] == ""
    assert modelstats.task_kind("Şu metnin yazım ve noktalama hatalarını düzelt: ...", agentic=False)[0] == "metin"
    assert modelstats.task_kind("Bu hatayı açıkla: TypeError", agentic=False)[0] == ""


# ---- yönlendirici: rol önceliği, A5 cezası, A10 ------------------------------------------------

def test_rol_onceligi():
    r = router.classify(agentic=True, level="kolay", level_reason="kısa")
    assert r[0] == "kod_kolay"
    assert router.classify(agentic=True, level="kolay", kind="veri")[0] == "veri"        # iş türü önce
    assert router.classify(agentic=True, mode="plan", level="kolay", kind="veri")[0] == "plan"
    assert router.classify(agentic=True, has_images=True, kind="web")[0] == "gorsel"
    assert router.classify(agentic=True, level="zor", level_reason="uzun")[0] == "kod"
    assert router.classify(agentic=False, level="kolay")[0] == "sohbet"                 # sohbette zorluk yok
    assert router.classify(agentic=False, kind="metin")[0] == "metin"
    assert router.classify(agentic=False, kind="veri")[0] == "sohbet"                   # veri rolü ajan işi
    assert router.classify(agentic=True)[0] == "kod"                                    # eski davranış


def test_yeni_rollerin_zincirleri_ve_etiketleri():
    for role in ("kod_kolay", "veri", "oyun", "web", "metin"):
        assert router.EVREN_ROUTES[role] and router.PAID_ROUTES[role] and role in router.ROLE_LABELS
    assert router.EVREN_ROUTES["kod_kolay"][0] == "gemma-4-31b"
    assert router.EVREN_ROUTES["kod"][0] != "gemma-4-31b"                               # gemma yalnız kolay işte önde


def test_kalite_cezasi_yalniz_siralamayi_degistirir():
    avail = {"deepseek-v4.1-flash", "qwen3.8-flash-next", "gemma-4-31b"}
    r = router.choose("kod", available=avail, penalties={"deepseek-v4.1-flash": "kalite puanı 0.40"})
    assert r.model == "qwen3.8-flash-next" and "deepseek-v4.1-flash" in r.fallbacks
    assert "geri alındı" in r.reason
    temiz = router.choose("kod", available=avail)
    assert temiz.model == "deepseek-v4.1-flash" and "geri alındı" not in temiz.reason
    # sağlıksız (30 dk) model cezalıdan da geride
    now = datetime.now(timezone.utc)
    health = {"qwen3.8-flash-next": {"healthy": 0, "last_test_at": now.isoformat()}}
    r2 = router.choose("kod", available=avail, health=health, now=now,
                       penalties={"deepseek-v4.1-flash": "x"})
    assert [r2.model, *r2.fallbacks] == ["gemma-4-31b", "deepseek-v4.1-flash", "qwen3.8-flash-next"]


def test_tutarlilik_yalniz_seedi_dinleyen_modelde_ve_veri_rolunde():
    assert router.consistent_body("veri", "gemma-4-31b") == {"temperature": 0, "seed": 42}
    assert router.consistent_body("veri", "deepseek-v4.1-flash") is None               # ölçüm: dinlemiyor
    assert router.consistent_body("kod", "gemma-4-31b") is None
    assert "betik" in router.ROLE_HINTS["veri"] and "kod" not in router.ROLE_HINTS


# ---- A5 kalite puanı -----------------------------------------------------------------------------

def _calls(model, n, role="kod"):
    return [{"model": model, "ok": 1, "role": role} for _ in range(n)]


def test_kalite_puani_tetiklenir_ve_tetiklenmez():
    assert modelstats.penalized(_calls("a", 10)) == {}
    az = _calls("a", 3) + [{"model": "a", "event": "loop"}] * 2
    assert modelstats.penalized(az) == {}                                             # az örnek → ceza yok
    cok = _calls("a", 10) + [{"model": "a", "event": "loop"}] * 3                    # 1 - 6/10 = 0.4
    assert "kalite puanı 0.40" in modelstats.penalized(cok)["a"]
    sinirda = _calls("a", 10) + [{"model": "a", "event": "loop"}] * 2                # 0.6 → ceza yok
    assert modelstats.penalized(sinirda) == {}
    isaret = [{"model": "b", "event": "feedback_bad"}] * 2
    assert "kötü işaretlendi" in modelstats.penalized(isaret)["b"]
    assert modelstats.penalized(isaret[:1]) == {}
    # yoklama ve yedeğe geçiş çağrı/olay sayılmaz
    q = modelstats.quality(_calls("a", 6, role=modelstats.PROBE_ROLE) + [{"model": "a", "event": "switch"}])
    assert q["a"]["calls"] == 0 and q["a"]["score"] is None


def test_yoklama_normal_hiza_ve_ozete_karismaz():
    rows = [{"model": "a", "ok": 1, "out_tokens": 400, "duration_s": 5, "first_chunk_s": 1}] * 6
    probes = [{"model": "a", "ok": 1, "role": modelstats.PROBE_ROLE, "out_tokens": 2, "duration_s": 0.3,
               "first_chunk_s": 0.2}] * 10
    assert modelstats.baselines(rows + probes)["a"].first_chunk_s == 1
    ev = modelstats.summary(rows + [{"model": "a", "ok": 0, "event": "loop"}])
    assert ev["a"]["calls"] == 6 and ev["a"]["errors"] == 0


# ---- koşucu: A10 gövde, A7 ipucu, A5 olaylar ------------------------------------------------------

class Script:
    def __init__(self, seq):
        self.seq = list(seq)
        self.bodies: list = []
        self.models: list = []
        self.systems: list = []

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, on_reasoning=None, tools=None, **kw):
        self.models.append(model)
        self.bodies.append(kw.get("extra_body"))
        self.systems.append(messages[0]["content"] if messages and messages[0]["role"] == "system" else "")
        r = self.seq.pop(0) if self.seq else ChatResult(content="bitti", finish_reason="stop")
        if isinstance(r, Exception):
            raise r
        return r


class Ev(AgentEvents):
    def __init__(self):
        self.statuses = []

    def status(self, text):
        self.statuses.append(text)

    def approval_needed(self, request):
        request.resolve(request.ALLOW)


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "t.db")
    yield d
    d.close()


def _runner(db, tmp_path, client, **kw):
    proj = tmp_path / "p"
    proj.mkdir(exist_ok=True)
    sid = db.create_session("x", str(proj))
    db.add_session_message(sid, "user", "görev")
    r = AgentRunner(client, "gemma-4-31b", session_id=sid, store=db, events=Ev(), workspace=Workspace(proj),
                    mode="auto", stream=False, **kw)
    return r, db.get_session_messages(sid)


def test_tutarlilik_govdesi_her_cagrida_ve_model_degisince_birakilir(db, tmp_path):
    err = ApiError(kind=ErrorKind.SERVER_ERROR, message="x", status=500)
    c = Script([ChatResult(content="1", tool_calls=[{"id": "a", "name": "list_files", "arguments": "{}"}],
                           finish_reason="tool_calls"), err, ChatResult(content="bitti", finish_reason="stop")])
    r, hist = _runner(db, tmp_path, c, base_body={"temperature": 0, "seed": 42},
                      fallback_models=["deepseek-v4.1-flash"], route_role="veri")
    r.run(hist)
    assert c.bodies[0] == {"temperature": 0, "seed": 42} and c.bodies[1] == {"temperature": 0, "seed": 42}
    assert c.models[-1] == "deepseek-v4.1-flash" and not (c.bodies[-1] or {}).get("seed")


def test_rol_ipucu_sistem_istemine_eklenir_yoksa_eklenmez(db, tmp_path):
    c = Script([ChatResult(content="bitti", finish_reason="stop")])
    r, hist = _runner(db, tmp_path, c, extra_hint=router.ROLE_HINTS["veri"])
    r.run(hist)
    assert "Veri / rapor işi" in c.systems[0]
    c2 = Script([ChatResult(content="bitti", finish_reason="stop")])
    r2, hist2 = _runner(db, tmp_path, c2)
    r2.run(hist2)
    assert "Veri / rapor işi" not in c2.systems[0] and c2.bodies[0] is None


def test_dongu_kalite_olayi_olarak_kaydedilir(db, tmp_path):
    kayit = []
    same = {"id": "a", "name": "read_file", "arguments": json.dumps({"path": "yok.txt"})}
    c = Script([ChatResult(content="", tool_calls=[dict(same, id=f"c{i}")], finish_reason="tool_calls")
                for i in range(12)])
    r, hist = _runner(db, tmp_path, c, stats_sink=kayit.append, route_role="kod_kolay")
    out = r.run(hist)
    assert out.stopped == "loop"
    loops = [k for k in kayit if k.get("event") == "loop"]
    assert len(loops) == 1 and loops[0]["model"] == "gemma-4-31b" and loops[0]["role"] == "kod_kolay"


def test_normal_turda_kalite_olayi_yok(db, tmp_path):
    kayit = []
    c = Script([ChatResult(content="bitti", finish_reason="stop")])
    r, hist = _runner(db, tmp_path, c, stats_sink=kayit.append)
    r.run(hist)
    assert not [k for k in kayit if k.get("event")]


# ---- A11 kota kapısı -----------------------------------------------------------------------------

class Q:
    def __init__(self, ratio, daily):
        self.usage_ratio, self.daily_remaining_tokens = ratio, daily
        self.reset_at, self.daily_reset_at = None, "2026-10-25T00:00:00Z"


def test_normal_turda_gunluk_kota_durdurmaz_pencere_bekletir():
    g = QuotaGate(lambda: Q(0.2, 10_000))
    assert g.before_call() == "daily"                                   # Derin/Proje: duraklat
    assert g.before_call(daily_blocks=False) is None                    # normal tur: devam (uyarı arayüzde)
    slept = []
    now = [0.0]

    def sleep(sec):                                                     # sahte saat: gerçekten beklemez
        slept.append(sec)
        now[0] += sec
    g2 = QuotaGate(lambda: Q(0.9, 5_000_000), sleep=sleep, clock=lambda: now[0])
    notes = []
    assert g2.before_call(status=notes.append, daily_blocks=False) is None
    assert slept and "yenilenmesi bekleniyor" in notes[0]
    g3 = QuotaGate(lambda: Q(0.5, 5_000_000), sleep=sleep, clock=lambda: now[0])
    n = len(slept)
    assert g3.before_call(daily_blocks=False) is None and len(slept) == n   # pencere rahat → bekleme yok


# ---- A13 planlayan + yazan ------------------------------------------------------------------------

def test_plan_blogu_okunur():
    assert architect.extract("ön söz <uygulama_plani>\nAmaç: x\n</uygulama_plani> son") == "Amaç: x"
    assert architect.extract("<uygulama_plani>\nAmaç: kapanışsız") == "Amaç: kapanışsız"
    assert architect.extract("plan yok") == ""
    assert "Planlayıcının planı" in architect.hint("Amaç: x", "deepseek") and architect.hint("", "d") == ""


def test_planlayici_yalniz_zor_iste_ve_farkli_motorda():
    ok = dict(enabled=True, auto_pro=True, agentic=True, mode="auto", level="zor", planner="a", writer="b")
    assert architect.wanted(**ok)
    assert not architect.wanted(**{**ok, "enabled": False})              # ayar kapalı (varsayılan)
    assert not architect.wanted(**{**ok, "level": "normal"})
    assert not architect.wanted(**{**ok, "mode": "plan"})
    assert not architect.wanted(**{**ok, "writer": "a"})                 # aynı motor → anlamsız
    assert not architect.wanted(**{**ok, "agentic": False})


def test_planlayici_salt_okunur_alt_ajanla_plan_getirir(tmp_path):
    (tmp_path / "app.py").write_text("print(1)\n", encoding="utf-8")
    c = Script([ChatResult(content="<uygulama_plani>\nAmaç: test\nAdımlar:\n1. app.py\n</uygulama_plani>",
                           finish_reason="stop")])
    plan, res = architect.make_plan(client=c, model="deepseek-v4.1-flash", fallbacks=[], root=tmp_path,
                                    request="bir CLI ekle")
    assert plan.startswith("Amaç: test") and c.models == ["deepseek-v4.1-flash"]
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "print(1)\n"
    bozuk = Script([ApiError(kind=ErrorKind.AUTH, message="x", status=401)])
    plan2, _ = architect.make_plan(client=bozuk, model="m", fallbacks=[], root=tmp_path, request="x")
    assert plan2 == ""                                                    # hata → plansız devam


# ---- A8 yoklama ve arayüz (AppContext / SessionView) --------------------------------------------

@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
    yield app, w
    w.close()


class ProbeClient:
    def __init__(self, fail=()):
        self.fail = set(fail)
        self.models = []

    def chat(self, model, messages, **kw):
        self.models.append(model)
        assert kw.get("max_tokens") and kw.get("max_tokens") <= 64             # yoklama hafif
        if model in self.fail:
            raise ApiError(kind=ErrorKind.SERVER_ERROR, message="bozuk", status=500)
        return ChatResult(content="tamam", finish_reason="stop", usage={"completion_tokens": 2}, first_chunk_s=0.3)

    def close(self):
        pass


def _probe_sync(ctx, **kw):
    import threading

    done = threading.Event()
    got = []
    started = ctx.probe_models("test", on_done=lambda r: (got.extend(r), done.set()), **kw)
    if started:
        assert done.wait(10)
    return started, got


def test_yoklama_kaydeder_bozugu_sona_alir_ve_30_dkda_bir(win):
    _app, w = win
    ctx = w.ctx
    pc = ProbeClient(fail={"deepseek-v4.1-flash"})
    ctx.probe_client_factory = lambda: pc
    assert ctx.probe_models("test") is False                              # testlerde otomatik yoklama kapalı
    started, got = _probe_sync(ctx, force=True)
    assert started and set(pc.models) == set(ctx.probe_candidates()) and "deepseek-v4.1-flash" in pc.models
    rows = ctx.db.recent_model_calls(1)
    assert all(r["role"] == modelstats.PROBE_ROLE for r in rows) and len(rows) == len(pc.models)
    h = ctx.db.get_model_health("deepseek-v4.1-flash")
    assert h is not None and not h["healthy"] and h["last_error"].startswith("yoklama:")
    assert ctx.ai_route("kod").model != "deepseek-v4.1-flash"             # 30 dk sıranın sonunda
    assert not ctx.probe_due()                                            # 30 dk dolmadan tekrar yok
    # sonraki başarılı yoklama yalnız YOKLAMA hatasını temizler
    ctx.probe_client_factory = lambda: ProbeClient()
    _probe_sync(ctx, force=True)
    assert ctx.db.get_model_health("deepseek-v4.1-flash")["healthy"]


def test_yoklama_yavaslik_beklemesine_dokunmaz(win):
    _app, w = win
    ctx = w.ctx
    ctx.db.upsert_model_health("gemma-4-31b", False, error="gemma-4-31b → x: yavaşlık: ...")
    ctx.probe_client_factory = lambda: ProbeClient()
    _probe_sync(ctx, force=True)
    assert not ctx.db.get_model_health("gemma-4-31b")["healthy"]


def test_kotu_yanit_isareti_bir_kez_sayilir_ve_geri_yuklenir(win):
    _app, w = win
    from evren_studio.ui.transcript import AssistantMessageWidget

    ctx = w.ctx
    a = AssistantMessageWidget("gemma-4-31b", True)
    a.finalize("yanıt")
    a.api_model, a.msg_id = "gemma-4-31b", 41
    got = []
    a.feedback_bad.connect(lambda m, i: (got.append((m, i)), ctx.record_feedback_bad(m, i)))
    a._mark_bad()
    a._mark_bad()                                                         # ikinci tık sayılmaz
    assert got == [("gemma-4-31b", 41)] and not a.bad_btn.isEnabled()
    ctx.record_feedback_bad("gemma-4-31b", 41)                            # aynı mesaj yeniden → sayılmaz
    assert ctx.db.marked_bad_messages() == {41}
    assert "gemma-4-31b" not in ctx.model_penalties()                     # tek işaret ceza değil
    ctx.record_feedback_bad("gemma-4-31b", 42)
    assert "gemma-4-31b" in ctx.model_penalties()
    assert ctx.ai_route("kod_kolay").model != "gemma-4-31b"
    b = AssistantMessageWidget("x", True)
    b.finalize("eski yanıt")
    b.api_model = ""
    b._mark_bad()
    assert b.bad_btn.isEnabled()                                          # gerçek model bilinmiyorsa işaret yok


def test_oturum_rotasi_zorluk_tur_ve_yukseltme(win, tmp_path):
    _app, w = win
    s = w.session
    proj = tmp_path / "proje"
    proj.mkdir()
    s.new_session()
    s.welcome._choose(str(proj))
    s.workspace = str(proj)

    def rota(text, **meta):
        return s._route([{"role": "user", "content": text, "meta": meta}])

    assert rota("README.md'deki yazım hatasını düzelt.").role == "kod_kolay"
    assert rota("Testlerden biri başarısız. Hatayı bul ve düzelt.").role == "kod"
    assert rota("satislar.xlsx dosyasından aylık rapor çıkar").role == "veri"
    s._last_route_role = "kod_kolay"
    assert rota("olmadı, düzelt").role == "kod"                           # şikâyet → güçlü motor
    s._last_route_role, s._kolay_fail = "kod_kolay", True
    assert rota("README.md'deki yazım hatasını düzelt.").role == "kod"   # önceki kolay tur başarısız
    s._kolay_fail = False
    w.ctx.settings.autopro_smart = False
    assert rota("README.md'deki yazım hatasını düzelt.").role == "kod"   # ayar kapalı → eski davranış
    w.ctx.settings.autopro_smart = True
    # "devam" otomatik mesajı işin kendisi değil: önceki gerçek istek belirler
    hist = [{"role": "user", "content": "satislar.xlsx dosyasından aylık rapor çıkar"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "devam", "meta": {"auto_continue": True}}]
    assert s._route(hist).role == "veri"
