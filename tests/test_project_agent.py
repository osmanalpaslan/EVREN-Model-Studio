"""Proje ajanı çekirdeği (agent/project.py) — sahte görev yürütücüsüyle, gerçek ağ yok."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from evren_studio.agent import project as pj
from evren_studio.api.errors import ApiError, ErrorKind

PLAN_TEXT = """İnceledim, plan aşağıda.

<plan>
- [ ] 1. **Veritabanı katmanı**
  Bitti ölçütü: db.py tabloları oluşturur, testleri geçer
  Doğrulama: `python -m unittest discover -s tests`
  Bağımlı:
- [ ] 2. Komut satırı arayüzü
  Bitti ölçütü: `python cli.py ekle x` çalışır
  Doğrulama: yok
  Bağımlı: 1
- [ ] 3. README
  Bitti ölçütü: README kurulum ve kullanım içerir
  Bağımlı: 9, 2
</plan>
"""


def test_plan_ayristirma_ve_yazim():
    tasks = pj.parse_plan(PLAN_TEXT)
    assert [t.title for t in tasks] == ["Veritabanı katmanı", "Komut satırı arayüzü", "README"]
    assert tasks[0].check == "python -m unittest discover -s tests" and tasks[1].check == ""
    assert tasks[1].depends == [1] and tasks[2].depends == [2]          # geçersiz bağımlılık (9) atılır
    st = pj.ProjectState(goal="Kütüphane sistemi", tasks=tasks)
    text = pj.render_plan(st)
    assert "- [ ] 1. Veritabanı katmanı" in text and "Bitti ölçütü: README" in text
    again = pj.parse_plan(text)
    assert [t.title for t in again] == [t.title for t in tasks]           # kendi biçimini okuyabilir
    assert pj.ProjectState.from_json(st.to_json()).tasks[1].depends == [1]


def test_inceleme_ayristirma():
    assert pj.parse_review('```json\n{"tamam": true, "neden": "ölçüt sağlandı"}\n```') == (True, "ölçüt sağlandı")
    assert pj.parse_review('{"tamam": false, "neden": "test yok"}')[0] is False
    assert pj.parse_review("bozuk yanıt")[0] is False


class Fake:
    """Senaryo: görev başına deneme sonuçları listesi (TaskRun veya ApiError)."""

    def __init__(self, root: Path, script: dict[int, list], reviews: dict[int, list] | None = None,
                 quota: list | None = None):
        self.root = root
        self.script = {k: list(v) for k, v in script.items()}
        self.reviews = {k: list(v) for k, v in (reviews or {}).items()}
        self.quota = list(quota or [])
        self.prompts: list[tuple[int, str, bool]] = []
        self.saved = 0
        self.slept = 0.0
        self.current = 0

    def run_task(self, task, prompt, fallback):
        self.current = task.idx
        self.prompts.append((task.idx, prompt, fallback))
        step = self.script[task.idx].pop(0)
        if isinstance(step, ApiError):
            return pj.TaskRun(stopped="error", error=step)
        if step.get("write"):
            (self.root / step["write"]).write_text(step.get("text", "x"), encoding="utf-8")
        return pj.TaskRun(stopped=step.get("stopped", "done"), summary=step.get("summary", "yaptım"),
                          model=step.get("model", "deepseek-v4-flash"))

    def review(self, messages):
        seq = self.reviews.get(self.current)
        ok = seq.pop(0) if seq else True
        return '{"tamam": %s, "neden": "%s"}' % ("true" if ok else "false", "tamam" if ok else "ölçüt sağlanmadı")

    def hooks(self, **kw):
        return pj.ProjectHooks(run_task=self.run_task, review=self.review,
                               run_check=lambda cmd: (0, "OK"), save=self._save,
                               quota_wait=lambda: self.quota.pop(0) if self.quota else (0.0, ""),
                               sleep=self._sleep, **kw)

    def _save(self, state):
        self.saved += 1
        pj.write_files(self.root, state)

    def _sleep(self, s):
        self.slept += s


def _git_repo(root: Path) -> None:
    def g(*a):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@t", "-c", "core.hooksPath=", *a],
                       cwd=root, check=True, capture_output=True)
    g("init", "-q", "-b", "master")
    (root / "README.md").write_text("# p\n", encoding="utf-8")
    g("add", "-A")
    g("commit", "-q", "-m", "ilk")


needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git yok")


@needs_git
def test_basarili_akis_dal_ve_commitler(tmp_path):
    _git_repo(tmp_path)
    fake = Fake(tmp_path, {1: [{"write": "db.py"}], 2: [{"write": "cli.py"}], 3: [{"write": "README.md", "text": "# yeni"}]})
    st = pj.ProjectState(goal="hedef", tasks=pj.parse_plan(PLAN_TEXT))
    out = pj.ProjectRunner(st, tmp_path, fake.hooks()).run()
    assert out.status == "bitti" and all(t.status == "bitti" for t in out.tasks)
    assert out.git and out.branch.startswith("evren-proje/")
    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True,
                         encoding="utf-8").stdout
    assert log.count("EVREN proje görev") == 3
    cur = subprocess.run(["git", "branch", "--show-current"], cwd=tmp_path, capture_output=True, text=True).stdout
    assert cur.strip() == out.branch                                    # ana dala dokunulmadı
    assert "Tamamlanan görevler:\n- 1. Veritabanı katmanı" in fake.prompts[1][1]   # önceki özet var
    assert "[x] 3. README" in (tmp_path / pj.PLAN_FILE).read_text(encoding="utf-8")
    rep = pj.render_report(out)
    assert "tamamlandı" in rep and "birleştirin" in rep


@needs_git
def test_takilma_stash_ve_bagimli_atlanir(tmp_path):
    _git_repo(tmp_path)
    fake = Fake(tmp_path, {1: [{"write": "a.py"}] * 3, 2: [], 3: []}, reviews={1: [False, False, False]})
    st = pj.ProjectState(goal="hedef", tasks=pj.parse_plan(PLAN_TEXT))
    out = pj.ProjectRunner(st, tmp_path, fake.hooks()).run()
    t1, t2, t3 = out.tasks
    assert t1.status == "takildi" and t1.attempts == pj.MAX_ATTEMPTS and "stash" in t1.note
    assert t2.status == "atlandi" and t3.status == "atlandi"            # 3 → 2 → 1 zinciri
    assert [p[2] for p in fake.prompts] == [False, False, True]          # son deneme yedek modelle
    assert "ÖNCEKİ DENEME BAŞARISIZ" in fake.prompts[1][1]
    stash = subprocess.run(["git", "stash", "list"], cwd=tmp_path, capture_output=True, text=True,
                           encoding="utf-8").stdout
    assert "EVREN takılan görev 1" in stash                              # değişiklik silinmedi


def test_git_yoksa_commitsiz_calisir(tmp_path):
    fake = Fake(tmp_path, {1: [{"write": "a.py"}]})
    st = pj.ProjectState(goal="hedef", tasks=[pj.Task(1, "tek görev", "a.py var")])
    out = pj.ProjectRunner(st, tmp_path, fake.hooks()).run()
    assert out.status == "bitti" and not out.git and out.tasks[0].commit == ""


def test_hiz_siniri_ve_kesintide_bekler_basarisiz_saymaz(tmp_path):
    rl = ApiError(kind=ErrorKind.RATE_LIMIT, message="pencere", status=429, retry_after_seconds=120)
    down = ApiError(kind=ErrorKind.SERVER_UNAVAILABLE, message="bakım", status=503)
    fake = Fake(tmp_path, {1: [rl, down, {"write": "a.py"}]})
    st = pj.ProjectState(goal="hedef", tasks=[pj.Task(1, "tek görev")])
    out = pj.ProjectRunner(st, tmp_path, fake.hooks(), use_git=False).run()
    assert out.status == "bitti" and out.tasks[0].attempts == 1          # bekleme denemeden sayılmaz
    assert fake.slept >= 120 + pj.OUTAGE_WAITS[0]


def test_kota_bitince_duraklar_ve_devam_eder(tmp_path):
    fake = Fake(tmp_path, {1: [{"write": "a.py"}], 2: [{"write": "b.py"}]},
                quota=[(0.0, ""), (-1, "günlük kota bitti; yarın devam")])
    st = pj.ProjectState(goal="hedef", tasks=[pj.Task(1, "bir"), pj.Task(2, "iki")])
    out = pj.ProjectRunner(st, tmp_path, fake.hooks(), use_git=False).run()
    assert out.status == "duraklatildi" and "günlük kota" in out.pause_reason
    assert [t.status for t in out.tasks] == ["bitti", "bekliyor"]
    assert "/proje-devam" in pj.render_report(out)
    again = pj.ProjectState.from_json(out.to_json())                      # DB'den geri yükleme
    out2 = pj.ProjectRunner(again, tmp_path, fake.hooks(), use_git=False).run()
    assert out2.status == "bitti" and [p[0] for p in fake.prompts] == [1, 2]   # 1. görev tekrarlanmadı


def test_kimlik_hatasinda_duraklar(tmp_path):
    fake = Fake(tmp_path, {1: [ApiError(kind=ErrorKind.AUTH, message="anahtar geçersiz", status=401)]})
    st = pj.ProjectState(goal="hedef", tasks=[pj.Task(1, "bir")])
    out = pj.ProjectRunner(st, tmp_path, fake.hooks(), use_git=False).run()
    assert out.status == "duraklatildi" and "kimlik" in out.pause_reason


def test_dogrulama_komutu_basarisizsa_tekrar_dener(tmp_path):
    codes = [(1, "FAILED (failures=1)"), (0, "OK")]
    fake = Fake(tmp_path, {1: [{"write": "a.py"}, {"write": "a.py", "text": "y"}]})
    hooks = fake.hooks()
    hooks.run_check = lambda cmd: codes.pop(0)
    st = pj.ProjectState(goal="hedef", tasks=[pj.Task(1, "bir", "testler geçer", check="python -m unittest")])
    out = pj.ProjectRunner(st, tmp_path, hooks, use_git=False).run()
    assert out.tasks[0].status == "bitti" and out.tasks[0].attempts == 2
    assert "doğrulama komutu başarısız" in fake.prompts[1][1]


@needs_git
def test_plan_dosyasi_kirli_sayilmaz(tmp_path):
    """Ajanın kendi EVREN_PLAN.md'si yanlış 'kaydedilmemiş değişiklik' uyarısı vermesin."""
    _git_repo(tmp_path)
    g = pj.Git(tmp_path)
    (tmp_path / pj.PLAN_FILE).write_text("plan", encoding="utf-8")
    assert not g.dirty()
    (tmp_path / "kullanici.txt").write_text("x", encoding="utf-8")
    assert g.dirty()
