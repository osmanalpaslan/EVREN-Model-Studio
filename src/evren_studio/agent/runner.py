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
from pathlib import Path
from typing import Any, Protocol

from ..api.errors import ApiError, ErrorKind
from . import modelstats, planguard, textproto
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
    JOB_TOOLS,
    SERVICE_TOOLS,
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

DEFAULT_MAX_STEPS = 80
CHARS_PER_TOKEN = 3.5
# "gerekirse yeniden oku" demiyoruz: modeli aynı dosyaları tekrar okumaya itiyordu (döngü).
TRIMMED_NOTE = ("[Bu araç çıktısı bağlam sınırı nedeniyle kısaltıldı. İşlem zaten yapıldı; "
                "yalnızca içeriğe gerçekten yeniden ihtiyacın varsa tekrar çağır.]")

# ---- döngü bekçisi (2026-10-17 gerçek API ölçümü, docs/knowledge/LOOP_ANALYSIS.md) ----
# Aynı araç + aynı parametre, arada başarılı dosya değişikliği olmadan:
REPEAT_WARN = 2        # 2. kez → sonuca uyarı eklenir
REPEAT_STOP = 3        # 3. kez → tur durur ("loop"), kullanıcı karar verir
# Bir dosya bu tur içinde daha önceki bir hâline geri dönerse (ileri-geri düzenleme):
FLIPFLOP_STOP = 2      # 1. kez uyarı, 2. kez tur durur
# glm-5.3 metin protokolünde tek yanıtta 39 çağrı (çoğu uydurma dosya) üretti:
MAX_CALLS_PER_STEP = 12
REPEAT_NOTE = ("\n\n[Döngü uyarısı] Bu çağrıyı bu turda aynı parametrelerle zaten {n} kez yaptın ve "
               "arada dosya değişmedi; sonuç aynı olacak. Farklı bir yol dene; ilerleyemiyorsan dur ve "
               "kullanıcıya neyin engel olduğunu açıkça söyle.")
FLIPFLOP_NOTE = ("\n\n[Döngü uyarısı] {path} dosyası bu turda daha önceki bir hâline geri döndü "
                 "(aynı değişikliği ileri-geri yapıyorsun). Gereksinimler çelişiyor olabilir: test "
                 "dosyalarını değiştirmeden veya testi kandırmadan çözemiyorsan dur ve kullanıcıya bildir.")
NUDGE_EMPTY = ("[Otomatik hatırlatma] Son yanıtın boş geldi (muhtemelen düşünme bütçesi tükendi). "
               "Kısa düşün; ya bir sonraki aracı çağır ya da sonucu kısaca yaz.")
NUDGE_INTENT = ("[Otomatik hatırlatma] Ne yapacağını söyleyip araç çağırmadan durdun. Söylediğin işi "
                "şimdi araçlarla yap; iş zaten bittiyse ne yaptığını özetle.")
NUDGE_REPEAT = ("[Otomatik hatırlatma] Son yanıtın aynı cümleleri tekrar tekrar yazıyordu ve araç "
                "çağırmadın. Tekrarı bırak: yapacağın işin aracını ŞİMDİ çağır; iş bittiyse kısa bir "
                "özet yaz, bitmediyse neyin eksik olduğunu açıkça söyle.")
REPEAT_COLLAPSED = "\n\n[Tekrar eden metin kısaltıldı.]"
_INTENT_RE = None


class _StepCancel:
    """Kullanıcı iptaline ek olarak, akışta metin tekrarı görülünce isteği kesmeye yarar."""

    def __init__(self, outer: Any):
        self.outer = outer
        self.repetition = False

    @property
    def cancelled(self) -> bool:
        return self.repetition or bool(self.outer is not None and getattr(self.outer, "cancelled", False))


STREAM_REPEAT_MIN = 8      # akışta bu kadar tekrar eden cümle görülürse istek kesilir
MAX_JSON_400_RETRIES = 2   # tur başına, sunucunun model JSON'unu okuyamadığı 400'lerde yeniden deneme


def looks_like_model_json_error(message: str) -> bool:
    """400 mesajı, sunucunun MODEL çıktısındaki JSON'u ayrıştıramadığını mı gösteriyor?"""
    m = (message or "").lower()
    return any(s in m for s in ("expecting ',' delimiter", "expecting value", "expecting property name",
                                "unterminated string", "extra data", "invalid control character",
                                "jsondecodeerror", "invalid \\escape"))


def collapse_repetition(text: str, min_dup: int = 3) -> tuple[str, bool]:
    """Aynı cümleleri defalarca yazan (dejenere) yanıtı kısaltır.

    auto (2026-10-17 maraton): araç çağırmadan "dosyayı okuyayım. Testleri
    çalıştıracağım. …" cümlelerini onlarca kez yazdı; koşucu bunu yanıt sandı.
    Dönüş: (kısaltılmış metin, tekrar vardı mı). Kısa (<12 harf) parçalar ve
    birkaç tekrar normal sayılır; en az 3 tekrar ve parçaların %30'u gerekir.
    """
    import re

    if not text or len(text) < 120:
        return text, False
    parts = [p for p in re.split(r"(?<=[.!?…:])\s+|\n+", text.strip()) if p.strip()]
    seen: set[str] = set()
    kept: list[str] = []
    dup = 0
    for p in parts:
        key = re.sub(r"\W+", " ", p.lower()).strip()
        if len(key) >= 12 and key in seen:
            dup += 1
            continue
        seen.add(key)
        kept.append(p)
    if dup >= min_dup and dup >= 0.3 * len(parts):
        return " ".join(kept) + REPEAT_COLLAPSED, True
    return text, False


def looks_like_unfinished_intent(text: str) -> bool:
    """Kısa ve 'yapacağım/inceleyeyim' gibi niyet bildiren bir son yanıt mı?"""
    global _INTENT_RE
    import re

    if _INTENT_RE is None:
        _INTENT_RE = re.compile(
            r"(eyim|ayım|eceğim|acağım|elim|alım|iyorum|ıyorum|uyorum|üyorum|let me[^.]*|i will[^.]*)"
            r"[\s.:!…]*$", re.I)
    t = (text or "").strip()
    return bool(t) and len(t) <= 300 and bool(_INTENT_RE.search(t))


