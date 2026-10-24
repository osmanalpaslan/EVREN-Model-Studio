"""E2 otomatik proje haritası (Qt'siz): dosya ağacı + kaynak dosyaların sembol özeti → sistem istemine.

Neden: ajan her yeni turda önce list_files/read_file ile projeyi tanımak için birkaç adım harcıyordu (her adım
tüm bağlamla bir model çağrısı). Harita en çok ~3 bin token (MAX_CHARS); Python için `ast` (yalnız üst düzey sınıf/
fonksiyon adları), JS/TS için basit tarayıcı. Büyük projede (MAX_FILES üstü) yalnız klasör düzeyi özet verilir.
Değişmeyen projede yeniden hesaplanmaz (dosya yolu + boyut + değişim zamanı parmak izi).
Harita bir İPUCUDUR: ajan dosyanın gerçek içeriğini yine okumalı (istem bunu söyler).
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path

MAX_CHARS = 9000                 # ~3 bin token (Türkçe/kod karışık ~3 karakter/token)
MAX_FILES = 1500                 # bunun üstünde yalnız klasör özeti
MAX_SYMBOL_BYTES = 300 * 1024    # daha büyük kaynak dosyada sembol çıkarılmaz
MAX_SYMBOLS_PER_FILE = 12
MIN_FILES = 3                    # bundan az dosyada harita gereksiz (list_files tek adım)
SKIP_DIRS = {".git", ".venv", "venv", "env", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache",
             "dist", "build", ".idea", ".vscode", ".next", "target", "bin", "obj", ".godot", ".evren"}
CODE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".gd", ".cs"}
_JS_SYM = re.compile(r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?(?:function\*?\s+(\w+)|class\s+(\w+)|"
                     r"(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\(?[\w,\s]*\)?\s*=>)", re.M)
_GD_SYM = re.compile(r"^(?:func\s+(\w+)|class_name\s+(\w+)|signal\s+(\w+))", re.M)
_CS_SYM = re.compile(r"^\s*(?:public|internal)\s+(?:static\s+|sealed\s+|abstract\s+|partial\s+)*"
                     r"(?:class|interface|record|struct|enum)\s+(\w+)", re.M)

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


def symbols(path: Path) -> list[str]:
    """Üst düzey semboller (sınıf, fonksiyon). Okunamayan/bozuk dosyada boş liste."""
    try:
        if path.stat().st_size > MAX_SYMBOL_BYTES:
            return []
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    suf = path.suffix.lower()
    names: list[str] = []
    if suf == ".py":
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            return ["(sözdizimi hatası)"]
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                meths = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and not n.name.startswith("_")]
                names.append(f"class {node.name}" + (f"({', '.join(meths[:6])}{'…' if len(meths) > 6 else ''})"
                                                     if meths else ""))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                names.append(f"{node.name}()")
    else:
        rx = {".gd": _GD_SYM, ".cs": _CS_SYM}.get(suf, _JS_SYM)
        for m in rx.finditer(text):
            n = next((g for g in m.groups() if g), None)
            if n:
                names.append(n)
    if len(names) > MAX_SYMBOLS_PER_FILE:
        names = names[:MAX_SYMBOLS_PER_FILE] + [f"… +{len(names) - MAX_SYMBOLS_PER_FILE}"]
    return names


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
        lines: list[str] = []
        for f in files:
            rel = f.relative_to(root).as_posix()
            syms = symbols(f) if f.suffix.lower() in CODE_SUFFIXES else []
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            kb = f" ({size // 1024} KB)" if size >= 50 * 1024 else ""
            lines.append(f"{rel}{kb}" + (f": {', '.join(syms)}" if syms else ""))
        text = "\n".join(lines)
        if len(text) > max_chars:
            # önce sembolleri at (yalnız yollar), yine sığmazsa kes ve söyle
            text = "\n".join(ln.split(": ", 1)[0] for ln in lines)
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
