"""Derin Mod: Claude Code'un "ultracode" moduna benzer çok ajanlı çalışma (Qt'siz çekirdek).

Kullanıcı kararları (2026-10-21): composer'daki "Derin" düğmesi açıkken HER iş bu akışla yürür;
yalnız ücretsiz EVREN; kota kapısı; ek API anahtarı yok (koşullar belirsiz).

Akış (fazları KOD sürer — model "sonraki faza geçmeyi" unutamaz):
1. ANLA      — 2–3 bağımsız, SALT OKUNUR alt ajan farklı açılardan projeyi inceler (paralel).
2. PLANLA    — iki farklı EVREN modeli bağımsız plan yazar; yargıç model birini seçer (iş ise).
3. UYGULA    — seçilen plan Proje ajanına verilir (onay kartı, görev görev, doğrulama, commit).
4. DOĞRULA   — 2 bağımsız denetçi değişikliği isteğe karşı ÇÜRÜTMEYE çalışır (paralel, salt okunur).
5. DÜZELT    — çoğunluğun ya da "yüksek" bulgusunun onayladığı sorunlar düzeltilir (en çok 2 tur).
Soru türü isteklerde 1 + yanıt turu yapılır.

Alt ajanlar arayüzsüzdür: AgentRunner bellek içi kayıtla koşar, onay isteğini HEMEN reddeder
(sonsuz bekleme olmasın), her model çağrısından önce kota kapısından geçer (agent/quota.py).
"""
from __future__ import annotations

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .runner import AgentEvents, AgentRunner, ApprovalRequest
from .tools import Workspace

REPORT_FILE = "EVREN_DERIN.md"
MAX_FIX_ROUNDS = 2
SUB_MAX_STEPS = 25
_CHANGE_VERBS = re.compile(
    r"\b(ekle|yap|yaz|düzelt|duzelt|değiştir|degistir|oluştur|olustur|kaldır|kaldir|sil|güncelle|guncelle|"
    r"geliştir|gelistir|uygula|taşı|tasi|refactor|implement|fix|add|create|build|kur|bağla|bagla|yeniden)",
    re.I)

ANGLES = [
    ("yapi", "Proje yapısı ve mimari: giriş noktaları, modüller, veri akışı; istekle ilgili bölümler nerede?"),
    ("kod", "İstekle doğrudan ilgili kod: hangi dosya/fonksiyonlar değişmeli ya da yanıtı içeriyor; kenar durumlar, riskler."),
    ("test", "Doğrulama yolu: mevcut testler, nasıl çalıştırılır, istek için hangi test/deneme gerekir; bozulabilecek yerler."),
]


@dataclass
class DeepState:
    goal: str
    kind: str = "is"                         # "is" (değişiklik) | "soru"
    phase: str = "anla"                       # anla | planla | uygula | dogrula | duzelt | bitti
    findings: list[dict] = field(default_factory=list)
    plans: list[dict] = field(default_factory=list)
    chosen: str = ""
    judge_note: str = ""
    issues: list[dict] = field(default_factory=list)
    fix_round: int = 0
    status: str = "calisiyor"                 # calisiyor | bitti | duraklatildi | durduruldu
    pause_reason: str = ""
    started_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    log: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


_QUESTION_WORD = re.compile(
    r"\b(ne|neden|niçin|nicin|nasıl|nasil|nerede|nereden|hangi|kaç|kac|kim|what|why|how|where|which|açıkla|acikla)\b",
    re.I)


def classify(text: str) -> str:
    """İş mi soru mu? Soru sözcüğü (ne, nasıl, nerede…) içerip "?" ile biten ya da değişiklik fiili içermeyen kısa
    istek "soru"dur (anla + yanıt; dosya değişmez). Fiiller ekli yazıldığından kök araması yapılır."""
    t = (text or "").strip()
    if t.endswith("?") and (_QUESTION_WORD.search(t) or not _CHANGE_VERBS.search(t)):
        return "soru"
    if _CHANGE_VERBS.search(t):
        return "is"
    return "soru" if len(t) < 400 else "is"


# ---- arayüzsüz alt ajan ----------------------------------------------------------------------

class MemoryStore:
    """SessionStore'un bellek içi karşılığı (alt ajanlar oturum veritabanını kirletmesin)."""

    def __init__(self):
        self.messages: list[dict] = []
        self._id = 0
        self.todos: list[dict] = []

    def add_session_message(self, session_id, role, content, **kw) -> int:
        self._id += 1
        self.messages.append({"id": self._id, "role": role, "content": content, **kw})
        return self._id

    def add_file_change(self, *a, **k) -> int:
        self._id += 1
        return self._id

    def set_session_todos(self, session_id, todos) -> None:
        self.todos = list(todos)


