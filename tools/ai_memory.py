"""Ortak geliştirici hafızası aracı (docs/ai-memory/).

Bu depoda çalışan her yapay zekâ motoru (Claude, Kilo, Cursor, Copilot,
Codex, Gemini, EVREN Studio ajanı …) bu aracı kullanır. Yalnızca standart
kütüphane gerekir.

Komutlar:
  baslangic                 Oturum başında okunacak her şeyi yazdırır
  ara KELIME...             Kayıt, oturum ve kurallarda arar
  kayit --baslik ... --motor ... --model ... [--tur --onem --alan]
                            Yeni hata/eksik kaydı şablonu oluşturur
  oturum --baslik ... --motor ... --model ... [--sonuc]
                            Yeni oturum günlüğü şablonu oluşturur
  indeks                    INDEX.md ve AGENTS.md kural özetini üretir
  denetle                   Biçim, bağlantı ve güncellik denetimi (hata → çıkış 1)
  kanca-kur                 Git ön-commit kancasını bu depo için etkinleştirir
  kanca                     (ön-commit kancası tarafından çağrılır)
  gozlem listele|goster|kayda-donustur|kapat|ekle|gonder
                            Uygulamanın gözlem ajanından gelen kayıtlar (gozlem-kayitlari dalı)

Örnek:
  .\\.venv\\Scripts\\python.exe tools\\ai_memory.py baslangic
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEM = ROOT / "docs" / "ai-memory"
INCIDENTS = MEM / "incidents"
SESSIONS = MEM / "sessions"
RULES = MEM / "RULES.md"
INDEX = MEM / "INDEX.md"
ENGINES = MEM / "ENGINES.md"
AGENTS = ROOT / "AGENTS.md"
PROJECT_STATE = ROOT / "docs" / "PROJECT_STATE.md"
DEVIR = ROOT / "docs" / "DEVIR_NOTU.md"
DEVIR_REL = "docs/DEVIR_NOTU.md"
DEVIR_SECTIONS = ("Şu an", "Geliştirme sırası", "Birleştirmeden önce")

TUR = ("hata", "eksik", "risk", "yanlis-iddia", "surec", "ortam")
ONEM = ("kritik", "yuksek", "orta", "dusuk")
DURUM = ("acik", "izleniyor", "cozuldu", "kabul-edildi")
SONUC = ("tamamlandi", "kismi", "basarisiz", "devam-ediyor")

INCIDENT_FIELDS = ("id", "tarih", "tur", "onem", "durum", "alan",
                   "kaynak_motor", "kaynak_model", "ortam")
INCIDENT_SECTIONS = ("Belirti", "Kök neden", "Çözüm", "Kanıt", "Önleme")
SESSION_FIELDS = ("id", "tarih", "motor", "model", "ortam", "sonuc")
SESSION_SECTIONS = ("Görev", "Yapılanlar", "Test", "Sorunlar", "Sonraki motor için notlar")

ENTRY_FILES = (
    "CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md",
    ".cursor/rules/ai-memory.mdc", ".kilocode/rules/ai-memory.md",
    ".roo/rules/ai-memory.md", ".clinerules/ai-memory.md",
    ".windsurf/rules/ai-memory.md",
)
BLOCK_START = "<!-- KURALLAR:BASLA -->"
BLOCK_END = "<!-- KURALLAR:BITIR -->"
ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$")
RULE_HEAD_RE = re.compile(r"^### (R-\d{2,3}) · (.+)$")
_TR = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")


# ---- yardımcılar -----------------------------------------------------------


def _out(text: str = "") -> None:
    sys.stdout.write(text + "\n")


def slugify(text: str, limit: int = 60) -> str:
    s = text.translate(_TR).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:limit].rstrip("-") or "kayit"


def read_text(path: Path) -> str:
    # Satır sonları normalize edilir: git core.autocrlf=true makinelerde
    # dosyalar CRLF ile çıkarılır; karşılaştırmalar bundan etkilenmemeli.
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))   # BOM'suz UTF-8, LF


def parse_doc(path: Path) -> tuple[dict[str, str], str]:
    """'---' arasındaki 'anahtar: değer' satırlarını ve gövdeyi döndürür."""
    text = read_text(path).replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition(":")
            value = value.split(" #", 1)[0].strip()
            meta[key.strip()] = value
    return meta, text[end + 5:]


def as_list(value: str) -> list[str]:
    value = (value or "").strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [v.strip() for v in value.split(",") if v.strip()]


def title_of(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "(başlıksız)"


def sections(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if current is not None:
                out[current] = "\n".join(buf).strip()
            current = line[3:].strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf).strip()
    return out


def _meaningful(text: str) -> bool:
    stripped = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()
    return bool(stripped)


def _section(secs: dict[str, str], name: str) -> str | None:
    for key, value in secs.items():
        if key == name or key.startswith(name):
            return value
    return None


def load(folder: Path) -> list[dict]:
    items = []
    if not folder.is_dir():
        return items
    for path in sorted(folder.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        meta, body = parse_doc(path)
        items.append({"path": path, "meta": meta, "body": body,
                      "title": title_of(body), "sections": sections(body)})
    return items


def parse_rules() -> list[dict]:
    if not RULES.exists():
        return []
    rules = []
    current = None
    for line in read_text(RULES).replace("\r\n", "\n").splitlines():
        m = RULE_HEAD_RE.match(line)
        if m:
            current = {"id": m.group(1), "title": m.group(2).strip(),
                       "kural": "", "neden": "", "kaynak": []}
            rules.append(current)
            continue
        if current is None:
            continue
        s = line.strip()
        for key, label in (("kural", "- **Kural:**"), ("neden", "- **Neden:**")):
            if s.startswith(label):
                current[key] = s[len(label):].strip()
        if s.startswith("- **Kaynak:**"):
            current["kaynak"] = as_list(s[len("- **Kaynak:**"):].replace("`", ""))
    return rules


def environment_string() -> str:
    return f"{platform.system()} {platform.release()}, Python {platform.python_version()}"


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, encoding="utf-8").stdout.strip()
    except OSError:
        return ""


def _git_run(root: Path, *args: str, timeout: float = 30.0) -> tuple[int, str]:
    """(çıkış kodu, çıktı). git yoksa / zaman aşımında (-1, hata)."""
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        return r.returncode, (r.stdout or r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, type(exc).__name__


def sync_with_remote(root: Path | None = None, auto: bool = True) -> list[str]:
    """Yerel kopyayı GitHub'la karşılaştırır; güvenliyse kendiliğinden eşitler.

    Kullanıcı başka bir bilgisayarda çalışıp GitHub'a göndermiş olabilir; motor
    bunu bilmeden eski kodu/hafızayı okumasın diye `baslangic` en başta bunu
    çalıştırır. Hiçbir zaman veri kaybettirmez:
    - Yalnızca İLERİ SARMA (--ff-only) yapılır; yerelde commit'lenmemiş
      değişiklik veya gönderilmemiş commit varsa dokunulmaz, uyarı verilir.
    - Bulunulan dal master'a tamamen birleştirilmişse (dalda master'da olmayan
      hiçbir commit yoksa) ve çalışma ağacı temizse master'a geçilir.
    Dönüş: ekrana yazılacak satırlar ("✓" yapıldı, "!" dikkat).
    """
    root = root or ROOT
    out: list[str] = []
    code, _ = _git_run(root, "rev-parse", "--is-inside-work-tree")
    if code != 0:
        return out
    code, remotes = _git_run(root, "remote")
    if code != 0 or "origin" not in remotes.split():
        return ["! Uzak depo (origin) tanımlı değil; başka bilgisayardaki işler görülemez."]
    code, msg = _git_run(root, "fetch", "--quiet", "--prune", "origin", timeout=45.0)
    if code != 0:
        return ["! GitHub'a ulaşılamadı (" + (msg.splitlines()[-1] if msg else "bilinmeyen hata")
                + "). Yerel kopya güncel OLMAYABİLİR; başka bilgisayarda yapılan işler görünmez."]

    def count(rng: str) -> int:
        c, o = _git_run(root, "rev-list", "--count", rng)
        return int(o) if c == 0 and o.isdigit() else 0

    _, branch = _git_run(root, "rev-parse", "--abbrev-ref", "HEAD")
    c, default = _git_run(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    default = default if c == 0 and default else "origin/master"
    default_local = default.split("/", 1)[1]
    _, status = _git_run(root, "status", "--porcelain", "--untracked-files=no")
    dirty = bool(status.strip())

    # 1) birleştirilmiş özellik dalında kalınmış → master'a geç
    if branch not in (default_local, "HEAD") and count(f"{default}..HEAD") == 0 \
            and count(f"HEAD..{default}") > 0:
        if auto and not dirty:
            c, msg = _git_run(root, "checkout", default_local)
            if c == 0:
                out.append(f"✓ '{branch}' dalı zaten master'a birleştirilmişti; '{default_local}' dalına geçildi.")
                branch = default_local
            else:
                out.append(f"! '{branch}' master'a birleştirilmiş ama '{default_local}' dalına geçilemedi: {msg[:200]}")
        else:
            out.append(f"! '{branch}' dalı master'a birleştirilmiş; yeni iş için önce: "
                       f"git checkout {default_local} ; git pull --ff-only"
                       + ("  (commit'lenmemiş değişiklik var: önce onları ele al)" if dirty else ""))

    # 2) bulunulan dalı kendi uzak dalıyla karşılaştır
    c, upstream = _git_run(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if c != 0:
        c2, _ = _git_run(root, "config", "--get", f"branch.{branch}.remote")
        if c2 == 0:
            out.append(f"! '{branch}' dalının GitHub'daki karşılığı silinmiş (büyük olasılıkla birleştirildi). "
                       f"Kontrol: git log --oneline {default} -5")
        elif branch != "HEAD":
            out.append(f"! '{branch}' dalı GitHub'a hiç gönderilmemiş (yalnızca bu bilgisayarda).")
    else:
        behind, ahead = count(f"HEAD..{upstream}"), count(f"{upstream}..HEAD")
        if behind and not ahead and not dirty and auto:
            c, msg = _git_run(root, "merge", "--ff-only", "--quiet", upstream)
            if c == 0:
                out.append(f"✓ GitHub'daki {behind} yeni commit otomatik alındı ({upstream}). "
                           "Başka bilgisayarda yapılan işler için aşağıdaki son oturumlara bak.")
            else:
                out.append(f"! {behind} yeni commit alınamadı: {msg[:200]}")
        elif behind:
            why = []
            if dirty:
                why.append("commit'lenmemiş yerel değişiklik var")
            if ahead:
                why.append(f"yerelde gönderilmemiş {ahead} commit var (dallar ayrışmış)")
            out.append(f"! Yerel kopya GitHub'ın {behind} commit GERİSİNDE ve otomatik alınmadı: "
                       + ", ".join(why or ["otomatik eşitleme kapalı"])
                       + ". Kullanıcıya sor; veri kaybettirecek komut (reset/checkout --) çalıştırma.")
        elif ahead:
            out.append(f"! Yerelde GitHub'a gönderilmemiş {ahead} commit var ('{branch}'). "
                       "Başka bilgisayarda devam edilecekse gönderilmesi gerekir (kullanıcı onayıyla).")
    if branch != default_local:
        newer = count(f"HEAD..{default}")
        if newer:
            out.append(f"! master'da ({default}) bu dalda olmayan {newer} commit var: başka bir bilgisayarda "
                       "birleştirilmiş iş olabilir. Gerekirse kullanıcıya master'ı bu dala almayı öner.")
    if dirty:
        out.append("! Commit'lenmemiş yerel değişiklikler var (git status). Başka motorun yarım işi olabilir; "
                   "üzerine yazmadan önce incele.")
    if not out:
        out.append(f"✓ Yerel kopya GitHub ile eşit ('{branch}').")
    return out


def active_work_branch(root: Path | None = None) -> tuple[str, str, str] | None:
    """GitHub'da master'a birleştirilmemiş, bulunulan daldan DAHA YENİ bir çalışma dalı var mı?

    Kullanıcı başka bilgisayarda bir özellik dalında çalışıp göndermiş olabilir; bu bilgisayar master'da (ya da
    eski bir dalda) kalmışsa motor devir notunun eski hâlini okur ve işi baştan yapar. Dönüş:
    (dal adı, son commit özeti, o dalın DEVIR_NOTU "Şu an" bölümü) ya da None. Yalnız okur (fetch
    `sync_with_remote`'ta yapılır); hiçbir dalı değiştirmez.
    """
    root = root or ROOT
    c, default = _git_run(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    default = default if c == 0 and default else "origin/master"
    c, refs = _git_run(root, "for-each-ref", "--sort=-committerdate", "--format=%(refname:short)|%(committerdate:unix)",
                       "refs/remotes/origin")
    if c != 0:
        return None
    _, head_time = _git_run(root, "log", "-1", "--format=%ct", "HEAD")
    _, branch = _git_run(root, "rev-parse", "--abbrev-ref", "HEAD")
    for line in refs.splitlines():
        name, _, ts = line.partition("|")
        if name in (default, "origin/HEAD", "origin") or name == f"origin/{branch}":
            if name == f"origin/{branch}":
                return None                  # en yeni çalışma zaten bulunulan dal
            continue
        c, n = _git_run(root, "rev-list", "--count", f"{default}..{name}")
        if c != 0 or not n.isdigit() or int(n) == 0:
            continue                         # birleştirilmiş dal
        c, extra = _git_run(root, "rev-list", "--count", f"HEAD..{name}")
        if c != 0 or not extra.isdigit() or int(extra) == 0:
            continue                         # bu kopyada zaten var
        # aynı saniyedeki commit'ler "eski" sayılmaz (yalnız kesin daha eskiyse dur; test kararsızlığı 2026-11-01)
        if head_time.isdigit() and ts.isdigit() and int(ts) < int(head_time):
            return None
        _, subject = _git_run(root, "log", "-1", "--format=%cd · %s", "--date=format:%Y-%m-%d %H:%M", name)
        c, note = _git_run(root, "show", f"{name}:{DEVIR_REL}")
        now = (_section(sections(note), "Şu an") or "") if c == 0 else ""
        return name.split("/", 1)[1], subject, now.strip()
    return None


# ---- üretilen içerik ----------------------------------------------------------


def render_rules_block(rules: list[dict]) -> str:
    lines = [f"- **{r['id']}** · {r['title']} — {r['kural']}" for r in rules]
    return BLOCK_START + "\n" + "\n".join(lines) + "\n" + BLOCK_END


def render_index(incidents: list[dict], sessions_: list[dict], rules: list[dict]) -> str:
    def link(item: dict, folder: str) -> str:
        return f"[{item['path'].stem}]({folder}/{item['path'].name})"

    open_items = [i for i in incidents if i["meta"].get("durum") in ("acik", "izleniyor")]
    order = {k: n for n, k in enumerate(ONEM)}
    open_items.sort(key=lambda i: (order.get(i["meta"].get("onem"), 9), i["path"].stem))
    lines = [
        "# Ortak Hafıza İndeksi",
        "",
        "> Bu dosya `tools/ai_memory.py indeks` ile üretilir; elle düzenleme.",
        "",
        f"Kayıt: {len(incidents)} · Açık/izlenen: {len(open_items)} · "
        f"Oturum: {len(sessions_)} · Kural: {len(rules)}",
        "",
        "## Açık ve izlenen kayıtlar",
        "",
    ]
    if open_items:
        lines += ["| Önem | Kayıt | Tür | Alan | Başlık |", "|---|---|---|---|---|"]
        for i in open_items:
            m = i["meta"]
            lines.append(f"| {m.get('onem')} | {link(i, 'incidents')} | {m.get('tur')} | "
                         f"{m.get('alan')} | {i['title']} |")
    else:
        lines.append("Açık kayıt yok.")
    lines += ["", "## Tüm kayıtlar (yeniden eskiye)", "",
              "| Tarih | Kayıt | Tür | Önem | Durum | Kaynak motor | Başlık |",
              "|---|---|---|---|---|---|---|"]
    for i in sorted(incidents, key=lambda x: x["path"].stem, reverse=True):
        m = i["meta"]
        lines.append(f"| {m.get('tarih')} | {link(i, 'incidents')} | {m.get('tur')} | "
                     f"{m.get('onem')} | {m.get('durum')} | {m.get('kaynak_motor')} | {i['title']} |")
    lines += ["", "## Oturum günlükleri (yeniden eskiye)", "",
              "| Tarih | Oturum | Motor / model | Sonuç | Başlık |", "|---|---|---|---|---|"]
    for s in sorted(sessions_, key=lambda x: x["path"].stem, reverse=True):
        m = s["meta"]
        lines.append(f"| {m.get('tarih')} | {link(s, 'sessions')} | {m.get('motor')} / "
                     f"{m.get('model')} | {m.get('sonuc')} | {s['title']} |")
    lines += ["", "## Kurallar", ""]
    for r in rules:
        lines.append(f"- **{r['id']}** · {r['title']}")
    return "\n".join(lines) + "\n"


def agents_with_block(rules: list[dict]) -> str | None:
    if not AGENTS.exists():
        return None
    text = read_text(AGENTS)
    pattern = re.compile(re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END), re.S)
    if not pattern.search(text):
        return None
    return pattern.sub(lambda _m: render_rules_block(rules), text)


# ---- denetim ------------------------------------------------------------------


def check() -> list[str]:
    errors: list[str] = []
    incidents = load(INCIDENTS)
    sessions_ = load(SESSIONS)
    rules = parse_rules()
    ids = set()

    for i in incidents:
        name = i["path"].name
        m = i["meta"]
        for f in INCIDENT_FIELDS:
            if not m.get(f):
                errors.append(f"incidents/{name}: '{f}' alanı eksik veya boş")
        if m.get("id") and m["id"] != i["path"].stem:
            errors.append(f"incidents/{name}: id ({m['id']}) dosya adıyla aynı olmalı")
        if not ID_RE.match(i["path"].stem):
            errors.append(f"incidents/{name}: dosya adı YYYY-MM-DD-kisa-baslik.md olmalı")
        for key, allowed in (("tur", TUR), ("onem", ONEM), ("durum", DURUM)):
            if m.get(key) and m[key] not in allowed:
                errors.append(f"incidents/{name}: {key}='{m[key]}' geçersiz ({', '.join(allowed)})")
        for sec in INCIDENT_SECTIONS:
            body = _section(i["sections"], sec)
            if body is None:
                errors.append(f"incidents/{name}: '## {sec}' bölümü yok")
            elif sec in ("Belirti", "Kök neden") and not _meaningful(body):
                errors.append(f"incidents/{name}: '## {sec}' bölümü doldurulmamış")
        if m.get("durum") == "cozuldu":
            sol = _section(i["sections"], "Çözüm") or ""
            if not _meaningful(sol):
                errors.append(f"incidents/{name}: durum 'cozuldu' ama Çözüm bölümü boş")
        ids.add(i["path"].stem)

    for s in sessions_:
        name = s["path"].name
        m = s["meta"]
        for f in SESSION_FIELDS:
            if not m.get(f):
                errors.append(f"sessions/{name}: '{f}' alanı eksik veya boş")
        if m.get("id") and m["id"] != s["path"].stem:
            errors.append(f"sessions/{name}: id dosya adıyla aynı olmalı")
        if not ID_RE.match(s["path"].stem):
            errors.append(f"sessions/{name}: dosya adı YYYY-MM-DD-kisa-baslik.md olmalı")
        if m.get("sonuc") and m["sonuc"] not in SONUC:
            errors.append(f"sessions/{name}: sonuc='{m['sonuc']}' geçersiz ({', '.join(SONUC)})")
        for sec in SESSION_SECTIONS:
            body = _section(s["sections"], sec)
            if body is None:
                errors.append(f"sessions/{name}: '## {sec}' bölümü yok")
            elif sec in ("Görev", "Yapılanlar") and not _meaningful(body):
                errors.append(f"sessions/{name}: '## {sec}' bölümü doldurulmamış")

    seen = set()
    for r in rules:
        if r["id"] in seen:
            errors.append(f"RULES.md: {r['id']} birden fazla kez tanımlı")
        seen.add(r["id"])
        if not r["kural"]:
            errors.append(f"RULES.md: {r['id']} için '- **Kural:**' satırı yok")
        for ref in r["kaynak"]:
            if ref not in ids and ref != "AGENTS.md":
                errors.append(f"RULES.md: {r['id']} olmayan kayda bağlı: {ref}")
    rule_ids = {r["id"] for r in rules}
    for i in incidents:
        for ref in as_list(i["meta"].get("kurallar", "")):
            if ref not in rule_ids:
                errors.append(f"incidents/{i['path'].name}: olmayan kurala bağlı: {ref}")

    if not INDEX.exists() or read_text(INDEX) != render_index(incidents, sessions_, rules):
        errors.append("INDEX.md güncel değil → `python tools/ai_memory.py indeks` çalıştırın")
    new_agents = agents_with_block(rules)
    if new_agents is None:
        errors.append("AGENTS.md yok veya kural bloğu işaretleri eksik")
    elif new_agents != read_text(AGENTS):
        errors.append("AGENTS.md kural özeti güncel değil → `python tools/ai_memory.py indeks`")

    if not DEVIR.exists():
        errors.append(f"{DEVIR_REL} yok (devir notu: işin şu anki yeri, R-35)")
    else:
        dsecs = sections(read_text(DEVIR))
        for sec in DEVIR_SECTIONS:
            body = _section(dsecs, sec)
            if body is None or not _meaningful(body):
                errors.append(f"{DEVIR_REL}: '## {sec}' bölümü yok veya boş")

    for rel in ENTRY_FILES:
        p = ROOT / rel
        if not p.exists():
            errors.append(f"{rel}: motor giriş dosyası yok")
        elif "AGENTS.md" not in read_text(p):
            errors.append(f"{rel}: AGENTS.md'ye yönlendirmiyor")

    for p in list(MEM.rglob("*.md")) + [AGENTS] + [ROOT / r for r in ENTRY_FILES]:
        if p.exists():
            raw = p.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                errors.append(f"{p.relative_to(ROOT)}: BOM'lu; BOM'suz UTF-8 olmalı")
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError:
                errors.append(f"{p.relative_to(ROOT)}: geçerli UTF-8 değil")
    return errors


# ---- komutlar -------------------------------------------------------------------


def cmd_baslangic(args) -> int:
    # Önce GitHub'la eşitle: hafıza dosyaları eşitlemeden SONRA okunur.
    sync_lines: list[str] = []
    if not getattr(args, "esitleme_yok", False) and not os.environ.get("EVREN_AI_MEMORY_NO_SYNC"):
        sync_lines = sync_with_remote()
    incidents = load(INCIDENTS)
    sessions_ = sorted(load(SESSIONS), key=lambda s: s["path"].stem, reverse=True)
    rules = parse_rules()
    _out("=" * 72)
    _out("ORTAK GELİŞTİRİCİ HAFIZASI — oturum başı özeti (AGENTS.md protokolü)")
    _out("=" * 72)
    if sync_lines:
        _out("## GitHub eşitleme (başka bilgisayarda yapılan işler)")
        for line in sync_lines:
            _out(f"  {line}")
    if sync_lines:
        work = active_work_branch()
        if work:
            name, subject, now = work
            _out("")
            _out(f"! DEVAM EDEN İŞ BAŞKA DALDA: '{name}' ({subject}). Bu bilgisayardaki kopya geride kalmış.")
            _out(f"    Devam için: git switch {name}   (commit'lenmemiş değişiklik varsa önce onları ele al)")
            for line in now.splitlines()[:14]:
                _out(f"    {line}")
    if DEVIR.exists():
        secs = sections(read_text(DEVIR))
        _out("")
        _out("## DEVİR NOTU (docs/DEVIR_NOTU.md) — işin şu anki yeri; buradan devam et, bitirirken güncelle")
        for name in ("Şu an", "Geliştirme sırası"):
            body = _section(secs, name) or ""
            _out(f"### {name}")
            for line in body.strip().splitlines()[:30]:
                _out(f"  {line}")
    gz_lines = baslangic_gozlem(fetch=bool(sync_lines))
    if gz_lines:
        _out("")
        _out(f"## Uygulamadan gelen gözlemler ({GOZLEM_BRANCH} dalı, gözlem ajanı)")
        for line in gz_lines:
            _out(f"  {line}" if not line.startswith("!") else line)
    hooks = git("config", "--get", "core.hooksPath")
    if hooks.replace("\\", "/") != "tools/hooks":
        _out("! Git ön-commit kancası bu makinede kurulu değil:")
        _out("    python tools/ai_memory.py kanca-kur")
    _out("")
    _out(f"## Kurallar ({len(rules)}) — HER BİRİNE UY")
    for r in rules:
        _out(f"- {r['id']} · {r['title']}")
        _out(f"    {r['kural']}")
    open_items = [i for i in incidents if i["meta"].get("durum") in ("acik", "izleniyor")]
    _out("")
    _out(f"## Açık / izlenen kayıtlar ({len(open_items)})")
    for i in open_items:
        m = i["meta"]
        _out(f"- [{m.get('onem')}] {i['path'].stem} — {i['title']} ({m.get('alan')})")
    if not open_items:
        _out("- yok")
    _out("")
    _out("## Son oturumlar ve sonraki motora notlar")
    for s in sessions_[:3]:
        m = s["meta"]
        _out(f"- {s['path'].stem} · {m.get('motor')} / {m.get('model')} · {m.get('sonuc')}")
        notes = _section(s["sections"], "Sonraki motor için notlar") or ""
        for line in re.sub(r"<!--.*?-->", "", notes, flags=re.S).strip().splitlines()[:8]:
            _out(f"    {line}")
    if PROJECT_STATE.exists():
        secs = sections(read_text(PROJECT_STATE))
        nxt = _section(secs, "Sıradaki iş")
        if nxt:
            _out("")
            _out("## docs/PROJECT_STATE.md → Sıradaki iş")
            for line in nxt.splitlines()[:12]:
                _out(f"  {line}")
    _out("")
    _out("Bitirirken: oturum günlüğü yaz → kayıt/kural ekle → `indeks` → `denetle` → pytest.")
    _out("Ayrıntı: AGENTS.md · Tüm liste: docs/ai-memory/INDEX.md")
    return 0


# ---- gözlem ajanından gelen kayıtlar (gozlem-kayitlari dalı; src/evren_studio/gozlem.py) ----------

GOZLEM_BRANCH = "gozlem-kayitlari"
GOZLEM_REF = f"refs/remotes/origin/{GOZLEM_BRANCH}"
_ONEM_SIRA = {o: i for i, o in enumerate(ONEM)}


def gozlem_fetch(root: Path | None = None) -> bool:
    code, _ = _git_run(root or ROOT, "fetch", "-q", "origin", f"+{GOZLEM_BRANCH}:{GOZLEM_REF}", timeout=45)
    return code == 0


def _front(text: str) -> tuple[dict[str, str], str]:
    meta: dict[str, str] = {}
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", text, re.S)
    if not m:
        return meta, text
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.split("  #", 1)[0].strip()
    return meta, m.group(2)


def _cat_files(root: Path, ref: str, paths: list[str]) -> dict[str, str]:
    """Birçok dosyayı tek `git cat-file --batch` ile okur (dalı çalışma kopyasına almadan)."""
    if not paths:
        return {}
    try:
        r = subprocess.run(["git", "cat-file", "--batch"], cwd=root, capture_output=True, timeout=60,
                           input="".join(f"{ref}:{p}\n" for p in paths).encode("utf-8"))
    except (OSError, subprocess.TimeoutExpired):
        return {}
    data, out, i = r.stdout, {}, 0
    for p in paths:
        nl = data.find(b"\n", i)
        if nl < 0:
            break
        head = data[i:nl].decode("utf-8", "replace").split()
        if len(head) < 3 or head[1] == "missing":
            i = nl + 1
            continue
        size = int(head[2])
        out[p] = data[nl + 1: nl + 1 + size].decode("utf-8", "replace")
        i = nl + 1 + size + 1
    return out


def gozlem_oku(root: Path | None = None, ref: str = GOZLEM_REF) -> list[dict]:
    """Daldaki gözlemleri makine dosyalarıyla birleştirir. Dal yoksa boş liste."""
    import json

    root = root or ROOT
    code, out = _git_run(root, "ls-tree", "-r", "--name-only", ref, "gozlemler")
    if code != 0:
        return []
    files = [ln.strip() for ln in out.splitlines() if ln.strip()]
    texts = _cat_files(root, ref, files)
    by: dict[str, dict] = {}
    for path, text in texts.items():
        parts = path.split("/")
        if len(parts) != 3:
            continue
        g = by.setdefault(parts[1], {"imza": parts[1], "meta": {}, "govde": "", "olaylar": []})
        if parts[2] == "kayit.md":
            g["meta"], g["govde"] = _front(text)
        elif parts[2].startswith("olay-") and parts[2].endswith(".json"):
            try:
                g["olaylar"].append(json.loads(text))
            except ValueError:
                pass
    out_list = []
    for g in by.values():
        m, ol = g["meta"], g["olaylar"]
        g["baslik"] = m.get("baslik") or g["imza"]
        g["onem"] = m.get("onem") if m.get("onem") in ONEM else "orta"
        g["durum"] = m.get("durum") or "acik"
        g["toplam"] = sum(int(o.get("sayac") or 0) for o in ol)
        g["makine"] = len(ol)
        g["son"] = max((o.get("son") or "" for o in ol), default="")
        g["ilk"] = min((o.get("ilk") or "" for o in ol if o.get("ilk")), default=m.get("ilk_gorulme", ""))
        g["surumler"] = sorted({v for o in ol for v in (o.get("surumler") or [])})
        kapali = m.get("cozuldu_tarih") or ""
        g["yeniden"] = g["durum"] == "cozuldu" and bool(kapali) and g["son"] > kapali
        out_list.append(g)
    return sorted(out_list, key=lambda g: (not g["yeniden"], g["durum"] != "acik", _ONEM_SIRA.get(g["onem"], 9),
                                           -g["toplam"]))


def gozlem_acik(items: list[dict]) -> list[dict]:
    return [g for g in items if g["durum"] == "acik" or g["yeniden"]]


def _gozlem_satir(g: dict) -> str:
    etiket = "YENİDEN GÖRÜLDÜ · " if g["yeniden"] else ""
    return (f"- [{g['onem']}] {etiket}{g['imza']} · {g['baslik']} · {g['toplam']} kez · {g['makine']} makine · "
            f"son {g['son'][:10]} · sürüm {', '.join(g['surumler'][-2:]) or '?'}")


def baslangic_gozlem(root: Path | None = None, fetch: bool = True) -> list[str]:
    """`baslangic` bölümü: açık gözlem varsa motora "kullanıcıya bildir" talimatı."""
    if fetch:
        gozlem_fetch(root)
    acik = gozlem_acik(gozlem_oku(root))
    if not acik:
        return []
    yeniden = sum(1 for g in acik if g["yeniden"])
    lines = [f"! KULLANICIYA BİLDİR: uygulamadan {len(acik)} açık gözlem geldi"
             + (f" ({yeniden} tanesi düzeltildikten sonra YENİDEN görüldü)" if yeniden else "")
             + ". İşe başlamadan listeyi kullanıcıya söyle ve düzeltmeyi öner (R-36).",
             "  Ayrıntı: python tools/ai_memory.py gozlem goster <imza> · kayda dönüştür: gozlem kayda-donustur <imza>"]
    lines += [_gozlem_satir(g) for g in acik[:10]]
    if len(acik) > 10:
        lines.append(f"- … ve {len(acik) - 10} tane daha: python tools/ai_memory.py gozlem listele")
    return lines


def _gozlem_bul(imza: str, root: Path | None = None) -> dict | None:
    for g in gozlem_oku(root):
        if g["imza"].startswith(imza):
            return g
    return None


def _src_gozlem():
    """Uygulamanın gozlem modülü (ekle/gönder için; okuma standart kütüphaneyle yapılır)."""
    src = str(ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from evren_studio import gozlem  # noqa: PLC0415

    return gozlem


def cmd_gozlem(args) -> int:
    ne = args.islem
    if ne in ("listele", "goster", "kayda-donustur", "kapat"):
        if not gozlem_fetch():
            _out("! gozlem-kayitlari dalı çekilemedi (dal henüz yok ya da ağ yok); son bilinen hâl gösteriliyor.")
    if ne == "listele":
        items = gozlem_oku()
        items = items if args.hepsi else gozlem_acik(items)
        _out(f"## Gözlemler ({'tümü' if args.hepsi else 'açık'}: {len(items)})")
        for g in items:
            _out(_gozlem_satir(g) + (f" · durum {g['durum']}" if args.hepsi else ""))
        if not items:
            _out("- yok")
        return 0
    if ne == "goster":
        g = _gozlem_bul(args.imza)
        if g is None:
            _out(f"Gözlem bulunamadı: {args.imza}")
            return 1
        _out(_gozlem_satir(g))
        _out(f"  durum: {g['durum']} · ilk: {g['ilk']} · son: {g['son']}")
        _out(g["govde"].strip())
        return 0
    if ne == "kayda-donustur":
        return _gozlem_kayda(args)
    if ne == "kapat":
        return _gozlem_kapat(args)
    if ne == "ekle":
        gz = _src_gozlem()
        imza = gz.kaydet(args.tur, args.baslik, onem=args.onem, alan=args.alan, mesaj=args.mesaj,
                         kaynak="motor", ayrinti={"kaynak_betik": args.betik} if args.betik else None)
        _out(f"Gözlem kuyruğa eklendi: {imza}" if imza else "Gözlem eklenmedi (EVREN_GOZLEM=0?).")
        if imza and args.gonder:
            _out(gz.gonder())
        return 0 if imza else 1
    if ne == "gonder":
        _out(_src_gozlem().gonder())
        return 0
    return 1


def _gozlem_kayda(args) -> int:
    g = _gozlem_bul(args.imza)
    if g is None:
        _out(f"Gözlem bulunamadı: {args.imza}")
        return 1
    secs = sections(g["govde"])
    tur = {"cokme": "hata", "gorev_hatasi": "hata", "api_hatasi": "hata", "qt_uyari": "hata"}.get(
        g["meta"].get("tur", ""), "risk")
    today = date.today().isoformat()
    path = _unique_path(INCIDENTS, f"{today}-{slugify(g['baslik'])}")
    belirti = "\n".join(x for x in (_section(secs, "Belirti") or "", "Konum:", _section(secs, "Konum") or "",
                                     "Ayrıntı:", _section(secs, "Ayrıntı") or "") if x).strip()
    text = f"""---
id: {path.stem}
tarih: {today}
tur: {tur}            # {' | '.join(TUR)}
onem: {g['onem']}          # {' | '.join(ONEM)}
durum: acik                # {' | '.join(DURUM)}
alan: {g['meta'].get('alan') or 'genel'}
kaynak_motor: EVREN Studio gözlem ajanı
kaynak_model: bilinmiyor
cozen_motor: {args.motor}
cozen_model: {args.model}
ortam: {environment_string()}
etiketler: [gozlem]
kurallar: []
---

# {g['baslik']}

## Belirti
Gözlem ajanından (uygulama çalışırken, otomatik ve temizlenmiş):
{belirti}

## Kök neden
<!-- Neden oldu? Doğrulandıysa "doğrulandı", tahminse "tahmin" yaz. -->

## Çözüm
<!-- Ne yapıldı? İşe YARAMAYAN denemeleri de yaz. Çözülmediyse "Henüz yok". -->

## Kanıt
Gözlem `{g['imza']}` (dal {GOZLEM_BRANCH}): {g['toplam']} kez, {g['makine']} makine, ilk {g['ilk']}, son {g['son']},
sürümler {', '.join(g['surumler']) or '?'}.

## Önleme
<!-- Tekrarını önleyen test/kural. Düzeltince: python tools/ai_memory.py gozlem kapat {g['imza']} --kayit {path.stem} -->

## İlgili dosyalar
"""
    write_text(path, text)
    _out(f"Oluşturuldu: {path.relative_to(ROOT).as_posix()}")
    _out(f"Kök nedeni bul ve düzelt; sonra: python tools/ai_memory.py gozlem kapat {g['imza']} --kayit {path.stem}")
    return 0


def _gozlem_kapat(args) -> int:
    """Daldaki kayit.md'nin durumunu günceller. Çalışma kopyasına dokunmaz: geçici worktree kullanılır."""
    import shutil
    import tempfile
    from datetime import datetime, timezone

    if _gozlem_bul(args.imza) is None:
        _out(f"Gözlem bulunamadı: {args.imza}")
        return 1
    imza = _gozlem_bul(args.imza)["imza"]
    tmp = Path(tempfile.mkdtemp(prefix="gozlem-"))
    hooks = tmp / "bos-kancalar"
    wt = tmp / "agac"
    try:
        for _ in range(3):
            gozlem_fetch()
            code, out = _git_run(ROOT, "worktree", "add", "-q", "--detach", str(wt), GOZLEM_REF)
            if code != 0:
                _out(f"Geçici çalışma ağacı açılamadı: {out}")
                return 1
            p = wt / "gozlemler" / imza / "kayit.md"
            meta_text = p.read_text(encoding="utf-8")
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            repl = {"durum": f"{args.durum}                # acik | cozuldu | kabul-edildi",
                    "cozuldu_tarih": now, "cozum_kaydi": args.kayit}
            for key, val in repl.items():
                meta_text = re.sub(rf"(?m)^{key}:.*$", f"{key}: {val}", meta_text, count=1)
            if args.not_:
                meta_text = meta_text.rstrip() + f"\n\n## Kapanış notu ({now[:10]})\n{args.not_}\n"
            p.write_text(meta_text, encoding="utf-8", newline="\n")
            hooks.mkdir(exist_ok=True)
            base = ["-C", str(wt), "-c", f"core.hooksPath={hooks}"]
            _git_run(ROOT, *base, "add", "-A")
            code, out = _git_run(ROOT, *base, "commit", "-q", "-m", f"gözlem {imza}: {args.durum} ({args.kayit})")
            if code != 0:
                _out(f"Commit edilemedi: {out}")
                return 1
            code, out = _git_run(ROOT, *base, "push", "-q", "origin", f"HEAD:{GOZLEM_BRANCH}", timeout=90)
            _git_run(ROOT, "worktree", "remove", "--force", str(wt))
            if code == 0:
                _out(f"Gözlem {imza} → {args.durum} (kayıt {args.kayit}). Yeniden görülürse baslangic bildirir.")
                return 0
        _out(f"Gönderilemedi: {out}")
        return 1
    finally:
        _git_run(ROOT, "worktree", "prune")
        shutil.rmtree(tmp, ignore_errors=True)


def _norm(s: str) -> str:
    return s.translate(_TR).lower()


def cmd_ara(args) -> int:
    words = [_norm(w) for w in args.kelimeler]
    hits = 0
    for folder, label in ((INCIDENTS, "kayıt"), (SESSIONS, "oturum")):
        for item in load(folder):
            text = _norm(item["body"] + " " + " ".join(item["meta"].values()))
            if all(w in text for w in words):
                hits += 1
                durum = item["meta"].get("durum") or item["meta"].get("sonuc", "")
                _out(f"[{label}] {item['path'].relative_to(ROOT).as_posix()} ({durum}) — {item['title']}")
    for r in parse_rules():
        text = _norm(" ".join([r["title"], r["kural"], r["neden"]]))
        if all(w in text for w in words):
            hits += 1
            _out(f"[kural] {r['id']} · {r['title']}")
    if not hits:
        _out("Eşleşme yok.")
    return 0


def _unique_path(folder: Path, stem: str) -> Path:
    p = folder / f"{stem}.md"
    n = 2
    while p.exists():
        p = folder / f"{stem}-{n}.md"
        n += 1
    return p


def cmd_kayit(args) -> int:
    today = args.tarih or date.today().isoformat()
    path = _unique_path(INCIDENTS, f"{today}-{slugify(args.baslik)}")
    text = f"""---
id: {path.stem}
tarih: {today}
tur: {args.tur}            # {' | '.join(TUR)}
onem: {args.onem}          # {' | '.join(ONEM)}
durum: acik                # {' | '.join(DURUM)}
alan: {args.alan}
kaynak_motor: {args.motor}
kaynak_model: {args.model}
cozen_motor:
cozen_model:
ortam: {args.ortam or environment_string()}
etiketler: []
kurallar: []
---

# {args.baslik}

## Belirti
<!-- Ne görüldü? Hata mesajı, ekran, test çıktısı. -->

## Kök neden
<!-- Neden oldu? Doğrulandıysa "doğrulandı", tahminse "tahmin" yaz. -->

## Çözüm
<!-- Ne yapıldı? İşe YARAMAYAN denemeleri de yaz. Çözülmediyse "Henüz yok". -->

## Kanıt
<!-- Test adı, komut çıktısı, commit kimliği. -->

## Önleme
<!-- Tekrarını önleyen test/kural. RULES.md'ye kural eklendiyse kimliğini yaz. -->

## İlgili dosyalar
"""
    write_text(path, text)
    _out(f"Oluşturuldu: {path.relative_to(ROOT).as_posix()}")
    _out("Bölümleri doldurun; bitince `indeks` ve `denetle` çalıştırın.")
    return 0


def cmd_oturum(args) -> int:
    today = args.tarih or date.today().isoformat()
    path = _unique_path(SESSIONS, f"{today}-{slugify(args.motor, 24)}-{slugify(args.baslik, 40)}")
    branch = git("rev-parse", "--abbrev-ref", "HEAD") or "?"
    text = f"""---
id: {path.stem}
tarih: {today}
motor: {args.motor}
model: {args.model}
ortam: {args.ortam or environment_string()}
dal: {branch}
sonuc: {args.sonuc}        # {' | '.join(SONUC)}
---

# {args.baslik}

## Görev
<!-- Kullanıcı ne istedi? -->

## Yapılanlar
<!-- Değişen dosyalar ve nedenleri; alınan kararlar. -->

## Test sonuçları
<!-- Çalıştırılan testler ve gerçek sonuçları. Çalıştırılmayanları da yaz. -->

## Sorunlar ve kayıtlar
<!-- Karşılaşılan sorunlar → docs/ai-memory/incidents/... kimlikleri. -->

## Sonraki motor için notlar
<!-- Yarım kalanlar, dikkat edilecekler, doğrulanmayanlar. -->
"""
    write_text(path, text)
    _out(f"Oluşturuldu: {path.relative_to(ROOT).as_posix()}")
    return 0


def cmd_indeks(_args) -> int:
    incidents = load(INCIDENTS)
    sessions_ = load(SESSIONS)
    rules = parse_rules()
    write_text(INDEX, render_index(incidents, sessions_, rules))
    new_agents = agents_with_block(rules)
    if new_agents is not None:
        write_text(AGENTS, new_agents)
    _out(f"INDEX.md ve AGENTS.md güncellendi ({len(incidents)} kayıt, "
         f"{len(sessions_)} oturum, {len(rules)} kural).")
    return 0


def cmd_denetle(_args) -> int:
    errors = check()
    if errors:
        _out(f"DENETİM BAŞARISIZ ({len(errors)} sorun):")
        for e in errors:
            _out(f"  - {e}")
        return 1
    _out("DENETİM_TAMAM: ortak hafıza geçerli ve güncel.")
    return 0


def cmd_kanca_kur(_args) -> int:
    subprocess.run(["git", "config", "core.hooksPath", "tools/hooks"], cwd=ROOT, check=False)
    _out("Ön-commit kancası etkin: core.hooksPath = tools/hooks")
    return 0


def cmd_kanca(_args) -> int:
    staged = [s for s in git("diff", "--cached", "--name-only").splitlines() if s]
    code = [s for s in staged if s.startswith(("src/", "tests/"))]
    memory = [s for s in staged if s.startswith("docs/ai-memory/")]
    if code and not memory:
        _out("COMMIT DURDURULDU (AGENTS.md protokolü):")
        _out("  src/ veya tests/ değişti ama docs/ai-memory/ altında değişiklik yok.")
        _out("  Oturum günlüğü yazın/güncelleyin:  python tools/ai_memory.py oturum --baslik ... --motor ... --model ...")
        _out("  Sonra: python tools/ai_memory.py indeks  ve dosyaları commit'e ekleyin.")
        return 1
    if any(s.startswith("src/") for s in staged) and DEVIR_REL not in staged:
        _out("COMMIT DURDURULDU (R-35, devir notu):")
        _out(f"  src/ değişti ama {DEVIR_REL} güncellenmedi. 'Şu an' bölümünü ve ilgili maddenin durumunu")
        _out("  (YAPILDI/SÜRÜYOR + commit) güncelleyip commit'e ekleyin; başka bilgisayardaki motor buradan devam eder.")
        return 1
    errors = check()
    if errors:
        _out("COMMIT DURDURULDU: ortak hafıza denetimi başarısız:")
        for e in errors[:20]:
            _out(f"  - {e}")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description="Ortak geliştirici hafızası (docs/ai-memory)")
    sub = p.add_subparsers(dest="komut", required=True)
    b = sub.add_parser("baslangic", help="oturum başı özeti (önce GitHub ile eşitler)")
    b.add_argument("--esitleme-yok", action="store_true",
                   help="GitHub kontrolünü ve otomatik ileri sarmayı atla")
    b.set_defaults(fn=cmd_baslangic)
    a = sub.add_parser("ara", help="hafızada ara")
    a.add_argument("kelimeler", nargs="+")
    a.set_defaults(fn=cmd_ara)
    k = sub.add_parser("kayit", help="yeni hata/eksik kaydı")
    k.add_argument("--baslik", required=True)
    k.add_argument("--motor", required=True, help="örn. 'Claude Code', 'Kilo Code (VS Code)'")
    k.add_argument("--model", required=True, help="örn. 'claude-opus-5-5', 'glm-5.3', 'bilinmiyor'")
    k.add_argument("--tur", choices=TUR, default="hata")
    k.add_argument("--onem", choices=ONEM, default="orta")
    k.add_argument("--alan", default="genel")
    k.add_argument("--ortam", default="")
    k.add_argument("--tarih", default="")
    k.set_defaults(fn=cmd_kayit)
    o = sub.add_parser("oturum", help="yeni oturum günlüğü")
    o.add_argument("--baslik", required=True)
    o.add_argument("--motor", required=True)
    o.add_argument("--model", required=True)
    o.add_argument("--sonuc", choices=SONUC, default="devam-ediyor")
    o.add_argument("--ortam", default="")
    o.add_argument("--tarih", default="")
    o.set_defaults(fn=cmd_oturum)
    g = sub.add_parser("gozlem", help="uygulamanın gözlem ajanından gelen kayıtlar")
    gs = g.add_subparsers(dest="islem", required=True)
    gl = gs.add_parser("listele", help="açık gözlemler")
    gl.add_argument("--hepsi", action="store_true", help="kapalıları da göster")
    gs.add_parser("goster", help="bir gözlemin ayrıntısı").add_argument("imza")
    gk = gs.add_parser("kayda-donustur", help="gözlemden docs/ai-memory/incidents kaydı aç")
    gk.add_argument("imza")
    gk.add_argument("--motor", default="bilinmiyor")
    gk.add_argument("--model", default="bilinmiyor")
    gc = gs.add_parser("kapat", help="düzeltilen gözlemi dalda kapat")
    gc.add_argument("imza")
    gc.add_argument("--kayit", required=True, help="ilgili docs/ai-memory/incidents kimliği")
    gc.add_argument("--durum", choices=("cozuldu", "kabul-edildi"), default="cozuldu")
    gc.add_argument("--not", dest="not_", default="")
    ge = gs.add_parser("ekle", help="geliştirme sırasında gözlem ekle (motorlar, gerçek API betikleri)")
    ge.add_argument("--baslik", required=True)
    ge.add_argument("--tur", default="gelistirici")
    ge.add_argument("--onem", choices=ONEM, default="orta")
    ge.add_argument("--alan", default="genel")
    ge.add_argument("--mesaj", default="")
    ge.add_argument("--betik", default="", help="gözlemi üreten betik/komut adı")
    ge.add_argument("--gonder", action="store_true", help="ekledikten sonra depoya gönder")
    gs.add_parser("gonder", help="bu bilgisayardaki kuyruğu depoya gönder")
    g.set_defaults(fn=cmd_gozlem)
    sub.add_parser("indeks", help="INDEX.md ve AGENTS.md kural özetini üret").set_defaults(fn=cmd_indeks)
    sub.add_parser("denetle", help="biçim ve güncellik denetimi").set_defaults(fn=cmd_denetle)
    sub.add_parser("kanca-kur", help="git ön-commit kancasını etkinleştir").set_defaults(fn=cmd_kanca_kur)
    sub.add_parser("kanca", help="ön-commit kancası").set_defaults(fn=cmd_kanca)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
