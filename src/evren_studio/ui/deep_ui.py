"""Derin Mod arayüz denetleyicisi (çekirdek: agent/deep.py).

Fazlar ARKA PLAN iş parçacığında (Task) koşar; sonuçlar ana iş parçacığına sinyalle döner (R-04, R-11).
Uygulama fazı Proje ajanına devredilir (plan onayı zorunlu — DECISIONS #48); Proje bitince
kancayla çekişmeli doğrulama ve düzeltme turları gelir. Yalnız EVREN (ücretsiz) kullanılır.
"""
from __future__ import annotations

import difflib
import itertools
import time
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal

from ..agent import deep as dp
from ..agent import project as pj
from ..agent.quota import QuotaGate
from ..api.client import CancelToken
from .workers import Task

MAX_PARALLEL = 3


class DeepController(QObject):
    sig_note = Signal(str, str)
    sig_label = Signal(str)
    notify = Signal(str, str)

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.state: dp.DeepState | None = None
        self.active = False                 # Derin akışı sürüyor (fazlar arası, Proje yürütmesi dahil)
        self.busy = False                   # arka plan fazı (anla/planla/doğrula) çalışıyor
        self.label = ""
        self._cancel = CancelToken()
        self._start_msg: int | None = None
        self._gate: QuotaGate | None = None
        self._base = ""                     # Proje'nin başlangıç commit'i (git varsa)
        self._quota_hit = False             # bir alt ajan günlük kota yüzünden durdu
        self._pending_commit = False
        self.sig_note.connect(lambda t, i: view._note(t, i), Qt.QueuedConnection)
        self.sig_label.connect(self._set_label, Qt.QueuedConnection)
        view.project.finished_hooks.append(self._project_finished)

    # ---- yardımcılar ----------------------------------------------------------------------

    @property
    def ctx(self):
        return self.view.ctx

    @property
    def enabled(self) -> bool:
        return bool(self.ctx.settings.deep_mode)

    def set_enabled(self, on: bool, quiet: bool = False) -> None:
        self.ctx.settings.deep_mode = bool(on)
        self.ctx.save_settings()
        self.view.composer.set_deep(bool(on))
        if not quiet:
            self.view._note(
                "Derin Mod açık: işler anla → planla → uygula → çekişmeli doğrula → düzelt akışıyla, birden "
                "çok EVREN ajanıyla yürür (daha yavaş, daha çok token; yalnız ücretsiz EVREN)." if on
                else "Derin Mod kapandı: mesajlar normal ajan turuyla yürür.", "spark" if on else "dot")

    def _set_label(self, text: str) -> None:
        self.label = text
        self.view._tick_run()

    def _ws(self) -> str | None:
        return self.view.project._ws()

    def unavailable_reason(self) -> str:
        if not self._ws():
            return "Derin Mod bir proje klasöründe çalışır: önce “Proje klasörü bağla” ile klasör seçin."
        if "evren" not in self.ctx.available_providers():
            return "Derin Mod yalnız EVREN (ücretsiz) ile çalışır: Ayarlar'dan EVREN API anahtarı girin."
        return ""

    def _evren_chain(self, role: str) -> list[str]:
        r = self.ctx.ai_route(role)
        return [m for m in [r.model] + r.fallbacks if m and self.ctx.provider_of(m) == "evren"]

    def _quota(self):
        client = self.ctx.make_client()
        try:
            return client.get_quota()
        finally:
            client.close()

    def _sub(self, model: str | None, role: str):
        """Arka plan iş parçacığında çağrılır: (istem, işaret) → SubResult."""
        chain = self._evren_chain(role)
        if model:
            chain = [model] + [m for m in chain if m != model]
        root = Path(self._ws())

        def run(prompt: str, marker: str) -> dp.SubResult:
            if not chain:
                return dp.SubResult("", "error", "EVREN modeli yok")
            client = self.ctx.make_client()
            info = self.ctx.model_info(chain[0])
            try:
                res = dp.run_subagent(client=client, model=chain[0], fallbacks=chain[1:], root=root,
                                      prompt=prompt, marker=marker, gate=self._gate, cancel=self._cancel,
                                      context_tokens=getattr(info, "context_length", None))
            finally:
                client.close()
            if res.stopped == "quota_daily":
                self._quota_hit = True
            return res
        return run

    def _log(self, text: str) -> None:
        if self.state is not None:
            from datetime import datetime

            self.state.log.append(f"{datetime.now().strftime('%H:%M:%S')} {text}")
        self.sig_note.emit(f"Derin Mod · {text}", "spark")

    def _bg(self, fn, on_done) -> None:
        self.busy = True

        def done(result) -> None:
            self.busy = False
            on_done(result)

        def failed(exc: Exception) -> None:
            self.busy = False
            self._finish("durduruldu", f"beklenmeyen hata: {type(exc).__name__}: {exc}"[:300])
        Task(fn, on_done=done, on_error=failed).start()

    # ---- giriş noktaları -------------------------------------------------------------------

    def command(self, arg: str) -> None:
        """/derin → aç/kapat; /derin <istek> → bu isteği (düğme kapalı olsa da) Derin Mod'la yürüt;
        /derin-durdur → durdur."""
        a = (arg or "").strip()
        if a.lower() in ("", "aç", "ac", "kapat", "kapa"):
            self.set_enabled(not self.enabled if not a else a.lower() in ("aç", "ac"))
            return
        self.start(a)

    def start(self, goal: str) -> bool:
        sv = self.view
        if self.active:
            sv._note("Derin Mod zaten çalışıyor. Durdurmak için Esc veya /derin-durdur.", "alert")
            return True
        reason = self.unavailable_reason()
        if reason:
            sv._note(reason, "alert")
            return False
        sid = sv._ensure_session(f"Derin: {goal[:60]}")
        if sid is None:
            return False
        self.state = dp.DeepState(goal=goal, kind=dp.classify(goal))
        self._start_msg = self.view.project._add_user(goal, f"Derin Mod · {'soru' if self.state.kind == 'soru' else 'iş'}\n{goal}",
                                                      {"deep": "istek"})
        self._cancel = CancelToken()
        self._base, self._quota_hit, self._pending_commit = "", False, False
        par = max(1, min(int(getattr(self.ctx.settings, "deep_parallel", 2) or 2), MAX_PARALLEL))
        self._gate = QuotaGate(self._quota, max_parallel=par)
        self.active = True
        self._log("başladı — 1/5 ANLA: bağımsız alt ajanlar projeyi farklı açılardan inceliyor (salt okunur)")
        self.sig_label.emit("Derin · anla")
        self._run_understand()
        return True

    # ---- fazlar ----------------------------------------------------------------------------

    def _run_understand(self) -> None:
        st = self.state
        st.phase = "anla"
        sub = self._sub(None, "kod")
        self._bg(lambda: dp.understand(st, sub, self._gate, self._gate.max_parallel, self._log),
                 lambda _r: self._after_understand())

    def _quota_paused(self) -> bool:
        if not self._quota_hit:
            return False
        self._pause("günlük EVREN kotası azaldı")
        return True

    def _after_understand(self) -> None:
        st = self.state
        if self._stopped():
            return
        if self._quota_paused():
            return
        if st.kind == "soru":
            self._answer()
            return
        st.phase = "planla"
        self._log("2/5 PLANLA: iki farklı EVREN modeli bağımsız plan yazıyor; yargıç model seçecek")
        self.sig_label.emit("Derin · planla")
        models = self._evren_chain("plan")
        subs = {m: self._sub(m, "plan") for m in models[:2]}

        def judge(messages):
            text, _m = self.ctx.ai_chat("inceleme", messages, max_tokens=600, session_id=self.view.session_id,
                                        evren_only=True)
            return text
        self._bg(lambda: dp.plan(st, lambda m, p, k: subs[m](p, k), models[:2], judge, self._gate,
                                 self._gate.max_parallel, self._log),
                 self._after_plan)

    def _after_plan(self, tasks) -> None:
        st = self.state
        if self._stopped():
            return
        if self._quota_paused():
            return
        proj = self.view.project
        proj.evren_only = True
        if not tasks:
            self._log("geçerli plan çıkmadı; Proje ajanının tek modelli planlamasına geçiliyor")
            st.phase = "uygula"
            proj.plan(st.goal)
            return
        st.phase = "uygula"
        self._log(f"3/5 UYGULA: seçilen plan ({len(tasks)} görev) onayınıza sunuldu; onaylarsanız Proje ajanı "
                  "görev görev yürütür")
        self.sig_label.emit("")
        proj.present_plan(st.goal, tasks, title=f"Derin Mod planı (Plan {st.chosen})")

    def _project_finished(self, pstate: pj.ProjectState) -> None:
        st = self.state
        if not self.active or st is None or st.phase != "uygula":
            return
        if pstate.status == "durduruldu":
            self._finish("durduruldu", "proje durduruldu")
            return
        if pstate.status != "bitti":
            st.status, st.pause_reason = "duraklatildi", pstate.pause_reason
            self._log("proje duraklatıldı; proje sürdürülüp bitince doğrulama otomatik başlar")
            return
        st.status = "calisiyor"
        self._base = pstate.base_commit if pstate.git else ""
        self._verify()

    def _diff(self) -> str:
        ws = Path(self._ws())
        if self._base:
            return pj.Git(ws).diff_since(self._base)
        sv = self.view
        rows = [r for r in sv.ctx.db.list_file_changes(sv.session_id)
                if self._start_msg is not None and (r["turn_id"] or 0) >= self._start_msg]
        return "\n".join("".join(difflib.unified_diff(
            (r["before_text"] or "").splitlines(True), (r["after_text"] or "").splitlines(True),
            f"a/{r['path']}", f"b/{r['path']}")) for r in rows)

    def _verify(self) -> None:
        st = self.state
        st.phase = "dogrula"
        self._log(f"4/5 DOĞRULA: iki bağımsız denetçi değişikliği isteğe karşı çürütmeye çalışıyor"
                  + (f" (düzeltme turu {st.fix_round})" if st.fix_round else ""))
        self.sig_label.emit("Derin · doğrula")
        subs = [self._sub(None, "inceleme"), self._sub(None, "kod")]
        counter = itertools.count()

        def sub(prompt, marker):                 # denetçiler farklı modeller (bakış çeşitliliği)
            return subs[next(counter) % 2](prompt, marker)
        ws, base = self._ws(), self._base
        diff_now = None if base else self._diff()    # git yoksa değişiklik kaydı ana iş parçacığında okunur
        commit, self._pending_commit = self._pending_commit, False
        fix_round = st.fix_round

        def job():
            if base and commit:
                git = pj.Git(Path(ws))
                if git.dirty():
                    git.commit_all(f"Derin Mod: doğrulama düzeltmeleri (tur {fix_round})")
            diff = pj.Git(Path(ws)).diff_since(base) if base else diff_now
            return dp.verify(st, diff or "", sub, self._gate, self._gate.max_parallel, self._log)
        self._bg(job, self._after_verify)

    def _after_verify(self, issues) -> None:
        st = self.state
        if self._stopped() or self._quota_paused():
            return
        if not issues:
            self._finish("bitti")
            return
        if st.fix_round >= dp.MAX_FIX_ROUNDS:
            self._finish("bitti", f"{len(issues)} sorun {dp.MAX_FIX_ROUNDS} düzeltme turundan sonra kaldı")
            return
        st.fix_round += 1
        st.phase = "duzelt"
        self._log(f"5/5 DÜZELT: {len(issues)} onaylanmış sorun düzeltiliyor (tur {st.fix_round}/{dp.MAX_FIX_ROUNDS})")
        self.sig_label.emit("Derin · düzelt")
        self._agent_turn(dp.fix_prompt(st.goal, issues), f"Derin Mod · düzeltme turu {st.fix_round}",
                         "auto", "kod", self._after_fix)

    def _after_fix(self, outcome, exc) -> None:
        if self._stopped():
            return
        if exc is not None:
            self._finish("duraklatildi", f"düzeltme turu hata verdi: {exc}"[:300])
            return
        self._pending_commit = True          # commit doğrulama işinde, arka planda (R-04)
        self._verify()

    def _answer(self) -> None:
        st = self.state
        st.phase = "yanit"
        self._log("YANIT: bulgular birleştirilip soru yanıtlanıyor")
        self.sig_label.emit("Derin · yanıt")
        self._agent_turn(dp.answer_prompt(st.goal, st.findings), "Derin Mod · yanıt", "plan", "kod",
                         lambda outcome, exc: self._finish("bitti" if exc is None else "duraklatildi",
                                                           "" if exc is None else str(exc)[:300]))

    def _agent_turn(self, prompt: str, display: str, mode: str, role: str, hook) -> None:
        sv = self.view
        msg_id = self.view.project._add_user(prompt, display, {"deep": self.state.phase})
        chain = self._evren_chain(role)
        if not chain:
            self._finish("duraklatildi", "EVREN model listesi yok (Ayarlar > bağlantıyı yenileyin)")
            return
        sv._turn_id = msg_id
        sv._turn_hook = hook
        sv.start_run(history_from=msg_id, mode_override=mode, model_override=(chain[0], chain[1:], role))
        if not sv.running:
            sv._turn_hook = None
            self._finish("duraklatildi", "ajan turu başlatılamadı")

    # ---- durdur / duraklat / bitir ---------------------------------------------------------

    def _stopped(self) -> bool:
        if not self.active:
            return True
        if self._cancel.cancelled:
            self._finish("durduruldu", "kullanıcı durdurdu")
            return True
        return False

    def _pause(self, reason: str) -> None:
        from .project_ui import schedule_auto_resume

        st = self.state
        text = f"Derin Mod duraklatıldı ({st.phase}): {reason}."
        if self._gate is not None and self._gate._q is not None:      # yenilenme saati için (ağ yok)
            self.view.project._quota_cache = (time.monotonic(), self._gate._q)
        auto = schedule_auto_resume(self, reason)
        self._finish("duraklatildi", reason, keep=True)
        if auto:
            text += " " + auto
        self.view._note(text, "alert")

    def _auto_resume(self) -> None:
        self._resume_timer = None
        st = self.state
        if self.active or st is None or st.status != "duraklatildi" or self.view.running:
            return
        self.view._note("Kota yenilendi: Derin Mod kaldığı fazdan sürdürülüyor.", "refresh")
        self._cancel = CancelToken()
        self._quota_hit = False
        self.active = True
        self.view.project.evren_only = st.phase != "anla"
        st.status = "calisiyor"
        {"anla": self._run_understand, "planla": self._after_understand,
         "dogrula": self._verify}.get(st.phase, self._run_understand)()

    def stop(self) -> None:
        from .project_ui import cancel_auto_resume

        if getattr(self, "_resume_timer", None) is not None and not self.active:
            cancel_auto_resume(self)
            self.view._note("Derin Mod'un otomatik sürdürülmesi iptal edildi.", "stop")
            return
        if not self.active:
            return
        self._cancel.cancel()
        self.view._note("Derin Mod durduruluyor (çalışan alt ajanlar güvenli noktada kesilir).", "stop")
        proj = self.view.project
        if not self.busy:
            self._finish("durduruldu", "kullanıcı durdurdu")
        if proj.active:
            proj.stop()
        elif self.view.running:
            self.view._stop_run()

    def _finish(self, status: str, reason: str = "", keep: bool = False) -> None:
        st = self.state
        if st is None:
            return
        was_active = self.active
        self.active = False
        self.label = ""
        self.view.project.evren_only = False
        st.status = status
        st.pause_reason = reason
        if status == "bitti":
            st.phase = "bitti"
        try:
            dp.write_report(Path(self._ws()), st)
        except OSError:
            pass
        if keep or not was_active:
            return
        if status == "bitti":
            n = len(st.issues)
            text = ("tamamlandı" + (f"; {n} sorun açık kaldı" if n and st.fix_round >= dp.MAX_FIX_ROUNDS else
                                    "; denetçiler onaylanmış sorun bulmadı" if st.kind == "is" else "")
                    + (f" ({reason})" if reason else "") + f". Rapor: {dp.REPORT_FILE}")
            self.view._note(f"Derin Mod {text}", "check")
            self.notify.emit("EVREN Studio — Derin Mod bitti", text)
        else:
            self.view._note(f"Derin Mod {'durduruldu' if status == 'durduruldu' else 'duraklatıldı'}: {reason}. "
                            f"Rapor: {dp.REPORT_FILE}", "stop" if status == "durduruldu" else "alert")
