"""QA ajanı: web uygulamasını gerçek bir test uzmanı gibi tarayıcıda deneyen katman (Qt'siz).

Akış (kullanıcı kararı 2026-10-19: masaüstü değil, web kısmı gerçek QA gibi test edilsin):
1. PLAN — salt okunur turda proje incelenir; nasıl çalıştırılacağı ve 4–12 kullanıcı
   senaryosu (adımlar + beklenen sonuç, uç durumlar dahil) `<qa_plan>` JSON'u olarak verilir.
2. ONAY — kullanıcı senaryoları onaylar (kart). Onaysız yürütülmez.
3. YÜRÜTME — her senaryo TEMİZ bağlamla ayrı turda, Otomatik modda, DOSYAYA YAZMADAN çalışır:
   gerekirse start_service ile sunucu, Playwright ile gezinme/tıklama/yazma, konsol ve ağ
   denetimi; gerekirse visual_check (görsel model) ve qa_audit (erişilebilirlik/performans/
   güvenlik). Sonuç `<qa_sonuc>` JSON'u: gecti | kaldi | engellendi + kanıt.
4. RAPOR — `EVREN_QA_RAPORU.md` + arayüz notu + Windows bildirimi; istenirse kalan hatalar
   Proje ajanına "düzelt" hedefi olarak verilir.

Yalnız EVREN modelleriyle çalışır (ücretli sağlayıcıyla MCP/QA yok — kullanıcı kararı).
Arayüz bağlantısı: ui/qa_ui.py.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ..api.errors import ApiError, ErrorKind
from .tools import READ, ToolSpec

REPORT_FILE = "EVREN_QA_RAPORU.md"
MAX_SCENARIOS = 12
OUTAGE_WAITS = (60, 180, 300)
STATUS_LABEL = {"bekliyor": "bekliyor", "calisiyor": "çalışıyor", "gecti": "geçti", "kaldi": "KALDI",
                "engellendi": "engellendi"}
STATUS_MARK = {"bekliyor": " ", "calisiyor": "~", "gecti": "x", "kaldi": "!", "engellendi": "-"}


@dataclass
class Scenario:
    idx: int
    title: str
    steps: list[str] = field(default_factory=list)
    expected: str = ""
    status: str = "bekliyor"
    actual: str = ""
    evidence: str = ""
    summary: str = ""
    seconds: float = 0.0

    def todo(self) -> dict:
        st = {"bekliyor": "pending", "calisiyor": "in_progress"}.get(self.status, "completed")
        # Panel tamamlananı tikle gösterir: başarısızlık metnin BAŞINDA görünsün
        prefix = {"kaldi": "✗ KALDI — ", "engellendi": "– engellendi — ", "gecti": "✓ "}.get(self.status, "")
        return {"content": f"{prefix}{self.title}", "status": st}


@dataclass
class QaState:
    goal: str
    run_hint: str = ""
    scenarios: list[Scenario] = field(default_factory=list)
    status: str = "onay_bekliyor"        # onay_bekliyor | calisiyor | bitti | duraklatildi | durduruldu
    pause_reason: str = ""
    started_at: str = ""
    finished_at: str = ""
    log: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "QaState":
        d = json.loads(text)
        d["scenarios"] = [Scenario(**s) for s in d.get("scenarios", [])]
        return cls(**d)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for s in self.scenarios:
            out[s.status] = out.get(s.status, 0) + 1
        return out


# ---- istemler ---------------------------------------------------------------------------------

def planning_prompt(goal: str, feedback: str = "") -> str:
    fb = f"\n\nKullanıcının önceki plana geri bildirimi: {feedback}" if feedback else ""
    return f"""QA PLANI İSTEĞİ — bu turda hiçbir dosyayı değiştirme, yalnız incele.

Hedef: {goal or "web uygulamasının ana işlevlerini test et"}{fb}

