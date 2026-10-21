"""QA ajanının arayüz denetleyicisi: /qa komutları, senaryo onay kartı, gözetimsiz test, rapor.

Çekirdek Qt'siz `agent/qa.py`'dedir (QaRunner). Proje ajanıyla aynı düzen: plan turu ve her
senaryo turu normal tur yolundan (start_run) geçer — araç kartları ve tarayıcı adımları görünür;
senaryo turları temiz bağlamla, Otomatik modda ve DOSYAYA YAZMADAN (no_writes) çalışır.
QaRunner arka plan iş parçacığında döner, turları Qt sinyaliyle ana iş parçacığına yaptırır (R-11).

Yalnız EVREN modelleri (kullanıcı kararı 2026-10-19: ücretli sağlayıcıyla MCP/QA yok) ve
Playwright MCP gerekir. Durum: veri/qa/<oturum>.json · rapor: proje klasöründe EVREN_QA_RAPORU.md.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ..agent import mcp as mcpmod
from ..agent import qa
from ..agent import router
from ..agent.tools import ToolBox, Workspace
from ..api.errors import ApiError
from . import icons, theme
from .workers import Task

QA_COMMANDS = {
    "/qa": "QA ajanı: /qa <neyi test etsin> — web uygulamasını tarayıcıda gerçek bir test uzmanı gibi dener",
    "/qa-duzelt": "QA senaryolarını değiştir: /qa-duzelt <geri bildirim>",
    "/qa-devam": "Duraklatılan QA testini kaldığı yerden sürdür",
    "/qa-durdur": "Çalışan QA testini güvenli noktada durdur",
}
VISION_SYSTEM = ("Bir web sayfasının ekran görüntüsünü inceleyen QA uzmanısın. Soruyu Türkçe, kısa ve somut "
                 "yanıtla: gördüğün metinleri aynen yaz, yerleşim/görünürlük/taşma sorunlarını belirt. "
                 "Görmediğin şeyi uydurma; emin değilsen söyle.")


class QaPlanCard(QFrame):
    approved = Signal()
    edit_requested = Signal()
    cancelled = Signal()

    def __init__(self, state: qa.QaState, parent=None):
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
        ic.setPixmap(icons.pixmap("check", p.accent, 18))
        head.addWidget(ic)
        head.addWidget(QLabel(f"<b>QA planı</b> — {len(state.scenarios)} senaryo"), 1)
        lay.addLayout(head)
        if state.run_hint:
            hint = QLabel(f"<span style='color:{p.text_dim}'>Çalıştırma: {state.run_hint}</span>")
            hint.setWordWrap(True)
            lay.addWidget(hint)
        for s in state.scenarios:
            steps = " → ".join(s.steps[:6])
            row = QLabel(f"<b>{s.idx}.</b> {s.title}"
                         + (f"<br><span style='color:{p.text_dim}'>{steps}</span>" if steps else "")
                         + (f"<br><span style='color:{p.text_dim}'>Beklenen: {s.expected}</span>" if s.expected else ""))
            row.setWordWrap(True)
            row.setTextFormat(Qt.RichText)
            lay.addWidget(row)
        info = QLabel("Onaylarsanız senaryolar Otomatik modda, tarayıcıda, siz başında olmadan sırayla denenir. "
                      "QA ajanı dosya DEĞİŞTİRMEZ; sonuç EVREN_QA_RAPORU.md'ye yazılır. Esc veya /qa-durdur "
                      "ile durdurursunuz.")
        info.setWordWrap(True)
        info.setProperty("role", "dim")
        lay.addWidget(info)
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.cancel_btn = QPushButton("İptal")
        self.edit_btn = QPushButton("Değiştir")
        self.ok_btn = QPushButton("Onayla ve testi başlat")
        self.ok_btn.setProperty("variant", "primary")
        for b, sig, done in ((self.cancel_btn, self.cancelled, "İptal edildi"),
                             (self.edit_btn, self.edit_requested, "Düzeltme istendi"),
                             (self.ok_btn, self.approved, "Onaylandı — test ediliyor")):
            sig.connect(lambda _=None, d=done: self._lock(d))
            b.clicked.connect(sig.emit)
            btns.addWidget(b)
        lay.addLayout(btns)
        self.result = QLabel("")
        self.result.setProperty("role", "dim")
        self.result.setVisible(False)
        lay.addWidget(self.result)

    def _lock(self, text: str) -> None:
        for b in (self.ok_btn, self.edit_btn, self.cancel_btn):
            b.setEnabled(False)
            b.setVisible(False)
        self.result.setText("✓ " + text)
        self.result.setVisible(True)


class QaDoneCard(QFrame):
    """Bitiş kartı: özet + (kalan hata varsa) "Hataları düzelt" → Proje ajanı."""

    fix_requested = Signal()

    def __init__(self, state: qa.QaState, parent=None):
        super().__init__(parent)
        self.setObjectName("PlanCard")
        p = theme.current()
        self.setStyleSheet(f"QFrame#PlanCard {{ background: {p.surface}; border: 1px solid {p.border_strong};"
                           f" border-radius: 12px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        c = state.counts()
        lay.addWidget(QLabel(f"<b>QA sonucu</b> — {c.get('gecti', 0)} geçti · {c.get('kaldi', 0)} kaldı · "
                             f"{c.get('engellendi', 0)} engellendi (EVREN_QA_RAPORU.md)"))
        for s in state.scenarios:
            mark = {"gecti": "✓", "kaldi": "✗", "engellendi": "–"}.get(s.status, "·")
            color = {"gecti": p.success, "kaldi": p.danger}.get(s.status, p.text_dim)
            row = QLabel(f"<span style='color:{color}'>{mark}</span> {s.idx}. {s.title}"
                         + (f" — <span style='color:{p.text_dim}'>{s.summary or s.actual[:120]}</span>"
                            if s.status != "gecti" else ""))
            row.setWordWrap(True)
            row.setTextFormat(Qt.RichText)
            lay.addWidget(row)
        if c.get("kaldi"):
            btns = QHBoxLayout()
            btns.addStretch(1)
            self.fix_btn = QPushButton("Hataları düzelt (Proje ajanı)")
            self.fix_btn.setProperty("variant", "primary")
            self.fix_btn.clicked.connect(lambda _=None: (self.fix_btn.setEnabled(False), self.fix_requested.emit()))
            btns.addWidget(self.fix_btn)
            lay.addLayout(btns)


class QaController(QObject):
    sig_run = Signal(object)
    sig_status = Signal(str)
    sig_changed = Signal(object)
    notify = Signal(str, str)

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.state: qa.QaState | None = None
        self.active = False
        self.planning = False
        self._cancel = threading.Event()
        self.label = ""
        self.sig_run.connect(self._do_run, Qt.QueuedConnection)
        self.sig_status.connect(lambda t: view._note(t, "check"), Qt.QueuedConnection)
        self.sig_changed.connect(self._show, Qt.QueuedConnection)

    @property
    def ctx(self):
        return self.view.ctx

    def _ws(self) -> str | None:
        return self.view.workspace if self.view.session_id else (self.view.workspace or self.view.welcome.workspace)

    def _evren_model(self, role: str) -> tuple[str, list[str], str]:
        """Yalnız EVREN modelleri (oturum ücretli modelde olsa bile)."""
        ids = {m for m in self.ctx.available_model_ids() if self.ctx.provider_of(m) == "evren"}
        r = router.choose(role, available=ids or None)
        return r.model, r.fallbacks, role

    def _pw_config(self):
        return next((c for c in self.ctx.mcp_configs() if c.name == "playwright"), None)

    def _state_path(self) -> Path:
        return self.ctx.settings.resolved_data_dir() / "qa" / f"oturum-{self.view.session_id}.json"

    def _save(self, state: qa.QaState) -> None:
        try:
            p = self._state_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(state.to_json(), encoding="utf-8")
        except OSError:
            pass

    def _show(self, state: qa.QaState) -> None:
        done = sum(1 for s in state.scenarios if s.status in ("gecti", "kaldi", "engellendi"))
        cur = next((s for s in state.scenarios if s.status == "calisiyor"), None)
        self.label = f"QA {cur.idx if cur else done}/{len(state.scenarios)}" if self.active else ""
        self.view.panel.todos.set_todos([s.todo() for s in state.scenarios])

    def _add_user(self, content: str, display: str, meta: dict) -> int:
        return self.view.project._add_user(content, display, meta)

    # ---- komutlar ----
    def command(self, cmd: str, arg: str) -> None:
        sv = self.view
        if cmd == "/qa-durdur":
            self.stop()
            return
        if cmd == "/qa-devam":
            self.resume()
            return
        if self.active or self.planning or sv.project.active or sv.project.planning:
            sv._note("Bir ajan zaten çalışıyor. Durdurmak için /qa-durdur veya /proje-durdur yazın.", "alert")
            return
        problem = self.precheck()
        if problem:
            sv._note(problem, "alert")
            return
        if cmd == "/qa":
            self.plan(arg.strip())
        elif cmd == "/qa-duzelt":
            if self.state is None:
                sv._note("Düzeltilecek bir QA planı yok. Önce /qa <neyi test etsin> yazın.", "alert")
                return
            self.plan(self.state.goal, feedback=arg.strip() or "Senaryoları daha net ve ölçülebilir yaz.")

    def precheck(self) -> str:
        """Başlamadan önce koşullar; sorun varsa kullanıcıya gösterilecek metin."""
        if not self._ws():
            return "QA ajanı bir proje klasöründe çalışır: önce “Proje klasörü bağla” ile web projesini seçin."
        if "evren" not in self.ctx.available_providers():
            return ("QA ajanı yalnız ücretsiz EVREN modelleriyle çalışır (ücretli sağlayıcıyla çalışmaz). "
                    "Ayarlar'dan EVREN API anahtarını girin.")
        if self._pw_config() is None:
            return ("QA ajanı tarayıcı için Playwright MCP gerektirir: Ayarlar > MCP Sunucuları'ndan "
                    "“Playwright'ı kur” ve etkinleştirin.")
        return ""

    def plan(self, goal: str, feedback: str = "") -> None:
        sv = self.view
        sid = sv._ensure_session(f"QA: {(goal or 'web uygulaması')[:60]}")
        if sid is None:
            return
        self.planning = True
        self._goal = goal or "web uygulamasının ana işlevlerini test et"
        display = (f"QA ajanı · test planı isteği\n{self._goal}" if not feedback
                   else f"QA ajanı · plan düzeltme\n{feedback}")
        msg_id = self._add_user(qa.planning_prompt(self._goal, feedback), display, {"qa": "plan"})
        model, fallbacks, role = self._evren_model("plan")
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
            sv._note(f"QA planı çıkarılamadı: {exc}", "alert")
            return
        msgs = [m for m in sv.ctx.db.get_session_messages(sv.session_id) if m["role"] == "assistant"]
        run_hint, scenarios = qa.parse_plan(msgs[-1]["content"] if msgs else "")
        if not scenarios:
            sv._note("Model senaryoları beklenen biçimde vermedi. /qa-duzelt yazıp yeniden deneyin "
                     "(örn. /qa-duzelt senaryoları <qa_plan> bloğu içinde ver).", "alert")
            return
        self.state = qa.QaState(goal=self._goal, run_hint=run_hint, scenarios=scenarios)
        self._save(self.state)
        card = QaPlanCard(self.state)
        card.approved.connect(self.start)
        card.edit_requested.connect(lambda: (sv.composer.set_text("/qa-duzelt "), sv.composer.focus()))
        card.cancelled.connect(self._cancel_plan)
        sv.transcript.add(card)
        sv.transcript.scroll_to_bottom()
        self._show(self.state)

    def _cancel_plan(self) -> None:
        if self.state is not None:
            self.state.status = "durduruldu"
            self._save(self.state)
        self.view._note("QA planı iptal edildi.", "stop")
        self.state = None

    # ---- yürütme ----
    def start(self) -> None:
        if self.state is None or self.active:
            return
        from .project_ui import cancel_auto_resume

        cancel_auto_resume(self)
        self._cancel.clear()
        self.active = True
        sv = self.view
        sv.keep_services = True              # senaryolar arası geliştirme sunucusu açık kalsın
        try:
            mcpmod.ensure_axe(self.ctx.settings.resolved_data_dir())
        except Exception:
            pass
        sv._note("QA ajanı başladı: senaryolar tarayıcıda deneniyor. Bilgisayar uykuya geçmez; bitince "
                 "bildirim alırsınız.", "spark")
        state = self.state
        hooks = qa.QaHooks(run_scenario=self._run_blocking, save=self._save, status=self.sig_status.emit,
                           changed=self.sig_changed.emit, quota_wait=sv.project._quota_wait,
                           cancelled=self._cancel.is_set, services=self._services_info,
                           ask_result=self._ask_blocking)

        def job():
            from ..agent.project import keep_awake

            keep_awake(True)
            try:
                return qa.QaRunner(state, hooks).run()
            finally:
                keep_awake(False)

        Task(job, on_done=self._finished, on_error=self._crashed).start()

    def resume(self) -> None:
        sv = self.view
        if self.active:
            sv._note("QA zaten çalışıyor.", "check")
            return
        if self.state is None and sv.session_id:
            try:
                self.state = qa.QaState.from_json(self._state_path().read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                self.state = None
        if self.state is None or self.state.status not in ("duraklatildi", "calisiyor", "onay_bekliyor"):
            sv._note("Bu oturumda sürdürülecek bir QA testi yok.", "alert")
            return
        problem = self.precheck()
        if problem:
            sv._note(problem, "alert")
            return
        sv._note("QA testi kaldığı yerden sürdürülüyor.", "refresh")
        self.start()

    def _auto_resume(self) -> None:
        self._resume_timer = None
        if self.active or self.view.running:
            return
        from .project_ui import return_to_session

        return_to_session(self)
        self.view._note("Kota yenilendi: QA testi kaldığı yerden otomatik sürdürülüyor.", "refresh")
        self.resume()

    def stop(self) -> None:
        if getattr(self, "_resume_timer", None) is not None and not self.active:
            from .project_ui import cancel_auto_resume

            cancel_auto_resume(self)
            self.view._note("QA testinin otomatik sürdürülmesi iptal edildi.", "stop")
            return
        if not self.active:
            self.view._note("Çalışan bir QA testi yok.", "check")
            return
        self._cancel.set()
        self.view.stop()
        self.view._note("QA durduruluyor (geçerli senaryo güvenli noktada kesilir).", "stop")

    def _end(self) -> None:
        self.active = False
        self.label = ""
        self.view.keep_services = False
        self.view.stop_services()

    def _finished(self, state: qa.QaState) -> None:
        self._end()
        sv = self.view
        self._save(state)
        try:
            qa.write_report(Path(self._ws()), state)
        except OSError:
            pass
        c = state.counts()
        summary = f"{c.get('gecti', 0)} geçti, {c.get('kaldi', 0)} kaldı, {c.get('engellendi', 0)} engellendi"
        if state.status == "bitti":
            title, text = "QA testi tamamlandı", summary + ". Rapor: EVREN_QA_RAPORU.md"
        else:
            from .project_ui import schedule_auto_resume

            title, text = "QA testi duraklatıldı", f"{state.pause_reason} ({summary}). Sürdürmek için /qa-devam."
            auto = schedule_auto_resume(self, state.pause_reason)
            if auto:
                text += " " + auto
        sv._note(f"{title}: {text}", "check" if state.status == "bitti" else "alert")
        if state.status == "bitti":
            card = QaDoneCard(state)
            card.fix_requested.connect(lambda: sv.project.plan(qa.fix_goal(state)))
            sv.transcript.add(card)
            sv.transcript.scroll_to_bottom()
        self.notify.emit(f"EVREN Studio — {title}", text)
        self._show(state)

    def _crashed(self, exc: Exception) -> None:
        self._end()
        if self.state is not None:
            self.state.status = "duraklatildi"
            self.state.pause_reason = f"beklenmeyen hata: {type(exc).__name__}: {exc}"[:300]
            self._save(self.state)
        self.view._note(f"QA ajanı beklenmeyen bir hatayla durdu: {exc}. /qa-devam ile sürdürebilirsiniz.", "alert")
        self.notify.emit("EVREN Studio — QA durdu", str(exc)[:200])

    def _services_info(self) -> str:
        out = []
        for sm in list(self.view._services.values()):
            for name, svc in list(sm.services.items()):
                if svc.alive:
                    out.append(f"{name}" + (f" · http://127.0.0.1:{svc.port}/" if svc.port else ""))
        return ", ".join(out)

    # -- iş parçacığı kancaları --
    def _ask_blocking(self, sc: qa.Scenario, prompt: str) -> str:
        req = {"sc": sc, "prompt": prompt, "event": threading.Event(), "followup": True}
        self.sig_run.emit(req)
        req["event"].wait()
        return req["result"][0]

    def _run_blocking(self, sc: qa.Scenario, prompt: str):
        req = {"sc": sc, "prompt": prompt, "event": threading.Event()}
        self.sig_run.emit(req)
        req["event"].wait()
        return req["result"]

    def _vision(self, question: str, image_path: str) -> str:
        msgs = [{"role": "system", "content": VISION_SYSTEM},
                {"role": "user", "content": question, "_images": [image_path]}]
        text, model = self.ctx.ai_chat("gorsel", msgs, max_tokens=600, session_id=self.view.session_id,
                                       evren_only=True)
        return f"[{model}] {text}"

    def _do_run(self, req: dict) -> None:
        sv = self.view
        sc: qa.Scenario = req["sc"]
        n = len(self.state.scenarios) if self.state else "?"
        followup = bool(req.get("followup"))
        display = (f"QA senaryosu {sc.idx}/{n}: sonuç isteniyor" if followup
                   else f"QA senaryosu {sc.idx}/{n}: {sc.title}")
        msg_id = self._add_user(req["prompt"], display, {"qa_scenario": sc.idx})
        if not followup:
            self._scenario_msg = msg_id
        start_from = getattr(self, "_scenario_msg", msg_id) if followup else msg_id
        model, fallbacks, role = self._evren_model("kod")
        ws = Path(self._ws())
        s = self.ctx.settings
        pw = self._pw_config()
        data_dir = self.ctx.mcp.data_dir

        def run_cmd(command: str):
            r = ToolBox(Workspace(ws), command_timeout=120, output_limit=s.tool_output_limit).run_command(command)
            return r.exit_code, r.output
        tools = qa.QaTools(self.ctx.mcp, pw, ws, self._vision, mcpmod.playwright_dir(data_dir) / "cikti",
                           mcpmod.axe_path(data_dir), run_cmd) if pw is not None else None

        def hook(outcome, exc) -> None:
            msgs = [m for m in sv.ctx.db.get_session_messages(sv.session_id) if m["id"] > msg_id]
            texts = [m["content"] for m in msgs if m["role"] == "assistant" and (m["content"] or "").strip()]
            req["result"] = (texts[-1] if texts else "", getattr(outcome, "stopped", None),
                             exc if isinstance(exc, ApiError) else None)
            req["event"].set()

        sv._turn_id = msg_id
        sv._turn_hook = hook
        sv.start_run(history_from=start_from, mode_override="auto", model_override=(model, fallbacks, role),
                     no_writes=True, extra_tools=tools, final_marker="<qa_sonuc>")
        if not sv.running and not req["event"].is_set():
            sv._turn_hook = None
            req["result"] = ("", "error", None)
            req["event"].set()
