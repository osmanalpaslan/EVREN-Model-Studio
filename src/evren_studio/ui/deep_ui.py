"""Derin Mod arayüz denetleyicisi (çekirdek: agent/deep.py).

Fazlar ARKA PLAN iş parçacığında (Task) koşar; sonuçlar ana iş parçacığına sinyalle döner (R-04, R-11).
Uygulama fazı Proje ajanına devredilir (plan onayı zorunlu — DECISIONS #48); Proje bitince
kancayla çekişmeli doğrulama ve düzeltme turları gelir. Yalnız EVREN (ücretsiz) kullanılır.

2026-10-21 (hesap kapama oturumu) düzeltmeleri:
- Anla'nın bulduğu kullanıcı kararları planlamadan ÖNCE soru kartıyla sorulur (gözetimsiz ajan
  "onay"ı kendi kendine yazıyordu).
- Her alt ajan bitince ilerleme notu düşer; dökümü veri klasörüne yazılır (alt ajanlar ekranda
  iz bırakmadan 15-20 dk çalışıyordu).
- Proje kısmen biterse Derin "bitti" demez: bekler, proje sürdürülüp bitince doğrulama başlar.
- Denetçiler farklı modellerdir; proje görev durumları denetçilere verilir.
"""
from __future__ import annotations

