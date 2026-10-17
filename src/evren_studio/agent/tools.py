"""Ajan araçları — tümü seçili proje klasörüyle sınırlıdır.

Güvenlik kuralları (docs/SECURITY.md):
- Her yol proje köküne göre çözülür; kök dışına (.. veya sembolik bağlantı
  ile) çıkan yollar reddedilir.
- `.git` klasörüne doğrudan yazılamaz.
- İkili dosyalar ve 512 KB üstü dosyalar okunmaz; 2 MB üstü içerik yazılmaz.
- Komutlar proje kökünde, zaman aşımıyla çalışır; çıktı kısaltılır.
- Yazma ve komut araçları önce "hazırlanır" (diff/komut önizlemesi), izin
  politikası onay verirse uygulanır. Bu modül izin KARARI vermez.
"""
from __future__ import annotations

import difflib
import fnmatch
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".idea", ".vs",
    ".next", ".nuxt", "dist", "build", "bin", "obj", ".gradle", "target",
    ".egg-info",
}
MAX_READ_BYTES = 512 * 1024
MAX_READ_LINES = 2000
MAX_WRITE_BYTES = 2 * 1024 * 1024
MAX_LIST_ENTRIES = 500
MAX_SEARCH_RESULTS = 200
MAX_SEARCH_FILE_BYTES = 1024 * 1024
DEFAULT_OUTPUT_LIMIT = 20_000

READ, WRITE, EXEC, META = "read", "write", "exec", "meta"


class ToolError(Exception):
    """Modele ve kullanıcıya gösterilecek Türkçe araç hatası."""


# ---- araç tanımları --------------------------------------------------------


@dataclass(frozen=True)
class ToolSpec:
    name: str
    kind: str
    description: str
    parameters: dict[str, Any]

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def signature(self) -> str:
        props = self.parameters.get("properties", {})
        required = set(self.parameters.get("required", []))
        parts = [p if p in required else f"{p}?" for p in props]
        return f"{self.name}({', '.join(parts)})"


def _obj(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required}


TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        "list_files", READ,
        "Proje klasöründeki dosya ve klasörleri ağaç biçiminde listeler. "
        ".git, .venv, node_modules gibi klasörler atlanır.",
        _obj({
            "path": {"type": "string", "description": "Proje köküne göre klasör yolu (varsayılan '.')"},
            "depth": {"type": "integer", "description": "En fazla derinlik (1-6, varsayılan 2)"},
        }, []),
    ),
    ToolSpec(
        "read_file", READ,
        "Bir metin dosyasını satır numaralarıyla okur. Büyük dosyalarda "
        "start_line/end_line ile aralık iste.",
        _obj({
            "path": {"type": "string", "description": "Proje köküne göre dosya yolu"},
            "start_line": {"type": "integer", "description": "İlk satır (1'den başlar)"},
            "end_line": {"type": "integer", "description": "Son satır (dahil)"},
        }, ["path"]),
    ),
    ToolSpec(
        "search_files", READ,
        "Dosya içeriklerinde düzenli ifade (regex) arar; 'yol:satır: metin' "
        "biçiminde sonuç döndürür.",
        _obj({
            "pattern": {"type": "string", "description": "Python regex deseni"},
            "path": {"type": "string", "description": "Aranacak klasör (varsayılan '.')"},
            "glob": {"type": "string", "description": "Dosya adı filtresi, örn. '*.py'"},
            "ignore_case": {"type": "boolean", "description": "Büyük/küçük harf duyarsız (varsayılan true)"},
        }, ["pattern"]),
    ),
    ToolSpec(
        "find_files", READ,
        "Glob deseniyle dosya bulur, örn. '**/*.py' veya 'src/**/test_*.py'.",
        _obj({
            "pattern": {"type": "string", "description": "Glob deseni"},
        }, ["pattern"]),
    ),
    ToolSpec(
        "write_file", WRITE,
        "Yeni dosya oluşturur veya bir dosyanın TÜM içeriğini yeniden yazar. "
        "Küçük değişiklikler için edit_file kullan.",
        _obj({
            "path": {"type": "string", "description": "Proje köküne göre dosya yolu"},
            "content": {"type": "string", "description": "Dosyanın yeni tam içeriği"},
        }, ["path", "content"]),
    ),
    ToolSpec(
        "edit_file", WRITE,
        "Dosyada old_string metnini new_string ile değiştirir. old_string "
        "dosyada birebir (girinti dahil) ve TEK kez geçmelidir; tüm "
        "geçişler için replace_all=true ver.",
        _obj({
            "path": {"type": "string", "description": "Proje köküne göre dosya yolu"},
            "old_string": {"type": "string", "description": "Değiştirilecek mevcut metin"},
            "new_string": {"type": "string", "description": "Yerine yazılacak metin"},
            "replace_all": {"type": "boolean", "description": "Tüm geçişleri değiştir"},
        }, ["path", "old_string", "new_string"]),
    ),
    ToolSpec(
        "run_command", EXEC,
        "Proje kökünde bir kabuk komutu çalıştırır (Windows'ta PowerShell). "
        "Çıktı ve çıkış kodu döner. Etkileşimli veya sonsuza dek çalışan "
        "komutlar (sunucu başlatma vb.) çalıştırma.",
        _obj({
            "command": {"type": "string", "description": "Çalıştırılacak komut"},
            "timeout_seconds": {"type": "integer", "description": "Zaman aşımı (varsayılan ayardan)"},
        }, ["command"]),
    ),
    ToolSpec(
        "install_program", EXEC,
        "Projenin ihtiyaç duyduğu, bilgisayarda eksik bir programı kurar (winget/npm ile, "
        "yalnız bilinen listeden: git, python, uv, node, pnpm, yarn, go, rust, dotnet, java). "
        "Ayara göre sorulmadan kurulur ya da kullanıcıya sorulur. Kurulumu run_command ile "
        "kendin yapmaya çalışma.",
        _obj({
            "name": {"type": "string", "description": "Program adı, örn. 'pnpm', 'node', 'go'"},
            "reason": {"type": "string", "description": "Neden gerekli (kullanıcıya gösterilir)"},
        }, ["name"]),
    ),
    ToolSpec(
        "update_todos", META,
        "Çok adımlı işler için görev listesini günceller. Her çağrıda listenin "
        "TAMAMINI gönder; aynı anda yalnızca bir görev in_progress olmalı.",
        _obj({
            "todos": {
                "type": "array",
                "items": _obj({
                    "content": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
                }, ["content", "status"]),
            },
        }, ["todos"]),
    ),
]
SPEC_BY_NAME = {s.name: s for s in TOOL_SPECS}
READ_ONLY_SPECS = [s for s in TOOL_SPECS if s.kind in (READ, META)]


# ---- yardımcılar -------------------------------------------------------------


