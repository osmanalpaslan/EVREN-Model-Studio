"""E2 otomatik proje haritası (Qt'siz): dosya ağacı + kaynak dosyaların sembol özeti → sistem istemine.

Neden: ajan her yeni turda önce list_files/read_file ile projeyi tanımak için birkaç adım harcıyordu (her adım
tüm bağlamla bir model çağrısı). Harita en çok ~3 bin token (MAX_CHARS); Python için `ast` (yalnız üst düzey sınıf/
fonksiyon adları); Go, Rust, Java, C#, JS/TS, PHP, C/C++, Ruby, Kotlin için tree-sitter (agent/tsmap.py, Madde 20 C1;
çözümleyici yoksa eski basit tarayıcı). Büyük projede (MAX_FILES üstü) yalnız klasör düzeyi özet verilir.
Sembollerin hepsi sığmazsa (C1, Aider fikri) BAŞKA dosyalardan en çok başvurulan dosyaların sembolleri önce gösterilir;
kalanlar yalnız yol olarak kalır (eskiden tüm semboller birden atılıyordu).
Değişmeyen projede yeniden hesaplanmaz (dosya yolu + boyut + değişim zamanı parmak izi).
Harita bir İPUCUDUR: ajan dosyanın gerçek içeriğini yine okumalı (istem bunu söyler).
"""
from __future__ import annotations

import ast
import os
import re
from collections import Counter
from pathlib import Path

from . import tsmap

MAX_CHARS = 9000                 # ~3 bin token (Türkçe/kod karışık ~3 karakter/token)
MAX_FILES = 1500                 # bunun üstünde yalnız klasör özeti
MAX_SYMBOL_BYTES = 300 * 1024    # daha büyük kaynak dosyada sembol çıkarılmaz
MAX_SYMBOLS_PER_FILE = 12
MIN_FILES = 3                    # bundan az dosyada harita gereksiz (list_files tek adım)
SKIP_DIRS = {".git", ".venv", "venv", "env", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache",
             "dist", "build", ".idea", ".vscode", ".next", "target", "bin", "obj", ".godot", ".evren"}
CODE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".gd", ".cs"} | set(tsmap.GRAMMARS)
_JS_SYM = re.compile(r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?(?:function\*?\s+(\w+)|class\s+(\w+)|"
                     r"(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\(?[\w,\s]*\)?\s*=>)", re.M)
_GD_SYM = re.compile(r"^(?:func\s+(\w+)|class_name\s+(\w+)|signal\s+(\w+))", re.M)
_CS_SYM = re.compile(r"^\s*(?:public|internal)\s+(?:static\s+|sealed\s+|abstract\s+|partial\s+)*"
                     r"(?:class|interface|record|struct|enum)\s+(\w+)", re.M)
_REGEX_SYM = {".gd": _GD_SYM, ".cs": _CS_SYM, ".js": _JS_SYM, ".ts": _JS_SYM, ".tsx": _JS_SYM, ".jsx": _JS_SYM,
              ".mjs": _JS_SYM}
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")

_cache: dict[str, tuple[tuple, str]] = {}


def _files(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for f in sorted(filenames):
            if f.startswith(".") and f not in (".env.example", ".gitignore"):
                continue
            out.append(Path(dirpath) / f)
            if len(out) > MAX_FILES:
                return out
    return out


def _fingerprint(files: list[Path]) -> tuple:
    fp = []
    for f in files:
        try:
            st = f.stat()
            fp.append((str(f), st.st_size, int(st.st_mtime)))
        except OSError:
            pass
    return tuple(fp)


def _read(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_SYMBOL_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _py_defs(text: str) -> list[tuple[str, str]]:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return [("(sözdizimi hatası)", "")]
    out: list[tuple[str, str]] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            meths = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and not n.name.startswith("_")]
            out.append((f"class {node.name}" + (f"({', '.join(meths[:6])}{'…' if len(meths) > 6 else ''})"
                                                if meths else ""), node.name))
            out += [("", m) for m in meths]
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            out.append((f"{node.name}()", node.name))
    return out


def _defs(path: Path, text: str) -> list[tuple[str, str]]:
    """[(gösterim, ad)]; gösterimi boş olan yalnız başvuru sayımı içindir."""
    suf = path.suffix.lower()
    if suf == ".py":
        return _py_defs(text)
    found = tsmap.definitions(text, suf)
    if found is not None:
        return found
    rx = _REGEX_SYM.get(suf)
    if rx is None:
        return []
    out = []
    for m in rx.finditer(text):
        n = next((g for g in m.groups() if g), None)
        if n:
            out.append((n, n))
    return out


def _shown(defs: list[tuple[str, str]]) -> list[str]:
    names = [s for s, _n in defs if s]
    if len(names) > MAX_SYMBOLS_PER_FILE:
        names = names[:MAX_SYMBOLS_PER_FILE] + [f"… +{len(names) - MAX_SYMBOLS_PER_FILE}"]
    return names


def symbols(path: Path) -> list[str]:
    """Üst düzey semboller (sınıf, fonksiyon). Okunamayan/bozuk dosyada boş liste."""
    text = _read(path)
    if text is None:
        return []
    return _shown(_defs(path, text))


def rank(texts: dict[Path, str], defs: dict[Path, list[tuple[str, str]]]) -> Counter:
    """Dosya puanı = tanımladığı adların BAŞKA dosyalarda geçme sayısı (dosya başına bir kez). Aider'ın PageRank'inin
    sade hâli: çok kullanılan çekirdek dosyalar önce gelir."""
    owners: dict[str, set[Path]] = {}
    for f, ds in defs.items():
        for _s, n in ds:
            if n and len(n) >= 3:
                owners.setdefault(n, set()).add(f)
    score: Counter = Counter()
    if not owners:
        return score
    for f, text in texts.items():
        for tok in set(_IDENT.findall(text)):
            for o in owners.get(tok, ()):
                if o != f:
                    score[o] += 1
    return score


def _dir_summary(root: Path, files: list[Path]) -> str:
    counts: dict[str, int] = {}
    for f in files:
        rel = f.relative_to(root).parts
        key = rel[0] + "/" if len(rel) > 1 else "(kök)"
        counts[key] = counts.get(key, 0) + 1
    lines = [f"Büyük proje ({len(files)}+ dosya): yalnız klasör özeti. Ayrıntı için list_files/find_files kullan."]
    lines += [f"- {k}: {v} dosya" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])[:40]]
    return "\n".join(lines)


