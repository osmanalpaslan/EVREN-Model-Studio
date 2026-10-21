"""Proje ajanının arayüz denetleyicisi: /proje komutları, plan onay kartı, gözetimsiz yürütme.

Çekirdek mantık Qt'siz `agent/project.py`'dedir (ProjectRunner). Burası onu
SessionView'a bağlar:
- Plan turu ve her görev turu, sohbetin NORMAL tur yolundan (start_run) geçer:
  araç kartları, canlı yanıt, değişiklik kaydı görünür. Ajan yalnızca o görevin
  mesajından itibaren geçmişi görür (temiz bağlam) ve Otomatik modda çalışır.
- ProjectRunner arka plan iş parçacığında döner; görev turlarını Qt sinyaliyle ana
  iş parçacığına yaptırır ve tur bitene kadar bekler (R-11).
- Durum DB'de (project_runs) ve proje klasöründe EVREN_PLAN.md / EVREN_RAPOR.md.
"""
from __future__ import annotations

import difflib
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ..agent import project as pj
from ..agent import router
from ..agent.tools import ToolBox, Workspace
from ..api.errors import ApiError
from . import icons, theme
from .workers import Task

QUOTA_CACHE_S = 60
DAILY_MIN_TOKENS = 400_000         # günlük kalan bunun altına inerse temiz noktada duraklat
WINDOW_PAUSE_RATIO = 0.85          # 5 dk penceresi bu orana gelince yenilenmesini bekle

PROJECT_COMMANDS = {
    "/proje": "Proje ajanı: /proje <hedef> — plan çıkarır, onayınızla görev görev yürütür",
    "/proje-duzelt": "Proje planını değiştir: /proje-duzelt <geri bildirim>",
    "/proje-devam": "Duraklatılan projeyi kaldığı yerden sürdür",
    "/proje-durdur": "Çalışan projeyi güvenli noktada durdur",
}