def call_signature(call: "ToolCall") -> str:
    return call.name + " " + json.dumps(call.arguments, ensure_ascii=False, sort_keys=True)


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
    stopped: str = "done"            # done | cancelled | max_steps | loop | error | context_limit | budget
    steps: int = 0
    protocol: str = "native"
    last_text: str = ""
    test_edits: list[str] = field(default_factory=list)   # istenmeden değiştirilen var olan test dosyaları
    open_plan_items: list[str] = field(default_factory=list)  # tur bittiğinde plan/görev listesinde açık kalanlar
    model_switches: list[tuple[str, str, str]] = field(default_factory=list)   # (eski, yeni, neden)


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


MAX_HISTORY_IMAGES = 6      # geçmişte modele yeniden gönderilen en fazla görsel (en yeniler)


def to_api_messages(system: str, history: list[dict], protocol: str,
                    images: bool = True) -> list[dict]:
    """Kayıtlı geçmiş → API mesajları. Kullanıcı mesajındaki görseller (meta.images)
    `_images` iç alanıyla taşınır; istemci gönderirken sağlayıcı biçimine çevirir
    (api/images.py). images=False (ör. özet isteği) görselleri yalnızca adıyla not eder."""
    msgs: list[dict] = [{"role": "system", "content": system}]
    pending_text_results: list[str] = []
    kept = 0
    keep_ids: set[int] = set()
    for m in reversed(history_after_summary(history)):
        imgs = (m.get("meta") or {}).get("images") if m.get("role") == "user" else None
        if imgs and images and kept < MAX_HISTORY_IMAGES:
            keep_ids.add(id(m))
            kept += len(imgs)

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
                state = (m.get("meta") or {}).get("provider_state")
                if state:
                    entry["_provider_state"] = state   # istemciler kullanır, EVREN siler
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
            entry = {"role": role, "content": content}
            imgs = (m.get("meta") or {}).get("images") if role == "user" else None
            if imgs:
                if id(m) in keep_ids:
                    entry["_images"] = list(imgs)
                else:
                    names = ", ".join(Path(p).name for p in imgs)
                    entry["content"] = (content + "\n" if content else "") + f"[ekli görsel: {names}]"
            msgs.append(entry)
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
                 hard_context_limit: int | None = None,
                 before_model_call: Any = None,
                 stall_retry_body: dict[str, Any] | None = None,
                 install_mode: str = "otomatik",
                 fallback_models: list[str] | None = None,
                 mcp: Any = None, edit_check: bool = True, services: Any = None,
                 test_check: bool = False, no_writes: bool = False, extra_tools: Any = None,
                 final_marker: str | None = None, plan_guard: bool = False, jobs: Any = None,
                 stats_sink: Any = None, baselines: dict | None = None,
                 slow_factor: float = modelstats.FACTOR_TURN, route_role: str = "",
                 base_body: dict[str, Any] | None = None, extra_hint: str = ""):
        self.client = client
        self.model = model
        # MCP araçları (agent/mcp.py; McpToolset veya LazyToolset): specs/get/call/notes.
        # Yalnız proje klasörlü oturumda kullanılır; okuma dışındaki araçlar izinden geçer.
        self.mcp = mcp
        self._mcp_noted = False
        # Hata bekçisi (agent/diagnostics.py): düzenlemeden sonra kesin hataları sonuca ekler
        self.edit_check = edit_check
        # Arka plan servisleri (agent/services.py: start_service/service_logs/stop_service); None → yok
        self.services = services
        # Test bekçisi (agent/testcheck.py): tur sonunda projenin testleri; tur başında geçenler bozulursa dürt
        self.test_check = test_check
        # QA ajanı: dosyaya yazma araçları sunulmaz ve engellenir (test eder, kod değiştirmez)
        self.no_writes = no_writes
        # Ek araçlar (QA: visual_check, qa_audit): specs() → ToolSpec listesi, run(call) → ToolResult
        self.extra_tools = extra_tools
        # Son yanıtta bulunması gereken işaret (QA: "<qa_sonuc>"); yoksa model bir kez hatırlatılır
        self.final_marker = final_marker
        # Plan bekçisi (agent/planguard.py): plan/görev listesinde açık madde varken tur bitmesin
        self.plan_guard = plan_guard
        # Uzun işler (agent/jobs.py: start_job/wait_job/job_status/stop_job); None → yok
        self.jobs = jobs
        # Auto Pro gerçek kullanım kaydı (A1): her çağrı ve yedeğe geçiş `stats_sink(dict)` ile bildirilir.
        # `baselines`: model → modelstats.Baseline (o günkü normal hız); yoksa yavaşlık kuralı çalışmaz (A3).
        self.stats_sink = stats_sink
        self.route_role = route_role
        self._slow = modelstats.SlowDetector(baselines, slow_factor)
        # F2: her çağrıya eklenecek alanlar (A10 tutarlılık: temperature/seed — yalnız seed'i dinleyen modelde;
        # model değişince bırakılır) ve tur ipucuna eklenecek metin (A7 rol talimatı, A13 planlayıcının planı).
        self.base_body = dict(base_body) if base_body else None
        self._base_body_model = model
        self.extra_hint = (extra_hint or "").strip()
        self._history_ref: list[dict] | None = None
        self._work = 0                       # gerçek iş sayacı (başarılı yazma/komut/servis/iş)
        # EVREN Akıllı (agent/router.py): birincil model sunucu hatası verir veya döngüye
        # girerse sıradaki yedeğe geçilir; görev ortasında başka nedenle model DEĞİŞMEZ.
        self.fallback_models = [m for m in (fallback_models or []) if m != model]
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
        # Her model çağrısından ÖNCE çağrılır; None → devam, metin → tur o
        # nedenle durur (ör. "budget": aylık bütçe doldu, arayüz onay ister).
        self.before_model_call = before_model_call
        # Boş yanıttan sonra yapılan TEK yeniden denemede isteğe eklenecek alanlar
        # (ör. {"reasoning_effort": "none"}; yalnız modeli destekliyorsa verilir).
        self.stall_retry_body = stall_retry_body
        # Ortam denetimi: "otomatik" → eksik program sorulmadan kurulur, "manuel" → sorulur.
        # Ajanın çalışma modundan bağımsızdır (kullanıcı kararı 2026-10-17).
        self.install_mode = install_mode if install_mode in ("otomatik", "manuel") else "otomatik"
        self._env_section: str | None = None
        self._nudge: str | None = None          # sonraki çağrıya eklenecek geçici hatırlatma
        self._extra_body: dict[str, Any] | None = None
        self._writes: list[tuple[str, str | None, str | None]] = []  # (yol, önce, sonra) — son araç
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
        plan = normalize_mode(self.mode) == "plan"
        base = READ_ONLY_SPECS if plan else TOOL_SPECS
        base = [s for s in base
                if (self.services is not None or s.name not in SERVICE_TOOLS)
                and (self.jobs is not None or s.name not in JOB_TOOLS)
                and not (self.no_writes and s.kind == WRITE)]
        if self.extra_tools is not None:
            base = base + [s for s in self.extra_tools.specs(read_only_only=plan) if s.name not in SPEC_BY_NAME]
        if self.mcp is None:
            return base
        extra = self.mcp.specs(read_only_only=plan)
        if not self._mcp_noted:
            self._mcp_noted = True
            for note in getattr(self.mcp, "notes", []) or []:
                self.events.status(note)
        return list(base) + [s for s in extra if s.name not in SPEC_BY_NAME]

    def _spec(self, name: str):
        spec = SPEC_BY_NAME.get(name)
        if spec is None and self.extra_tools is not None:
            spec = next((s for s in self.extra_tools.specs() if s.name == name), None)
        if spec is None and self.mcp is not None and self.agentic and name.startswith("mcp__"):
            tool = self.mcp.get(name)
            spec = tool.spec if tool is not None else None
        return spec

    def _system(self) -> str:
        if not self.agentic:
            return build_chat_system()
        if self._env_section is None:
            from . import environment

            try:
                self._env_section = environment.prompt_section(
                    environment.quick_status(self.workspace.root), self.install_mode)
            except OSError:
                self._env_section = ""
        specs = self._specs()
        system = build_agent_system(self.workspace, normalize_mode(self.mode), specs,
                                    text_protocol=(self.protocol == "text"),
                                    env_section=self._env_section)
        if self.mcp is not None:
            from .mcp import prompt_section

            section = prompt_section(specs, list(getattr(self.mcp, "hints", []) or []))
            if section:
                system += "\n\n" + section
        if self._plan_guard_active():
            section = planguard.system_section(*self._open_plan())
            if section:
                system += "\n\n" + section          # özetten/kısaltmadan sonra da plan görünür kalsın
        hint = getattr(self, "_turn_hint", "")
        return system + "\n\n" + hint if hint else system

    def _compute_turn_hint(self, history: list[dict]) -> str:
        """Tur başı: kullanıcının andığı ama projede olmayan dosyalar için uyarı (scope.py)."""
        if not self.agentic or self.workspace is None:
            return ""
        for m in reversed(history):
            if m.get("role") != "user":
                continue
            if (m.get("meta") or {}).get("auto_continue"):
                continue
            text = (m.get("content") or "").split("\n\n<ekli_dosyalar>", 1)[0]
            from .scope import user_allows_test_edits

            self._tests_allowed = user_allows_test_edits(text)
            try:
                from .scope import missing_hint, missing_mentions

                missing = missing_mentions(text, self.workspace.root)
            except OSError:
                return ""
            return missing_hint(missing) if missing else ""
        return ""

    def _record(self, **rec: Any) -> None:
        if self.stats_sink is None:
            return
        try:
            self.stats_sink({"role": self.route_role or None, **rec})
        except Exception:
            pass                                  # kayıt hatası turu bozmasın

    def _quality(self, event: str, detail: str = "") -> None:
        """A5: kalite olayı (modelstats.QUALITY_WEIGHTS) — o anki model adına kaydedilir."""
        self._record(model=self.model, ok=False, event=event, detail=detail[:200])

    def _switch_model(self, outcome: "TurnOutcome", exc: ApiError | None, loop_reason: str = "",
                      slow_reason: str = "") -> bool:
        """Yedek model varsa ona geçer. Kota/hız sınırı hesap başınadır: model değiştirmek
        çözmez, geçilmez. Döngüde tur başına yalnız bir kez geçilir. Yavaşlıkta (A3, DECISIONS #88)
        yalnız güvenli noktada ve görev başına bir kez (koşucu döngüsü ve SlowDetector sağlar)."""
        if not self.fallback_models:
            return False
        if exc is not None:
            # UNKNOWN_RESULT: akış koptu / zaman aşımı — eskiden tur hatayla bitiyordu; yedek modele
            # yeniden sormak güvenli (sohbet isteğinin yan etkisi yok, yalnız token).
            failover = {ErrorKind.SERVER_UNAVAILABLE, ErrorKind.SERVER_ERROR, ErrorKind.TIMEOUT,
                        ErrorKind.NOT_FOUND, ErrorKind.NETWORK, ErrorKind.UNKNOWN_RESULT}
            image_refused = exc.kind == ErrorKind.VALIDATION and "feature_not_enabled" in (exc.message or "")
            if exc.kind not in failover and not image_refused:
                return False
            reason = f"{exc.kind.value}" + (f" (HTTP {exc.status})" if exc.status else "")
        elif slow_reason:
            reason = f"yavaşlık: {slow_reason}"
        else:
            if any(s[2].startswith("döngü") for s in outcome.model_switches):
                return False
            reason = f"döngü: {loop_reason}"
            self._turn_hint = (getattr(self, "_turn_hint", "") + "\n\n# Model değişti (bu tur)\n"
                               f"Önceki model döngüye girdi ({loop_reason}). Aynı çağrıları tekrarlama; "
                               "farklı bir yol dene veya neyin engel olduğunu kullanıcıya açıkla.").strip()
        old, new = self.model, self.fallback_models.pop(0)
        self.model = new
        outcome.model_switches.append((old, new, reason))
        self._slow.reset()
        self._record(model=old, ok=False, event="switch", detail=f"{old} → {new}: {reason}")
        self.events.status(f"{old} → {new}: {reason}. Auto Pro yedek modele geçti; görev aynı yerden sürüyor.")
        return True

    def _remaining_test_edits(self) -> list[str]:
        """Turda istenmeden değiştirilip hâlâ eski hâline dönmemiş test dosyaları."""
        out = []
        for rel, before in getattr(self, "_test_orig", {}).items():
            try:
                now = self.toolbox.load_text(self.workspace.resolve(rel)).text
            except Exception:
                now = None
            if now != before:
                out.append(rel)
        return out

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
        if self._nudge:
            # Geçici: kayda yazılmaz, yalnız bu çağrıda gider.
            messages.append({"role": "user", "content": self._nudge})
            self._nudge = None
        extra_body, self._extra_body = self._extra_body, None
        tools = None
        if self.agentic and self.protocol == "native":
            tools = [s.openai_schema() for s in self._specs()]

        guard = _StepCancel(self.cancel)
        streamed: list[str] = []

        def on_delta(text: str, _finish: str = "") -> None:
            self.events.text_delta(text)
            streamed.append(text)
            # Akışta aynı cümleler dönüp duruyorsa isteği erken kes (zaman ve kota).
            if len(streamed) % 25 == 0 and not guard.repetition:
                if collapse_repetition("".join(streamed), min_dup=STREAM_REPEAT_MIN)[1]:
                    guard.repetition = True

        kwargs: dict[str, Any] = {}
        if self.base_body and self.model == self._base_body_model:
            extra_body = {**self.base_body, **(extra_body or {})}
        if extra_body:
            kwargs["extra_body"] = extra_body
        result = self.client.chat(
            self.model, messages, stream=self.stream, cancel=guard,
            on_delta=on_delta, on_reasoning=self.events.reasoning_delta,
            tools=tools, **kwargs,
        )
        if guard.repetition and not self._cancelled():
            result.finish_reason = "repetition"
        return result

    # -- ana döngü ---------------------------------------------------------------------

    def run(self, history: list[dict]) -> TurnOutcome:
        """`history` kayıtlı mesajlardır (son kullanıcı mesajı dahil); yerinde uzatılır."""
        outcome = TurnOutcome(protocol=self.protocol)
        self._tests_allowed = True
        self._test_orig: dict[str, str | None] = {}     # yol → turdaki ilk hâli
        self._wrote = False
        self._test_baseline = None
        self._history_ref = history
        plan_nudges = 0
        plan_strikes = 0
        plan_work_mark = -1
        self._turn_hint = "\n\n".join(h for h in (self._compute_turn_hint(history), self.extra_hint) if h)
        step = 0
        fallback_used = False
        # döngü bekçisi durumu (tur başına)
        repeats: dict[str, int] = {}                 # imza → son yazmadan beri kaç kez
        file_states: dict[str, list[int]] = {}       # yol → içerik özetleri (sırayla)
        flipflops = 0
        nudged: set[str] = set()
        loop_reason = ""
        json_retries = 0
        pending_slow = ""
        while step < self.max_steps:
            if self._cancelled():
                outcome.stopped = "cancelled"
                break
            if pending_slow:
                # Güvenli nokta: önceki adımın araçları tamamlandı, yarım düzenleme yok (DECISIONS #88)
                if self._switch_model(outcome, None, slow_reason=pending_slow):
                    self._slow.used = True
                pending_slow = ""
            step += 1
            outcome.steps = step
            if self.before_model_call is not None:
                stop = self.before_model_call(step)
                if stop:
                    outcome.stopped = stop
                    break
            self.events.step_started(step)
            t0 = time.monotonic()
            try:
                result = self._call_model(history)
            except ApiError as exc:
                self._record(model=self.model, ok=False, error_kind=exc.kind.value,
                             duration_s=round(time.monotonic() - t0, 1), detail=(exc.message or "")[:200])
                # EVREN, modelin ürettiği bozuk araç JSON'unu kendisi ayrıştıramayınca 400
                # döndürüyor ("Expecting ',' delimiter"); bu tek seferlik — aynı adımı yeniden dene,
                # yerel protokolü bırakma (2026-10-17 maraton: auto 3 denemede 1 kez).
                if (exc.kind == ErrorKind.VALIDATION and json_retries < MAX_JSON_400_RETRIES
                        and looks_like_model_json_error(exc.message)):
                    json_retries += 1
                    self.events.status("Sunucu, modelin ürettiği araç çağrısını okuyamadı (400); "
                                       "aynı adım yeniden deneniyor.")
                    step -= 1
                    continue
                # Model görseli reddetti (400 feature_not_enabled): protokol sorunu değil,
                # model sorunu — metin protokolüne geçmeden önce görsel okuyan yedeğe geç.
                if (exc.kind == ErrorKind.VALIDATION and "feature_not_enabled" in (exc.message or "")
                        and self._switch_model(outcome, exc)):
                    step -= 1
                    continue
                if (self.agentic and self.protocol == "native" and self.allow_fallback
                        and not fallback_used and exc.kind == ErrorKind.VALIDATION):
                    fallback_used = True
                    self.protocol = outcome.protocol = "text"
                    self.events.protocol_changed(
                        "text", f"Model yerel araç çağrısını reddetti ({exc.status}); "
                                "metin protokolüne geçildi.")
                    step -= 1
                    continue
                if self._switch_model(outcome, exc):
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
            content, repetitive = collapse_repetition(content)

            cancelled = result.finish_reason == "cancelled_by_user"
            duration = round(time.monotonic() - t0, 1)
            routed = getattr(result, "routed_model", None)
            meta: dict[str, Any] = {"duration_s": duration, "requested_model": self.model}
            if result.finish_reason:
                meta["finish_reason"] = result.finish_reason
            if routed and routed != self.model:
                meta["routed_model"] = routed
            token_usage = result.token_usage() if hasattr(result, "token_usage") else {}
            if any(token_usage.values()):
                meta["usage"] = token_usage
            if not cancelled:
                rec = {"model": self.model, "ok": True, "duration_s": duration,
                       "first_chunk_s": getattr(result, "first_chunk_s", None),
                       "out_tokens": token_usage.get("output_tokens") or None,
                       "empty": not content.strip() and not calls}
                self._record(**rec)
                if self.fallback_models:
                    pending_slow = self._slow.observe(self.model, rec)
            state = getattr(result, "provider_state", None)
            if state:
                meta["provider_state"] = state
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
                stall = ("repeat" if repetitive else self._stall_kind(content, result)) if self.agentic else None
                if stall == "intent" and normalize_mode(self.mode) == "plan":
                    # Plan modunda "…değiştireceğim" ile biten yanıt beklenen sonuçtur (plan), dürtme.
                    stall = None
                if stall and stall not in nudged and step < self.max_steps:
                    # Boş yanıt / "inceleyeyim" deyip durma / metin tekrarı: bir kez otomatik dürt.
                    nudged.add(stall)
                    self._nudge = {"empty": NUDGE_EMPTY, "repeat": NUDGE_REPEAT}.get(stall, NUDGE_INTENT)
                    if stall == "empty" and self.stall_retry_body:
                        self._extra_body = dict(self.stall_retry_body)
                    self.events.status(
                        "Model boş yanıt döndürdü; kısa bir hatırlatmayla bir kez yeniden deneniyor."
                        if stall == "empty" else
                        "Model işi yapmadan durdu; devam etmesi için bir kez hatırlatıldı.")
                    continue
                if not content.strip():
                    self.events.status("Model boş yanıt döndürdü (düşünme bütçesi tükenmiş olabilir). "
                                       "Başka bir model seçebilir veya mesajı yeniden gönderebilirsiniz.")
                if (self.final_marker and self.final_marker not in content and "marker" not in nudged
                        and step < self.max_steps and not self._cancelled()):
                    nudged.add("marker")
                    self._nudge = (f"Yanıtın tamamlanmadı: istenen {self.final_marker} bloğunu yazmadın. "
                                   f"Şimdi yalnız sonucu {self.final_marker} … bloğu içinde, istenen JSON "
                                   "biçimiyle ver (yeni araç çağırma gerekmiyorsa çağırma).")
                    self.events.status("Model sonuç bloğunu yazmadı; bir kez hatırlatıldı.")
                    continue
                if (self._plan_guard_active() and "ENGEL:" not in content and "SORU:" not in content
                        and not self._cancelled()):
                    items, source = self._open_plan()
                    if items:
                        if plan_work_mark >= 0 and self._work == plan_work_mark:
                            plan_strikes += 1
                        else:
                            plan_strikes = 0
                        if plan_nudges < planguard.PLAN_NUDGE_MAX and plan_strikes < planguard.NO_PROGRESS_STOP \
                                and step < self.max_steps:
                            plan_nudges += 1
                            plan_work_mark = self._work
                            self._nudge = planguard.nudge_text(items, source)
                            self.events.status(f"Plan bekçisi: planda {len(items)} açık madde var; ajan "
                                               f"sıradakine devam ettiriliyor ({plan_nudges}).")
                            continue
                        outcome.open_plan_items = items
                        if plan_strikes >= planguard.NO_PROGRESS_STOP:
                            self._quality("plan_stall", f"{len(items)} açık madde")
                        self.events.status(f"Plan bekçisi: planda {len(items)} açık madde kaldı ama ajan "
                                           "ilerleme göstermiyor; durdu. 'devam' yazarak sürdürebilirsiniz.")
                if "tests" not in nudged and step < self.max_steps and not self._cancelled():
                    gate = self._test_gate()
                    if gate:
                        self._quality("test_break")
                        nudged.add("tests")
                        self._nudge = gate
                        continue
                outcome.stopped = "done"
                break

            for i, call in enumerate(calls):
                if self._cancelled():
                    res = ToolResult(False, "İşlem kullanıcı tarafından iptal edildi.", "İptal edildi")
                elif loop_reason:
                    # Döngü bu yanıtın içinde algılandı: kalan çağrılar çalıştırılmaz.
                    res = ToolResult(False, "Döngü algılandığı için bu çağrı çalıştırılmadı.",
                                     "Atlandı (döngü)")
                elif i >= MAX_CALLS_PER_STEP:
                    res = ToolResult(False, f"Tek yanıtta en fazla {MAX_CALLS_PER_STEP} araç çağrısı "
                                     "çalıştırılır; bu çağrı atlandı. Gerçekten gerekiyorsa sonraki "
                                     "adımda iste.", "Atlandı (çok fazla çağrı)")
                else:
                    self._writes = []
                    res = self._execute(call)
                    note, stop = self._guard(call, res, repeats, file_states)
                    if note:
                        res.content += note
                    if stop == "flipflop":
                        flipflops += 1
                        if flipflops >= FLIPFLOP_STOP:
                            loop_reason = loop_reason or (
                                f"bir dosya tekrar tekrar eski hâline döndürüldü ({res.extra.get('path', '?')})")
                    elif stop:
                        loop_reason = loop_reason or stop
                self._save(history, "tool", res.content, tool_call_id=call.id, name=call.name,
                           meta={"error": not res.ok, "summary": res.summary, **res.extra})
            for err in parse_errors:
                fake = ToolCall(textproto.new_call_id(), "arac_cagrisi", "")
                self._save(history, "tool", err, tool_call_id=fake.id, name="arac_cagrisi",
                           meta={"error": True, "summary": "Araç bloğu okunamadı"})
            if self._cancelled():
                outcome.stopped = "cancelled"
                break
            if loop_reason:
                self._quality("loop", loop_reason)
            if loop_reason and self._switch_model(outcome, None, loop_reason):
                repeats.clear()
                file_states.clear()
                flipflops = 0
                nudged.clear()
                loop_reason = ""
                continue
            if loop_reason:
                outcome.stopped = "loop"
                self.events.status(
                    f"Döngü algılandı: {loop_reason}. Model aynı işi sonuç almadan tekrarlıyor; "
                    "tur durduruldu. Yeni bir yönlendirme yazın ya da başka bir model deneyin.")
                break
            if self.hard_context_limit and self._history_tokens(history) >= self.hard_context_limit:
                outcome.stopped = "context_limit"
                break
        else:
            outcome.stopped = "max_steps"
            if self._plan_guard_active():
                outcome.open_plan_items = self._open_plan()[0]
            self.events.status(f"Adım sınırına ({self.max_steps}) ulaşıldı; devam etmek için mesaj gönderin.")
        outcome.test_edits = self._remaining_test_edits()
        if outcome.test_edits:
            self._quality("test_edit", ", ".join(outcome.test_edits))
        return outcome

    def _plan_guard_active(self) -> bool:
        return bool(self.plan_guard and self.agentic and normalize_mode(self.mode) != "plan"
                    and not self.no_writes and not self.final_marker
                    and not planguard.plan_only_request(self._history_ref or []))

    def _open_plan(self) -> tuple[list[str], str]:
        if self._history_ref is None:
            return [], ""
        try:
            return planguard.open_items(self._history_ref, self.workspace.root if self.workspace else None)
        except Exception:
            return [], ""

    @staticmethod
    def _stall_kind(content: str, result: Any) -> str | None:
        """Araçsız son yanıt bitmemiş iş gibi mi görünüyor? → "empty" | "intent" | None"""
        if not (content or "").strip():
            return "empty"
        if looks_like_unfinished_intent(content):
            return "intent"
        return None

    def _guard(self, call: ToolCall, res: ToolResult, repeats: dict[str, int],
               file_states: dict[str, list[int]]) -> tuple[str, str]:
        """Döngü bekçisi. Dönüş: (sonuca eklenecek not, durma nedeni | "flipflop" | "")."""
        spec = self._spec(call.name)
        if spec is None or spec.kind == META:
            return "", ""
        if spec.kind == WRITE:
            if not res.ok:
                key = call_signature(call)
                repeats[key] = repeats.get(key, 0) + 1
                if repeats[key] >= REPEAT_STOP:
                    return "", f"aynı başarısız düzenleme {repeats[key]} kez denendi ({call.name})"
                if repeats[key] >= REPEAT_WARN:
                    return REPEAT_NOTE.format(n=repeats[key] - 1), ""
                return "", ""
            # Başarılı yazma: dosyalar değişti, okuma/komut tekrarları yeniden sayılır.
            repeats.clear()
            note, stop = "", ""
            for path, before, after in self._writes:
                h = hash(after)
                states = file_states.setdefault(path, [hash(before)])
                if len(states) >= 2 and h in states[:-1]:
                    note, stop = FLIPFLOP_NOTE.format(path=path), "flipflop"
                states.append(h)
            return note, stop
        key = call_signature(call)
        repeats[key] = repeats.get(key, 0) + 1
        n = repeats[key]
        if n >= REPEAT_STOP:
            return "", f"“{describe_call(call)}” {n} kez aynı sonuçla tekrarlandı"
        if n >= REPEAT_WARN:
            return REPEAT_NOTE.format(n=n - 1), ""
        return "", ""

    def _history_tokens(self, history: list[dict]) -> int:
        return estimate_tokens(to_api_messages("", history, self.protocol)) + 2_500

    # -- araç yürütme -------------------------------------------------------------------------

    def _execute(self, call: ToolCall) -> ToolResult:
        spec = self._spec(call.name)
        if spec is None:
            names = [sp.name for sp in self._specs()] or list(SPEC_BY_NAME)
            return ToolResult(False, f"Bilinmeyen araç: {call.name}. Kullanılabilir araçlar: "
                              + ", ".join(names), f"Bilinmeyen araç: {call.name}")
        if call.parse_error:
            return ToolResult(False, call.parse_error, "Parametreler okunamadı")
        if self.toolbox is None:
            return ToolResult(False, "Bu oturumda proje klasörü yok; araç kullanılamaz.", "Proje yok")
        if self.no_writes and spec.kind == WRITE:
            return ToolResult(False, "Bu çalışmada (QA) dosya değiştirilemez: yalnız test et ve bulguyu raporla.",
                              "Engellendi (QA)")
        if normalize_mode(self.mode) == "plan" and spec.kind in (WRITE, EXEC):
            _d, reason = decide(self.mode, spec.kind, self.perms)
            return ToolResult(False, reason, "Plan modunda engellendi")
        self.events.tool_started(call, describe_call(call))
        try:
            if call.name.startswith("mcp__") and call.name not in SPEC_BY_NAME:
                res = self._run_mcp(call, spec)
            elif call.name in SERVICE_TOOLS:
                res = self._run_service(call)
            elif call.name in JOB_TOOLS:
                res = self._run_job(call)
            elif self.extra_tools is not None and call.name not in SPEC_BY_NAME:
                res = self.extra_tools.run(call)
            elif call.name == "install_program":
                res = self._run_install(call)
            elif spec.kind == READ:
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

    def _run_mcp(self, call: ToolCall, spec) -> ToolResult:
        """MCP sunucusunun aracı. Salt okuma listesindeki araç sormadan çalışır; diğerleri
        komut gibi izin sisteminden geçer (Manuel/Kabul: sorulur, Otomatik: sorulmaz, Plan:
        engelli — üstte). Sunucunun yaptığı dosya değişiklikleri fark kartına GİRMEZ."""
        from .mcp import McpError

        server = call.name.split("__")[1] if call.name.count("__") >= 2 else "mcp"
        tool = call.name.split("__", 2)[-1]
        if spec.kind != READ:
            key = f"mcp:{call.name}"
            decision, reason = decide(self.mode, EXEC, self.perms)
            if key in self.perms.command_prefixes:
                decision = Decision.ALLOW
            if decision == Decision.DENY:
                return ToolResult(False, reason, "Engellendi")
            if decision == Decision.ASK:
                args = json.dumps(call.arguments, ensure_ascii=False)[:600]
                ok, feedback = self._approve(
                    call, EXEC, f"MCP aracı çalışsın mı? {server} · {tool}", args, prefix=key,
                    reason="Dış MCP sunucusunun aracı; yaptığı dosya değişiklikleri Değişiklikler "
                           "paneline düşmez ve geri alınamaz.")
                if not ok:
                    msg = "Kullanıcı bu MCP aracının çalışmasına izin vermedi."
                    if feedback:
                        msg += f" Kullanıcının notu: {feedback}"
                    return ToolResult(False, msg, f"Reddedildi: {server}.{tool}", {"denied": True})
        try:
            text, is_error = self.mcp.call(call.name, call.arguments)
        except McpError as exc:
            return ToolResult(False, f"MCP hatası: {exc}", f"MCP hatası: {server}.{tool}")
        out = truncate_middle(text, self.output_limit)
        first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")[:80]
        summary = f"MCP {server}.{tool}" + (f": {first}" if first else "")
        if is_error:
            return ToolResult(False, f"MCP aracı hata döndürdü: {out}", f"MCP hata: {server}.{tool}",
                              {"output": truncate_middle(text, 4000)})
        return ToolResult(True, out, summary, {"output": truncate_middle(text, 4000), "mcp": server})

    def _run_service(self, call: ToolCall) -> ToolResult:
        if self.services is None:
            return ToolResult(False, "Bu oturumda arka plan servisi kullanılamıyor.", "Servis yok")
        a = call.arguments
        if call.name == "service_logs":
            out = self.services.logs(str(a.get("name") or ""), int(a.get("lines") or 60))
            return ToolResult(True, truncate_middle(out, self.output_limit), "Servis çıktısı okundu",
                              {"output": truncate_middle(out, 4000)})
        if call.name == "stop_service":
            out = self.services.stop(str(a.get("name") or ""))
            return ToolResult(True, out, out)
        command = _req(a, "command").strip()
        decision, reason = decide(self.mode, EXEC, self.perms, command,
                                  root=self.workspace.root if self.workspace else None)
        if decision == Decision.DENY:
            return ToolResult(False, reason, "Engellendi")
        if decision == Decision.ASK:
            ok, feedback = self._approve(call, EXEC, "Servis (arka planda) başlatılsın mı?", command,
                                         prefix=command_prefix(command), reason=reason)
            if not ok:
                msg = "Kullanıcı bu servisin başlatılmasını reddetti."
                if feedback:
                    msg += f" Kullanıcının notu: {feedback}"
                return ToolResult(False, msg, f"Reddedildi: {command[:80]}", {"command": command, "denied": True})
        port = a.get("port")
        try:
            port = int(port) if port not in (None, "") else None
        except (TypeError, ValueError):
            port = None
        out = self.services.start(command, str(a.get("name") or ""), port, str(a.get("ready_text") or ""),
                                  cancel=self.cancel)
        ok = "çalışıyor" in out.split("\n", 1)[0]
        self._work += 1
        return ToolResult(ok, truncate_middle(out, self.output_limit), out.split("\n", 1)[0][:120],
                          {"command": command, "output": truncate_middle(out, 4000)})

    def _run_job(self, call: ToolCall) -> ToolResult:
        if self.jobs is None:
            return ToolResult(False, "Bu oturumda uzun iş kullanılamıyor.", "Uzun iş yok")
        a = call.arguments
        jid = str(a.get("job_id") or "")
        if call.name == "job_status":
            job = self.jobs.get(jid)
            out = job.summary(int(a.get("lines") or 40))
            return ToolResult(True, truncate_middle(out, self.output_limit), f"İş {job.id}: {job.state()}")
        if call.name == "stop_job":
            job = self.jobs.stop(jid)
            return ToolResult(True, f"İş {job.id} durduruldu.\n{job.summary(15)}", f"İş durduruldu: {job.id}")
        if call.name == "wait_job":
            job, why = self.jobs.wait(jid, a.get("max_minutes") or 60, cancel=self.cancel,
                                      progress=lambda t: self.events.tool_output(call, t))
            if not job.running:
                job.notified = True                       # sonucu model aldı; ayrıca bildirim gerekmez
            ok = (not job.running) and job.exit_code == 0
            return ToolResult(ok, truncate_middle(f"Bekleme: {why}.\n{job.summary(60)}", self.output_limit),
                              f"İş {job.id}: {job.state()} ({job.elapsed() / 60:.1f} dk)",
                              {"output": truncate_middle(job.summary(40), 4000)})
        command = _req(a, "command").strip()
        decision, reason = decide(self.mode, EXEC, self.perms, command,
                                  root=self.workspace.root if self.workspace else None)
        if decision == Decision.DENY:
            return ToolResult(False, reason, "Engellendi")
        if decision == Decision.ASK:
            ok, feedback = self._approve(call, EXEC, "Uzun iş (arka planda) başlatılsın mı?", command,
                                         prefix=command_prefix(command), reason=reason)
            if not ok:
                msg = "Kullanıcı bu uzun işin başlatılmasını reddetti."
                if feedback:
                    msg += f" Kullanıcının notu: {feedback}"
                return ToolResult(False, msg, f"Reddedildi: {command[:80]}", {"command": command, "denied": True})
        job = self.jobs.start(self.workspace.root, command, str(a.get("name") or ""))
        self._work += 1
        return ToolResult(True, f"Uzun iş başlatıldı: {job.id}\nKomut: {command}\nTam çıktı: {job.log_path}\n"
                                "Sonucu almak için wait_job çağır (bekleme kota harcamaz).",
                          f"Uzun iş başlatıldı: {job.id}", {"command": command, "job_id": job.id})

    def _test_gate(self) -> str:
        """Test bekçisi (tur sonu). Dönüş: modele gidecek dürtme metni ya da ""."""
        from . import testcheck

        base = getattr(self, "_test_baseline", None)
        if not (self.test_check and getattr(self, "_wrote", False) and self.toolbox is not None
                and base in ("gecti", "yok") and normalize_mode(self.mode) != "plan"):
            return ""
        cmd = testcheck.detect_command(self.workspace.root)
        if not cmd:
            return ""
        self.events.status(f"Test bekçisi: proje testleri çalıştırılıyor ({cmd})…")
        state, code, out = testcheck.run(self.toolbox, cmd, cancel=self.cancel)
        if state == "gecti":
            self.events.status(f"Test bekçisi: testler geçti ({cmd}).")
            return ""
        if state != "dustu":
            return ""
        self.events.status("Test bekçisi: değişiklikten sonra testler düştü; model düzeltmesi için uyarıldı.")
        return testcheck.NUDGE.format(cmd=cmd, code=code, tail=testcheck.tail(out))

    def _test_baseline_once(self) -> None:
        """İlk yazmadan ÖNCE testlerin durumu (yalnız tur başında geçenler korunur)."""
        if not self.test_check or getattr(self, "_test_baseline", None) is not None or self.toolbox is None:
            return
        from . import testcheck

        cmd = testcheck.detect_command(self.workspace.root)
        if not cmd:
            self._test_baseline = "yok"
            return
        state, _code, _out = testcheck.run(self.toolbox, cmd, cancel=self.cancel)
        self._test_baseline = state

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
            elif kind == "install":
                self.perms.allow_installs = True
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
        self._test_baseline_once()
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
        self._wrote = True
        from .planguard import is_plan_file

        if not is_plan_file(change.rel_path):
            self._work += 1                  # plan dosyasını işaretlemek tek başına ilerleme sayılmaz
        self._writes.append((change.rel_path, change.before, change.after))
        change_id = self.store.add_file_change(self.session_id, self.turn_id, change.rel_path,
                                               change.before, change.after)
        self.events.file_changed(change_id, change)
        added, removed = change.stats
        verb = "Oluşturuldu" if change.is_new else "Düzenlendi"
        extra = {"diff": change.diff, "path": change.rel_path, "change_id": change_id}
        if decision == Decision.ALLOW and normalize_mode(self.mode) in ("kabul", "auto"):
            extra["auto_approved"] = True
        content = f"{verb}: {change.rel_path} (+{added} −{removed} satır)."
        warn = self._post_edit_check(change.rel_path, change.after)
        if warn:
            content += warn
            extra["diagnostics"] = warn.strip()
        from .scope import TEST_EDIT_WARNING, is_test_path

        if not change.is_new and is_test_path(change.rel_path) and not getattr(self, "_tests_allowed", True):
            content += TEST_EDIT_WARNING.format(path=change.rel_path)
            self._test_orig.setdefault(change.rel_path, change.before)
            extra["test_edit"] = True
        return ToolResult(True, content, f"{verb}: {change.rel_path}  +{added} −{removed}", extra)

    def _post_edit_check(self, rel_path: str, text: str | None) -> str:
        """Hata bekçisi: önce yerleşik (sözdizimi/JSON), sorun yoksa Serena teşhisi. Hiçbir
        hata turu düşürmez."""
        if not self.edit_check or self.workspace is None:
            return ""
        from . import diagnostics

        try:
            problems = diagnostics.builtin_problems(rel_path, text, self.workspace.root)
            if not problems and self.mcp is not None and hasattr(self.mcp, "diagnostics"):
                problems = self.mcp.diagnostics(rel_path)
        except Exception:
            return ""
        return diagnostics.note(rel_path, problems)

    def _run_install(self, call: ToolCall) -> ToolResult:
        """Ortam denetimi: bilinen listedeki eksik programı ayara göre sorarak/sormadan kurar."""
        from . import environment as envmod

        name = str(_req(call.arguments, "name"))
        key = envmod.normalize_tool(name)
        if key is None:
            known = ", ".join(sorted(envmod.KNOWN_TOOLS))
            return ToolResult(False, f"'{name}' bilinen kurulum listesinde yok (kurulabilenler: {known}). "
                              "Kullanıcıya bu programı kendisinin kurması gerektiğini söyle.",
                              f"Bilinmeyen program: {name}")
        tool = envmod.KNOWN_TOOLS[key]
        exe = envmod.find_exe(tool)
        if exe:
            return ToolResult(True, f"{tool.title} zaten kurulu: {exe}", f"Zaten kurulu: {tool.title}")
        plan = envmod.describe_plan(key)
        reason = str(call.arguments.get("reason") or "").strip()
        asked = False
        if self.install_mode != "otomatik" and not self.perms.allow_installs:
            asked = True
            ok, feedback = self._approve(
                call, "install", f"{tool.title} kurulsun mu?", plan,
                reason=reason or "Proje bu programa ihtiyaç duyuyor; bilgisayarda kurulu değil.")
            if not ok:
                msg = (f"Kullanıcı {tool.title} kurulumunu reddetti. Program olmadan devam etmenin "
                       "yolunu bul ya da kullanıcıya programı kendisinin kurabileceğini söyle.")
                if feedback:
                    msg += f" Kullanıcının notu: {feedback}"
                return ToolResult(False, msg, f"Kurulum reddedildi: {tool.title}",
                                  {"command": plan, "denied": True})
        result = envmod.install(key, on_output=lambda chunk: self.events.tool_output(call, chunk),
                                cancel=self.cancel)
        self._env_section = None          # sonraki istemde güncel durum
        steps = ("\n" + "\n".join(result.steps)) if result.steps else ""
        if result.ok:
            text = f"{tool.title} kuruldu" + (f" (sürüm {result.version})" if result.version else "") + "."
            if result.needs_restart:
                text += (" Kurulum başarılı ama program bu oturumda henüz bulunamıyor; gerekirse "
                         "kullanıcıdan EVREN Studio'yu yeniden başlatmasını iste.")
            if tool.npm_package and result.command.startswith("npm"):
                text += (f" PowerShell'de `{tool.exes[0]}.cmd` olarak çağır (betik politikası "
                         f"`{tool.exes[0]}.ps1` kabuğunu engelleyebilir).")
            summary = f"Kuruldu: {tool.title}" + (f" {result.version}" if result.version else "")
        else:
            text = f"{tool.title} kurulamadı. Komut: {result.command or plan}"
            summary = f"Kurulamadı: {tool.title}"
        return ToolResult(result.ok, text + steps + ("\n" + result.output[-1500:] if result.output else ""),
                          summary, {"command": result.command or plan,
                                    "output": result.output[-4000:],
                                    "auto_approved": not asked,
                                    "auto_reason": "Program kurulumu: Otomatik" if not asked else ""})

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
        self._work += 1                      # komut çalıştı (sonucu ne olursa olsun bir iş adımı)
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
        "install_program": lambda: f"Program kuruluyor: {a.get('name', '?')}",
        "start_service": lambda: f"Servis başlatılıyor: {a.get('command', '')}",
        "service_logs": lambda: f"Servis çıktısı: {a.get('name') or ''}".strip(),
        "stop_service": lambda: f"Servis kapatılıyor: {a.get('name') or ''}".strip(),
        "start_job": lambda: f"Uzun iş başlatılıyor: {a.get('command', '')}",
        "wait_job": lambda: f"Uzun iş bekleniyor: {a.get('job_id') or ''}".strip(),
        "job_status": lambda: f"Uzun iş durumu: {a.get('job_id') or ''}".strip(),
        "stop_job": lambda: f"Uzun iş durduruluyor: {a.get('job_id') or ''}".strip(),
        "update_todos": lambda: "Görev listesi güncelleniyor",
    }.get(call.name, lambda: _describe_mcp(call))()


def _describe_mcp(call: ToolCall) -> str:
    if call.name.startswith("mcp__") and call.name.count("__") >= 2:
        _p, server, tool = call.name.split("__", 2)
        hint = next((str(v) for v in call.arguments.values() if isinstance(v, str) and v), "")
        return f"MCP {server}: {tool}" + (f" — {hint[:60]}" if hint else "")
    return call.name