def truncate_middle(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = int(limit * 0.6)
    tail = limit - head
    dropped = len(text) - limit
    return (
        text[:head]
        + f"\n\n… [{dropped} karakter kısaltıldı] …\n\n"
        + text[-tail:]
    )


def is_binary(data: bytes) -> bool:
    return b"\x00" in data[:8192]


@dataclass
class TextFile:
    """Diskten okunan metin; satır sonları modele '\\n' olarak gösterilir."""

    text: str          # '\n' normalize edilmiş içerik
    encoding: str
    newline: str       # '\r\n' veya '\n'
    bom: bool = False

    def to_disk(self, text_lf: str) -> bytes:
        body = text_lf.replace("\r\n", "\n")
        if self.newline == "\r\n":
            body = body.replace("\n", "\r\n")
        data = body.encode(self.encoding)
        if self.bom:
            data = b"\xef\xbb\xbf" + data
        return data


def decode_bytes(data: bytes) -> TextFile:
    bom = data.startswith(b"\xef\xbb\xbf")
    if bom:
        data = data[3:]
    for enc in ("utf-8", "cp1254"):
        try:
            raw = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raw, enc = data.decode("latin-1"), "latin-1"
    newline = "\r\n" if "\r\n" in raw else "\n"
    return TextFile(raw.replace("\r\n", "\n"), enc, newline, bom)


def make_diff(before: str | None, after: str | None, rel_path: str,
              context: int = 3) -> str:
    a = (before or "").splitlines(keepends=True)
    b = (after or "").splitlines(keepends=True)
    diff = difflib.unified_diff(
        a, b,
        fromfile="/dev/null" if before is None else f"a/{rel_path}",
        tofile="/dev/null" if after is None else f"b/{rel_path}",
        n=context,
    )
    out = []
    for line in diff:
        out.append(line if line.endswith("\n") else line + "\n")
    return "".join(out)


def diff_stats(diff: str) -> tuple[int, int]:
    added = removed = 0
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed


# ---- çalışma alanı -------------------------------------------------------------


class Workspace:
    """Proje kökü ve güvenli yol çözümleme."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ToolError(f"Proje klasörü bulunamadı: {root}")

    def resolve(self, path: str | None, for_write: bool = False) -> Path:
        if path is None or not str(path).strip():
            raise ToolError("Yol (path) boş olamaz.")
        p = Path(str(path).strip())
        if not p.is_absolute():
            p = self.root / p
        rp = p.resolve()
        if rp != self.root and not rp.is_relative_to(self.root):
            raise ToolError(
                f"'{path}' proje klasörünün dışında; erişim engellendi."
            )
        if for_write:
            parts = rp.relative_to(self.root).parts
            if parts and parts[0].lower() == ".git":
                raise ToolError(".git klasörüne doğrudan yazılamaz.")
        return rp

    def rel(self, p: Path) -> str:
        r = p.resolve().relative_to(self.root).as_posix()
        return r or "."

    def git_branch(self) -> str | None:
        head = self.root / ".git" / "HEAD"
        try:
            text = head.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if text.startswith("ref:"):
            return text.split("/", 2)[-1]
        return text[:10]

    def project_memory(self, limit: int = 20_000) -> tuple[str | None, str]:
        """Proje talimatlarını döndürür: EVREN.md varsa YALNIZ o; yoksa AGENTS.md,
        o da yoksa CLAUDE.md.

        EVREN.md varken AGENTS.md eklenmez: uzun, "ZORUNLU" adımlarla dolu bir
        AGENTS.md küçük modelleri asıl işten uzaklaştırıyordu (2026-10-17 ölçüm:
        tek satırlık iş 23 adım sürdü). EVREN.md kısa ve EVREN ajanına özel tutulur.
        """
        names = next(([n] for n in ("EVREN.md", "AGENTS.md", "CLAUDE.md")
                      if (self.root / n).is_file()), [])
        parts: list[str] = []
        used: list[str] = []
        budget = limit
        for name in names:
            try:
                data = (self.root / name).read_bytes()[:limit * 2]
            except OSError:
                continue
            text = decode_bytes(data).text.strip()
            if not text or budget <= 0:
                continue
            chunk = text[:budget]
            parts.append(f"## {name}\n{chunk}" if len(names) > 1 else chunk)
            used.append(name)
            budget -= len(chunk)
        if not parts:
            return None, ""
        return " + ".join(used), "\n\n".join(parts)


def _walk(root: Path, start: Path):
    """IGNORED_DIRS'i atlayarak dosyaları sıralı gezer."""
    for dirpath, dirnames, filenames in os.walk(start):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in IGNORED_DIRS and not d.endswith(".egg-info")
        )
        for name in sorted(filenames):
            yield Path(dirpath) / name


# ---- değişiklik ve komut sonuçları -------------------------------------------------


@dataclass
class FileChange:
    """Onay öncesi hazırlanan dosya değişikliği (diff önizlemesiyle)."""

    rel_path: str
    abs_path: Path
    before: str | None          # None → yeni dosya
    after: str                  # '\n' normalize
    diff: str
    file_meta: TextFile | None = None

    @property
    def is_new(self) -> bool:
        return self.before is None

    @property
    def stats(self) -> tuple[int, int]:
        return diff_stats(self.diff)

    def summary(self) -> str:
        added, removed = self.stats
        verb = "Oluşturulacak" if self.is_new else "Düzenlenecek"
        return f"{verb}: {self.rel_path} (+{added} −{removed})"


@dataclass
class CommandResult:
    command: str
    exit_code: int | None
    output: str
    duration: float
    timed_out: bool = False
    cancelled: bool = False

    def to_text(self, limit: int = DEFAULT_OUTPUT_LIMIT) -> str:
        if self.cancelled:
            head = "Komut kullanıcı tarafından durduruldu."
        elif self.timed_out:
            head = f"Komut zaman aşımına uğradı ({self.duration:.0f} sn) ve sonlandırıldı."
        else:
            head = f"Çıkış kodu: {self.exit_code} ({self.duration:.1f} sn)"
        body = truncate_middle(self.output.strip(), limit) or "(çıktı yok)"
        return f"{head}\n{body}"


