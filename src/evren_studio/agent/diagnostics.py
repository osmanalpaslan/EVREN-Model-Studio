"""Hata bekçisi: ajan bir dosyayı düzenledikten hemen sonra kesin hataları bulup modele geri verir.

Neden (kullanıcı hedefi 2026-10-19: "proje geliştirirken sorunsuz, doğru uygulama"): EVREN
motorları yazdığı kodu denetlemeden "bitti" diyebiliyor. Düzenleme sonucuna hata eklenince
model aynı turda düzeltir.

İki katman:
1. Yerleşik (her zaman, Serena gerekmez): Python sözdizimi (compile), JSON, TOML ve Node
   varsa JavaScript sözdizimi (`node --check`).
2. Serena (yalnız Serena bu turda sunuluyorsa): dil sunucusu hataları (pyright, tsserver…).
   YALNIZ kesin hatalar: önem = Error ve güvenilir kodlar. Eksik paket/çözülemeyen import
   uyarıları ATILIR — Serena'nın ortamında projenin bağımlılıkları kurulu olmayabilir; zayıf model
   bu yanlış alarmla import'u silebilir (ölçüm 2026-10-19: requests "could not be resolved").

Hiçbir denetim hatası turu düşürmez; denetim yapılamazsa sessizce atlanır.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

MAX_PROBLEMS = 8
# pyright: anlamı kesin, yanlış alarm olasılığı düşük hatalar
PYRIGHT_CODES = {"reportUndefinedVariable", "reportCallIssue", "reportRedeclaration",
                 "reportSelfClsParameterName", "reportIndexIssue", "reportUnhashable",
                 "reportNoOverloadImplementation"}
# Bilerek DIŞARIDA: reportArgumentType/reportAssignmentType/reportAttributeAccessIssue —
# tip açıklaması olmayan Python kodunda çıkarıma dayanır, yanlış alarm verebilir.
# Bağımlılık eksikliğinden doğan (projenin değil ortamın) hataları
_ENV_NOISE = ("could not be resolved", "cannot find module", "unresolved import", "no module named",
              "import cycles", "is not a known attribute of module", "stub file not found")
# Kodla bildirilen ortam hataları: C# eksik paket/başvuru (restore yapılmamış olabilir), TS modül yok
_ENV_NOISE_CODES = {"CS0246", "CS0234", "CS0012", "CS0400", "2307", "2792", "7016"}


def builtin_problems(rel_path: str, text: str | None, root: Path | None = None) -> list[str]:
    """Hızlı, kesin yerel denetimler. Dönüş: "satır N: ileti" listesi (boş = sorun yok)."""
    if text is None:
        return []
    ext = os.path.splitext(rel_path)[1].lower()
    if ext in (".py", ".pyw"):
        try:
            compile(text, rel_path, "exec", dont_inherit=True)
        except SyntaxError as exc:
            return [f"satır {exc.lineno or '?'}: sözdizimi hatası: {exc.msg}"]
        except (ValueError, OverflowError, RecursionError):
            return []
    elif ext == ".json":
        try:
            json.loads(text)
        except ValueError as exc:
            line = getattr(exc, "lineno", "?")
            return [f"satır {line}: geçersiz JSON: {getattr(exc, 'msg', exc)}"]
    elif ext == ".toml":
        try:
            import tomllib

            tomllib.loads(text)
        except Exception as exc:  # tomllib.TOMLDecodeError
            return [f"geçersiz TOML: {exc}"]
    elif ext in (".js", ".mjs", ".cjs") and root is not None:
        return _node_check(Path(root) / rel_path)
    return []


# ---- ruff (Madde 20 A2, 2026-11-11; docs/knowledge/REPO_TARAMASI_2026-11.md) ------------------------------------------
# Yerleşik denetim Python'da yalnız sözdizimini görüyordu; modellerin en sık hatası (eksik import / tanımsız ad) ancak
# Serena açıkken yakalanıyordu. ruff (Astral, MIT) aynı işi Serena'sız, milisaniyede yapar. YALNIZ kesin hatalar
# (flake8'in CI'da "gerçek hata" diye kullandığı küme): E9 sözdizimi/G-Ç, F63 karşılaştırma/assert hataları, F7 yapı
# (döngü dışı break/continue, fonksiyon dışı return…), F82 tanımsız ad. Stil/kullanılmayan import BİLEREK yok (gürültü).
# Yıldızlı içe aktarmada ruff F821 değil F405 verir (seçili değil) → yanlış alarm yok (test sınar).
RUFF_SELECT = "E9,F63,F7,F82"
_ruff_cache: list[str | None] = []


def ruff_bin() -> str | None:
    """Kurulum paketinde `_internal/tools/ruff.exe`; kaynaktan çalışırken ortamdaki ruff. Yoksa None (denetim atlanır)."""
    import sys

    if _ruff_cache:
        return _ruff_cache[0]
    found = None
    base = getattr(sys, "_MEIPASS", None)
    if base and (Path(base) / "tools" / "ruff.exe").is_file():
        found = str(Path(base) / "tools" / "ruff.exe")
    if found is None:
        try:
            from ruff.__main__ import find_ruff_bin

            found = str(find_ruff_bin())
        except Exception:
            found = shutil.which("ruff")
    _ruff_cache.append(found)
    return found


def ruff_problems(rel_path: str, text: str) -> list[str]:
    """Dosya diske DEĞİL standart girdiden verilir (--isolated: projenin ruff ayarı karışmaz). Hata → sessizce []."""
    exe = ruff_bin()
    if not exe or not text.strip():
        return []
    try:
        r = subprocess.run([exe, "check", "--isolated", "--no-cache", "--select", RUFF_SELECT, "--output-format", "json",
                            "--stdin-filename", rel_path, "-"], input=text, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
        items = json.loads(r.stdout or "[]")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []
    out = []
    for d in items if isinstance(items, list) else []:
        code, msg = d.get("code") or "", d.get("message") or ""
        row = (d.get("location") or {}).get("row", "?")
        if code == "F821":
            msg = f"tanımsız ad ({msg}) — içe aktarma ya da tanım eksik"
        out.append(f"satır {row}: {code} {msg}")
    return out[:MAX_PROBLEMS]


def lint_problems(rel_path: str, text: str | None) -> list[str]:
    """Sözdizimi TEMİZKEN çalışan ikinci katman (şimdilik yalnız Python: ruff)."""
    if text is None or os.path.splitext(rel_path)[1].lower() not in (".py", ".pyw"):
        return []
    return ruff_problems(rel_path, text)


def merge(first: list[str], second: list[str]) -> list[str]:
    """İki kaynağın bulguları; aynı satır için ikincisininki atılır (model aynı hatayı iki kez görmesin)."""
    import re

    rows = {m.group(1) for p in first if (m := re.match(r"satır (\d+)", p))}
    extra = [p for p in second if not ((m := re.match(r"satır (\d+)", p)) and m.group(1) in rows)]
    return (first + extra)[:MAX_PROBLEMS]


def _node_check(path: Path) -> list[str]:
    node = shutil.which("node") or (r"C:\Program Files\nodejs\node.exe"
                                    if os.name == "nt" and Path(r"C:\Program Files\nodejs\node.exe").exists()
                                    else None)
    if not node or not path.exists():
        return []
    try:
        r = subprocess.run([node, "--check", str(path)], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=20,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if r.returncode == 0:
        return []
    lines = [ln for ln in (r.stderr or "").splitlines() if ln.strip()]
    loc = next((ln for ln in lines if str(path.name) in ln and ":" in ln), "")
    msg = next((ln for ln in lines if "Error" in ln), lines[-1] if lines else "sözdizimi hatası")
    line = loc.rsplit(":", 1)[-1] if loc else "?"
    return [f"satır {line}: {msg.strip()}"]


def serena_problems(raw: str) -> list[str]:
    """Serena get_diagnostics_for_file çıktısından (JSON: dosya → önem → sembol → [teşhis])
    yalnız kesin hataları seçer."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    out: list[str] = []
    for _file, by_sev in (data or {}).items():
        if not isinstance(by_sev, dict):
            continue
        for sev, by_sym in by_sev.items():
            if str(sev).lower() != "error" or not isinstance(by_sym, dict):
                continue
            for sym, items in by_sym.items():
                for d in items or []:
                    msg = " ".join(str(d.get("message", "")).split())
                    code = str(d.get("code") or "")
                    src = str(d.get("source") or "").lower()
                    if any(n in msg.lower() for n in _ENV_NOISE) or code in _ENV_NOISE_CODES:
                        continue
                    if src == "pyright" and code and code not in PYRIGHT_CODES:
                        continue
                    line = ((d.get("range") or {}).get("start") or {}).get("line")
                    where = f"satır {line + 1}" if isinstance(line, int) else "satır ?"
                    inside = f" ({sym} içinde)" if sym and sym != "<file>" else ""
                    out.append(f"{where}{inside}: {msg}" + (f" [{code}]" if code else ""))
    return out


def note(rel_path: str, problems: list[str]) -> str:
    """Araç sonucuna eklenecek uyarı (sorun yoksa boş)."""
    if not problems:
        return ""
    shown = problems[:MAX_PROBLEMS]
    more = f"\n- … ve {len(problems) - len(shown)} hata daha" if len(problems) > len(shown) else ""
    return (f"\n\n⚠ HATA BEKÇİSİ — {rel_path} düzenlemeden sonra denetlendi, {len(problems)} kesin hata var. "
            "Görevi bitirmeden önce düzelt (dosyayı yeniden oku, edit_file ile düzelt):\n"
            + "\n".join(f"- {p}" for p in shown) + more)
