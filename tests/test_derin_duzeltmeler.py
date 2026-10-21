"""2026-10-21 hesap kapama oturumundan çıkan düzeltmeler (gerçek ağ yok).

Oturum: Derin Mod 1 sa 50 dk çalıştı, Excel raporu oluşmadı (12 görevden 3'ü bitti) ama "bitti, sorun yok"
dedi. Kök nedenler: iç içe PowerShell'de `$` yutulması (doğrulama komutu bozuk → görev 3 kez denendi),
zincirleme atlama, kullanıcıya sorulmayan kararlar, BOM'suz .ps1, görünmeyen alt ajanlar.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest

from evren_studio.agent import deep as dp
from evren_studio.agent import project as pj
from evren_studio.agent.tools import ToolBox, Workspace, needs_ps_bom, unwrap_powershell
from evren_studio.api.client import ChatResult

# ---- 1. iç içe PowerShell ------------------------------------------------------------------------


@pytest.mark.parametrize("cmd, want", [
    ('powershell -NoProfile -Command "$t=(Get-Content out\\isler.tsv).Count; Write-Output $t"',
     "$t=(Get-Content out\\isler.tsv).Count; Write-Output $t"),
    ('powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Write-Output \\"a b\\""', 'Write-Output "a b"'),
    ("pwsh -c Get-Date", "Get-Date"),
    ('powershell -NoProfile -Command "Get-ChildItem | Select-Object Name"', "Get-ChildItem | Select-Object Name"),
])
def test_ic_ice_powershell_acilir(cmd, want):
    assert unwrap_powershell(cmd) == want


@pytest.mark.parametrize("cmd", [
    'powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\\a.ps1"; Write-Output "EXIT=$LASTEXITCODE"',
    'powershell -NoProfile -Command "(Get-ChildItem x).Count"; powershell -NoProfile -Command "Test-Path y"',
    "powershell -NoProfile -Command 'Write-Output $env:USERNAME'",       # tek tırnak: dış kabuk genişletmez
    "Get-ChildItem -Force",
    "python -m pytest -q",
    "powershell -EncodedCommand SQBlAHgA",
])
def test_belirsiz_veya_gereksiz_durumlara_dokunulmaz(cmd):
    assert unwrap_powershell(cmd) == cmd


@pytest.mark.skipif(os.name != "nt", reason="yalnız Windows PowerShell")
def test_ic_ice_komut_gercekte_calisir(tmp_path):
    """Oturumdaki doğrulama komutu biçimi: eskiden dış kabuk `$t`'yi yutup ParameterBindingException veriyordu."""
    (tmp_path / "isler.tsv").write_text("a\nb\nc\n", encoding="utf-8")
    tb = ToolBox(Workspace(tmp_path))
    r = tb.run_command('powershell -NoProfile -Command "$t=(Get-Content isler.tsv).Count; Write-Output $t"',
                       timeout_seconds=60)
    assert r.exit_code == 0 and r.output.strip().splitlines()[-1].strip() == "3", r.output


# ---- 9. .ps1 BOM ----------------------------------------------------------------------------------

def _write(tb, path, text):
    ch = tb.prepare_write(path, text)
    tb.apply_change(ch)


def test_turkce_ps1_bom_ile_yazilir_digerleri_bomsuz(tmp_path):
    tb = ToolBox(Workspace(tmp_path))
    _write(tb, "tr.ps1", "Write-Output 'Açık işler'\n")
    _write(tb, "ascii.ps1", "Write-Output 'ok'\n")
    _write(tb, "a.py", "print('Açık')\n")
    assert (tmp_path / "tr.ps1").read_bytes().startswith(b"\xef\xbb\xbf")
    assert not (tmp_path / "ascii.ps1").read_bytes().startswith(b"\xef\xbb\xbf")
    assert not (tmp_path / "a.py").read_bytes().startswith(b"\xef\xbb\xbf")
    # BOM'suz ASCII betiğe Türkçe eklenince BOM'a geçer; okurken BOM görünmez
    tb.apply_change(tb.prepare_edit("ascii.ps1", "'ok'", "'Sözleşme'"))
    assert (tmp_path / "ascii.ps1").read_bytes().startswith(b"\xef\xbb\xbf")
    assert tb.load_text(tmp_path / "ascii.ps1").text == "Write-Output 'Sözleşme'\n"
    assert needs_ps_bom(Path("x.PSM1"), "ğ") and not needs_ps_bom(Path("x.txt"), "ğ")