class HeadlessEvents(AgentEvents):
    """Onay isteğini ANINDA reddeder (arayüzsüz ajan sonsuza dek beklemesin); durumları toplar."""

    def __init__(self, status: Callable[[str], None] | None = None):
        self.notes: list[str] = []
        self._status = status

    def approval_needed(self, request: ApprovalRequest) -> None:
        request.resolve(ApprovalRequest.DENY, "Derin Mod alt ajanı salt okunurdur; bu işlem yapılmaz.")

    def status(self, text: str) -> None:
        self.notes.append(text)


@dataclass
class SubResult:
    text: str
    stopped: str
    error: str = ""


def run_subagent(*, client: Any, model: str, fallbacks: list[str], root: Path, prompt: str,
                 marker: str, gate=None, cancel=None, mcp=None, max_steps: int = SUB_MAX_STEPS,
                 context_tokens: int | None = None) -> SubResult:
    """Salt okunur (Plan modu) arayüzsüz alt ajan. Son yanıt metnini döndürür."""
    store = MemoryStore()
    history = [{"id": 0, "role": "user", "content": prompt}]
    store.messages.append(history[0])

    def before(_step):
        if gate is None:
            return None
        r = gate.before_call(cancel=cancel)
        return {"daily": "quota_daily", "cancelled": "cancelled"}.get(r) if r else None
    runner = AgentRunner(client, model, session_id=0, store=store, events=HeadlessEvents(),
                         workspace=Workspace(root), mode="plan", stream=False, cancel=cancel,
                         max_steps=max_steps, before_model_call=before, fallback_models=list(fallbacks),
                         final_marker=marker, mcp=mcp, context_tokens=context_tokens)
    try:
        out = runner.run(history)
    except Exception as exc:  # alt ajan hatası tüm Derin koşuyu düşürmesin
        return SubResult("", "error", f"{type(exc).__name__}: {exc}")
    texts = [m.get("content") or "" for m in history if m.get("role") == "assistant" and (m.get("content") or "").strip()]
    return SubResult(texts[-1] if texts else "", out.stopped)


def _block(text: str, tag: str) -> dict | None:
    from .qa import _json_block

    return _json_block(text or "", re.compile(rf"<{tag}>\s*(.*?)\s*</{tag}>", re.S))


# ---- istemler ----------------------------------------------------------------------------------

def understand_prompt(goal: str, angle: str) -> str:
    return f"""DERİN MOD · ANLA (salt okunur; dosya değiştirme).
Kullanıcının isteği: {goal}

Bakış açın: {angle}
Projeyi bu açıdan incele (gerekirse sembol/arama araçlarını kullan) ve yanıtının SONUNA tek bir blok koy:
<bulgu>
{{"ozet": "bu açıdan en önemli 3-6 tespit (kısa)",
  "dosyalar": ["ilgili/yol.py: neden"],
  "riskler": ["dikkat edilmesi gereken"],
  "oneri": "bu açıdan nasıl ilerlenmeli"}}
</bulgu>"""


def findings_text(findings: list[dict]) -> str:
    out = []
    for f in findings:
        d = f.get("data") or {}
        out.append(f"## {f.get('angle')}\n{d.get('ozet', '')}\nDosyalar: {', '.join(d.get('dosyalar') or [])}\n"
                   f"Riskler: {', '.join(d.get('riskler') or [])}\nÖneri: {d.get('oneri', '')}")
    return "\n\n".join(out) or "(bulgu yok)"


def plan_prompt(goal: str, findings: list[dict]) -> str:
    from .project import planning_prompt

    return (planning_prompt(goal) + "\n\nÖnceki inceleme bulguları (bağımsız alt ajanlar):\n"
            + findings_text(findings))


def judge_messages(goal: str, plans: list[dict]) -> list[dict]:
    body = "\n\n".join(f"### Plan {chr(65 + i)} ({p['model']})\n{p['render']}" for i, p in enumerate(plans))
    return [{"role": "system", "content": "Yazılım planlarını değerlendiren tarafsız bir yargıçsın. Türkçe, kısa yaz."},
            {"role": "user", "content": f"İstek: {goal}\n\n{body}\n\nHangi plan isteği en doğru, eksiksiz ve en az "
                                        "riskle karşılar? Kapsam dışı iş ekleyen planı cezalandır. YALNIZ şu JSON'u yaz: "
                                        '{"secim": "A" veya "B", "neden": "kısa", "eklenecek": "diğer plandan alınacak iyi fikir (yoksa boş)"}'}]