class PlanCard(QFrame):
    """Plan onay kartı: görevler + Onayla / Değiştir / İptal."""

    approved = Signal()
    edit_requested = Signal()
    cancelled = Signal()

    def __init__(self, state: pj.ProjectState, warnings: list[str], parent=None, title: str = "Proje planı"):
        super().__init__(parent)
        self.setObjectName("PlanCard")
        p = theme.current()
        self.setStyleSheet(f"QFrame#PlanCard {{ background: {p.surface}; border: 1px solid {p.accent};"
                           f" border-radius: 12px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap("list", p.accent, 18))
        head.addWidget(ic)
        title = QLabel(f"<b>{title}</b> — {len(state.tasks)} görev (EVREN_PLAN.md)")
        head.addWidget(title, 1)
        lay.addLayout(head)
        for t in state.tasks:
            row = QLabel(f"<b>{t.idx}.</b> {t.title}"
                         + (f"<br><span style='color:{p.text_dim}'>Bitti ölçütü: {t.criteria}</span>" if t.criteria else "")
                         + (f"<br><span style='color:{p.text_faint}'>Doğrulama: <code>{t.check}</code></span>" if t.check else "")
                         + (f"<br><span style='color:{p.text_faint}'>Bağımlı: {', '.join(map(str, t.depends))}</span>"
                            if t.depends else ""))
            row.setWordWrap(True)
            row.setTextFormat(Qt.RichText)
            lay.addWidget(row)
        for w in warnings:
            lab = QLabel("⚠ " + w)
            lab.setWordWrap(True)
            lab.setStyleSheet(f"color: {p.warning};")
            lay.addWidget(lab)
        info = QLabel("Onaylarsanız görevler Otomatik modda, siz başında olmadan sırayla yürütülür. "
                      "Her görev doğrulanır; takılan görev atlanır. Esc veya /proje-durdur ile durdurursunuz.")
        info.setWordWrap(True)
        info.setProperty("role", "dim")
        lay.addWidget(info)
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.cancel_btn = QPushButton("İptal")
        self.edit_btn = QPushButton("Değiştir")
        self.ok_btn = QPushButton("Onayla ve başlat")
        self.ok_btn.setProperty("variant", "primary")
        for b, sig, done in ((self.cancel_btn, self.cancelled, "İptal edildi"),
                             (self.edit_btn, self.edit_requested, "Düzeltme istendi"),
                             (self.ok_btn, self.approved, "Onaylandı — yürütülüyor")):
            sig.connect(lambda _=None, d=done: self._lock(d))
            b.clicked.connect(sig.emit)
            btns.addWidget(b)
        lay.addLayout(btns)
        self.result = QLabel("")
        self.result.setProperty("role", "dim")
        self.result.setVisible(False)
        lay.addWidget(self.result)

    def _lock(self, text: str = "") -> None:
        """Karar verilince düğmeler gizlenir, kararı yazan satır görünür (çift tıklama olmaz)."""
        for b in (self.ok_btn, self.edit_btn, self.cancel_btn):
            b.setEnabled(False)
            b.setVisible(False)
        if text:
            self.result.setText("✓ " + text)
            self.result.setVisible(True)


class ProjectController(QObject):
    sig_run_task = Signal(object)          # iş parçacığı → ana iş parçacığı: görev turu yap
    sig_status = Signal(str)
    sig_tasks = Signal(object)
    notify = Signal(str, str)              # (başlık, metin) → Windows bildirimi

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.state: pj.ProjectState | None = None
        self.run_id: int | None = None
        self.active = False                # yürütme sürüyor (görevler arası dahil)
        self.planning = False
        self._cancel = threading.Event()
        self._quota_cache: tuple[float, object] | None = None
        self.label = ""                    # çalışma çubuğu öneki: "Proje 3/8"
        self.finished_hooks: list = []     # proje bitince/duraklayınca (state) — Derin Mod doğrulaması
        self.evren_only = False            # Derin Mod: görev ve inceleme modelleri yalnız EVREN
        self.sig_run_task.connect(self._do_run_task, Qt.QueuedConnection)
        self.sig_status.connect(lambda t: view._note(t, "list"), Qt.QueuedConnection)
        self.sig_tasks.connect(self._show_tasks, Qt.QueuedConnection)

    # ---- yardımcılar ----------------------------------------------------------------------

    @property
    def ctx(self):
        return self.view.ctx

    def _ws(self) -> str | None:
        # Oturum henüz oluşmadıysa klasör karşılama ekranındaki seçimdedir
        return self.view.workspace if self.view.session_id else (self.view.workspace or self.view.welcome.workspace)

    def _evren_ids(self) -> set[str]:
        """Anahtarı olan sağlayıcıların gerçek modelleri (ad tarihsel)."""
        return self.ctx.available_model_ids()

    def _model_for(self, role: str, fallback: bool = False) -> tuple[str, list[str], str]:
        """(model, yedekler, rol). Oturum EVREN Akıllı ise rol tablosu; değilse oturum modeli,
        yedekler rol tablosundan."""
        chain = self.ctx.ai_route(role)
        session_model = self.view.model
        if router.is_auto_pro(session_model) or not session_model:
            models = [chain.model] + chain.fallbacks
        else:
            models = [session_model] + [m for m in [chain.model] + chain.fallbacks if m != session_model]
        if self.evren_only:                 # Derin Mod: ücretli sağlayıcıya ASLA (kullanıcı kararı)
            models = [m for m in models if self.ctx.provider_of(m) == "evren"] or models
        if fallback and len(models) > 1:
            models = models[1:] + models[:1]
        return models[0], models[1:], role

    def _add_user(self, content: str, display: str, meta: dict) -> int:
        from .transcript import UserMessageWidget

        sv = self.view
        msg_id = sv.ctx.db.add_session_message(sv.session_id, "user", content, meta={**meta, "display": display})
        w = UserMessageWidget(display, msg_id)
        w.text = display
        sv.transcript.add(w)
        sv.transcript.scroll_to_bottom()
        return msg_id

    def _save(self, state: pj.ProjectState) -> None:
        if self.run_id is not None:
            self.ctx.db.update_project_run(self.run_id, state.status, state.to_json())
        ws = self._ws()
        if ws:
            try:
                pj.write_files(Path(ws), state)
            except OSError:
                pass

    def _show_tasks(self, state: pj.ProjectState) -> None:
        done = sum(1 for t in state.tasks if t.status == "bitti")
        cur = next((t for t in state.tasks if t.status == "calisiyor"), None)
        self.label = f"Proje {cur.idx if cur else done}/{len(state.tasks)}"
        self.view.panel.todos.set_todos([t.todo() for t in state.tasks])

    # ---- komutlar -------------------------------------------------------------------------

    def command(self, cmd: str, arg: str) -> None:
        sv = self.view
        if cmd == "/proje-durdur":
            self.stop()
            return
        if cmd == "/proje-devam":
            self.resume()
            return
        if self.active or self.planning:
            sv._note("Proje ajanı zaten çalışıyor. Durdurmak için /proje-durdur yazın.", "alert")
            return
        if not self._ws():
            sv._note("Proje ajanı bir proje klasöründe çalışır: önce “Proje klasörü bağla” ile klasör seçin.",
                     "folder")
            return
        if cmd == "/proje":
            if not arg.strip():
                sv.composer.set_text("/proje ")
                sv._note("Hedefi yazın: /proje <ne yapılsın, ayrıntılı>", "list")
                return
            self.plan(arg.strip())
        elif cmd == "/proje-duzelt":
            if self.state is None:
                sv._note("Düzeltilecek bir plan yok. Önce /proje <hedef> yazın.", "alert")
                return
            self.plan(self.state.goal, feedback=arg.strip() or "Planı daha küçük ve net görevlere böl.")

    # ---- plan -----------------------------------------------------------------------------

    def plan(self, goal: str, feedback: str = "") -> None:
        sv = self.view
        sid = sv._ensure_session(f"Proje: {goal[:60]}")
        if sid is None:
            return
        self.planning = True
        self._goal = goal
        display = (f"Proje ajanı · plan isteği\n{goal}" if not feedback
                   else f"Proje ajanı · plan düzeltme\n{feedback}")
        msg_id = self._add_user(pj.planning_prompt(goal, feedback), display, {"project": "plan"})
        model, fallbacks, role = self._model_for("plan")
        sv._turn_id = msg_id
        sv._turn_hook = self._plan_done
        sv.start_run(history_from=msg_id, mode_override="plan", model_override=(model, fallbacks, role))
        if not sv.running:
            self.planning = False
            sv._turn_hook = None

    def _plan_done(self, outcome, exc) -> None:
        sv = self.view
        self.planning = False
        if exc is not None:
            sv._note(f"Plan çıkarılamadı: {exc}", "alert")
            return
        msgs = [m for m in sv.ctx.db.get_session_messages(sv.session_id) if m["role"] == "assistant"]
        text = msgs[-1]["content"] if msgs else ""
        tasks = pj.parse_plan(text)
        if not tasks:
            sv._note("Model planı beklenen biçimde vermedi. /proje-duzelt yazıp yeniden deneyin "
                     "(örn. /proje-duzelt planı <plan> bloğu içinde ver).", "alert")
            return
        self.present_plan(self._goal, tasks)

    def present_plan(self, goal: str, tasks: list[pj.Task], title: str = "Proje planı") -> None:
        """Planı kaydedip onay kartını gösterir (Proje planlaması ve Derin Mod ortak yolu)."""
        sv = self.view
        self._goal = goal
        self.state = pj.ProjectState(goal=goal, tasks=tasks)
        self.run_id = sv.ctx.db.add_project_run(sv.session_id, self._ws(), self.state.status, self.state.to_json())
        self._save(self.state)
        git = pj.Git(Path(self._ws()))
        warnings = []
        if not git.is_repo():
            warnings.append("Proje bir git deposu değil: kontrol noktası commit'i yapılamaz. Değişiklikler yine "
                            "de Değişiklikler panelinden geri alınabilir. (İsterseniz önce klasörde `git init` yapın.)")
        elif git.dirty():
            warnings.append("Kaydedilmemiş değişiklikleriniz var: proje dalının ilk commit'ine alınacak "
                            "(kaybolmaz, ana dalınız değişmez).")
        card = PlanCard(self.state, warnings, title=title)
        card.approved.connect(self.start)
        card.edit_requested.connect(lambda: (sv.composer.set_text("/proje-duzelt "), sv.composer.focus()))
        card.cancelled.connect(self._cancel_plan)
        sv.transcript.add(card)
        sv.transcript.scroll_to_bottom()
        self.sig_tasks.emit(self.state)

    def _cancel_plan(self) -> None:
        if self.state is not None and self.run_id is not None:
            self.state.status = "durduruldu"
            self._save(self.state)
        self.view._note("Proje planı iptal edildi.", "stop")
        self.state = None

    # ---- yürütme ---------------------------------------------------------------------------

    def start(self) -> None:
        if self.state is None or self.active:
            return
        cancel_auto_resume(self)
        self._cancel.clear()
        self.active = True
        state, ws = self.state, Path(self._ws())
        sv = self.view
        sv._note("Proje ajanı başladı. Bilgisayar bu sürede uykuya geçmez; bitince bildirim alırsınız.", "spark")
        hooks = pj.ProjectHooks(
            run_task=self._run_task_blocking, review=self._review, run_check=self._run_check,
            commit_message=self._commit_message,
            save=self._save, status=self.sig_status.emit, task_changed=self.sig_tasks.emit,
            quota_wait=self._quota_wait, cancelled=self._cancel.is_set)

        def job():
            pj.keep_awake(True)
            try:
                return pj.ProjectRunner(state, ws, hooks).run()
            finally:
                pj.keep_awake(False)

        Task(job, on_done=self._finished, on_error=self._crashed).start()

    def resume(self) -> None:
        sv = self.view
        if self.active:
            sv._note("Proje zaten çalışıyor.", "list")
            return
        row = sv.ctx.db.latest_project_run(sv.session_id) if sv.session_id else None
        if row is None or row["status"] not in ("duraklatildi", "calisiyor", "onay_bekliyor"):
            sv._note("Bu oturumda sürdürülecek bir proje yok.", "alert")
            return
        self.state = pj.ProjectState.from_json(row["state_json"])
        self.run_id = row["id"]
        self._show_tasks(self.state)
        sv._note("Proje kaldığı yerden sürdürülüyor.", "refresh")
        self.start()

    def _auto_resume(self) -> None:
        self._resume_timer = None
        if self.active or self.view.running:
            return
        return_to_session(self)
        self.view._note("Kota yenilendi: proje kaldığı yerden otomatik sürdürülüyor.", "refresh")
        self.resume()

    def stop(self) -> None:
        sv = self.view
        if getattr(self, "_resume_timer", None) is not None and not self.active:
            cancel_auto_resume(self)
            sv._note("Projenin otomatik sürdürülmesi iptal edildi.", "stop")
            return
        if not self.active:
            sv._note("Çalışan bir proje yok.", "list")
            return
        self._cancel.set()
        sv.stop()
        sv._note("Proje durduruluyor (geçerli görev güvenli noktada kesilir).", "stop")

    def _finished(self, state: pj.ProjectState) -> None:
        self.active = False
        self.label = ""
        sv = self.view
        self._save(state)
        try:
            pj.write_files(Path(self._ws()), state, report=True)
        except OSError:
            pass
        c = state.counts()
        summary = (f"{c.get('bitti', 0)}/{len(state.tasks)} görev bitti"
                   + (f", {c['takildi']} takıldı" if c.get("takildi") else "")
                   + (f", {c['atlandi']} atlandı" if c.get("atlandi") else ""))
        if state.status == "bitti":
            title = "Proje tamamlandı"
            text = summary + (f". Dal: {state.branch}" if state.git else "") + ". Rapor: EVREN_RAPOR.md"
        else:
            title = "Proje duraklatıldı"
            text = f"{state.pause_reason} ({summary}). Sürdürmek için /proje-devam."
            auto = schedule_auto_resume(self, state.pause_reason)
            if auto:
                text += " " + auto
        sv._note(f"{title}: {text}", "check" if state.status == "bitti" else "alert")
        self.notify.emit(f"EVREN Studio — {title}", text)
        self._show_tasks(state)
        for hook in list(self.finished_hooks):
            hook(state)

    def _crashed(self, exc: Exception) -> None:
        self.active = False
        self.label = ""
        if self.state is not None:
            self.state.status = "duraklatildi"
            self.state.pause_reason = f"beklenmeyen hata: {type(exc).__name__}: {exc}"[:300]
            self._save(self.state)
        self.view._note(f"Proje ajanı beklenmeyen bir hatayla durdu: {exc}. /proje-devam ile sürdürebilirsiniz.",
                        "alert")
        self.notify.emit("EVREN Studio — Proje durdu", str(exc)[:200])

    # -- iş parçacığı kancaları (arka plan) --

    def _run_task_blocking(self, task: pj.Task, prompt: str, fallback: bool) -> pj.TaskRun:
        req = {"task": task, "prompt": prompt, "fallback": fallback, "event": threading.Event()}
        self.sig_run_task.emit(req)
        req["event"].wait()
        return req["result"]

    def _do_run_task(self, req: dict) -> None:
        """Ana iş parçacığında: görev mesajını yaz, temiz bağlamla Otomatik turu başlat."""
        sv = self.view
        task: pj.Task = req["task"]
        n = len(self.state.tasks) if self.state else "?"
        display = f"Proje görevi {task.idx}/{n}: {task.title}" + (" (yedek model)" if req["fallback"] else "")
        msg_id = self._add_user(req["prompt"], display, {"project_task": task.idx})
        model, fallbacks, role = self._model_for("kod", fallback=req["fallback"])

        def hook(outcome, exc) -> None:
            req["result"] = self._task_result(msg_id, outcome, exc, model)
            req["event"].set()

        sv._turn_id = msg_id
        sv._turn_hook = hook
        sv.start_run(history_from=msg_id, mode_override="auto", model_override=(model, fallbacks, role))
        if not sv.running and not req["event"].is_set():
            sv._turn_hook = None
            req["result"] = pj.TaskRun(stopped="error", error=None, summary="tur başlatılamadı")
            req["event"].set()

    def _task_result(self, msg_id: int, outcome, exc, model: str) -> pj.TaskRun:
        sv = self.view
        msgs = [m for m in sv.ctx.db.get_session_messages(sv.session_id) if m["id"] > msg_id]
        texts = [m["content"] for m in msgs if m["role"] == "assistant" and (m["content"] or "").strip()]
        summary = texts[-1] if texts else ""
        used = model
        if outcome is not None and getattr(outcome, "model_switches", None):
            used = outcome.model_switches[-1][1]
        diff = ""
        if self.state is not None and not self.state.git:
            rows = [r for r in sv.ctx.db.list_file_changes(sv.session_id) if r["turn_id"] == msg_id]
            parts = []
            for r in rows:
                parts.append("".join(difflib.unified_diff(
                    (r["before_text"] or "").splitlines(True), (r["after_text"] or "").splitlines(True),
                    f"a/{r['path']}", f"b/{r['path']}")))
            diff = "\n".join(parts)
        if exc is not None:
            return pj.TaskRun(stopped="error", summary=summary, model=used,
                              error=exc if isinstance(exc, ApiError) else None)
        return pj.TaskRun(stopped=outcome.stopped, summary=summary, model=used, diff=diff)

    def _review(self, messages: list[dict]) -> str:
        """İnceleme: bağlı sağlayıcının inceleme rolü modeli (Auto Pro tablosu), yedekli."""
        text, _model = self.ctx.ai_chat("inceleme", messages, max_tokens=800, session_id=self.view.session_id,
                                        evren_only=self.evren_only)
        return text

    def _commit_message(self, task: pj.Task, diff: str) -> str:
        """Kontrol noktası commit mesajı (kullanıcı kararı: yapay zekâ önerisi). Hata → şablon."""
        msgs = [{"role": "system", "content": COMMIT_SYSTEM},
                {"role": "user", "content": f"Görev: {task.title}\nBitti ölçütü: {task.criteria}\n\n"
                                            f"Değişiklik özeti (kısaltılmış):\n{diff[:6000]}"}]
        try:
            text, _m = self.ctx.ai_chat("commit", msgs, max_tokens=120, session_id=self.view.session_id)
        except Exception:
            return ""
        return clean_commit_message(text)

    def _run_check(self, command: str) -> tuple[int | None, str]:
        s = self.ctx.settings
        tb = ToolBox(Workspace(self._ws()), command_timeout=s.command_timeout_seconds,
                     output_limit=s.tool_output_limit)
        r = tb.run_command(command, timeout_seconds=s.command_timeout_seconds)
        return r.exit_code, r.output

    def _quota_wait(self) -> tuple[float, str]:
        """Görev öncesi kota denetimi (iş parçacığında, 60 sn önbellekli). Hata → beklemeden devam."""
        if "evren" not in self.ctx.available_providers():
            return 0.0, ""                 # EVREN kotası yok; ücretli tarafta bütçe koruması geçerli
        now = time.monotonic()
        q = None
        if self._quota_cache and now - self._quota_cache[0] < QUOTA_CACHE_S:
            q = self._quota_cache[1]
        else:
            try:
                client = self.ctx.make_client()
                try:
                    q = client.get_quota()
                finally:
                    client.close()
                self._quota_cache = (now, q)
            except Exception:
                return 0.0, ""
        return quota_decision(q)


COMMIT_SYSTEM = ("Bir yazılım değişikliği için git commit mesajı yazıyorsun. Yalnızca mesajı yaz: Türkçe, "
                 "en çok 72 karakterlik tek özet satırı; gerekirse boş satırdan sonra en çok 3 kısa madde. "
                 "Tırnak, kod bloğu veya açıklama ekleme.")


def clean_commit_message(text: str) -> str:
    t = (text or "").strip().strip("`").strip()
    if t.lower().startswith(("commit mesajı:", "commit:")):
        t = t.split(":", 1)[1].strip()
    lines = [x.rstrip() for x in t.splitlines()]
    if not lines or not lines[0].strip():
        return ""
    first = lines[0].strip().strip('"').strip("'")[:72]
    rest = [x for x in lines[1:] if x.strip()][:3]
    return first + ("\n\n" + "\n".join(rest) if rest else "")


def schedule_auto_resume(ctrl, reason: str) -> str:
    """Kota yüzünden duraklayan çalışmayı kota yenilenince sürdürmek üzere zamanlar (Qt ana iş
    parçacığı). Yenilenme saati son kota sorgusunun ÖNBELLEĞİNDEN okunur (ağ isteği yok, R-04).
    Dönüş: kullanıcıya gösterilecek not ("" → zamanlanmadı)."""
    from datetime import datetime

    from ..agent.quota import resume_delay_ms

    if not ctrl.ctx.settings.auto_resume:
        return ""
    low = (reason or "").lower()
    cache = getattr(ctrl.view.project, "_quota_cache", None)
    q = cache[1] if cache else None
    if "günlük" in low:
        delay = resume_delay_ms(getattr(q, "daily_reset_at", None))
    elif "kota" in low or "pencere" in low or "rate" in low:
        delay = 6 * 60 * 1000                # 5 dk penceresi + pay
    else:
        return ""
    old = getattr(ctrl, "_resume_timer", None)
    if old is not None:
        old.stop()
    timer = QTimer(ctrl)
    timer.setSingleShot(True)
    timer.timeout.connect(ctrl._auto_resume)
    timer.start(delay)
    ctrl._resume_timer = timer
    ctrl._resume_sid = ctrl.view.session_id
    when = datetime.fromtimestamp(datetime.now().timestamp() + delay / 1000).strftime("%d.%m %H:%M")
    return (f"Kota yenilenince (yaklaşık {when}) otomatik sürdürülecek; uygulama açık kalmalı. "
            "İptal için durdur komutunu yazın.")


def return_to_session(ctrl) -> None:
    """Otomatik sürdürmeden önce, bekleme sırasında başka oturuma geçildiyse çalışmanın oturumuna dön."""
    sid = getattr(ctrl, "_resume_sid", None)
    if sid and ctrl.view.session_id != sid:
        ctrl.view.open_session(sid)


def cancel_auto_resume(ctrl) -> None:
    t = getattr(ctrl, "_resume_timer", None)
    if t is not None:
        t.stop()
        ctrl._resume_timer = None


def quota_decision(q) -> tuple[float, str]:
    """(bekle sn, neden) — -1: temiz noktada duraklat."""
    from datetime import datetime, timezone

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    remaining = num(getattr(q, "daily_remaining_tokens", None))
    if remaining is not None and remaining < DAILY_MIN_TOKENS:
        reset = getattr(q, "daily_reset_at", None) or "?"
        return -1, (f"günlük EVREN kotası azaldı (kalan ~{int(remaining):,} token); sıfırlanınca "
                    f"({reset}) /proje-devam ile sürdürün").replace(",", ".")
    ratio = num(getattr(q, "usage_ratio", None))
    if ratio is not None and ratio >= WINDOW_PAUSE_RATIO:
        wait = 300.0
        try:
            reset = datetime.fromisoformat(str(q.reset_at).replace("Z", "+00:00"))
            wait = max(10.0, min(360.0, (reset - datetime.now(timezone.utc)).total_seconds() + 5))
        except (TypeError, ValueError, AttributeError):
            pass
        return wait, f"5 dakikalık kota penceresi %{int(ratio * 100)} dolu; yenilenmesi bekleniyor"
    return 0.0, ""