@pytest.mark.skipif(os.name != "nt", reason="yalnız Windows PowerShell")
def test_bomlu_ps1_turkceyi_bozmadan_calisir(tmp_path):
    tb = ToolBox(Workspace(tmp_path))
    # ajanın kullandığı biçim (bu bilgisayarda betik çalıştırma politikası kapalı → Bypass + -File)
    _write(tb, "tr.ps1", "[Console]::OutputEncoding = [Text.Encoding]::UTF8\n"
                         "$s = 'Açık işler Sözleşme'\nWrite-Output $s.Length\nWrite-Output $s\n")
    r = tb.run_command("powershell -NoProfile -ExecutionPolicy Bypass -File tr.ps1", timeout_seconds=60)
    lines = r.output.strip().splitlines()
    assert r.exit_code == 0 and lines[0].strip() == "19" and "Açık işler Sözleşme" in r.output, r.output
    # bilinen kötü durum: aynı betik BOM'suz yazılınca PowerShell 5.1 ANSI okur (5 Türkçe harf 2'şer karakter)
    raw = (tmp_path / "tr.ps1").read_bytes()[3:]
    (tmp_path / "bomsuz.ps1").write_bytes(raw)
    bad = tb.run_command("powershell -NoProfile -ExecutionPolicy Bypass -File bomsuz.ps1", timeout_seconds=60)
    assert bad.output.strip().splitlines()[0].strip() == "24", bad.output


# ---- 2/3/5/8. Proje ajanı ------------------------------------------------------------------------

PLAN = """<plan>
- [ ] 1. Envanter
  Bitti ölçütü: profil var
- [ ] 2. Birleştir
  Bitti ölçütü: isler.tsv
  Doğrulama: `powershell -NoProfile -Command "$t=(Get-Content isler.tsv).Count; Write-Output $t"`
  Bağımlı: 1
- [ ] 3. Türet
  Bitti ölçütü: dağılım
  Bağımlı: 2
- [ ] 4. Bağımsız iş
  Bitti ölçütü: ayrı
</plan>"""


class Fake:
    def __init__(self, summaries: dict[int, list[str]], check=(0, "OK"), reviews: dict[int, list[bool]] | None = None):
        self.summaries = {k: list(v) for k, v in summaries.items()}
        self.check = check
        self.reviews = {k: list(v) for k, v in (reviews or {}).items()}
        self.prompts: list[tuple[int, str]] = []
        self.review_msgs: list[str] = []
        self.current = 0

    def run_task(self, task, prompt, fallback):
        self.current = task.idx
        self.prompts.append((task.idx, prompt))
        seq = self.summaries.get(task.idx) or ["yaptım"]
        text = seq.pop(0) if len(seq) > 1 else seq[0]
        return pj.TaskRun(stopped="done", summary=text, model="qwen3.8-flash-next")

    def review(self, messages):
        self.review_msgs.append(messages[-1]["content"])
        seq = self.reviews.get(self.current)
        ok = seq.pop(0) if seq else True
        return '{"tamam": %s, "neden": "x"}' % ("true" if ok else "false")

    def hooks(self):
        return pj.ProjectHooks(run_task=self.run_task, review=self.review,
                               run_check=lambda cmd: self.check, save=lambda s: None, sleep=lambda s: None)


def test_bozuk_dogrulama_komutu_gorevi_dusurmez_karari_inceleme_verir(tmp_path):
    broken = (1, "=(Get-Content isler.tsv).Count; Write-Output\nAt line:1 char:39\n+ ... Write-Output\n"
                 "    + CategoryInfo : InvalidArgument: (:) [Write-Output], ParameterBindingException\n"
                 "    + FullyQualifiedErrorId : MissingMandatoryParameter")
    fake = Fake({}, check=broken)
    st = pj.ProjectState(goal="g", tasks=pj.parse_plan(PLAN))
    out = pj.ProjectRunner(st, tmp_path, fake.hooks(), use_git=False).run()
    assert out.status == "bitti" and out.tasks[1].status == "bitti" and out.tasks[1].attempts == 1
    assert any("KOMUTUNUN yazımından" in m for m in fake.review_msgs)
    assert any("doğrulama komutunun kendisi bozuk" in x for x in out.log)


