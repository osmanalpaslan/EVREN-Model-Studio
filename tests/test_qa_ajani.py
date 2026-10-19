"""QA ajanı: plan/sonuç ayrıştırma, yürütücü, rapor, ön koşullar (2026-10-19; gerçek ağ/model yok)."""
from __future__ import annotations

import os

import pytest

from evren_studio.agent import qa
from evren_studio.api.errors import ApiError, ErrorKind

PLAN = """İnceledim.
<qa_plan>
{"calistirma": "statik: index.html",
 "senaryolar": [
   {"baslik": "Sayaç artar", "adimlar": ["Sayfayı aç", "Artır'a iki kez bas"], "beklenen": "sayaç 2 olur"},
   {"baslik": "Boş giriş", "adimlar": ["Formu boş gönder"], "beklenen": "hata mesajı görünür"},
   {"baslik": ""}
 ]}
</qa_plan>"""


def test_plan_ayristirilir_bos_baslik_atlanir():
    hint, scs = qa.parse_plan(PLAN)
    assert hint == "statik: index.html" and [s.title for s in scs] == ["Sayaç artar", "Boş giriş"]
    assert scs[0].steps == ["Sayfayı aç", "Artır'a iki kez bas"] and scs[1].idx == 2
    assert qa.parse_plan("plan yok")[1] == []
    fenced = '```json\n{"senaryolar": [{"baslik": "A"}]}\n```'
    assert [s.title for s in qa.parse_plan(fenced)[1]] == ["A"]          # blok yok, JSON var


def test_sonuc_ayristirma_ve_eksik_rapor():
    ok = qa.parse_result('Denedim.\n<qa_sonuc>{"sonuc": "geçti", "gerceklesen": "sayaç 2", "kanit": "p=2", "ozet": "çalışıyor"}</qa_sonuc>')
    assert ok == ("gecti", "sayaç 2", "p=2", "çalışıyor")
    assert qa.parse_result('<qa_sonuc>{"sonuc": "kaldi", "gerceklesen": "TypeError"}</qa_sonuc>')[0] == "kaldi"
    assert qa.parse_result('<qa_sonuc>{"sonuc": "engellendi"}</qa_sonuc>')[0] == "engellendi"
    st, *_rest, summ = qa.parse_result("sonuç yazmadım")
    assert st == "engellendi" and "bildirilmedi" in summ


def _state():
    _h, scs = qa.parse_plan(PLAN)
    return qa.QaState(goal="sayaç", run_hint="statik", scenarios=scs)


def test_yurutucu_sirayla_calistirir_raporlar():
    st = _state()
    asked, saved = [], []
    answers = iter([('<qa_sonuc>{"sonuc": "gecti", "ozet": "tamam"}</qa_sonuc>', "done", None),
                    ('<qa_sonuc>{"sonuc": "kaldi", "gerceklesen": "mesaj yok", "kanit": "konsol temiz"}</qa_sonuc>', "done", None)])

    def run(sc, prompt):
        asked.append((sc.idx, prompt))
        return next(answers)
    out = qa.QaRunner(st, qa.QaHooks(run_scenario=run, save=lambda s: saved.append(s.status))).run()
    assert out.status == "bitti" and [s.status for s in out.scenarios] == ["gecti", "kaldi"]
    assert "DOSYA DEĞİŞTİRME" in asked[0][1] and "<qa_sonuc>" in asked[0][1]
    assert "1. Sayaç artar: geçti" in asked[1][1]                       # önceki senaryo bağlamı
    rep = qa.render_report(out)
    assert "1 geçti · 1 kaldı" in rep and "## Düzeltilecekler" in rep and "mesaj yok" in rep
    goal = qa.fix_goal(out)
    assert "Boş giriş" in goal and "Sayaç artar" not in goal


