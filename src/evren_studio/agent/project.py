"""Proje ajanı: büyük bir isteği planlayıp görev görev, gözetimsiz yürüten katman (Qt'siz).

Akış (kullanıcı kararları, 2026-10-19 — docs/ILERIDE_YAPILACAKLAR.md madde 3):
1. PLAN — güçlü bir modelle salt okunur bir turda proje incelenir; çıktı katı bir
   biçimde görev listesidir (her görevde "Bitti ölçütü", isteğe bağlı doğrulama
   komutu ve bağımlılıklar). Plan `EVREN_PLAN.md` olarak yazılır.
2. ONAY — kullanıcı planı onaylar (veya değişiklik ister). Onaysız yürütülmez.
3. YÜRÜTME — her görev TEMİZ bağlamla ayrı bir ajan turunda (Otomatik mod) çalışır;
   önceki görevlerden yalnızca kısa bir özet verilir (uzun sohbet şişmesi yok).
4. DOĞRULAMA — varsa doğrulama komutu çalışır; ikinci bir model görevin farkını
   ölçüte göre inceler (JSON karar).
5. KONTROL NOKTASI — git deposuysa ayrı dalda her başarılı görev commit'lenir;
   başarısız denemenin değişiklikleri `git stash` ile kenara alınır (silinmez).
6. TAKILMA — en fazla MAX_ATTEMPTS deneme (geri bildirimle; son deneme yedek
   modelle); olmazsa "takıldı" işaretlenir, ona bağlı görevler atlanır, bağımsız
   görevlerle devam edilir.
7. GÖZETİMSİZ — kota penceresi / günlük kota / EVREN kesintisinde beklenir veya
   temiz noktada duraklatılır; durum DB'de tutulur, kaldığı yerden devam edilir.
8. RAPOR — `EVREN_RAPOR.md` + arayüz kartı + Windows bildirimi.

Arayüz bu modülü `ProjectHooks` üzerinden bağlar (bkz. ui/session_view.py).
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ..api.errors import ApiError, ErrorKind

PLAN_FILE = "EVREN_PLAN.md"
REPORT_FILE = "EVREN_RAPOR.md"
MAX_TASKS = 15
MAX_ATTEMPTS = 3                  # 1: birincil · 2: geri bildirimle · 3: yedek modelle
OUTAGE_WAITS = (60, 120, 300, 600, 900)          # EVREN kesintisinde bekleme (sn), toplam ~33 dk
REVIEW_DIFF_LIMIT = 14_000

STATUS_LABEL = {"bekliyor": "bekliyor", "calisiyor": "çalışıyor", "bitti": "bitti",
                "takildi": "takıldı", "atlandi": "atlandı"}
STATUS_MARK = {"bekliyor": " ", "calisiyor": "~", "bitti": "x", "takildi": "!", "atlandi": "-"}


@dataclass
class Task:
    idx: int
    title: str
    criteria: str = ""
    check: str = ""                   # doğrulama komutu (PowerShell), isteğe bağlı
    depends: list[int] = field(default_factory=list)
    status: str = "bekliyor"
    attempts: int = 0
    model: str = ""
    commit: str = ""
    note: str = ""
    seconds: float = 0.0

    def todo(self) -> dict:
        """Yan paneldeki Görevler sekmesi biçimi."""
        st = {"bitti": "completed", "calisiyor": "in_progress"}.get(self.status, "pending")
        label = f"{self.idx}. {self.title}"
        if self.status in ("takildi", "atlandi"):
            label += f"  ({STATUS_LABEL[self.status]})"
        return {"content": label, "status": st}


@dataclass
class ProjectState:
    goal: str
    tasks: list[Task]
    status: str = "onay_bekliyor"     # onay_bekliyor | calisiyor | duraklatildi | bitti | durduruldu
    branch: str = ""
    base_commit: str = ""
    git: bool = False
    started_at: str = ""
    finished_at: str = ""
    pause_reason: str = ""
    log: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "ProjectState":
        d = json.loads(text)
        d["tasks"] = [Task(**t) for t in d.get("tasks") or []]
        return cls(**d)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for t in self.tasks:
            out[t.status] = out.get(t.status, 0) + 1
        return out


# ---- plan ---------------------------------------------------------------------------------

PLAN_FORMAT = """Yanıtının SONUNDA planı tam olarak şu biçimde ver (başka biçim kullanma):