import difflib
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QPlainTextEdit

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
        self.awaiting_answers = False       # soru kartı yanıt bekliyor
        self.waiting_project = False        # proje kısmen bitti/duraklatıldı: bitince doğrulama başlar
        self.label = ""
        self._cancel = CancelToken()
        self._start_msg: int | None = None
        self._gate: QuotaGate | None = None
        self._base = ""                     # Proje'nin başlangıç commit'i (git varsa)
        self._quota_hit = False             # bir alt ajan günlük kota yüzünden durdu
        self._pending_commit = False
        self._questions_done = False
        self._qcard = None
        self._qedit: QPlainTextEdit | None = None
        self._tasks_text = ""
        self._subs_done = 0
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
        """Arka plan iş parçacığında çağrılır: (istem, işaret, etiket) → SubResult. Bitince ilerleme notu
        düşer ve döküm `<veri>/deep/<zaman>/<etiket>.md` dosyasına yazılır."""
        chain = self._evren_chain(role)
        if model:
            chain = [model] + [m for m in chain if m != model]
        root = Path(self._ws())
        log_dir = Path(self.state.log_dir) if self.state and self.state.log_dir else None

        def run(prompt: str, marker: str, label: str = "") -> dp.SubResult:
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
            name = label or role
            if log_dir is not None:
                try:
                    log_dir.mkdir(parents=True, exist_ok=True)
                    (log_dir / f"{name}.md").write_text(
                        f"# {name}\n\n{res.summary}\n\n" + (f"Hata: {res.error}\n\n" if res.error else "")
                        + res.transcript, encoding="utf-8")
                except OSError:
                    pass
            self._subs_done += 1
            ok = bool(marker) and marker in (res.text or "")
            self._log(f"{name} bitti — {res.summary}" + ("" if ok else " · sonuç bloğu YOK")
                      + (f" · hata: {res.error[:120]}" if res.error else ""))
            phase = self.state.phase if self.state else ""
            self.sig_label.emit(f"Derin · {phase} ({self._subs_done} alt ajan bitti)")
            return res
        return run

    def _log(self, text: str) -> None:
        if self.state is not None:
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
        if self.waiting_project:
            self.waiting_project = False
            sv._note("Önceki Derin akışının proje beklemesi bırakıldı (yeni Derin isteği başladı). Önceki proje "
                     "/proje-devam ile yine sürdürülebilir; doğrulaması yapılmaz.", "alert")
        self.state = dp.DeepState(goal=goal, kind=dp.classify(goal))
        self.state.log_dir = str(Path(self.ctx.data_dir()) / "deep" / datetime.now().strftime("%Y%m%d-%H%M%S"))
        self._start_msg = self.view.project._add_user(goal, f"Derin Mod · {'soru' if self.state.kind == 'soru' else 'iş'}\n{goal}",
                                                      {"deep": "istek"})
        self._cancel = CancelToken()
        self._base, self._quota_hit, self._pending_commit = "", False, False
        self._questions_done, self.awaiting_answers, self.waiting_project = False, False, False
        self._tasks_text, self._subs_done = "", 0
        par = max(1, min(int(getattr(self.ctx.settings, "deep_parallel", 2) or 2), MAX_PARALLEL))
        self._gate = QuotaGate(self._quota, max_parallel=par)
        self.ctx.probe_models("Derin")              # A8: bozuk/yavaş motor işe başlamadan sona alınsın
        self.active = True
        self._log("başladı — 1/5 ANLA: bağımsız alt ajanlar projeyi farklı açılardan inceliyor (salt okunur). "
                  "Her biri bitince burada not düşer.")
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
        if st.questions and not self._questions_done:
            self._ask_questions()
            return
        self._run_plan()

    def _ask_questions(self) -> None:
        """Anla'nın bulduğu kararları kullanıcıya sorar (yanıt kartta veya mesaj kutusunda)."""
        from .transcript import ChoiceCard

        st = self.state
        st.phase = "soru"
        self.awaiting_answers = True
        self.sig_label.emit("")
        items = "\n".join(f"{i}. {q}" for i, q in enumerate(st.questions, 1))
        card = ChoiceCard(
            "Planlamadan önce kararınız gereken konular var",
            "İnceleme bu soruların yanıtı olmadan işin doğru yapılamayacağını buldu. Yanıtları aşağıya (veya "
            "mesaj kutusuna) yazın; yanıtsız devam ederseniz ajan en makul varsayımı kullanır ve raporda "
            f"açıkça belirtir.\n\n{items}",
            [("Yanıtla ve devam", lambda: self.answer(self._qedit.toPlainText() if self._qedit else "")),
             ("Sormadan devam", lambda: self.answer(""))], icon_name="help")
        edit = QPlainTextEdit()
        edit.setPlaceholderText("Örn. 1) CRS sayfasını atla  2) kullanici_listesi.tsv'yi klasöre koydum …")
        edit.setFixedHeight(90)
        card.layout().insertWidget(2, edit)
        self._qcard, self._qedit = card, edit
        sv = self.view
        sv.transcript.add(card)
        sv.transcript.scroll_to_bottom()
        self._log(f"{len(st.questions)} konuda kararınız gerekiyor; yanıtlayınca planlama başlar")
        self.notify.emit("EVREN Studio — Derin Mod kararınızı bekliyor", st.questions[0][:180])

    def answer(self, text: str) -> None:
        """Soru kartının yanıtı (kart düğmesi veya mesaj kutusu). Boş → varsayımla devam."""
        if not self.awaiting_answers or self.state is None:
            return
        self.awaiting_answers = False
        self._questions_done = True
        self.state.answers = (text or "").strip()
        card = self._qcard
        if card is not None:
            for b in card.buttons:
                b.setEnabled(False)
                b.setVisible(False)
            if self._qedit is not None:
                self._qedit.setReadOnly(True)
            card.result.setText("✓ " + ("Yanıtlandı" if self.state.answers else "Sormadan devam edildi"))
            card.result.setVisible(True)
        self._log("yanıtınız alındı; planlamaya geçiliyor" if self.state.answers
                  else "yanıtsız devam: varsayımlar raporda belirtilecek")
        if self._stopped():
            return
        self._run_plan()

    def _run_plan(self) -> None:
        st = self.state
        st.phase = "planla"
        self._log("2/5 PLANLA: iki farklı EVREN modeli bağımsız plan yazıyor; yargıç model seçecek")
        self.sig_label.emit("Derin · planla")
        models = self._evren_chain("plan")
        subs = {m: self._sub(m, "plan") for m in models[:2]}

        def judge(messages):
            text, _m = self.ctx.ai_chat("inceleme", messages, max_tokens=600, session_id=self.view.session_id,
                                        evren_only=True)
            return text
        self._bg(lambda: dp.plan(st, lambda m, p, k: subs[m](p, k, f"plan-{m}"), models[:2], judge, self._gate,
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
            proj.plan(st.goal + (f"\n\n{dp.answers_text(st)}" if st.questions else ""))
            return
        st.phase = "uygula"
        self._log(f"3/5 UYGULA: seçilen plan ({len(tasks)} görev) onayınıza sunuldu; onaylarsanız Proje ajanı "
                  "görev görev yürütür (her göreve inceleme notu ve yanıtlarınız verilir)")
        self.sig_label.emit("")
        answers = [dp.answers_text(st)] if st.questions else []
        proj.present_plan(st.goal, tasks, title=f"Derin Mod planı (Plan {st.chosen})",
                          context=dp.context_note(st), answers=answers)

    def _project_finished(self, pstate: pj.ProjectState) -> None:
        st = self.state
        if not (self.active or self.waiting_project) or st is None or st.phase != "uygula":
            return
        c = pstate.counts()
        self._tasks_text = "\n".join(f"{t.idx}. [{pj.STATUS_LABEL[t.status]}] {t.title}" for t in pstate.tasks)
        if pstate.status == "durduruldu":
            self.waiting_project = False
            self._finish("durduruldu", "proje durduruldu")
            return
        if pstate.status != "bitti":
            # Kısmi proje "bitti" sayılmaz (2026-10-21: 3/12 görevle "sorun yok, bitti" denmişti)
            st.project_note = (f"Proje tamamlanmadı ({c.get('bitti', 0)}/{len(pstate.tasks)} görev): "
                               f"{pstate.pause_reason}")
            was = self.active
            self.waiting_project = True
            self._finish("duraklatildi", "proje görevleri tamamlanmadı", keep=True)
            self.view.project.evren_only = True          # proje sürdürülünce de yalnız EVREN
            if was:
                self.view._note("Derin Mod bekliyor: proje görevleri tamamlanmadı. Proje sürdürülüp bitince "
                                "doğrulama kendiliğinden başlar (/proje-devam). Beklemeyi bırakmak için "
                                "/derin-durdur.", "alert")
            return
        st.project_note = f"Proje tamamlandı: {len(pstate.tasks)}/{len(pstate.tasks)} görev bitti."
        self.waiting_project = False
        self.active = True
        st.status, st.pause_reason = "calisiyor", ""
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

    def _verifier_models(self) -> tuple[str | None, str | None]:
        """İki denetçi FARKLI model olsun (2026-10-21: kod rolünün birincili listeden kalkınca ikisi de
        aynı modele düşüyordu)."""
        a, b = self._evren_chain("inceleme"), self._evren_chain("kod")
        m1 = a[0] if a else (b[0] if b else None)
        m2 = next((m for m in b + a if m != m1), m1)
        return m1, m2

    def _verify(self) -> None:
        st = self.state
        st.phase = "dogrula"
        self._log(f"4/5 DOĞRULA: iki bağımsız denetçi değişikliği isteğe karşı çürütmeye çalışıyor"
                  + (f" (düzeltme turu {st.fix_round})" if st.fix_round else ""))
        self.sig_label.emit("Derin · doğrula")
        m1, m2 = self._verifier_models()
        subs = [self._sub(m1, "inceleme"), self._sub(m2, "kod")]

        def sub(prompt, marker, label=""):          # denetçiler farklı modeller (bakış çeşitliliği)
            return subs[1 if label.endswith("2") else 0](prompt, marker, label)
        ws, base = self._ws(), self._base
        diff_now = None if base else self._diff()    # git yoksa değişiklik kaydı ana iş parçacığında okunur
        commit, self._pending_commit = self._pending_commit, False
        fix_round = st.fix_round
        tasks = self._tasks_text

        def job():
            if base and commit:
                git = pj.Git(Path(ws))
                if git.dirty():
                    git.commit_all(f"Derin Mod: doğrulama düzeltmeleri (tur {fix_round})")
            diff = pj.Git(Path(ws)).diff_since(base) if base else diff_now
            return dp.verify(st, diff or "", sub, self._gate, self._gate.max_parallel, self._log, tasks)
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
        st = self.state
        if self.active or st is None or st.status != "duraklatildi" or self.view.running:
            return
        self.view._note("Kota yenilendi: Derin Mod kaldığı fazdan sürdürülüyor.", "refresh")
        self._cancel = CancelToken()
        self._quota_hit = False
        self.active = True
        self.view.project.evren_only = st.phase != "anla"
        st.status = "calisiyor"
        {"anla": self._run_understand, "planla": self._run_plan,
         "dogrula": self._verify}.get(st.phase, self._run_understand)()

    def stop(self) -> None:
        from .project_ui import cancel_auto_resume, has_pending_resume

        if has_pending_resume(self) and not self.active:
            cancel_auto_resume(self)
            self.view._note("Derin Mod'un otomatik sürdürülmesi iptal edildi.", "stop")
            return
        if self.waiting_project and not self.active:
            self.waiting_project = False
            self.view.project.evren_only = False
            if self.state is not None:
                self.state.status, self.state.pause_reason = "durduruldu", "kullanıcı beklemeyi bıraktı"
                try:
                    dp.write_report(Path(self._ws()), self.state)
                except OSError:
                    pass
            self.view._note("Derin Mod proje beklemesini bıraktı (proje ayrıca sürdürülebilir).", "stop")
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
        self.awaiting_answers = False
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