Proje klasörünü incele (README, package.json, giriş HTML'leri, sunucu kodu). Sonra yanıtının
SONUNA tek bir <qa_plan> bloğu koy; içinde yalnız şu JSON olsun:
<qa_plan>
{{"calistirma": "uygulama nasıl açılır: ör. 'statik: index.html' veya 'start_service: npm run dev, port 5173'",
  "senaryolar": [
    {{"baslik": "kısa ad", "adimlar": ["1. adım", "2. adım"], "beklenen": "doğru davranış"}}
  ]}}
</qa_plan>
Kurallar:
- 4 ile {MAX_SCENARIOS} arasında senaryo; her ana işlev en az bir senaryo.
- Gerçek bir test uzmanı gibi UÇ DURUMLAR ekle: boş/eksik giriş, çok uzun metin, Türkçe karakter
  (ğüşıöç İ), geçersiz değer, art arda hızlı tıklama, sayfayı yenileme/geri gitme.
- Adımlar tarayıcıda yapılabilir olsun (aç, tıkla, yaz, bekle, denetle); kod değiştirme adımı yazma.
- "beklenen" ölçülebilir olsun (ör. "sayaç 2 olur", "hata mesajı görünür", "konsolda hata yok")."""


def scenario_prompt(state: QaState, sc: Scenario, done: list[Scenario], services: str = "") -> str:
    prev = "\n".join(f"- {s.idx}. {s.title}: {STATUS_LABEL[s.status]}" for s in done[-6:]) or "- (ilk senaryo)"
    steps = "\n".join(f"  {i}. {s}" for i, s in enumerate(sc.steps, 1)) or "  (adım verilmedi; başlığa göre dene)"
    return f"""QA SENARYOSU {sc.idx}/{len(state.scenarios)} — gerçek bir test uzmanı gibi dene. DOSYA DEĞİŞTİRME
(yazma araçları kapalı); hatayı düzeltme, yalnız bul ve kanıtla.

Uygulama nasıl açılır: {state.run_hint or "proje klasörüne bak"}
Şu an çalışan servisler: {services or "yok"} (çalışıyorsa YENİDEN BAŞLATMA, doğrudan adresine git)
Senaryo: {sc.title}
Adımlar:
{steps}
Beklenen: {sc.expected or "uygulama hatasız çalışır"}

Önceki senaryolar:
{prev}

Nasıl:
- Sunucu gerekiyorsa start_service ile başlat (açıksa yeniden başlatma; service_logs ile bak).
  Statik dosyalar istemdeki yerel adresten açılır.
- mcp__playwright__browser_navigate → browser_snapshot (öğelerin `ref` değeri) → tıkla/yaz →
  her önemli adımdan sonra browser_snapshot ve browser_console_messages ile sonucu DENETLE.
- Görünüm önemliyse (yerleşim, görünürlük, taşma) visual_check ile sor. İstenirse qa_audit.
- Varsayım yapma: gördüğünü yaz. Adım yapılamıyorsa nedenini yaz.
- İşlevi etkilemeyen ufak konsol iletilerini (ör. eksik favicon.ico 404) tek başına KALDI sayma;
  yalnız kanıtta not et. Senaryonun beklenen davranışına odaklan.

Yanıtının SONUNA tek bir <qa_sonuc> bloğu koy (yalnız JSON):
<qa_sonuc>
{{"sonuc": "gecti | kaldi | engellendi",
  "gerceklesen": "ne oldu (kısa, somut)",
  "kanit": "konsol hatası / ekrandaki metin / ağ isteği / servis çıktısı",
  "ozet": "tek cümle"}}
</qa_sonuc>
gecti: beklenen oldu · kaldi: uygulamada hata var · engellendi: test yapılamadı (ör. sunucu açılmadı)."""


_PLAN_RE = re.compile(r"<qa_plan>\s*(.*?)\s*</qa_plan>", re.S)
_RES_RE = re.compile(r"<qa_sonuc>\s*(.*?)\s*</qa_sonuc>", re.S)


def _json_block(text: str, rx: re.Pattern) -> dict | None:
    m = list(rx.finditer(text or ""))
    if m:
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", m[-1].group(1).strip())
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except ValueError:
            pass
        loose = _loose_fields(raw)
        if loose:
            return loose
        text = raw
    # Blok yok veya bozuk: metindeki ilk geçerli (dış) JSON nesnesi
    dec = json.JSONDecoder()
    s = text or ""
    i = s.find("{")
    while i >= 0:
        try:
            data, _end = dec.raw_decode(s, i)
            if isinstance(data, dict):
                return data
        except ValueError:
            pass
        i = s.find("{", i + 1)
    return None


_LOOSE_KEYS = ("sonuc", "gerceklesen", "kanit", "ozet")


def _loose_fields(raw: str) -> dict | None:
    """Bozuk JSON'dan (ör. değer içinde kaçışsız çift tırnak — 2026-10-19 gerçek koşu) sonuç alanları.
    Her değer, bir sonraki bilinen anahtara ya da kapanış süslüsüne kadar alınır."""
    out: dict[str, str] = {}
    keys = "|".join(_LOOSE_KEYS)
    for m in re.finditer(rf'"({keys})"\s*:\s*"(.*?)"\s*(?=,\s*"(?:{keys})"\s*:|\}}\s*$)', raw, re.S):
        out[m.group(1)] = m.group(2).replace('\\"', '"').strip()
    return out if "sonuc" in out else None


def parse_plan(text: str) -> tuple[str, list[Scenario]]:
    data = _json_block(text, _PLAN_RE) or {}
    items = data.get("senaryolar") or data.get("scenarios") or []
    out: list[Scenario] = []
    for it in items[:MAX_SCENARIOS]:
        if not isinstance(it, dict):
            continue
        title = str(it.get("baslik") or it.get("title") or "").strip()
        if not title:
            continue
        steps = it.get("adimlar") or it.get("steps") or []
        steps = [str(s).strip() for s in steps if str(s).strip()] if isinstance(steps, list) else [str(steps)]
        out.append(Scenario(len(out) + 1, title[:140], steps[:12], str(it.get("beklenen") or it.get("expected") or "")))
    return str(data.get("calistirma") or data.get("run") or "").strip(), out


MISSING_RESULT = "Senaryo sonucu <qa_sonuc> bloğuyla bildirilmedi."
RESULT_REQUEST = ("Senaryo {idx} ({title}) için yaptığın denemenin SONUCUNU şimdi yalnız <qa_sonuc> bloğuyla ver "
                  "(istenen JSON biçimi). Yeni araç çağırma; gözlemlerine dayan.")


def parse_result(text: str) -> tuple[str, str, str, str]:
    """(durum, gerçekleşen, kanıt, özet). Blok yoksa "engellendi" (rapor eksik)."""
    data = _json_block(text, _RES_RE)
    if not data:
        return "engellendi", "", "", MISSING_RESULT
    raw = str(data.get("sonuc") or data.get("result") or "").lower()
    status = ("gecti" if raw.startswith(("gec", "geç", "pass")) else
              "kaldi" if raw.startswith(("kal", "fail")) else "engellendi")
    return (status, str(data.get("gerceklesen") or "")[:800], str(data.get("kanit") or "")[:1200],
            str(data.get("ozet") or "")[:300])


def render_plan(state: QaState) -> str:
    lines = [f"QA planı — {state.goal}", f"Çalıştırma: {state.run_hint or '-'}", ""]
    for s in state.scenarios:
        lines.append(f"{s.idx}. {s.title} — beklenen: {s.expected}")
    return "\n".join(lines)


def render_report(state: QaState) -> str:
    c = state.counts()
    rows = "\n".join(f"| {s.idx} | {s.title} | {STATUS_LABEL[s.status]} | {s.summary or s.actual[:80]} |"
                     for s in state.scenarios)
    out = [f"# EVREN QA Raporu", "",
           f"- Hedef: {state.goal}", f"- Çalıştırma: {state.run_hint or '-'}",
           f"- Başlangıç / bitiş: {state.started_at} / {state.finished_at or '-'}",
           f"- Sonuç: {c.get('gecti', 0)} geçti · {c.get('kaldi', 0)} kaldı · {c.get('engellendi', 0)} engellendi"
           f" · {c.get('bekliyor', 0)} bekliyor", "",
           "| # | Senaryo | Durum | Özet |", "|---|---|---|---|", rows, ""]
    for s in state.scenarios:
        out += [f"## {s.idx}. {s.title} — {STATUS_LABEL[s.status]}", ""]
        if s.steps:
            out += ["Adımlar:"] + [f"{i}. {x}" for i, x in enumerate(s.steps, 1)] + [""]
        out += [f"- Beklenen: {s.expected or '-'}", f"- Gerçekleşen: {s.actual or '-'}"]
        if s.evidence:
            out.append(f"- Kanıt: {s.evidence}")
        if s.seconds:
            out.append(f"- Süre: {round(s.seconds)} sn")
        out.append("")
    fails = [s for s in state.scenarios if s.status == "kaldi"]
    if fails:
        out += ["## Düzeltilecekler", ""] + [f"- [{s.idx}] {s.title}: {s.actual or s.summary}" for s in fails] + [""]
    out.append("_EVREN Studio QA ajanı tarafından üretildi; kanıtlar modelin tarayıcıda gözlemidir._")
    return "\n".join(out)


def fix_goal(state: QaState) -> str:
    """Kalan hatalar için Proje ajanı hedefi."""
    fails = [s for s in state.scenarios if s.status == "kaldi"]
    items = "\n".join(f"- {s.title}: beklenen '{s.expected}', gerçekleşen '{s.actual}'. Kanıt: {s.evidence[:300]}"
                      for s in fails)
    return ("QA testinde bulunan hataları düzelt (rapor: EVREN_QA_RAPORU.md). Her düzeltmeden sonra davranışı "
            f"tarayıcıda doğrula:\n{items}")


# ---- QA araçları (görsel göz, denetimler) --------------------------------------------------------

VISUAL_SPEC = ToolSpec(
    "visual_check", READ,
    "Tarayıcıdaki sayfanın ekran görüntüsünü alır ve görsel okuyabilen bir modele SORAR (ör. 'Kaydet "
    "düğmesi görünüyor mu?', 'metin taşıyor mu?', 'düzen bozuk mu?'). Metin özetinin (browser_snapshot) "
    "göremeyeceği görünüm sorunları için; her çağrı ek kota harcar, gerektiğinde kullan.",
    {"type": "object", "properties": {"question": {"type": "string", "description": "Ekrana dair somut soru"},
                                      "full_page": {"type": "boolean", "description": "Tüm sayfa (varsayılan görünen alan)"}},
     "required": ["question"]})
AUDIT_SPEC = ToolSpec(
    "qa_audit", READ,
    "Ek kalite denetimi: kind='erisilebilirlik' (açık sayfada axe-core: eksik etiket, kontrast, alt metin), "
    "'performans' (açık sayfanın yükleme süresi, en büyük dosyalar), 'guvenlik' (projede unutulmuş "
    "anahtar/parola taraması ve npm bağımlılık açıkları).",
    {"type": "object", "properties": {"kind": {"type": "string", "enum": ["erisilebilirlik", "performans", "guvenlik"]}},
     "required": ["kind"]})

_PERF_JS = """() => {
  const n = performance.getEntriesByType('navigation')[0];
  const res = performance.getEntriesByType('resource');
  const size = r => (r.transferSize || r.encodedBodySize || 0);
  const big = res.map(r => ({url: r.name, kb: Math.round(size(r) / 1024), ms: Math.round(r.duration)}))
                 .sort((a, b) => b.kb - a.kb).slice(0, 5);
  return {yukleme_ms: n ? Math.round(n.loadEventEnd - n.startTime) : null,
          dom_hazir_ms: n ? Math.round(n.domContentLoadedEventEnd - n.startTime) : null,
          kaynak_sayisi: res.length, toplam_kb: Math.round(res.reduce((a, r) => a + size(r), 0) / 1024),
          en_buyukler: big};
}"""
_SECRET_PATTERNS = [
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "özel anahtar"),
    (r"AKIA[0-9A-Z]{16}", "AWS erişim anahtarı"),
    (r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}", "OpenAI/Anthropic anahtarı"),
    (r"\bghp_[A-Za-z0-9]{30,}", "GitHub belirteci"),
    (r"(?i)\b(?:password|parola|sifre|şifre|api[_-]?key|secret)\s*[:=]\s*['\"][^'\"\s]{6,}['\"]", "gömülü parola/anahtar"),
]
_SCAN_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".env", ".yml", ".yaml", ".toml", ".ini", ".cfg",
             ".php", ".rb", ".go", ".cs", ".java", ".html", ".vue", ".svelte"}


class QaTools:
    """AgentRunner.extra_tools: visual_check + qa_audit. Playwright'ın AÇIK sayfasını kullanır
    (aynı MCP süreci). vision(question, image_path) → yanıt metni (arayüz: EVREN görsel modeli)."""

    def __init__(self, manager, pw_config, project_root: Path, vision: Callable[[str, str], str] | None,
                 shots_dir: Path, axe_path: Path | None = None, run_command: Callable[[str], tuple[int | None, str]] | None = None):
        self.manager = manager
        self.cfg = pw_config
        self.root = Path(project_root)
        self.vision = vision
        self.shots = Path(shots_dir)
        self.axe_path = axe_path
        self.run_command = run_command
        self.shots_taken: list[str] = []

    def specs(self, read_only_only: bool = False) -> list[ToolSpec]:
        out = [AUDIT_SPEC]
        if self.vision is not None:
            out.insert(0, VISUAL_SPEC)
        return out

    def run(self, call):
        from .mcp import McpError, result_text
        from .runner import ToolResult

        a = call.arguments or {}
        try:
            if call.name == "visual_check":
                q = str(a.get("question") or "").strip() or "Sayfada görünür bir sorun var mı?"
                self.shots.mkdir(parents=True, exist_ok=True)
                path = self.shots / f"goz-{datetime.now().strftime('%H%M%S')}-{len(self.shots_taken) + 1}.png"
                args = {"filename": str(path), "type": "png"}
                if a.get("full_page"):
                    args["fullPage"] = True
                self.manager.call(self.cfg, self.root, "browser_take_screenshot", args)
                if not path.exists():
                    return ToolResult(False, "Ekran görüntüsü alınamadı (açık sayfa yok mu? önce browser_navigate).",
                                      "Görsel göz: görüntü yok")
                self.shots_taken.append(str(path))
                answer = self.vision(q, str(path)) if self.vision else ""
                return ToolResult(True, f"Görsel model yanıtı (ekran görüntüsü: {path.name}):\n{answer}",
                                  f"Görsel göz: {q[:60]}", {"screenshot": str(path)})
            kind = str(a.get("kind") or "")
            if kind == "performans":
                res = self.manager.call(self.cfg, self.root, "browser_evaluate", {"function": _PERF_JS})
                return ToolResult(True, "Performans (açık sayfa):\n" + result_text(res)[0][:3000], "Denetim: performans")
            if kind == "erisilebilirlik":
                if self.axe_path is None or not self.axe_path.exists():
                    return ToolResult(False, "axe-core kurulu değil (Ayarlar > MCP > Playwright'ı yeniden kurun).",
                                      "Denetim: axe yok")
                src = self.axe_path.read_text(encoding="utf-8")
                fn = ("async () => { if (!window.axe) { const s = document.createElement('script'); s.textContent = "
                      + json.dumps(src) + "; document.head.appendChild(s); } "
                      "const r = await window.axe.run(document, {resultTypes: ['violations']}); "
                      "return r.violations.map(v => ({kural: v.id, etki: v.impact, aciklama: v.help, "
                      "oge_sayisi: v.nodes.length, ornek: v.nodes.slice(0, 2).map(n => n.target.join(' '))})); }")
                res = self.manager.call(self.cfg, self.root, "browser_evaluate", {"function": fn})
                text = result_text(res)[0]
                return ToolResult(True, "Erişilebilirlik (axe-core, açık sayfa) ihlalleri:\n" + text[:5000],
                                  "Denetim: erişilebilirlik")
            if kind == "guvenlik":
                return ToolResult(True, self._security(), "Denetim: güvenlik")
            return ToolResult(False, "kind: erisilebilirlik | performans | guvenlik", "Geçersiz denetim")
        except McpError as exc:
            return ToolResult(False, f"Denetim yapılamadı: {exc}", "Denetim hatası")

    def _security(self) -> str:
        from .tools import IGNORED_DIRS

        hits: list[str] = []
        scanned = 0
        for p in self.root.rglob("*"):
            if any(part in IGNORED_DIRS for part in p.relative_to(self.root).parts) or not p.is_file():
                continue
            if p.suffix.lower() not in _SCAN_EXT and not p.name.startswith(".env"):
                continue
            scanned += 1
            if scanned > 3000:
                break
            try:
                text = p.read_text(encoding="utf-8", errors="replace")[:400_000]
            except OSError:
                continue
            for rx, label in _SECRET_PATTERNS:
                for m in re.finditer(rx, text):
                    line = text.count("\n", 0, m.start()) + 1
                    hits.append(f"{p.relative_to(self.root).as_posix()}:{line}: {label} (değer gizlendi)")
                    break
        out = [f"Gizli bilgi taraması: {scanned} dosya, {len(hits)} bulgu."] + [f"- {h}" for h in hits[:20]]
        if (self.root / "package-lock.json").exists() and self.run_command is not None:
            code, text = self.run_command("npm audit --json")
            try:
                v = (json.loads(text[text.find("{"):]).get("metadata") or {}).get("vulnerabilities") or {}
                found = ", ".join(f"{k}={n}" for k, n in v.items() if n)
                out.append("npm bağımlılık açıkları: " + (found or "yok"))
            except (ValueError, AttributeError):
                out.append(f"npm audit okunamadı (çıkış {code}).")
        return "\n".join(out)


# ---- yürütücü ----------------------------------------------------------------------------------

@dataclass
class QaHooks:
    run_scenario: Callable[[Scenario, str], tuple[str, str | None, ApiError | None]]  # → (yanıt, durma, hata)
    save: Callable[[QaState], None]
    status: Callable[[str], None] = lambda t: None
    changed: Callable[[QaState], None] = lambda s: None
    quota_wait: Callable[[], tuple[float, str]] = lambda: (0.0, "")
    cancelled: Callable[[], bool] = lambda: False
    sleep: Callable[[float], None] = time.sleep
    services: Callable[[], str] = lambda: ""          # çalışan servisler (ad · port), istemde gösterilir
    # Sonuç bloğu yoksa aynı senaryo bağlamında "yalnız sonucu ver" turu (→ yanıt metni)
    ask_result: Callable[[Scenario, str], str] | None = None


class QaRunner:
    def __init__(self, state: QaState, hooks: QaHooks):
        self.state = state
        self.hooks = hooks

    def _log(self, text: str) -> None:
        self.state.log.append(f"{datetime.now().strftime('%H:%M:%S')} {text}")
        self.hooks.status(text)

    def _save(self) -> None:
        self.hooks.save(self.state)
        self.hooks.changed(self.state)

    def _wait(self, seconds: float, reason: str) -> bool:
        self._log(f"Bekleniyor ({int(seconds)} sn): {reason}")
        left = seconds
        while left > 0:
            if self.hooks.cancelled():
                return False
            step = min(5.0, left)
            self.hooks.sleep(step)
            left -= step
        return True

    def run(self) -> QaState:
        st = self.state
        st.status = "calisiyor"
        st.started_at = st.started_at or datetime.now().strftime("%Y-%m-%d %H:%M")
        self._save()
        for sc in st.scenarios:
            if sc.status in ("gecti", "kaldi", "engellendi"):
                continue
            if self.hooks.cancelled():
                return self._pause("kullanıcı durdurdu")
            wait, why = self.hooks.quota_wait()
            if wait < 0:
                return self._pause(why)
            if wait > 0 and not self._wait(wait, why):
                return self._pause("kullanıcı durdurdu")
            sc.status = "calisiyor"
            self._save()
            done = [s for s in st.scenarios if s.status in ("gecti", "kaldi", "engellendi")]
            prompt = scenario_prompt(st, sc, done, self.hooks.services())
            t0 = time.monotonic()
            for attempt, outage in enumerate((0,) + OUTAGE_WAITS):
                text, stopped, err = self.hooks.run_scenario(sc, prompt)
                if err is not None and err.kind in (ErrorKind.SERVER_UNAVAILABLE, ErrorKind.SERVER_ERROR,
                                                    ErrorKind.NETWORK, ErrorKind.TIMEOUT) \
                        and attempt < len(OUTAGE_WAITS):
                    if not self._wait(OUTAGE_WAITS[attempt], f"EVREN yanıt vermiyor ({err.kind.value})"):
                        return self._pause("kullanıcı durdurdu")
                    continue
                break
            sc.seconds = time.monotonic() - t0
            if stopped == "cancelled" or self.hooks.cancelled():
                sc.status = "bekliyor"
                return self._pause("kullanıcı durdurdu")
            if err is not None and err.kind in (ErrorKind.RATE_LIMIT, ErrorKind.QUOTA_EXHAUSTED):
                sc.status = "bekliyor"
                return self._pause(f"kota: {err.message[:120]}")
            sc.status, sc.actual, sc.evidence, sc.summary = parse_result(text)
            if sc.summary == MISSING_RESULT and err is None and self.hooks.ask_result is not None                     and not self.hooks.cancelled():
                self._log(f"Senaryo {sc.idx}: sonuç bloğu yok, yalnız sonuç isteniyor")
                again = self.hooks.ask_result(sc, RESULT_REQUEST.format(idx=sc.idx, title=sc.title))
                sc.status, sc.actual, sc.evidence, sc.summary = parse_result(again)
            if err is not None:
                sc.status, sc.summary = "engellendi", f"tur hatası: {err.message[:160]}"
            self._log(f"Senaryo {sc.idx}: {STATUS_LABEL[sc.status]} — {sc.summary or sc.title}")
            self._save()
        st.status = "bitti"
        st.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._save()
        return st

    def _pause(self, reason: str) -> QaState:
        self.state.status = "duraklatildi"
        self.state.pause_reason = reason
        self._log(f"QA duraklatıldı: {reason}")
        self._save()
        return self.state


def write_report(root: Path, state: QaState) -> Path:
    path = Path(root) / REPORT_FILE
    path.write_text(render_report(state), encoding="utf-8")
    return path