<plan>
- [ ] 1. <kısa, tek iş içeren görev başlığı>
  Bitti ölçütü: <dışarıdan denetlenebilir sonuç>
  Doğrulama: `<isteğe bağlı PowerShell komutu, ör. python -m unittest discover -s tests>`
  Bağımlı: <yoksa boş bırak; varsa önceki görev numaraları, ör. 1, 2>
- [ ] 2. ...
</plan>

Kurallar: 3-{max} görev; her görev tek turda (en çok ~40 araç adımı) bitirilebilecek
büyüklükte olsun; testler ilgili görevin içinde yazılsın; son görev "tüm testleri
çalıştır ve README'yi güncelle" türünde bir toparlama olsun. Doğrulama komutu yalnız
proje klasöründe çalışan, kısa süren, girdi beklemeyen bir komut olabilir."""


def planning_prompt(goal: str, feedback: str = "") -> str:
    fb = f"\n\nKullanıcının önceki plana geri bildirimi:\n{feedback}\nPlanı buna göre düzelt." if feedback else ""
    return ("PROJE PLANLAMA (henüz kod yazma, dosya değiştirme).\n\nHedef:\n" + goal.strip() + fb
            + "\n\nÖnce proje klasörünü incele (dosya listesi, varsa README/testler), sonra hedefi "
            "uygulanabilir görevlere böl.\n\n" + PLAN_FORMAT.format(max=MAX_TASKS))


_TASK_RE = re.compile(r"^\s*-\s*\[[ xX~!\-]\]\s*(?:(\d+)[.)]\s*)?(.+?)\s*$")


def parse_plan(text: str) -> list[Task]:
    """<plan> bloğundan (yoksa tüm metinden) görevleri çıkarır."""
    m = re.search(r"<plan>(.*?)</plan>", text or "", re.S | re.I)
    body = m.group(1) if m else (text or "")
    tasks: list[Task] = []
    for line in body.splitlines():
        tm = _TASK_RE.match(line)
        if tm:
            title = re.sub(r"\*\*(.+?)\*\*", r"\1", tm.group(2)).strip()
            tasks.append(Task(idx=len(tasks) + 1, title=title[:200]))
            continue
        if not tasks:
            continue
        s = line.strip()
        low = s.lower()
        if low.startswith(("bitti ölçütü:", "bitti olcutu:", "ölçüt:")):
            tasks[-1].criteria = s.split(":", 1)[1].strip()
        elif low.startswith(("doğrulama:", "dogrulama:")):
            cmd = s.split(":", 1)[1].strip().strip("`").strip()
            tasks[-1].check = "" if cmd.lower() in ("", "yok", "-", "isteğe bağlı") else cmd
        elif low.startswith(("bağımlı:", "bagimli:")):
            tasks[-1].depends = [int(x) for x in re.findall(r"\d+", s.split(":", 1)[1])]
    for t in tasks:
        t.depends = [d for d in t.depends if 0 < d < t.idx]
    return tasks[:MAX_TASKS]


def render_plan(state: ProjectState) -> str:
    lines = ["# EVREN Proje Planı", "", "> EVREN Studio proje ajanı tarafından yazıldı ve güncellenir.", "",
             "## Hedef", "", state.goal.strip(), "", "## Görevler", ""]
    for t in state.tasks:
        lines.append(f"- [{STATUS_MARK.get(t.status, ' ')}] {t.idx}. {t.title}")
        if t.criteria:
            lines.append(f"  Bitti ölçütü: {t.criteria}")
        if t.check:
            lines.append(f"  Doğrulama: `{t.check}`")
        if t.depends:
            lines.append(f"  Bağımlı: {', '.join(map(str, t.depends))}")
        if t.status != "bekliyor":
            extra = f"  Durum: {STATUS_LABEL[t.status]}"
            if t.commit:
                extra += f" · commit {t.commit[:8]}"
            if t.note:
                extra += f" · {t.note[:200]}"
            lines.append(extra)
    lines.append("")
    lines.append("İşaretler: [x] bitti · [~] çalışıyor · [!] takıldı · [-] atlandı")
    return "\n".join(lines) + "\n"


def task_prompt(state: ProjectState, task: Task, feedback: str = "") -> str:
    done = [t for t in state.tasks if t.status == "bitti"]
    prev = "\n".join(f"- {t.idx}. {t.title}" + (f" — {t.note}" if t.note else "") for t in done) or "- (yok)"
    fb = (f"\n\nÖNCEKİ DENEME BAŞARISIZ OLDU. Neden:\n{feedback}\nBu sorunu gider; aynı yaklaşımı "
          "tekrarlama.") if feedback else ""
    check = f"\nDoğrulama komutu: `{task.check}` — bitirmeden önce çalıştır ve geçtiğini göster." if task.check else ""
    return (f"PROJE GÖREVİ {task.idx}/{len(state.tasks)}: {task.title}\n\n"
            f"Bitti ölçütü: {task.criteria or '(belirtilmedi — görevin açık sonucu)'}{check}\n\n"
            f"Projenin genel hedefi (bağlam için, bu turda YALNIZ yukarıdaki görevi yap):\n{state.goal.strip()}\n\n"
            f"Tamamlanan görevler:\n{prev}\n\n"
            "Gerekirse önce ilgili dosyaları oku. Bu görevin kapsamı dışına çıkma; sonraki görevleri "
            "yapma. Bitirince ne yaptığını ve ölçütün nasıl sağlandığını kısaca yaz." + fb)


# ---- inceleme --------------------------------------------------------------------------------

REVIEW_SYSTEM = ("Bir yazılım projesinde tek bir görevin sonucunu denetleyen titiz bir gözden geçirensin. "
                 "Yalnızca verilen görev ve bitti ölçütüne göre karar ver. Yanıtın YALNIZCA şu JSON olsun: "
                 '{"tamam": true|false, "neden": "<kısa Türkçe gerekçe>"}')


def review_messages(task: Task, diff: str, check_output: str, agent_summary: str) -> list[dict]:
    body = (f"Görev: {task.title}\nBitti ölçütü: {task.criteria or '(yok)'}\n\n"
            f"Ajanın özeti:\n{agent_summary[-2500:] or '(yok)'}\n\n"
            f"Doğrulama komutu çıktısı:\n{check_output[-3000:] or '(komut yok)'}\n\n"
            f"Değişiklikler (diff, kısaltılmış olabilir):\n{diff[:REVIEW_DIFF_LIMIT] or '(değişiklik yok)'}")
    return [{"role": "system", "content": REVIEW_SYSTEM}, {"role": "user", "content": body}]


def parse_review(text: str) -> tuple[bool, str]:
    m = re.search(r"\{.*\}", text or "", re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            return bool(d.get("tamam")), str(d.get("neden") or "")[:400]
        except json.JSONDecodeError:
            pass
    low = (text or "").lower()
    return ('"tamam": true' in low or "tamam: evet" in low), (text or "")[:300]


# ---- git -----------------------------------------------------------------------------------------

class Git:
    """Proje klasöründe git; yalnız güvenli işlemler (dal aç, commit, stash). reset/push YOK."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _run(self, *args: str, timeout: int = 60) -> tuple[int, str]:
        try:
            r = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout,
                               env=_git_env())
            return r.returncode, (r.stdout or r.stderr or "").strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            return -1, type(exc).__name__

    def is_repo(self) -> bool:
        return self._run("rev-parse", "--is-inside-work-tree")[0] == 0

    def head(self) -> str:
        c, o = self._run("rev-parse", "HEAD")
        return o if c == 0 else ""

    def dirty(self, ignore: tuple[str, ...] = (PLAN_FILE, REPORT_FILE, "EVREN_QA_RAPORU.md")) -> bool:
        """Kullanıcının kaydedilmemiş değişikliği var mı? Ajanın kendi plan/rapor dosyaları
        sayılmaz (2026-10-19: yazılan EVREN_PLAN.md yanlış "kaydedilmemiş değişiklik" uyarısı verdi)."""
        c, o = self._run("status", "--porcelain")
        if c != 0:
            return False
        paths = [line[3:].strip().strip('"') for line in o.splitlines() if line.strip()]
        return any(p not in ignore for p in paths)

    def start_branch(self, name: str) -> tuple[bool, str]:
        c, o = self._run("checkout", "-b", name)
        return c == 0, o

    def commit_all(self, message: str) -> str:
        self._run("add", "-A")
        c, o = self._run("commit", "-q", "-m", message)
        return self.head() if c == 0 else ""

    def stash(self, message: str) -> bool:
        return self._run("stash", "push", "-u", "-m", message)[0] == 0

    def diff_since(self, rev: str, limit: int = REVIEW_DIFF_LIMIT) -> str:
        """İzlenen dosyaların farkı + yeni (izlenmeyen) dosyaların içeriği. Git dizinine
        DOKUNMAZ: `add -N` stash'i bozuyordu (test_project_agent ile bulundu)."""
        c, o = self._run("diff", rev or "HEAD")
        parts = [o] if c == 0 and o else []
        c, names = self._run("ls-files", "--others", "--exclude-standard")
        for name in (names.splitlines() if c == 0 else []):
            if sum(len(x) for x in parts) > limit:
                break
            try:
                body = (self.root / name).read_text(encoding="utf-8", errors="replace")[:4000]
            except OSError:
                continue
            parts.append(f"--- yeni dosya: {name}\n{body}")
        return "\n".join(parts)