def find_project_venv(root: Path) -> Path | None:
    """Projedeki sanal ortamın betik klasörü (.venv/Scripts veya .venv/bin)."""
    for name in (".venv", "venv", "env"):
        for sub in ("Scripts", "bin"):
            d = root / name / sub
            if (d / "python.exe").exists() or (d / "python").exists():
                return d
    return None


def project_env(root: Path) -> dict[str, str]:
    """Komut ortamı: UTF-8 çıktı + varsa projenin sanal ortamı PATH'in başında."""
    env = dict(os.environ)
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    venv_bin = find_project_venv(root)
    if venv_bin is not None:
        env["VIRTUAL_ENV"] = str(venv_bin.parent)
        env["PATH"] = str(venv_bin) + os.pathsep + env.get("PATH", "")
    return env


def shell_argv(command: str) -> list[str]:
    if os.name == "nt":
        prefix = (
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
            "$OutputEncoding=[System.Text.Encoding]::UTF8; "
        )
        return ["powershell.exe", "-NoProfile", "-NonInteractive",
                "-Command", prefix + command]
    return ["/bin/bash", "-lc", command]


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True, timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# ---- araç kutusu -------------------------------------------------------------------


class ToolBox:
    """Araç uygulamaları. İzin kararı çağırana (AgentRunner) aittir."""

    def __init__(self, workspace: Workspace, command_timeout: int = 120,
                 output_limit: int = DEFAULT_OUTPUT_LIMIT,
                 skip_file: Callable[[str], bool] | None = None):
        self.ws = workspace
        self.command_timeout = command_timeout
        self.output_limit = output_limit
        # Aramada içeriği okunmayacak dosyalar (ör. .env): göreli yol → True
        self.skip_file = skip_file

    # -- okuma ----------------------------------------------------------------

    def list_files(self, path: str = ".", depth: int = 2) -> str:
        base = self.ws.resolve(path or ".")
        if not base.is_dir():
            raise ToolError(f"'{path}' bir klasör değil.")
        depth = max(1, min(int(depth or 2), 6))
        lines: list[str] = []
        truncated = False

        def visit(d: Path, level: int) -> None:
            nonlocal truncated
            try:
                entries = sorted(d.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except OSError:
                return
            for e in entries:
                if len(lines) >= MAX_LIST_ENTRIES:
                    truncated = True
                    return
                if e.is_dir():
                    if e.name in IGNORED_DIRS or e.name.endswith(".egg-info"):
                        continue
                    lines.append("  " * level + e.name + "/")
                    if level + 1 < depth:
                        visit(e, level + 1)
                else:
                    lines.append("  " * level + e.name)

        visit(base, 0)
        head = f"{self.ws.rel(base)}/"
        if truncated:
            lines.append(f"… (ilk {MAX_LIST_ENTRIES} kayıt gösterildi)")
        return head + "\n" + ("\n".join(lines) if lines else "(boş klasör)")

    def load_text(self, abs_path: Path) -> TextFile:
        try:
            size = abs_path.stat().st_size
        except OSError as exc:
            raise ToolError(f"Dosya okunamadı: {exc}") from exc
        if size > MAX_READ_BYTES:
            raise ToolError(
                f"Dosya çok büyük ({size // 1024} KB); en fazla "
                f"{MAX_READ_BYTES // 1024} KB okunur."
            )
        data = abs_path.read_bytes()
        if is_binary(data):
            raise ToolError("İkili (binary) dosya okunamaz.")
        return decode_bytes(data)

    def read_file(self, path: str, start_line: int | None = None,
                  end_line: int | None = None) -> str:
        p = self.ws.resolve(path)
        if not p.is_file():
            raise ToolError(f"Dosya bulunamadı: {path}")
        tf = self.load_text(p)
        lines = tf.text.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        total = len(lines)
        start = max(1, int(start_line or 1))
        end = int(end_line) if end_line else min(total, start + MAX_READ_LINES - 1)
        end = min(end, total, start + MAX_READ_LINES - 1)
        width = len(str(end)) if end else 1
        body = "\n".join(
            f"{i:>{width}}\t{lines[i - 1]}" for i in range(start, end + 1)
        )
        note = ""
        if end < total:
            note = f"\n… (dosya {total} satır; {start}-{end} gösterildi)"
        if total == 0:
            return f"{self.ws.rel(p)} (boş dosya)"
        return f"{self.ws.rel(p)} ({total} satır)\n{body}{note}"

    def search_files(self, pattern: str, path: str = ".", glob: str | None = None,
                     ignore_case: bool = True) -> str:
        if not pattern:
            raise ToolError("Arama deseni (pattern) boş olamaz.")
        flags = re.IGNORECASE if ignore_case in (None, True) else 0
        try:
            rx = re.compile(pattern, flags)
        except re.error:
            rx = re.compile(re.escape(pattern), flags)
        base = self.ws.resolve(path or ".")
        files = [base] if base.is_file() else _walk(self.ws.root, base)
        results: list[str] = []
        skipped = 0
        for f in files:
            if glob and not fnmatch.fnmatch(f.name, glob):
                continue
            if self.skip_file is not None and self.skip_file(self.ws.rel(f)):
                skipped += 1
                continue
            try:
                if f.stat().st_size > MAX_SEARCH_FILE_BYTES:
                    continue
                data = f.read_bytes()
            except OSError:
                continue
            if is_binary(data):
                continue
            text = decode_bytes(data).text
            for no, line in enumerate(text.split("\n"), 1):
                if rx.search(line):
                    results.append(f"{self.ws.rel(f)}:{no}: {line.strip()[:240]}")
                    if len(results) >= MAX_SEARCH_RESULTS:
                        results.append(f"… (ilk {MAX_SEARCH_RESULTS} eşleşme)")
                        return "\n".join(results)
        note = f"\n({skipped} gizli bilgi dosyası aramaya dahil edilmedi)" if skipped else ""
        return ("\n".join(results) if results else "Eşleşme bulunamadı.") + note

    def find_files(self, pattern: str) -> str:
        if not pattern:
            raise ToolError("Glob deseni boş olamaz.")
        pat = pattern.replace("\\", "/").lstrip("./") if pattern not in (".", "./") else "*"
        found: list[str] = []
        for f in _walk(self.ws.root, self.ws.root):
            rel = self.ws.rel(f)
            if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(f.name, pat) or (
                pat.startswith("**/") and fnmatch.fnmatch(rel, pat[3:])
            ):
                found.append(rel)
                if len(found) >= MAX_LIST_ENTRIES:
                    found.append(f"… (ilk {MAX_LIST_ENTRIES} dosya)")
                    break
        return "\n".join(found) if found else "Dosya bulunamadı."

    # -- yazma (hazırla → uygula) ------------------------------------------------

    def prepare_write(self, path: str, content: str) -> FileChange:
        if content is None:
            raise ToolError("content parametresi gerekli.")
        p = self.ws.resolve(path, for_write=True)
        if p.is_dir():
            raise ToolError(f"'{path}' bir klasör; dosya yolu verin.")
        if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
            raise ToolError("İçerik 2 MB sınırını aşıyor.")
        meta = None
        before = None
        if p.exists():
            meta = self.load_text(p)
            before = meta.text
        after = content.replace("\r\n", "\n")
        if before is not None and before == after:
            raise ToolError("Yeni içerik mevcut dosyayla aynı; değişiklik yok.")
        rel = self.ws.rel(p)
        return FileChange(rel, p, before, after, make_diff(before, after, rel), meta)

    def prepare_edit(self, path: str, old_string: str, new_string: str,
                     replace_all: bool = False) -> FileChange:
        p = self.ws.resolve(path, for_write=True)
        if not p.is_file():
            raise ToolError(
                f"Dosya bulunamadı: {path}. Yeni dosya için write_file kullanın."
            )
        if not old_string:
            raise ToolError("old_string boş olamaz.")
        if old_string == new_string:
            raise ToolError("old_string ile new_string aynı.")
        meta = self.load_text(p)
        old = old_string.replace("\r\n", "\n")
        new = (new_string or "").replace("\r\n", "\n")
        count = meta.text.count(old)
        if count == 0:
            raise ToolError(
                "old_string dosyada bulunamadı. Dosyayı read_file ile yeniden "
                "okuyup metni birebir (girinti dahil) kopyalayın."
            )
        if count > 1 and not replace_all:
            raise ToolError(
                f"old_string dosyada {count} kez geçiyor. Daha fazla bağlam "
                "ekleyerek tekil yapın veya replace_all=true verin."
            )
        after = meta.text.replace(old, new) if replace_all else meta.text.replace(old, new, 1)
        rel = self.ws.rel(p)
        return FileChange(rel, p, meta.text, after, make_diff(meta.text, after, rel), meta)

    def apply_change(self, change: FileChange) -> None:
        # Hazırlık sonrası dosya dışarıdan değiştiyse üzerine yazma.
        if change.before is None:
            if change.abs_path.exists():
                raise ToolError("Dosya onay beklenirken oluşturulmuş; işlem iptal edildi.")
        else:
            current = self.load_text(change.abs_path).text if change.abs_path.exists() else None
            if current != change.before:
                raise ToolError(
                    "Dosya onay beklenirken değişmiş; üzerine yazılmadı. "
                    "Dosyayı yeniden okuyun."
                )
        meta = change.file_meta or TextFile("", "utf-8", "\n")
        change.abs_path.parent.mkdir(parents=True, exist_ok=True)
        change.abs_path.write_bytes(meta.to_disk(change.after))

    # -- komut ------------------------------------------------------------------------

    def run_command(self, command: str, timeout_seconds: int | None = None,
                    cancel: Any = None,
                    on_output: Callable[[str], None] | None = None) -> CommandResult:
        if not command or not command.strip():
            raise ToolError("Komut boş olamaz.")
        timeout = int(timeout_seconds or self.command_timeout)
        timeout = max(1, min(timeout, 1800))
        env = project_env(self.ws.root)
        start = time.monotonic()
        try:
            proc = subprocess.Popen(
                shell_argv(command), cwd=str(self.ws.root),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            raise ToolError(f"Komut başlatılamadı: {exc}") from exc

        chunks: list[str] = []

        def reader() -> None:
            assert proc.stdout is not None
            for raw in iter(proc.stdout.readline, b""):
                text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
                chunks.append(text)
                if on_output:
                    try:
                        on_output(text)
                    except Exception:
                        pass

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        timed_out = cancelled = False
        while proc.poll() is None:
            if cancel is not None and getattr(cancel, "cancelled", False):
                cancelled = True
                _kill_tree(proc)
                break
            if time.monotonic() - start > timeout:
                timed_out = True
                _kill_tree(proc)
                break
            time.sleep(0.05)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        t.join(timeout=2)
        return CommandResult(
            command=command,
            exit_code=proc.returncode,
            output="".join(chunks),
            duration=time.monotonic() - start,
            timed_out=timed_out,
            cancelled=cancelled,
        )


def validate_todos(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        raise ToolError("todos bir liste olmalı.")
    out = []
    for item in raw[:50]:
        if not isinstance(item, dict) or not str(item.get("content", "")).strip():
            raise ToolError("Her görevin 'content' alanı olmalı.")
        status = item.get("status", "pending")
        if status not in ("pending", "in_progress", "completed"):
            status = "pending"
        out.append({"content": str(item["content"]).strip()[:300], "status": status})
    return out


def revert_file(root: Path, rel_path: str, before: str | None, after: str | None,
                force: bool = False) -> str:
    """Kayıtlı bir değişikliği geri alır. Dosya sonradan değiştiyse force ister."""
    ws = Workspace(root)
    p = ws.resolve(rel_path, for_write=True)
    current: str | None = None
    meta: TextFile | None = None
    if p.exists():
        data = p.read_bytes()
        meta = decode_bytes(data)
        current = meta.text
    if not force and current != after:
        raise ToolError(
            f"{rel_path} değişiklikten sonra yeniden düzenlenmiş; geri alma "
            "sonraki düzenlemeleri de silecek."
        )
    if before is None:
        if p.exists():
            p.unlink()
        return f"{rel_path} silindi (ajan tarafından oluşturulmuştu)."
    meta = meta or TextFile("", "utf-8", "\n")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(meta.to_disk(before))
    return f"{rel_path} önceki haline döndürüldü."
