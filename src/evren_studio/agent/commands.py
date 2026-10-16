"""Otomatik mod için KURAL TABANLI komut sınıflandırıcı.

Karar sırası (her alt komut için; `;`, `&&`, `||`, `|` ile ayrılır):
1. Riskli kalıp → güvenli DEĞİL (gerekçesiyle): silme, git geçmişini
   değiştirme/gönderme, ağdan indirip çalıştırma, sistem ayarı, paket kurma,
   süreç sonlandırma, ortam değişkeni kalıcılaştırma …
2. Proje dışına çıkan yol (mutlak yol kök dışında veya `..`) → güvenli değil.
3. Dosyaya yönlendirme (`>`, `>>`), komut ikamesi (`` ` ``, `$(`) → güvenli değil.
4. Güvenli listede (salt okuma, test, derleme, lint) → güvenli.
5. Diğer her şey → "tanınmayan komut" → güvenli değil (kullanıcıya sorulur).

Bu bir güvenlik garantisi değildir; yalnızca açıkça zararsız bilinen komutların
onaysız çalışmasını sağlar. Liste bilerek dar tutulur: şüphede sor.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

_CHAIN_TOKENS = (";", "&&", "||", "|", ">", "<", "`", "$(", "\n")
_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")
_MULTI_WORD_TOOLS = {
    "git", "python", "py", "pip", "npm", "npx", "pnpm", "yarn", "node",
    "dotnet", "uv", "cargo", "go", "poetry", "pytest",
}


@dataclass(frozen=True)
class Verdict:
    safe: bool
    reason: str


# ---- riskli kalıplar (alt komut başına, küçük harf) --------------------------

RISKY: list[tuple[re.Pattern, str]] = [(re.compile(p, re.I), r) for p, r in [
    (r"^(remove-item|rm|ri|del|erase|rd|rmdir)\b", "dosya/klasör silme"),
    (r"^(format|diskpart|mkfs|fdisk)\b", "disk biçimlendirme"),
    (r"^git\s+push\b", "uzak depoya gönderme (git push)"),
    (r"^git\s+(reset\s+--hard|clean\b|checkout\s+--|checkout\s+\.|restore\b|rebase\b|"
     r"filter-branch|reflog\s+expire|gc\s+--prune|stash\s+(drop|clear)|branch\s+-[dD]\b|"
     r"tag\s+-d|commit\s+--amend|push)", "git geçmişini/çalışma alanını geri döndürülemez değiştirme"),
    (r"^(iex|invoke-expression)\b|\|\s*(iex|invoke-expression)\b", "metni komut olarak çalıştırma"),
    (r"^(curl|wget|iwr|irm|invoke-webrequest|invoke-restmethod|start-bitstransfer)\b", "ağ isteği / indirme"),
    (r"^(ssh|scp|sftp|ftp|telnet|nc|ncat)\b", "uzak bağlantı"),
    (r"^(start-process|saps|start)\b", "yeni süreç başlatma"),
    (r"^(stop-process|kill|taskkill|spps)\b", "süreç sonlandırma"),
    (r"^(shutdown|restart-computer|stop-computer|logoff)\b", "bilgisayarı kapatma/yeniden başlatma"),
    (r"^(set-executionpolicy|reg|regedit|bcdedit|netsh|sc|schtasks|set-service|"
     r"new-service|set-itemproperty|new-itemproperty)\b", "sistem ayarı değiştirme"),
    (r"^(setx)\b|\[environment\]::setenvironmentvariable", "kalıcı ortam değişkeni"),
    (r"^(pip|pip3)\s+(install|uninstall|download)\b|^(python|py)(\.exe)?\s+-m\s+pip\s+(install|uninstall|download)\b",
     "paket kurma/kaldırma"),
    (r"^(npm|pnpm|yarn)\s+(install|i|add|remove|uninstall|publish|update|upgrade|link)\b|^npx\s+-y\b",
     "paket kurma/yayınlama"),
    (r"^(winget|choco|scoop|msiexec|apt|apt-get|brew)\b", "sistem paketi kurma"),
    (r"^(npm|pnpm|yarn)\s+publish\b|^(twine|dotnet\s+nuget\s+push|cargo\s+publish)\b", "paket yayınlama"),
    (r"^(runas|sudo|gsudo)\b", "yönetici yetkisi"),
    (r"^(copy-item|cp|copy|move-item|mv|move|rename-item|ren|set-content|sc|add-content|"
     r"out-file|new-item|ni|mkdir|md|clear-content)\b", "dosya sistemi değiştirme (komutla)"),
    (r"^(python|py)(\.exe)?\s+-c\b|^node\s+-e\b|^(powershell|pwsh|cmd)(\.exe)?\b", "satır içi kod çalıştırma"),
]]

# ---- güvenli liste (alt komutun başlangıcı, küçük harf) ------------------------

SAFE_PREFIXES: tuple[str, ...] = (
    # git — salt okuma
    "git status", "git diff", "git log", "git show", "git branch", "git rev-parse",
    "git ls-files", "git blame", "git grep", "git remote -v", "git stash list",
    "git describe", "git shortlog", "git tag", "git config --get", "git config --list",
    # dosya/klasör görüntüleme
    "dir", "ls", "get-childitem", "gci", "tree", "get-content", "gc", "type", "cat",
    "select-string", "sls", "findstr", "get-location", "pwd", "test-path", "resolve-path",
    "get-item", "gi", "measure-object", "get-filehash", "where", "where.exe", "get-command",
    "echo", "write-output", "write-host", "get-date", "hostname", "whoami", "get-childitem",
    # python
    "python -m pytest", "py -m pytest", "pytest", "python -m unittest", "py -m unittest",
    "python --version", "python -v", "py --version", "python -m pip list", "python -m pip show",
    "python -m pip freeze", "pip list", "pip show", "pip freeze", "python -m compileall",
    "python -m mypy", "mypy", "python -m ruff check", "ruff check", "ruff format --check",
    "python -m black --check", "black --check", "flake8", "python -m flake8", "pylint",
    "python -m pylint", "python -m py_compile", "python -m evren_studio --version",
    # node
    "node --version", "node -v", "npm --version", "npm -v", "npm ls", "npm list", "npm test",
    "npm run test", "npm run lint", "npm run build", "npm run typecheck", "npx tsc --noemit",
    "npx eslint", "npx prettier --check", "pnpm test", "pnpm run test", "pnpm lint", "yarn test",
    # .NET / rust / go
    "dotnet --info", "dotnet --version", "dotnet build", "dotnet test", "dotnet restore",
    "cargo build", "cargo test", "cargo check", "cargo clippy", "cargo fmt --check",
    "go build", "go test", "go vet", "go version", "gofmt -l",
)


def is_chained(command: str) -> bool:
    return any(tok in command for tok in _CHAIN_TOKENS)


def command_prefix(command: str) -> str:
    """'Bu oturumda hep izin ver' için önerilen komut öneki."""
    tokens = command.strip().split()
    if not tokens:
        return ""
    first = tokens[0].lower()
    if first in _MULTI_WORD_TOOLS and len(tokens) > 1:
        if tokens[1] == "-m" and len(tokens) > 2:
            return " ".join(tokens[:3])
        return " ".join(tokens[:2])
    return tokens[0]


def _norm(segment: str) -> str:
    s = re.sub(r"\s+", " ", segment.strip()).lower()
    s = re.sub(r"^\.\\\.venv\\scripts\\|^\.venv[\\/](scripts|bin)[\\/]", "", s)
    return re.sub(r"^(python|py|pip|node|npm)\.exe\b", r"\1", s)


def _escapes_root(segment: str, root: Path | None) -> str | None:
    for tok in re.findall(r"""(?:"[^"]*"|'[^']*'|\S+)""", segment):
        t = tok.strip("\"'")
        if not t or t.startswith("-"):
            continue
        if ".." in t.replace("\\", "/").split("/"):
            return f"proje dışına çıkan yol ({t})"
        win = PureWindowsPath(t)
        is_abs = win.is_absolute() or t.startswith("/") or t.startswith("~") or t.startswith("$env:")
        if is_abs:
            if root is None:
                return f"mutlak yol ({t})"
            try:
                inside = Path(t).expanduser().resolve().is_relative_to(Path(root).resolve())
            except (OSError, ValueError):
                inside = False
            if not inside:
                return f"proje dışındaki yol ({t})"
    return None