def test_kesinti_bekler_kota_ve_iptal_duraklatir():
    st = _state()
    calls = []
    seq = iter([("", "error", ApiError(kind=ErrorKind.SERVER_UNAVAILABLE, message="503")),
                ('<qa_sonuc>{"sonuc": "gecti"}</qa_sonuc>', "done", None),
                ("", "error", ApiError(kind=ErrorKind.RATE_LIMIT, message="pencere"))])
    out = qa.QaRunner(st, qa.QaHooks(run_scenario=lambda sc, p: (calls.append(sc.idx), next(seq))[1],
                                     save=lambda s: None, sleep=lambda s: None)).run()
    assert calls == [1, 1, 2] and out.scenarios[0].status == "gecti"
    assert out.status == "duraklatildi" and "kota" in out.pause_reason and out.scenarios[1].status == "bekliyor"
    # kaldığı yerden sürer: geçen tekrar koşulmaz
    calls.clear()
    out2 = qa.QaRunner(out, qa.QaHooks(run_scenario=lambda sc, p: (calls.append(sc.idx),
                                                                   ('<qa_sonuc>{"sonuc":"gecti"}</qa_sonuc>', "done", None))[1],
                                       save=lambda s: None)).run()
    assert calls == [2] and out2.status == "bitti"
    st3 = _state()
    out3 = qa.QaRunner(st3, qa.QaHooks(run_scenario=lambda sc, p: ("", "cancelled", None), save=lambda s: None)).run()
    assert out3.status == "duraklatildi" and out3.scenarios[0].status == "bekliyor"


def test_durum_json_gidip_gelir():
    st = _state()
    again = qa.QaState.from_json(st.to_json())
    assert again.scenarios[1].title == "Boş giriş" and again.run_hint == "statik"


# ---- arayüz -------------------------------------------------------------------------------------

@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    yield app, w
    w.close()


def test_on_kosullar_klasor_evren_playwright(win, tmp_path):
    _app, w = win
    sv = w.session
    assert "proje klasöründe" in sv.qa.precheck()
    sv.welcome.workspace = str(tmp_path)
    w.ctx._cached_key = ""
    w.ctx._provider_keys = {"anthropic": "sk-ant-api03-SAHTE1234567890abcdef", "openai": None}
    assert "yalnız ücretsiz EVREN" in sv.qa.precheck()                # ücretli anahtarla QA yok
    w.ctx._cached_key = "evren_llm_SAHTE_123456789"
    assert "Playwright" in sv.qa.precheck()
    from evren_studio.agent import mcp

    w.ctx.settings.mcp_servers = [mcp.playwright_config().to_dict()]
    assert sv.qa.precheck() == ""


def test_qa_modeli_her_zaman_evren(win):
    _app, w = win
    w.ctx._cached_key = "evren_llm_SAHTE_123456789"
    w.ctx._provider_keys = {"anthropic": "sk-ant-api03-SAHTE1234567890abcdef", "openai": None}
    w.session.model = "claude-sonnet-5-5"
    for role in ("plan", "kod"):
        model, fallbacks, _ = w.session.qa._evren_model(role)
        assert w.ctx.provider_of(model) == "evren" and all(w.ctx.provider_of(m) == "evren" for m in fallbacks)


def test_ai_chat_evren_only_ucretliye_gitmez(win, monkeypatch):
    _app, w = win
    w.ctx._cached_key = ""
    w.ctx._provider_keys = {"anthropic": "sk-ant-api03-SAHTE1234567890abcdef", "openai": None}
    with pytest.raises(RuntimeError, match="yalnız EVREN"):
        w.ctx.ai_chat("gorsel", [{"role": "user", "content": "x"}], evren_only=True)


def test_plan_ve_bitis_kartlari(win):
    _app, w = win
    from evren_studio.ui.qa_ui import QaDoneCard, QaPlanCard

    st = _state()
    card = QaPlanCard(st)
    hits = []
    card.approved.connect(lambda: hits.append("ok"))
    card.ok_btn.click()
    assert hits == ["ok"] and not card.ok_btn.isVisible()
    st.scenarios[0].status, st.scenarios[1].status = "gecti", "kaldi"
    done = QaDoneCard(st)
    fixes = []
    done.fix_requested.connect(lambda: fixes.append(1))
    done.fix_btn.click()
    assert fixes == [1]
    st.scenarios[1].status = "gecti"
    assert not hasattr(QaDoneCard(st), "fix_btn")                     # hata yoksa düzelt düğmesi yok