def verify_prompt(goal: str, diff: str, lens: str) -> str:
    return f"""DERİN MOD · ÇEKİŞMELİ DOĞRULAMA (salt okunur; dosya değiştirme).
Kullanıcının isteği: {goal}
Bakış açın: {lens}

Aşağıdaki değişiklik isteği DOĞRU ve EKSİKSİZ karşılıyor mu? Sen bir denetçisin: hatayı bulmaya,
iddiayı ÇÜRÜTMEYE çalış. Gerekirse dosyaları oku. Uydurma; emin değilsen "orta" ya da "dusuk" ver.
Değişiklik (kısaltılmış):
```diff
{diff[:12000]}
```
Yanıtının SONUNA tek blok:
<denetim>
{{"sorunlar": [{{"ciddiyet": "yuksek|orta|dusuk", "dosya": "yol", "aciklama": "somut sorun ve kanıt"}}],
  "genel": "kısa değerlendirme"}}
</denetim>
Sorun yoksa "sorunlar": []."""


VERIFY_LENSES = [
    "doğruluk: mantık hataları, kenar durumlar, istenen davranış gerçekten sağlanıyor mu",
    "bütünlük ve kapsam: eksik kalan parça, bozulan mevcut davranış, istenmeyen ek değişiklik",
]


def confirmed_issues(results: list[dict]) -> list[dict]:
    """Çekişmeli karar: 'yuksek' bulgu tek denetçiden de kabul; diğerleri iki denetçi aynı dosyada
    söylerse kabul. Aynı sorun tekrarlanmaz."""
    all_issues = []
    for r in results:
        for s in (r.get("sorunlar") or []):
            if isinstance(s, dict) and s.get("aciklama"):
                all_issues.append(s)
    by_file: dict[str, int] = {}
    for s in all_issues:
        by_file[str(s.get("dosya") or "")] = by_file.get(str(s.get("dosya") or ""), 0) + 1
    out, seen = [], set()
    for s in all_issues:
        key = (str(s.get("dosya") or ""), str(s.get("aciklama"))[:60])
        if key in seen:
            continue
        sev = str(s.get("ciddiyet") or "").lower()
        if sev.startswith("yuk") or sev.startswith("yük") or (sev.startswith("orta") and by_file.get(key[0], 0) >= 2):
            out.append(s)
            seen.add(key)
    return out


def fix_prompt(goal: str, issues: list[dict]) -> str:
    items = "\n".join(f"- [{i.get('ciddiyet')}] {i.get('dosya', '')}: {i.get('aciklama')}" for i in issues)
    return (f"DERİN MOD · DÜZELT. İstek: {goal}\n\nBağımsız denetçiler şu sorunları onayladı:\n{items}\n\n"
            "Bunları düzelt; yalnız bu sorunlarla ilgili değişiklik yap (kapsam dışına çıkma). Testler varsa çalıştır. "
            "Sonunda neyi düzelttiğini ve neyin doğrulanamadığını özetle.")


def answer_prompt(goal: str, findings: list[dict]) -> str:
    return (f"DERİN MOD · YANIT. Kullanıcının sorusu: {goal}\n\nBağımsız inceleme bulguları:\n{findings_text(findings)}\n\n"
            "Bulguları kod üzerinde gerekirse doğrula ve soruyu kesin, kaynaklı (dosya:satır) yanıtla. Emin olmadığın "
            "şeyi 'doğrulanmadı' diye belirt.")


def render_report(st: DeepState) -> str:
    lines = [f"# EVREN Derin Mod raporu", "", f"- İstek: {st.goal}", f"- Tür: {st.kind}", f"- Başlangıç: {st.started_at}",
             f"- Durum: {st.status}" + (f" ({st.pause_reason})" if st.pause_reason else ""), "", "## Anla — bulgular", "",
             findings_text(st.findings), ""]
    if st.plans:
        lines += ["## Planla", ""] + [f"- Plan {chr(65 + i)} ({p['model']}): {len(p.get('tasks') or [])} görev"
                                      for i, p in enumerate(st.plans)]
        lines += [f"- Seçilen: {st.chosen} — {st.judge_note}", ""]
    if st.phase in ("dogrula", "duzelt", "bitti") and st.kind == "is":
        lines += ["## Doğrula", ""] + ([f"- [{i.get('ciddiyet')}] {i.get('dosya', '')}: {i.get('aciklama')}"
                                        for i in st.issues] or ["- Onaylanan sorun yok."]) + [""]
        lines.append(f"- Düzeltme turu: {st.fix_round}")
    lines += ["", "## Günlük", ""] + [f"- {x}" for x in st.log[-40:]]
    return "\n".join(lines) + "\n"


# ---- paralel yürütücü --------------------------------------------------------------------------