def classify_segment(segment: str, root: Path | None = None) -> Verdict:
    s = _norm(segment)
    if not s:
        return Verdict(True, "boş")
    for rx, reason in RISKY:
        if rx.search(s):
            return Verdict(False, reason)
    if "`" in s or "$(" in s:
        return Verdict(False, "komut ikamesi")
    if re.search(r"(?<![-\w])>{1,2}|(?<![-\w])<", s):
        return Verdict(False, "dosyaya yönlendirme")
    esc = _escapes_root(segment, root)
    if esc:
        return Verdict(False, esc)
    for prefix in SAFE_PREFIXES:
        if s == prefix or s.startswith(prefix + " "):
            return Verdict(True, f"güvenli liste ({prefix})")
    return Verdict(False, "güvenli listede olmayan komut")


def classify_command(command: str, root: Path | None = None) -> Verdict:
    """Tüm alt komutlar güvenliyse güvenli; ilk güvensiz alt komutun gerekçesi döner."""
    if not command or not command.strip():
        return Verdict(False, "boş komut")
    if "\n" in command.strip():
        return Verdict(False, "çok satırlı komut")
    segments = [p for p in _SPLIT_RE.split(command) if p.strip()]
    reasons = []
    for seg in segments:
        v = classify_segment(seg, root)
        if not v.safe:
            return Verdict(False, f"{v.reason}: “{seg.strip()[:60]}”")
        reasons.append(v.reason)
    return Verdict(True, reasons[0] if len(reasons) == 1 else "tüm alt komutlar güvenli listede")