def _git_env() -> dict:
    import os

    env = dict(os.environ)
    env.setdefault("GIT_AUTHOR_NAME", "EVREN Studio")
    env.setdefault("GIT_AUTHOR_EMAIL", "evren-studio@localhost")
    env.setdefault("GIT_COMMITTER_NAME", env["GIT_AUTHOR_NAME"])
    env.setdefault("GIT_COMMITTER_EMAIL", env["GIT_AUTHOR_EMAIL"])
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


# ---- yürütücü --------------------------------------------------------------------------------

@dataclass
class TaskRun:
    """Bir görev denemesinin sonucu (arayüzdeki ajan turundan)."""
    stopped: str                      # done | loop | max_steps | error | cancelled | context_limit
    summary: str = ""                 # ajanın son yanıtı
    model: str = ""
    diff: str = ""                    # git yoksa uygulamanın değişiklik kaydından
    error: ApiError | None = None


@dataclass
class ProjectHooks:
    """Arayüzün sağladığı işlemler. run_task/review arka plan iş parçacığında çağrılır."""
    run_task: Callable[[Task, str, bool], TaskRun]          # (görev, istem, yedek_model_mi) → sonuç
    review: Callable[[list[dict]], str]                     # mesajlar → inceleme modeli yanıtı
    run_check: Callable[[str], tuple[int | None, str]]      # komut → (çıkış kodu, çıktı)
    save: Callable[[ProjectState], None]                    # durum kaydı (DB) + plan dosyası
    status: Callable[[str], None] = lambda text: None      # arayüz notu
    task_changed: Callable[[ProjectState], None] = lambda s: None
    quota_wait: Callable[[], tuple[float, str]] = lambda: (0.0, "")    # (bekle sn, neden) / (-1, neden)=duraklat
    commit_message: Callable[[Task, str], str] | None = None          # yapay zekâ commit mesajı (boş → şablon)
    cancelled: Callable[[], bool] = lambda: False
    sleep: Callable[[float], None] = time.sleep