def build(root: str | Path, max_chars: int = MAX_CHARS) -> str:
    """Harita metni ("" → harita gereksiz: çok küçük/boş proje)."""
    root = Path(root)
    files = _files(root)
    if len(files) < MIN_FILES:
        return ""
    key = str(root.resolve())
    fp = _fingerprint(files)
    hit = _cache.get(key)
    if hit and hit[0] == fp:
        return hit[1]
    if len(files) > MAX_FILES:
        text = _dir_summary(root, files)
    else:
        texts: dict[Path, str] = {}
        defs: dict[Path, list[tuple[str, str]]] = {}
        for f in files:
            if f.suffix.lower() in CODE_SUFFIXES:
                t = _read(f)
                if t is not None:
                    texts[f] = t
                    defs[f] = _defs(f, t)
        paths: list[str] = []
        sym: dict[Path, str] = {}
        for f in files:
            rel = f.relative_to(root).as_posix()
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            paths.append(rel + (f" ({size // 1024} KB)" if size >= 50 * 1024 else ""))
            shown = _shown(defs.get(f, []))
            if shown:
                sym[f] = ", ".join(shown)
        full = [p + (f": {sym[f]}" if f in sym else "") for f, p in zip(files, paths)]
        text = "\n".join(full)
        if len(text) > max_chars:
            # C1: önce en çok başvurulan dosyaların sembolleri; sığmayanlar yalnız yol
            base = "\n".join(paths)
            note = "\n(semboller yalnız en çok kullanılan dosyalarda; kalanı için read_file / find_files)"
            budget = max_chars - len(base) - len(note)
            keep: set[Path] = set()
            if budget > 0 and sym:
                score = rank(texts, defs)
                for f in sorted(sym, key=lambda x: (-score.get(x, 0), str(x))):
                    cost = len(sym[f]) + 2
                    if cost <= budget:
                        keep.add(f)
                        budget -= cost
            if keep:
                text = "\n".join(p + (f": {sym[f]}" if f in keep else "") for f, p in zip(files, paths)) + note
            else:
                text = base
                if len(text) > max_chars:
                    cut = text[:max_chars].rsplit("\n", 1)[0]
                    text = cut + f"\n… (harita kısaltıldı: toplam {len(files)} dosya; kalanı için list_files)"
                else:
                    text += "\n(sembol özeti sığmadığı için yalnız dosya yolları)"
    _cache[key] = (fp, text)
    return text


def prompt_section(root: str | Path) -> str:
    try:
        m = build(root)
    except OSError:
        return ""
    if not m:
        return ""
    return ("# Proje haritası (otomatik; dosya ağacı ve üst düzey semboller)\n"
            "Projeyi tanımak için baştan list_files çağırmana gerek yok; ama bir dosyayı değiştirmeden önce gerçek "
            "içeriğini read_file ile oku (harita yalnız ipucu, eski olabilir).\n" + m + "\n")