def test_betik_icindeki_hata_gercek_basarisizliktir(tmp_path):
    real = (1, "At C:\\p\\scripts\\birlestir.ps1:15 char:3\n+ $t = $h[$ix['x']]\nUnexpected token")
    assert not pj.check_command_broken(real[1])
    fake = Fake({}, check=real)
    st = pj.ProjectState(goal="g", tasks=pj.parse_plan(PLAN))
    out = pj.ProjectRunner(st, tmp_path, fake.hooks(), use_git=False).run()
    assert out.tasks[1].status == "takildi" and out.tasks[1].attempts == pj.MAX_ATTEMPTS


def test_takilan_gorev_varsa_proje_bitti_sayilmaz_surdurunce_yeniden_dener(tmp_path):
    fake = Fake({}, reviews={2: [False, False, False]})
    st = pj.ProjectState(goal="g", tasks=pj.parse_plan(PLAN))
    out = pj.ProjectRunner(st, tmp_path, fake.hooks(), use_git=False).run()
    assert [t.status for t in out.tasks] == ["bitti", "takildi", "atlandi", "bitti"]   # bağımsız iş yine yapıldı
    assert out.status == "duraklatildi" and out.pause_reason.startswith("Proje kısmen bitti (2/4)")
    assert "görev 2 takıldı" in out.pause_reason and "/proje-devam" in out.pause_reason
    # sürdürme: takılan görev sıfırdan, önceki nedenle; ona bağlı görev yeniden beklemeye
    fake.reviews = {}
    again = pj.ProjectState.from_json(out.to_json())
    out2 = pj.ProjectRunner(again, tmp_path, fake.hooks(), use_git=False).run()
    assert out2.status == "bitti" and [t.status for t in out2.tasks] == ["bitti"] * 4
    retry = [p for i, p in fake.prompts if i == 2][-1]
    assert "ÖNCEKİ DENEME BAŞARISIZ" in retry


def test_soru_ile_duran_gorev_projeyi_duraklatir_yanit_sonraki_istemlere_gecer(tmp_path):
    fake = Fake({1: ["Dosyaları inceledim.\n\nSORU: CRS verisi yok; CRS sayfası atlansın mı?", "tamam"]})
    st = pj.ProjectState(goal="g", tasks=pj.parse_plan(PLAN), context="SKILL özeti: 25 sütun")
    out = pj.ProjectRunner(st, tmp_path, fake.hooks(), use_git=False).run()
    t1 = out.tasks[0]
    assert out.status == "duraklatildi" and "kararınız gerekiyor" in out.pause_reason
    assert t1.status == "bekliyor" and t1.attempts == 0 and t1.note.startswith("SORU:")
    assert "SORU:" in fake.prompts[0][1] and "SKILL özeti: 25 sütun" in fake.prompts[0][1]   # talimat + bağlam
    out.answers.append("Görev 1 sorusu: CRS … → Yanıt: atla")
    t1.note = ""
    out2 = pj.ProjectRunner(out, tmp_path, fake.hooks(), use_git=False).run()
    assert out2.status == "bitti"
    assert "Kullanıcının kararları" in fake.prompts[-1][1] and "Yanıt: atla" in fake.prompts[-1][1]


def test_soru_ayiklama_ve_planlama_kurallari():
    assert pj.extract_question("bitti.\n**SORU:** Çıktı adı ne olsun?") == "Çıktı adı ne olsun?"
    assert pj.extract_question("Kullanıcıya soru sormadım, iş bitti.") == ""
    p = pj.planning_prompt("hedef")
    assert "SARMALAMA" in p and "kullanıcı BAŞINDA OLMADAN" in p
    old = pj.ProjectState.from_json(json.dumps({"goal": "g", "tasks": []}))        # eski kayıt okunur
    assert old.context == "" and old.answers == []


# ---- 5/6. Derin Mod çekirdeği ------------------------------------------------------------------------

def test_sorular_birlesir_tekrar_edenler_bir_kez():
    f = [{"data": {"sorular": ["CRS AKTIVASYON verisi yok; CRS sayfası atlansın mı?", "kısa"]}},
         {"data": {"sorular": ["CRS aktivasyon verisi olmadığı için CRS sayfası atlansın mı yoksa boş mu kalsın?",
                               "kullanici_listesi.tsv klasöre konacak mı?"]}},
         {"data": {}}]
    qs = dp.collect_questions(f)
    assert len(qs) == 2 and "kullanici_listesi" in qs[1]
    st = dp.DeepState(goal="g", questions=qs)
    assert "varsayımı" in dp.answers_text(st)
    st.answers = "1) atla 2) koydum"
    assert "Kullanıcının yanıtı" in dp.answers_text(st) and "2) koydum" in dp.plan_prompt("g", f, dp.answers_text(st))


class ScriptClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.seen: list[str] = []

    def chat(self, model, messages, **kw):
        self.seen.append(str(messages[-1].get("content")))
        return self.replies.pop(0) if self.replies else ChatResult(content="bitti", finish_reason="stop")

    def close(self):
        pass


def test_alt_ajan_blok_vermezse_yalniz_sonuc_turu_acilir(tmp_path):
    """R-26 ikinci katman: ikinci planlayıcı plan vermemişti."""
    client = ScriptClient([
        ChatResult(tool_calls=[{"id": "c1", "name": "list_files", "arguments": "{}"}]),
        ChatResult(content="İnceledim, plan şöyle olabilir…", finish_reason="stop"),
        ChatResult(content="Hâlâ düşünüyorum.", finish_reason="stop"),            # dürtmeye rağmen bloksuz
        ChatResult(content="<plan>\n- [ ] 1. İş\n  Bitti ölçütü: x\n</plan>", finish_reason="stop"),
    ])
    res = dp.run_subagent(client=client, model="m", fallbacks=[], root=tmp_path, prompt="planla", marker="<plan>")
    assert "<plan>" in res.text and pj.parse_plan(res.text)
    assert any("Araç KULLANMADAN" in s for s in client.seen)
    assert res.tools == 1 and res.seconds >= 0 and "list_files" in res.transcript


def test_dogrulama_istemi_nihai_ciktiyi_ve_gorevleri_ister():
    p = dp.verify_prompt("rapor", "+x", dp.VERIFY_LENSES[1], "1. [bitti] a\n2. [takıldı] b")
    assert "nihai çıktının" in p and "[takıldı] b" in p


# ---- arayüz akışı ----------------------------------------------------------------------------------

BULGU_SORU = ('<bulgu>{"ozet": "skill + 5 xlsx", "dosyalar": ["SKILL.md: kurallar"], "riskler": ["CRS yok"], '
              '"oneri": "önce sor", "sorular": ["CRS verisi yok: CRS sayfası atlansın mı?"]}</bulgu>')
PLAN2 = "<plan>\n- [ ] 1. Raporu yaz\n  Bitti ölçütü: rapor.xlsx var\n- [ ] 2. Özet\n  Bitti ölçütü: README\n</plan>"


class FakeClient:
    def __init__(self, task_replies=None):
        self.calls = []
        self.lock = threading.Lock()
        self.task_replies = list(task_replies or [])
        self.prompts: list[str] = []

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None, tools=None, **kw):
        sys_text = messages[0]["content"] if messages else ""
        users = [m for m in messages if m["role"] == "user"]
        first = users[0]["content"] if users else ""
        kind = ("review" if sys_text == pj.REVIEW_SYSTEM else "judge" if "tarafsız bir yargıç" in sys_text
                else "anla" if "DERİN MOD · ANLA" in first else "dogrula" if "ÇEKİŞMELİ DOĞRULAMA" in first
                else "plan" if "PROJE PLANLAMA" in first else "task")
        with self.lock:
            self.calls.append((kind, model))
            self.prompts.append(first)
        if kind == "review":
            return ChatResult(content='{"tamam": true, "neden": "ok"}', finish_reason="stop")
        if kind == "judge":
            return ChatResult(content='{"secim": "A", "neden": "net"}', finish_reason="stop")
        if kind == "anla":
            return ChatResult(content="İnceledim.\n" + BULGU_SORU, finish_reason="stop")
        if kind == "plan":
            return ChatResult(content=PLAN2, finish_reason="stop")
        if kind == "dogrula":
            return ChatResult(content='<denetim>{"sorunlar": [], "genel": "-"}</denetim>', finish_reason="stop")
        with self.lock:
            reply = self.task_replies.pop(0) if self.task_replies else "Görev tamamlandı."
        return ChatResult(content=reply, finish_reason="stop")

    def close(self):
        pass


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