class ProjectRunner:
    def __init__(self, state: ProjectState, root: Path, hooks: ProjectHooks, use_git: bool = True):
        self.state = state
        self.root = Path(root)
        self.hooks = hooks
        self.git = Git(self.root) if use_git else None

    # -- yardımcılar --
    def _log(self, text: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.state.log.append(f"{stamp} {text}")
        self.hooks.status(text)

    def _save(self) -> None:
        self.hooks.save(self.state)
        self.hooks.task_changed(self.state)

    def _wait(self, seconds: float, reason: str) -> bool:
        """Kesilebilir bekleme; iptal edilirse False."""
        self._log(f"Bekleniyor ({int(seconds)} sn): {reason}")
        remaining = float(seconds)
        while remaining > 0:
            if self.hooks.cancelled():
                return False
            chunk = min(5.0, remaining)
            self.hooks.sleep(chunk)          # 5 sn'lik parçalar: iptal hızlı fark edilir
            remaining -= chunk
        return not self.hooks.cancelled()

    def _prepare_git(self) -> None:
        st = self.state
        if self.git is None or not self.git.is_repo():
            st.git = False
            self._log("Proje git deposu değil: kontrol noktası commit'i yapılmayacak; değişiklikler "
                      "uygulamanın Değişiklikler panelinden geri alınabilir.")
            return
        st.git = True
        if st.branch:
            return                          # devam: dal zaten açıldı
        name = "evren-proje/" + datetime.now().strftime("%Y%m%d-%H%M%S")
        ok, out = self.git.start_branch(name)
        if not ok:
            st.git = False
            self._log(f"Git dalı açılamadı ({out[:120]}); commit yapılmadan devam ediliyor.")
            return
        st.branch = name
        if self.git.dirty():
            st.base_commit = self.git.commit_all("EVREN proje: başlangıç (önceki kaydedilmemiş değişiklikler)")
            self._log("Kaydedilmemiş değişiklikleriniz proje dalının ilk commit'ine alındı (kaybolmadı).")
        else:
            st.base_commit = self.git.head()
        self._log(f"Kontrol noktaları için '{name}' dalı açıldı; ana dalınıza dokunulmaz.")

    def _deps_failed(self, task: Task) -> list[int]:
        by = {t.idx: t for t in self.state.tasks}
        return [d for d in task.depends if by.get(d) and by[d].status in ("takildi", "atlandi")]

    # -- ana döngü --
    def run(self) -> ProjectState:
        st = self.state
        st.status = "calisiyor"
        st.pause_reason = ""
        st.started_at = st.started_at or datetime.now().isoformat(timespec="seconds")
        self._prepare_git()
        self._save()
        for task in st.tasks:
            if task.status in ("bitti", "takildi", "atlandi"):
                continue
            if self.hooks.cancelled():
                return self._pause("Kullanıcı durdurdu.")
            bad = self._deps_failed(task)
            if bad:
                task.status, task.note = "atlandi", f"bağlı olduğu görev(ler) tamamlanamadı: {bad}"
                self._log(f"Görev {task.idx} atlandı: {task.note}")
                self._save()
                continue
            result = self._run_task(task)
            if result == "pause":
                return st
        st.status = "bitti"
        st.finished_at = datetime.now().isoformat(timespec="seconds")
        self._log("Proje tamamlandı: " + ", ".join(f"{STATUS_LABEL[k]} {v}" for k, v in st.counts().items()))
        self._save()
        return st

    def _pause(self, reason: str) -> ProjectState:
        st = self.state
        for t in st.tasks:
            if t.status == "calisiyor":
                t.status = "bekliyor"
        st.status = "duraklatildi"
        st.pause_reason = reason
        self._log(f"Proje duraklatıldı: {reason}")
        self._save()
        return st

    def _run_task(self, task: Task) -> str:
        st = self.state
        feedback = ""
        outages = 0
        while task.attempts < MAX_ATTEMPTS:
            wait, why = self.hooks.quota_wait()
            if wait < 0:
                self._pause(why)
                return "pause"
            if wait > 0 and not self._wait(wait, why):
                self._pause("Kullanıcı durdurdu.")
                return "pause"
            task.status = "calisiyor"
            task.attempts += 1
            fallback = task.attempts >= MAX_ATTEMPTS
            self._log(f"Görev {task.idx}/{len(st.tasks)} başladı (deneme {task.attempts}): {task.title}")
            self._save()
            t0 = time.monotonic()
            run = self.hooks.run_task(task, task_prompt(st, task, feedback), fallback)
            task.seconds += time.monotonic() - t0
            task.model = run.model or task.model
            if run.stopped == "cancelled" or self.hooks.cancelled():
                task.attempts -= 1
                self._pause("Kullanıcı durdurdu.")
                return "pause"
            if run.error is not None:
                kind = run.error.kind
                if kind in (ErrorKind.RATE_LIMIT,):
                    task.attempts -= 1                       # hız sınırı başarısızlık sayılmaz
                    wait = run.error.retry_after_seconds or 300
                    if not self._wait(wait, "EVREN hız/kota penceresi doldu"):
                        self._pause("Kullanıcı durdurdu.")
                        return "pause"
                    continue
                if kind in (ErrorKind.SERVER_UNAVAILABLE, ErrorKind.SERVER_ERROR, ErrorKind.TIMEOUT,
                            ErrorKind.NETWORK, ErrorKind.UNKNOWN_RESULT):
                    task.attempts -= 1
                    if outages >= len(OUTAGE_WAITS):
                        self._pause(f"EVREN uzun süredir yanıt vermiyor ({kind.value}); daha sonra devam edin.")
                        return "pause"
                    if not self._wait(OUTAGE_WAITS[outages], f"EVREN geçici olarak yanıt vermiyor ({kind.value})"):
                        self._pause("Kullanıcı durdurdu.")
                        return "pause"
                    outages += 1
                    continue
                if kind in (ErrorKind.AUTH, ErrorKind.QUOTA_EXHAUSTED):
                    self._pause(f"Devam edilemiyor: {kind.value} — {run.error.message[:160]}")
                    return "pause"
                feedback = f"API hatası: {kind.value} {run.error.message[:200]}"
                continue
            ok, reason = self._verify(task, run)
            if ok:
                if self.git is not None and st.git:
                    message = f"EVREN proje görev {task.idx}: {task.title}"[:120]
                    if self.hooks.commit_message is not None:
                        suggested = self.hooks.commit_message(task, run.diff or self.git.diff_since("HEAD"))
                        if suggested:
                            message = f"{suggested.splitlines()[0][:72]}\n\nEVREN proje görev {task.idx}: " \
                                      f"{task.title}" + ("\n\n" + "\n".join(suggested.splitlines()[1:]).strip()
                                                       if len(suggested.splitlines()) > 1 else "")
                    task.commit = self.git.commit_all(message)
                task.status = "bitti"
                task.note = reason[:200] if reason else ""
                self._log(f"Görev {task.idx} bitti" + (f" (commit {task.commit[:8]})" if task.commit else ""))
                self._save()
                return "ok"
            feedback = reason or f"tur '{run.stopped}' ile bitti"
            self._log(f"Görev {task.idx} doğrulanamadı (deneme {task.attempts}): {feedback[:200]}")
            if task.attempts < MAX_ATTEMPTS and self.git is not None and st.git:
                pass                                       # sonraki deneme mevcut değişikliklerin üstünden düzeltir
        # tüm denemeler bitti
        task.status = "takildi"
        task.note = feedback[:300]
        if self.git is not None and st.git and self.git.dirty():
            if self.git.stash(f"EVREN takılan görev {task.idx}: {task.title}"[:120]):
                task.note += " · değişiklikler git stash'e alındı (silinmedi)"
            else:
                task.note += " · değişiklikler stash'e alınamadı, çalışma klasöründe duruyor"
        self._log(f"Görev {task.idx} takıldı; bağımsız görevlerle devam ediliyor.")
        self._save()
        return "failed"

    def _verify(self, task: Task, run: TaskRun) -> tuple[bool, str]:
        if run.stopped not in ("done", "max_steps", "loop", "context_limit"):
            return False, f"tur '{run.stopped}' ile bitti"
        check_out = ""
        if task.check:
            code, out = self.hooks.run_check(task.check)
            check_out = f"$ {task.check}\n(çıkış {code})\n{out}"
            if code != 0:
                return False, f"doğrulama komutu başarısız (çıkış {code}): {out.strip()[-300:]}"
        diff = run.diff
        if not diff and self.git is not None and self.state.git:
            diff = self.git.diff_since("HEAD")
        try:
            text = self.hooks.review(review_messages(task, diff, check_out, run.summary))
        except ApiError as exc:
            # İnceleme modeli yanıt vermezse komut geçtiyse kabul et; yoksa ajanın sözüne güvenme
            return (bool(task.check), f"inceleme yapılamadı ({exc.kind.value})"
                    + ("; doğrulama komutu geçti" if task.check else ""))
        return parse_review(text)


# ---- rapor ---------------------------------------------------------------------------------------

def render_report(state: ProjectState) -> str:
    c = state.counts()
    total_s = sum(t.seconds for t in state.tasks)
    lines = ["# EVREN Proje Raporu", "",
             f"- Durum: **{ {'bitti': 'tamamlandı', 'duraklatildi': 'duraklatıldı', 'durduruldu': 'durduruldu'}.get(state.status, state.status)}**"
             + (f" — {state.pause_reason}" if state.pause_reason else ""),
             f"- Görevler: {len(state.tasks)} · bitti {c.get('bitti', 0)} · takıldı {c.get('takildi', 0)}"
             f" · atlandı {c.get('atlandi', 0)} · bekliyor {c.get('bekliyor', 0)}",
             f"- Süre (görevlerde): {int(total_s // 60)} dk {int(total_s % 60)} sn",
             f"- Git: {'dal `' + state.branch + '`' if state.git else 'kullanılmadı (depo değil)'}",
             "", "## Görevler", ""]
    for t in state.tasks:
        lines.append(f"### {t.idx}. {t.title} — {STATUS_LABEL[t.status]}")
        if t.model:
            lines.append(f"- Model: {t.model} · deneme: {t.attempts}")
        if t.commit:
            lines.append(f"- Commit: `{t.commit[:12]}`")
        if t.note:
            lines.append(f"- Not: {t.note}")
        lines.append("")
    need = [t for t in state.tasks if t.status in ("takildi", "atlandi")]
    lines.append("## Sizden beklenen")
    lines.append("")
    if state.status == "duraklatildi":
        lines.append(f"- Proje duraklatıldı ({state.pause_reason}). Devam etmek için sohbette `/proje-devam` yazın.")
    for t in need:
        lines.append(f"- Görev {t.idx} ({STATUS_LABEL[t.status]}): {t.note or 'ayrıntı yok'}")
    if not need and state.status == "bitti":
        lines.append("- Değişiklikleri inceleyin" + (f" ve `{state.branch}` dalını ana dala birleştirin."
                                                    if state.git else "."))
    lines += ["", "## Günlük", ""] + [f"- {x}" for x in state.log[-60:]]
    return "\n".join(lines) + "\n"


def write_files(root: Path, state: ProjectState, report: bool = False) -> None:
    (Path(root) / PLAN_FILE).write_text(render_plan(state), encoding="utf-8")
    if report:
        (Path(root) / REPORT_FILE).write_text(render_report(state), encoding="utf-8")


def keep_awake(on: bool) -> None:
    """Windows: proje çalışırken bilgisayar uykuya geçmesin (yalnız bu iş parçacığı)."""
    try:
        import ctypes

        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
    except (AttributeError, OSError):
        pass