def run_parallel(jobs: list[Callable[[], Any]], gate=None, max_parallel: int = 2) -> list[Any]:
    """İşleri kotaya duyarlı paralellikle çalıştırır (pencere doluyken tek tek)."""
    limit = max(1, min(max_parallel, gate.parallel_limit() if gate is not None else max_parallel))
    results: list[Any] = [None] * len(jobs)
    sem = threading.Semaphore(limit)

    def wrap(i, fn):
        with sem:
            try:
                results[i] = fn()
            except Exception as exc:
                results[i] = exc
    with ThreadPoolExecutor(max_workers=limit) as ex:
        for i, fn in enumerate(jobs):
            ex.submit(wrap, i, fn)
    return results


def understand(st: DeepState, sub: Callable[[str, str], SubResult], gate=None, max_parallel: int = 2,
               log: Callable[[str], None] = lambda t: None) -> None:
    """ANLA: açılar paralel; her alt ajan <bulgu> verir (yoksa bir kez daha istenir — R-26)."""
    angles = ANGLES if st.kind == "is" else ANGLES[:2]

    def one(key, angle):
        res = sub(understand_prompt(st.goal, angle), "<bulgu>")
        data = _block(res.text, "bulgu") or {}
        return {"angle": key, "data": data, "raw": res.text[-1500:], "stopped": res.stopped, "error": res.error}
    results = run_parallel([lambda k=k, a=a: one(k, a) for k, a in angles], gate, max_parallel)
    st.findings = [r for r in results if isinstance(r, dict)]
    ok = sum(1 for f in st.findings if f.get("data"))
    log(f"Anla: {ok}/{len(angles)} inceleme bulgu verdi")


def plan(st: DeepState, sub_with_model: Callable[[str, str, str], SubResult], models: list[str],
         judge: Callable[[list[dict]], str], gate=None, max_parallel: int = 2,
         log: Callable[[str], None] = lambda t: None):
    """PLANLA: iki model bağımsız plan; yargıç seçer. Dönüş: seçilen görev listesi (project.Task)."""
    from . import project as pj

    prompt = plan_prompt(st.goal, st.findings)

    def one(model):
        res = sub_with_model(model, prompt, "<plan>")
        tasks = pj.parse_plan(res.text)
        return {"model": model, "tasks": tasks, "render": "\n".join(f"{t.idx}. {t.title} — ölçüt: {t.criteria}"
                                                                     for t in tasks)}
    results = [r for r in run_parallel([lambda m=m: one(m) for m in models[:2]], gate, max_parallel)
               if isinstance(r, dict) and r.get("tasks")]
    st.plans = [{"model": r["model"], "render": r["render"], "tasks": [asdict(t) for t in r["tasks"]]} for r in results]
    if not results:
        log("Planla: geçerli plan çıkmadı")
        return []
    if len(results) == 1:
        st.chosen, st.judge_note = "A", "tek geçerli plan"
        return results[0]["tasks"]
    try:
        verdict = judge(judge_messages(st.goal, results))
        m = re.search(r"\{.*\}", verdict or "", re.S)
        data = json.loads(m.group(0)) if m else {}
    except Exception:
        data = {}
    choice = 1 if str(data.get("secim", "A")).strip().upper().startswith("B") else 0
    st.chosen = "AB"[choice]
    st.judge_note = str(data.get("neden") or "")[:300] + (f" · eklenecek: {data.get('eklenecek')}" if data.get("eklenecek") else "")
    log(f"Planla: yargıç Plan {st.chosen}'yi seçti ({results[choice]['model']})")
    tasks = results[choice]["tasks"]
    extra = str(data.get("eklenecek") or "").strip()
    if extra and tasks:
        tasks[-1].criteria = (tasks[-1].criteria + f" · Ayrıca: {extra}")[:400]
    return tasks


def verify(st: DeepState, diff: str, sub: Callable[[str, str], SubResult], gate=None, max_parallel: int = 2,
           log: Callable[[str], None] = lambda t: None) -> list[dict]:
    if not diff.strip():
        log("Doğrula: değişiklik bulunamadı")
        st.issues = []
        return []
    results = run_parallel([lambda l=l: _block(sub(verify_prompt(st.goal, diff, l), "<denetim>").text, "denetim") or {}
                            for l in VERIFY_LENSES], gate, max_parallel)
    st.issues = confirmed_issues([r for r in results if isinstance(r, dict)])
    log(f"Doğrula: {len(st.issues)} onaylanmış sorun")
    return st.issues


def write_report(root: Path, st: DeepState) -> Path:
    p = Path(root) / REPORT_FILE
    p.write_text(render_report(st), encoding="utf-8")
    return p
