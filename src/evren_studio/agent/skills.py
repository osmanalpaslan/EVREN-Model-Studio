"""F4 skill'ler (Qt'siz): SKILL.md klasörlerini tanır, proje bazında etkinleştirir, ajana `read_skill` ile açar.

Biçim (Anthropic skill düzeni ile uyumlu): klasörde `SKILL.md`; başında isteğe bağlı YAML benzeri ön bilgi
    ---
    name: hesap-kapama-raporu
    description: Hesap kapama raporu üretir; ...
    denetci: scripts/denetle.py        # isteğe bağlı (F4 #13); `checker:` da kabul
    ---
Ön bilgi yoksa ad = klasör adı, açıklama = ilk paragraf. Diğer dosyalar (references/, scripts/) ajana `read_skill`
ile açılır. Skill'ler uygulama veri klasörüne KOPYALANIR (kaynak klasör taşınsa da çalışsın); "kaynaktan yenile"
kaynağı tekrar kopyalar.

İsteme yalnız ad + kısa açıklama girer (7.2 kararı); içerik gerektiğinde okunur. Denetçi betiği skill'i kullanıcı
eklediği için güvenilir sayılır ama yine de izin moduna göre sorulur (arayüz).
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

SKILL_FILE = "SKILL.md"
DESC_MAX = 300                    # isteme giren açıklama
READ_MAX_BYTES = 400 * 1024
LIST_MAX = 200
CHECKER_NAMES = ("denetle.py", "denetci.py", "check.py", "validate.py", "scripts/denetle.py", "scripts/check.py",
                 "scripts/validate.py")
SCOPES = {"tum": "Tüm projeler", "secili": "Yalnız seçtiğim projeler", "hicbiri": "Hiçbir proje (kapalı)"}
SKIP_COPY = shutil.ignore_patterns(".git", "__pycache__", ".venv", "venv", "node_modules", "*.pyc")


class SkillError(Exception):
    pass


@dataclass
class Skill:
    slug: str
    name: str
    description: str
    folder: str                    # uygulama veri klasöründeki kopya
    source: str = ""               # eklendiği kaynak klasör
    enabled: bool = True
    scope: str = "tum"             # tum | secili | hicbiri
    projects: list[str] = field(default_factory=list)
    checker: str = ""              # skill klasörüne göre denetçi betiği ("" → yok)

    def applies_to(self, workspace: str | None) -> bool:
        """Bu proje klasöründe etkin mi? (klasörsüz sohbette skill yok)"""
        if not self.enabled or not workspace or self.scope == "hicbiri":
            return False
        if self.scope == "tum":
            return True
        w = _norm(workspace)
        return any(_norm(p) == w for p in self.projects)

    def to_row(self) -> dict:
        return {"slug": self.slug, "name": self.name, "description": self.description, "folder": self.folder,
                "source": self.source, "enabled": int(self.enabled), "scope": self.scope,
                "projects": json.dumps(self.projects, ensure_ascii=False), "checker": self.checker}

    @classmethod
    def from_row(cls, r) -> "Skill":
        d = dict(r)
        try:
            projects = json.loads(d.get("projects") or "[]")
        except ValueError:
            projects = []
        return cls(slug=d["slug"], name=d["name"], description=d.get("description") or "", folder=d["folder"],
                   source=d.get("source") or "", enabled=bool(d.get("enabled", 1)), scope=d.get("scope") or "tum",
                   projects=[str(p) for p in projects if p], checker=d.get("checker") or "")


def _norm(p: str) -> str:
    try:
        return str(Path(p).resolve()).lower()
    except OSError:
        return str(p).lower()


def slugify(name: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = re.sub(r"[^a-z0-9]+", "-", name.translate(tr).lower()).strip("-")
    return s[:60] or "skill"


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """(ön bilgi, gövde). Basit `anahtar: değer` satırları; çok satırlı değer `>`/`|` ile devam eder."""
    t = text.lstrip("﻿")
    m = re.match(r"---\s*\n(.*?)\n---\s*\n?", t, re.S)
    if not m:
        return {}, t
    meta: dict[str, str] = {}
    key = None
    for line in m.group(1).splitlines():
        km = re.match(r"([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if km and not line.startswith((" ", "\t")):
            key = km.group(1).lower()
            val = km.group(2).strip()
            meta[key] = "" if val in (">", "|", ">-", "|-") else val.strip("\"'")
        elif key and line.strip():
            meta[key] = (meta[key] + " " + line.strip()).strip()
    return meta, t[m.end():]


def describe_folder(folder: Path) -> tuple[str, str, str]:
    """(ad, açıklama, denetçi) — SKILL.md yoksa SkillError."""
    f = folder / SKILL_FILE
    if not f.is_file():
        raise SkillError(f"{folder} klasöründe {SKILL_FILE} yok.")
    text = f.read_text(encoding="utf-8", errors="replace")
    meta, body = parse_frontmatter(text)
    name = meta.get("name") or folder.name
    desc = meta.get("description") or ""
    if not desc:
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip() and not p.strip().startswith("#")]
        desc = re.sub(r"\s+", " ", paras[0]) if paras else ""
    checker = meta.get("denetci") or meta.get("checker") or ""
    if checker and not (folder / checker).is_file():
        checker = ""
    if not checker:
        checker = next((c for c in CHECKER_NAMES if (folder / c).is_file()), "")
    return name, desc[:1000], checker


def install(src: Path, skills_root: Path, existing: set[str] | None = None) -> Skill:
    """Kaynak klasörü veri klasörüne kopyalar (aynı ad varsa -2, -3 …). Kaynakta SKILL.md şart.
    `src` doğrudan SKILL.md'nin olduğu klasör ya da onu içeren tek alt klasör olabilir."""
    src = Path(src)
    if not (src / SKILL_FILE).is_file():
        subs = [d for d in src.iterdir() if d.is_dir() and (d / SKILL_FILE).is_file()] if src.is_dir() else []
        if len(subs) == 1:
            src = subs[0]
    name, desc, checker = describe_folder(src)
    base = slugify(name)
    taken = set(existing or set()) | {p.name for p in skills_root.iterdir()} if skills_root.is_dir() else set(existing or set())
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    dest = skills_root / slug
    skills_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, ignore=SKIP_COPY)
    return Skill(slug=slug, name=name, description=desc, folder=str(dest), source=str(src), checker=checker)


