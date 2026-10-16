"""Ajan döngüsü: model → araç çağrıları → izin → sonuç → model …

Döngü arka plan iş parçacığında çalışır; arayüzle `AgentEvents` geri
çağrıları üzerinden konuşur. Onay gereken işlemlerde `ApprovalRequest`
yayınlanır ve kullanıcı karar verene (veya iptal edene) kadar beklenir.

Her mesaj ve dosya değişikliği oluştuğu anda `store` üzerinden kalıcı
kaydedilir; API hatası veya uygulama kapanması işi kaybettirmez.

Araç protokolü:
- "native": OpenAI uyumlu `tools` / `tool_calls` (EVREN şemasında var).
- "text"  : `<arac_cagrisi>` blokları (textproto.py).
"native" istek 400/422 ile reddedilirse ve geri dönüşe izin verildiyse
aynı adım metin protokolüyle bir kez daha denenir.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..api.errors import ApiError, ErrorKind
from . import textproto
from .permissions import (
    Decision,
    SessionPermissions,
    command_prefix,
    decide,
    is_sensitive_read,
    normalize_mode,
)
from .prompts import build_agent_system, build_chat_system
from .tools import (
    EXEC,
    META,
    READ,
    READ_ONLY_SPECS,
    SPEC_BY_NAME,
    TOOL_SPECS,
    WRITE,
    CommandResult,
    FileChange,
    ToolBox,
    ToolError,
    Workspace,
    truncate_middle,
    validate_todos,
)

DEFAULT_MAX_STEPS = 40
CHARS_PER_TOKEN = 3.5
TRIMMED_NOTE = "[Bağlam sınırı nedeniyle eski araç çıktısı kısaltıldı; gerekirse yeniden oku.]"


# ---- veri yapıları --------------------------------------------------------------


@dataclass
class ToolCall:
    id: str
    name: str
    raw_arguments: str
    arguments: dict[str, Any] = field(default_factory=dict)
    parse_error: str | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "ToolCall":
        text = raw.get("arguments") or ""
        if isinstance(text, dict):
            return cls(raw.get("id") or textproto.new_call_id(), raw.get("name", ""),
                       json.dumps(text, ensure_ascii=False), text)
        try:
            args = json.loads(text) if str(text).strip() else {}
            if not isinstance(args, dict):
                raise ValueError
            return cls(raw.get("id") or textproto.new_call_id(), raw.get("name", ""), text, args)
        except (json.JSONDecodeError, ValueError):
            return cls(raw.get("id") or textproto.new_call_id(), raw.get("name", ""), text, {},
                       "Araç parametreleri geçerli JSON değil.")

    def to_raw(self) -> dict[str, str]:
        return {"id": self.id, "name": self.name, "arguments": self.raw_arguments}


@dataclass
class ToolResult:
    ok: bool
    content: str                     # modele giden metin
    summary: str                     # arayüzde tek satır
    extra: dict[str, Any] = field(default_factory=dict)


class ApprovalRequest:
    """Kullanıcı onayı bekleyen işlem. resolve() arayüz tarafından çağrılır."""

    ALLOW = "allow"
    ALLOW_SESSION = "allow_session"
    DENY = "deny"

    def __init__(self, call: ToolCall, kind: str, title: str, detail: str,
                 change: FileChange | None = None, prefix: str | None = None,
                 reason: str = ""):
        self.reason = reason       # neden soruldu (ör. "Otomatik mod sordu: paket kurma")
        self.call = call
        self.kind = kind
        self.title = title
        self.detail = detail
        self.change = change
        self.prefix = prefix
        self.decision: str | None = None
        self.feedback: str = ""
        self._event = threading.Event()

    def resolve(self, decision: str, feedback: str = "") -> None:
        if self._event.is_set():
            return
        self.decision = decision
        self.feedback = feedback.strip()
        self._event.set()

    @property
    def resolved(self) -> bool:
        return self._event.is_set()

    def wait(self, cancel: Any = None) -> str:
        while not self._event.wait(0.1):
            if cancel is not None and getattr(cancel, "cancelled", False):
                self.resolve(self.DENY, "")
        return self.decision or self.DENY


class AgentEvents:
    """Arayüz geri çağrıları. Varsayılanlar hiçbir şey yapmaz."""

    def text_delta(self, text: str) -> None: ...
    def reasoning_delta(self, text: str) -> None: ...
    def step_started(self, step: int) -> None: ...
    def message_saved(self, message: dict[str, Any]) -> None: ...
    def tool_started(self, call: ToolCall, title: str) -> None: ...
    def tool_output(self, call: ToolCall, chunk: str) -> None: ...
    def tool_finished(self, call: ToolCall, result: ToolResult) -> None: ...
    def approval_needed(self, request: ApprovalRequest) -> None: ...
    def todos_changed(self, todos: list[dict[str, str]]) -> None: ...
    def file_changed(self, change_id: int | None, change: FileChange) -> None: ...
    def protocol_changed(self, protocol: str, reason: str) -> None: ...
    def status(self, text: str) -> None: ...


class SessionStore(Protocol):
    def add_session_message(self, session_id: int, role: str, content: str, *,
                            reasoning: str | None = None,
                            tool_calls: list[dict] | None = None,
                            tool_call_id: str | None = None,
                            name: str | None = None,
                            meta: dict | None = None,
                            model: str | None = None,
                            request_id: str | None = None) -> int: ...

    def add_file_change(self, session_id: int, turn_id: int | None, rel_path: str,
                        before: str | None, after: str | None) -> int: ...

    def set_session_todos(self, session_id: int, todos: list[dict]) -> None: ...


@dataclass
class TurnOutcome:
    stopped: str = "done"            # done | cancelled | max_steps | error
    steps: int = 0
    protocol: str = "native"
    last_text: str = ""


# ---- geçmiş → API mesajları ----------------------------------------------------------


def history_after_summary(history: list[dict]) -> list[dict]:
    """Son özetten (role=summary) sonrasını; özeti başta kullanıcı mesajı olarak verir."""
    idx = None
    for i, m in enumerate(history):
        if m.get("role") == "summary":
            idx = i
    if idx is None:
        return list(history)
    summary = history[idx]
    rest = history[idx + 1:]
    return [{"role": "user", "content": "[Önceki konuşmanın özeti]\n" + (summary.get("content") or "")},
            {"role": "assistant", "content": "Anladım, özetten devam ediyorum."}] + rest


def to_api_messages(system: str, history: list[dict], protocol: str) -> list[dict]:
    msgs: list[dict] = [{"role": "system", "content": system}]
    pending_text_results: list[str] = []

    def flush() -> None:
        if pending_text_results:
            msgs.append({"role": "user", "content": "\n\n".join(pending_text_results)})
            pending_text_results.clear()

    for m in history_after_summary(history):
        role = m.get("role")
        content = m.get("content") or ""
        if role == "tool":
            if protocol == "native":
                msgs.append({"role": "tool", "tool_call_id": m.get("tool_call_id") or "",
                             "content": content})
            else:
                ok = not (m.get("meta") or {}).get("error")
                pending_text_results.append(
                    textproto.render_result(m.get("name") or "?", content, ok))
            continue
        flush()
        if role == "assistant":
            calls = m.get("tool_calls") or []
            if protocol == "native":
                entry: dict[str, Any] = {"role": "assistant", "content": content}
                if calls:
                    entry["tool_calls"] = [
                        {"id": c["id"], "type": "function",
                         "function": {"name": c["name"], "arguments": c.get("arguments") or "{}"}}
                        for c in calls
                    ]
                msgs.append(entry)
            else:
                blocks = [textproto.render_call(c["name"], c.get("arguments") or "{}") for c in calls]
                text = "\n\n".join([content] + blocks if content else blocks) or content
                msgs.append({"role": "assistant", "content": text})
        elif role in ("user", "system"):
            msgs.append({"role": role, "content": content})
    flush()
    return msgs


def estimate_tokens(messages: list[dict]) -> int:
    total = 0
    for m in messages:
        total += len(m.get("content") or "")
        for c in m.get("tool_calls") or []:
            total += len(json.dumps(c, ensure_ascii=False))
    return int(total / CHARS_PER_TOKEN)


def trim_for_context(history: list[dict], context_tokens: int | None,
                     keep_recent: int = 8) -> list[dict]:
    """Bağlam sınırına yaklaşılırsa eski araç çıktılarını kısaltır (kayıt değişmez)."""
    if not context_tokens:
        return history
    budget = int(context_tokens * 0.7)
    trimmed = [dict(m) for m in history]
    if estimate_tokens(trimmed) <= budget:
        return trimmed
    for i, m in enumerate(trimmed[:-keep_recent] if len(trimmed) > keep_recent else []):
        if m.get("role") == "tool" and len(m.get("content") or "") > 400:
            trimmed[i]["content"] = TRIMMED_NOTE
            if estimate_tokens(trimmed) <= budget:
                break
    return trimmed


# ---- koşucu ------------------------------------------------------------------------------


class AgentRunner:
    def __init__(self, client: Any, model: str, *, session_id: int,
                 store: SessionStore, events: AgentEvents | None = None,
                 workspace: Workspace | None = None, mode: str = "manuel",
                 protocol: str = "native", allow_protocol_fallback: bool = True,
                 permissions: SessionPermissions | None = None,
                 cancel: Any = None, stream: bool = True,
                 max_steps: int = DEFAULT_MAX_STEPS,
                 command_timeout: int = 120, output_limit: int = 20_000,
                 context_tokens: int | None = None, turn_id: int | None = None,
                 hard_context_limit: int | None = None):
        self.client = client
        self.model = model
        self.session_id = session_id
        self.store = store
        self.events = events or AgentEvents()
        self.workspace = workspace
        self.mode = normalize_mode(mode)
        self.protocol = protocol
        self.allow_fallback = allow_protocol_fallback
        self.perms = permissions or SessionPermissions()
        self.cancel = cancel
        self.stream = stream
        self.max_steps = max_steps
        self.output_limit = output_limit
        self.context_tokens = context_tokens
        self.turn_id = turn_id
        # Tur içi güvenli nokta denetimi: araç sonuçlarından sonra geçmiş bu
        # tahmini token sayısını aşarsa tur "context_limit" ile durur; arayüz
        # özetleyip otomatik devam eder (compaction.py).
        self.hard_context_limit = hard_context_limit
        self.toolbox = (
            ToolBox(workspace, command_timeout=command_timeout, output_limit=output_limit,
                    skip_file=is_sensitive_read)
            if workspace else None
        )

    # -- yardımcılar --------------------------------------------------------------

    @property
    def agentic(self) -> bool:
        return self.workspace is not None

    def _specs(self):
        if not self.agentic:
            return []
        return READ_ONLY_SPECS if normalize_mode(self.mode) == "plan" else TOOL_SPECS

    def _system(self) -> str:
        if not self.agentic:
            return build_chat_system()
        return build_agent_system(self.workspace, normalize_mode(self.mode), self._specs(),
                                  text_protocol=(self.protocol == "text"))

    def _cancelled(self) -> bool:
        return bool(self.cancel is not None and getattr(self.cancel, "cancelled", False))

    def _save(self, history: list[dict], role: str, content: str, **kw) -> dict:
        msg_id = self.store.add_session_message(self.session_id, role, content, **kw)
        msg = {"id": msg_id, "role": role, "content": content}
        msg.update({k: v for k, v in kw.items() if v is not None})
        history.append(msg)
        self.events.message_saved(msg)
        return msg

    def _call_model(self, history: list[dict]):
        visible = trim_for_context(history, self.context_tokens)
        messages = to_api_messages(self._system(), visible, self.protocol)
        tools = None
        if self.agentic and self.protocol == "native":
            tools = [s.openai_schema() for s in self._specs()]

        def on_delta(text: str, _finish: str = "") -> None:
            self.events.text_delta(text)

        return self.client.chat(
            self.model, messages, stream=self.stream, cancel=self.cancel,
            on_delta=on_delta, on_reasoning=self.events.reasoning_delta,
            tools=tools,
        )

    # -- ana döngü ---------------------------------------------------------------------

    def run(self, history: list[dict]) -> TurnOutcome:
        """`history` kayıtlı mesajlardır (son kullanıcı mesajı dahil); yerinde uzatılır."""
        outcome = TurnOutcome(protocol=self.protocol)
        step = 0
        fallback_used = False
        while step < self.max_steps:
            if self._cancelled():
                outcome.stopped = "cancelled"
                break
            step += 1
            outcome.steps = step
            self.events.step_started(step)
            t0 = time.monotonic()
            try:
                result = self._call_model(history)
            except ApiError as exc:
                if (self.agentic and self.protocol == "native" and self.allow_fallback
                        and not fallback_used and exc.kind == ErrorKind.VALIDATION):
                    fallback_used = True
                    self.protocol = outcome.protocol = "text"
                    self.events.protocol_changed(
                        "text", f"Model yerel araç çağrısını reddetti ({exc.status}); "
                                "metin protokolüne geçildi.")
                    step -= 1
                    continue
                outcome.stopped = "error"
                raise

            content = result.content or ""
            raw_calls = list(getattr(result, "tool_calls", None) or [])
            parse_errors: list[str] = []
            if self.agentic and (self.protocol == "text" or (not raw_calls and textproto.OPEN in content)):
                content, text_calls, parse_errors = textproto.parse_tool_calls(content)
                raw_calls += text_calls
            calls = [ToolCall.from_raw(c) for c in raw_calls] if self.agentic else []

            cancelled = result.finish_reason == "cancelled_by_user"
            duration = round(time.monotonic() - t0, 1)
            routed = getattr(result, "routed_model", None)
            meta: dict[str, Any] = {"duration_s": duration, "requested_model": self.model}
            if result.finish_reason:
                meta["finish_reason"] = result.finish_reason
            if routed and routed != self.model:
                meta["routed_model"] = routed
            self._save(
                history, "assistant", content,
                reasoning=result.reasoning or None,
                tool_calls=[c.to_raw() for c in calls] or None,
                model=routed or self.model,
                request_id=result.request_id,
                meta=meta,
            )
            outcome.last_text = content
            if cancelled:
                outcome.stopped = "cancelled"
                # Yanıtsız kalan araç çağrılarına iptal sonucu yaz (geçmiş tutarlı kalsın)
                for call in calls:
                    self._save(history, "tool", "İşlem kullanıcı tarafından iptal edildi.",
                               tool_call_id=call.id, name=call.name, meta={"error": True})
                break
            if not calls and not parse_errors:
                outcome.stopped = "done"
                break

            for call in calls:
                if self._cancelled():
                    res = ToolResult(False, "İşlem kullanıcı tarafından iptal edildi.", "İptal edildi")
                else:
                    res = self._execute(call)
                self._save(history, "tool", res.content, tool_call_id=call.id, name=call.name,
                           meta={"error": not res.ok, "summary": res.summary, **res.extra})
            for err in parse_errors:
                fake = ToolCall(textproto.new_call_id(), "arac_cagrisi", "")
                self._save(history, "tool", err, tool_call_id=fake.id, name="arac_cagrisi",
                           meta={"error": True, "summary": "Araç bloğu okunamadı"})
            if self._cancelled():
                outcome.stopped = "cancelled"
                break
            if self.hard_context_limit and self._history_tokens(history) >= self.hard_context_limit:
                outcome.stopped = "context_limit"
                break
        else:
            outcome.stopped = "max_steps"
            self.events.status(f"Adım sınırına ({self.max_steps}) ulaşıldı; devam etmek için mesaj gönderin.")
        return outcome

    def _history_tokens(self, history: list[dict]) -> int:
        return estimate_tokens(to_api_messages("", history, self.protocol)) + 2_500

    # -- araç yürütme -------------------------------------------------------------------------

    def _execute(self, call: ToolCall) -> ToolResult:
        spec = SPEC_BY_NAME.get(call.name)
        if spec is None:
            return ToolResult(False, f"Bilinmeyen araç: {call.name}. Kullanılabilir araçlar: "
                              + ", ".join(SPEC_BY_NAME), f"Bilinmeyen araç: {call.name}")
        if call.parse_error:
            return ToolResult(False, call.parse_error, "Parametreler okunamadı")
        if self.toolbox is None:
            return ToolResult(False, "Bu oturumda proje klasörü yok; araç kullanılamaz.", "Proje yok")
        if normalize_mode(self.mode) == "plan" and spec.kind in (WRITE, EXEC):
            _d, reason = decide(self.mode, spec.kind, self.perms)
            return ToolResult(False, reason, "Plan modunda engellendi")
        self.events.tool_started(call, describe_call(call))
        try:
            if spec.kind == READ:
                res = self._run_read(call)
            elif spec.kind == META:
                res = self._run_todos(call)
            elif spec.kind == WRITE:
                res = self._run_write(call)
            else:
                res = self._run_exec(call)
        except ToolError as exc:
            res = ToolResult(False, str(exc), str(exc)[:120])
        except TypeError as exc:
            res = ToolResult(False, f"Geçersiz parametreler: {exc}", "Geçersiz parametreler")
        except Exception as exc:  # beklenmeyen yerel hata: modele bildir, döngü sürsün
            res = ToolResult(False, f"Araç hatası: {type(exc).__name__}: {exc}", "Araç hatası")
        self.events.tool_finished(call, res)
        return res

    def _run_read(self, call: ToolCall) -> ToolResult:
        a = call.arguments
        tb = self.toolbox
        if call.name == "list_files":
            out = tb.list_files(a.get("path") or ".", a.get("depth") or 2)
            summary = f"Listelendi: {a.get('path') or '.'}"
        elif call.name == "read_file":
            rel = self.workspace.rel(self.workspace.resolve(_req(a, "path")))
            decision, reason = decide(self.mode, READ, self.perms, path=rel)
            if decision == Decision.ASK:
                ok, feedback = self._approve(call, READ, f"Gizli olabilecek dosya okunsun mu? {rel}",
                                             rel, reason=reason)
                if not ok:
                    msg = "Kullanıcı bu dosyanın okunmasına izin vermedi."
                    if feedback:
                        msg += f" Kullanıcının notu: {feedback}"
                    return ToolResult(False, msg, f"Reddedildi: {rel}", {"denied": True})
            out = tb.read_file(_req(a, "path"), a.get("start_line"), a.get("end_line"))
            rng = ""
            if a.get("start_line") or a.get("end_line"):
                rng = f" (satır {a.get('start_line') or 1}–{a.get('end_line') or 'son'})"
            summary = f"Okundu: {a['path']}{rng}"
        elif call.name == "search_files":
            out = tb.search_files(_req(a, "pattern"), a.get("path") or ".", a.get("glob"),
                                  a.get("ignore_case", True))
            n = 0 if out.startswith("Eşleşme bulunamadı") else len(out.splitlines())
            summary = f"Arandı: “{a['pattern']}” — {n} sonuç"
        else:
            out = tb.find_files(_req(a, "pattern"))
            n = 0 if out.startswith("Dosya bulunamadı") else len(out.splitlines())
            summary = f"Bulundu: {a['pattern']} — {n} dosya"
        return ToolResult(True, truncate_middle(out, self.output_limit), summary,
                          {"output": truncate_middle(out, 4000)})

    def _run_todos(self, call: ToolCall) -> ToolResult:
        todos = validate_todos(call.arguments.get("todos"))
        self.store.set_session_todos(self.session_id, todos)
        self.events.todos_changed(todos)
        done = sum(1 for t in todos if t["status"] == "completed")
        return ToolResult(True, "Görev listesi güncellendi.",
                          f"Görevler güncellendi ({done}/{len(todos)})", {"todos": todos})

    def _approve(self, call: ToolCall, kind: str, title: str, detail: str,
                 change: FileChange | None = None, prefix: str | None = None,
                 reason: str = "") -> tuple[bool, str]:
        req = ApprovalRequest(call, kind, title, detail, change, prefix, reason)
        self.events.approval_needed(req)
        decision = req.wait(self.cancel)
        if decision == ApprovalRequest.ALLOW_SESSION:
            if kind == WRITE:
                self.perms.allow_all_writes = True
            elif kind == READ:
                self.perms.allow_sensitive_reads = True
            elif prefix:
                self.perms.command_prefixes.add(prefix)
        return decision in (ApprovalRequest.ALLOW, ApprovalRequest.ALLOW_SESSION), req.feedback

    def _run_write(self, call: ToolCall) -> ToolResult:
        a = call.arguments
        if call.name == "write_file":
            change = self.toolbox.prepare_write(_req(a, "path"), a.get("content"))
        else:
            change = self.toolbox.prepare_edit(_req(a, "path"), a.get("old_string"),
                                               a.get("new_string", ""), bool(a.get("replace_all")))
        decision, reason = decide(self.mode, WRITE, self.perms, path=change.rel_path)
        if decision == Decision.DENY:
            return ToolResult(False, reason, "Engellendi")
        if decision == Decision.ASK:
            ok, feedback = self._approve(call, WRITE, change.summary(), change.diff, change=change,
                                         reason=reason)
            if not ok:
                msg = "Kullanıcı bu dosya değişikliğini reddetti."
                if feedback:
                    msg += f" Kullanıcının notu: {feedback}"
                return ToolResult(False, msg, f"Reddedildi: {change.rel_path}",
                                  {"diff": change.diff, "path": change.rel_path, "denied": True})
        self.toolbox.apply_change(change)
        change_id = self.store.add_file_change(self.session_id, self.turn_id, change.rel_path,
                                               change.before, change.after)
        self.events.file_changed(change_id, change)
        added, removed = change.stats
        verb = "Oluşturuldu" if change.is_new else "Düzenlendi"
        extra = {"diff": change.diff, "path": change.rel_path, "change_id": change_id}
        if decision == Decision.ALLOW and normalize_mode(self.mode) in ("kabul", "auto"):
            extra["auto_approved"] = True
        return ToolResult(True, f"{verb}: {change.rel_path} (+{added} −{removed} satır).",
                          f"{verb}: {change.rel_path}  +{added} −{removed}", extra)

    def _run_exec(self, call: ToolCall) -> ToolResult:
        command = _req(call.arguments, "command").strip()
        decision, reason = decide(self.mode, EXEC, self.perms, command,
                                  root=self.workspace.root if self.workspace else None)
        if decision == Decision.DENY:
            return ToolResult(False, reason, "Engellendi")
        prefix = command_prefix(command)
        if decision == Decision.ASK:
            ok, feedback = self._approve(call, EXEC, "Komut çalıştırılsın mı?", command, prefix=prefix,
                                         reason=reason)
            if not ok:
                msg = "Kullanıcı bu komutun çalıştırılmasını reddetti."
                if feedback:
                    msg += f" Kullanıcının notu: {feedback}"
                return ToolResult(False, msg, f"Reddedildi: {command[:80]}",
                                  {"command": command, "denied": True})
        result: CommandResult = self.toolbox.run_command(
            command, call.arguments.get("timeout_seconds"), cancel=self.cancel,
            on_output=lambda chunk: self.events.tool_output(call, chunk),
        )
        ok = result.exit_code == 0 and not result.timed_out and not result.cancelled
        state = "zaman aşımı" if result.timed_out else (
            "durduruldu" if result.cancelled else f"çıkış {result.exit_code}")
        return ToolResult(ok, result.to_text(self.output_limit), f"Çalıştırıldı: {command[:80]} ({state})",
                          {"command": command, "exit_code": result.exit_code,
                           "output": truncate_middle(result.output, 8000),
                           "duration": round(result.duration, 1),
                           "auto_approved": decision == Decision.ALLOW,
                           "auto_reason": reason if decision == Decision.ALLOW else ""})


def _req(args: dict, key: str) -> Any:
    value = args.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ToolError(f"'{key}' parametresi gerekli.")
    return value


def describe_call(call: ToolCall) -> str:
    a = call.arguments
    return {
        "list_files": lambda: f"Klasör listeleniyor: {a.get('path') or '.'}",
        "read_file": lambda: f"Okunuyor: {a.get('path', '?')}",
        "search_files": lambda: f"Aranıyor: “{a.get('pattern', '')}”",
        "find_files": lambda: f"Dosya aranıyor: {a.get('pattern', '')}",
        "write_file": lambda: f"Yazılıyor: {a.get('path', '?')}",
        "edit_file": lambda: f"Düzenleniyor: {a.get('path', '?')}",
        "run_command": lambda: f"Komut: {a.get('command', '')}",
        "update_todos": lambda: "Görev listesi güncelleniyor",
    }.get(call.name, lambda: call.name)()