def test_qa_komutlari_listede(win):
    from evren_studio.ui.composer import SLASH_COMMANDS

    assert {"/qa", "/qa-duzelt", "/qa-devam", "/qa-durdur"} <= set(SLASH_COMMANDS)


def test_servis_bilgisi_istemde():
    st = _state()
    p = qa.scenario_prompt(st, st.scenarios[0], [], "server · http://127.0.0.1:8765/")
    assert "server · http://127.0.0.1:8765/" in p and "YENİDEN BAŞLATMA" in p
    assert "Şu an çalışan servisler: yok" in qa.scenario_prompt(st, st.scenarios[0], [])


def test_son_isaret_yoksa_bir_kez_hatirlatilir(tmp_path):
    from test_agent_runner import FakeClient, make_runner
    from evren_studio.api.client import ChatResult
    from evren_studio.db import Database

    db = Database(tmp_path / "t.db")
    try:
        root = tmp_path / "p"
        root.mkdir()
        client = FakeClient([ChatResult(content="Denedim, sorun yok.", finish_reason="stop"),
                             ChatResult(content='<qa_sonuc>{"sonuc": "gecti"}</qa_sonuc>', finish_reason="stop"),
                             ChatResult(content="fazla", finish_reason="stop")])
        runner, history, _ = make_runner(db, client, root, mode="auto", final_marker="<qa_sonuc>")
        runner.run(history)
        assert len(client.calls) == 2 and "<qa_sonuc>" in str(client.calls[1]["messages"][-1]["content"])
        client2 = FakeClient([ChatResult(content="yok", finish_reason="stop"), ChatResult(content="yine yok", finish_reason="stop")])
        r2, h2, _ = make_runner(db, client2, root, mode="auto", final_marker="<qa_sonuc>")
        r2.run(h2)
        assert len(client2.calls) == 2                                  # yalnız BİR kez
        client3 = FakeClient([ChatResult(content="işaretsiz normal yanıt", finish_reason="stop")])
        r3, h3, _ = make_runner(db, client3, root, mode="auto")
        r3.run(h3)
        assert len(client3.calls) == 1                                  # işaret istenmezse dürtme yok
    finally:
        db.close()


def test_sonuc_yoksa_ayni_baglamda_sonuc_istenir():
    st = _state()
    asked = []

    def ask(sc, prompt):
        asked.append((sc.idx, prompt))
        return '<qa_sonuc>{"sonuc": "kaldi", "gerceklesen": "uyarı yok"}</qa_sonuc>'
    out = qa.QaRunner(st, qa.QaHooks(run_scenario=lambda sc, p: ("denedim ama yazmadım", "done", None),
                                     save=lambda s: None, ask_result=ask)).run()
    assert [s.status for s in out.scenarios] == ["kaldi", "kaldi"] and len(asked) == 2
    assert "yalnız <qa_sonuc>" in asked[0][1]
    # sonuç zaten varsa ek tur yok
    asked.clear()
    qa.QaRunner(_state(), qa.QaHooks(run_scenario=lambda sc, p: ('<qa_sonuc>{"sonuc":"gecti"}</qa_sonuc>', "done", None),
                                     save=lambda s: None, ask_result=ask)).run()
    assert asked == []


def test_bozuk_json_sonuc_esnek_okunur():
    # 2026-10-19 gerçek koşu: değer içinde kaçışsız çift tırnak
    raw = ('<qa_sonuc>\n{"sonuc": "gecti",\n  "gerceklesen": "Selamla tıklandı; mesaj \'""\' kaldı",\n'
           '  "kanit": "evaluate: mesaj \'""\'; konsol temiz",\n  "ozet": "beklenen davranış sağlandı"}\n</qa_sonuc>')
    st, actual, ev, summ = qa.parse_result(raw)
    assert st == "gecti" and "mesaj" in actual and "konsol temiz" in ev and summ == "beklenen davranış sağlandı"
    assert qa.parse_result("<qa_sonuc>{bozuk ve anahtarsız}</qa_sonuc>")[0] == "engellendi"