def refresh(skill: Skill) -> Skill:
    """Kaynaktan yeniden kopyalar (kaynak yoksa SkillError). Ayarlar (etkinlik, kapsam) korunur."""
    src = Path(skill.source)
    if not skill.source or not (src / SKILL_FILE).is_file():
        raise SkillError("Kaynak klasör bulunamadı; skill'i yeniden ekleyin.")
    dest = Path(skill.folder)
    tmp = dest.with_name(dest.name + ".yeni")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(src, tmp, ignore=SKIP_COPY)
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)
    skill.name, skill.description, skill.checker = describe_folder(dest)
    return skill


def prompt_section(skills: list[Skill]) -> str:
    if not skills:
        return ""
    lines = ["# Skill'ler (kullanıcının bu proje için etkinleştirdiği iş talimatları)",
             "İş bir skill'in konusuna giriyorsa ÖNCE `read_skill` ile onun SKILL.md'sini oku ve kurallarına uy; "
             "SKILL.md'nin andığı ek dosyaları (references/…) da read_skill ile aç. Konu dışıysa okuma."]
    for s in skills:
        d = re.sub(r"\s+", " ", s.description).strip()
        lines.append(f"- {s.name}: {d[:DESC_MAX]}{'…' if len(d) > DESC_MAX else ''}")
    return "\n".join(lines) + "\n"


def find(skills: list[Skill], name: str) -> Skill | None:
    key = (name or "").strip().lower()
    return next((s for s in skills if key in (s.name.lower(), s.slug.lower())), None)


def read(skill: Skill, path: str | None = None) -> str:
    """Skill dosyası (varsayılan SKILL.md) ya da path="?" → dosya listesi. Skill klasörü dışına çıkılamaz."""
    root = Path(skill.folder).resolve()
    if path and path.strip() in ("?", ".", "/", "liste"):
        files = []
        for p in sorted(root.rglob("*")):
            if p.is_file():
                files.append(f"{p.relative_to(root).as_posix()} ({max(1, p.stat().st_size // 1024)} KB)")
            if len(files) >= LIST_MAX:
                files.append("…")
                break
        return f"{skill.name} skill'inin dosyaları:\n" + "\n".join(files)
    rel = (path or SKILL_FILE).replace("\\", "/").lstrip("/")
    p = (root / rel).resolve()
    try:
        p.relative_to(root)
    except ValueError as exc:
        raise SkillError("Skill klasörünün dışı okunamaz.") from exc
    if not p.is_file():
        raise SkillError(f"{skill.name} içinde dosya yok: {rel} (path='?' ile listeyi gör)")
    data = p.read_bytes()
    if len(data) > READ_MAX_BYTES:
        raise SkillError(f"Dosya çok büyük ({len(data) // 1024} KB).")
    if b"\x00" in data[:4096]:
        raise SkillError("İkili dosya okunamaz (Excel ise kopyalayıp read_table kullan).")
    text = data.decode("utf-8-sig", errors="replace")
    return f"[skill: {skill.name}] {rel}\n{text}"