def _wait(app, cond, timeout=30.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def _session(w, tmp_path, client, monkeypatch):
    proj = tmp_path / "proje"
    proj.mkdir()
    w.ctx.make_client = lambda log_sink=None: client
    s = w.session
    s.new_session()
    s.welcome._choose(str(proj))
    s.composer.set_model("auto-pro", emit=True)
    monkeypatch.setattr(s.deep, "_diff", lambda: "--- a/r\n+++ b/r\n+rapor\n")
    return s, proj


def test_derin_sorulari_planlamadan_once_sorar_yanit_gorevlere_iner(win, tmp_path, monkeypatch):
    from evren_studio.ui.project_ui import PlanCard
    from evren_studio.ui.transcript import ChoiceCard

    app, w = win
    client = FakeClient()
    s, proj = _session(w, tmp_path, client, monkeypatch)
    s.send("/derin hesap kapama raporunu excel olarak oluştur")
    assert _wait(app, lambda: s.deep.awaiting_answers)
    from PySide6.QtWidgets import QLabel

    def texts(card):
        return " ".join(lab.text() for lab in card.findChildren(QLabel))
    cards = [c for c in s.findChildren(ChoiceCard) if "kararınız" in texts(c)]
    assert cards and "CRS sayfası atlansın mı" in texts(cards[-1])
    assert "plan" not in [k for k, _m in client.calls]                  # yanıt gelmeden plan yok
    s.send("CRS sayfasını atla")                                          # mesaj kutusundan yanıt
    assert _wait(app, lambda: s.findChildren(PlanCard))
    assert any("CRS sayfasını atla" in p for p in client.prompts if "PROJE PLANLAMA" in p)
    # her görev dosyası bulmak yerine not + yanıtla başlar
    s.findChildren(PlanCard)[-1].approved.emit()
    assert _wait(app, lambda: s.deep.state.status == "bitti" and not s.deep.active, 40)
    task_prompts = [p for p in client.prompts if p.startswith("PROJE GÖREVİ")]
    assert task_prompts and "Proje bilgi notu" in task_prompts[0] and "CRS sayfasını atla" in task_prompts[0]
    # görünürlük: alt ajan notları ve dökümleri
    log_dir = Path(s.deep.state.log_dir)
    assert (log_dir / "anla-yapi.md").is_file() and any(log_dir.glob("plan-*.md"))
    assert any("anla-kod bitti" in x for x in s.deep.state.log)
    rep = (proj / dp.REPORT_FILE).read_text(encoding="utf-8")
    assert "Kullanıcıya sorulanlar" in rep and "CRS sayfasını atla" in rep
    # iki denetçi farklı modeller
    assert len({m for k, m in client.calls if k == "dogrula"}) == 2


def test_soru_yoksa_kart_cikmaz_sormadan_devam_da_calisir(win, tmp_path, monkeypatch):
    from evren_studio.ui.project_ui import PlanCard

    app, w = win
    client = FakeClient()
    s, _proj = _session(w, tmp_path, client, monkeypatch)
    s.send("/derin rapor ekle")
    assert _wait(app, lambda: s.deep.awaiting_answers)
    s.deep.answer("")                                                    # "Sormadan devam"
    assert _wait(app, lambda: s.findChildren(PlanCard))
    plan_prompt = next(p for p in client.prompts if "PROJE PLANLAMA" in p)
    assert "en makul varsayımı" in plan_prompt


def test_proje_kismen_biterse_derin_bitti_demez_bekler_surdurunce_dogrular(win, tmp_path, monkeypatch):
    from evren_studio.ui.project_ui import PlanCard

    app, w = win
    client = FakeClient(task_replies=["Baktım.\n\nSORU: Çıktı dosyasının adı ne olsun?"])
    s, proj = _session(w, tmp_path, client, monkeypatch)
    s.send("/derin rapor ekle")
    assert _wait(app, lambda: s.deep.awaiting_answers)
    s.deep.answer("atla")
    assert _wait(app, lambda: s.findChildren(PlanCard))
    s.findChildren(PlanCard)[-1].approved.emit()
    assert _wait(app, lambda: s.deep.waiting_project and not s.project.active, 30)
    st = s.deep.state
    assert st.status == "duraklatildi" and st.phase == "uygula" and "dogrula" not in [k for k, _m in client.calls]
    assert "tamamlanmadı" in st.project_note
    assert "Durum: duraklatildi" in (proj / dp.REPORT_FILE).read_text(encoding="utf-8")
    s.composer.set_text("")
    s.send("/proje-devam rapor.xlsx olsun")
    assert _wait(app, lambda: st.status == "bitti" and not s.deep.active and not s.deep.waiting_project, 40)
    assert "dogrula" in [k for k, _m in client.calls]
    assert any("rapor.xlsx olsun" in p for p in client.prompts if p.startswith("PROJE GÖREVİ"))
