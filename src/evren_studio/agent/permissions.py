"""Çalışma modları ve izin politikası.

Modlar:
- plan      : yalnızca okuma araçları; dosya değiştirme ve komut YOK.
- onayli    : okuma serbest; her dosya değişikliği ve komut onaya sunulur.
- otomatik  : okuma ve dosya değişiklikleri serbest; komutlar yine onaylı.

Komutlar hiçbir modda kendiliğinden çalışmaz: kullanıcı ya tek tek onaylar
ya da "bu oturumda hep izin ver" ile belirli bir komut önekine izin verir.
Zincirleme/yönlendirme içeren komutlar (; && || | > ` $( ) önek iznine
rağmen her zaman sorulur.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field

from .tools import EXEC, META, READ, WRITE

MODES: dict[str, str] = {
    "plan": "Plan",
    "onayli": "Onaylı",
    "otomatik": "Otomatik düzenleme",
}
MODE_HINTS: dict[str, str] = {
    "plan": "Yalnızca okur ve plan çıkarır; dosya değiştirmez, komut çalıştırmaz.",
    "onayli": "Her dosya değişikliği ve komut için onayınızı ister.",
    "otomatik": "Dosyaları onaysız düzenler; komutlar için yine onay ister.",
}
DEFAULT_MODE = "onayli"

_CHAIN_TOKENS = (";", "&&", "||", "|", ">", "<", "`", "$(", "\n")
_MULTI_WORD_TOOLS = {
    "git", "python", "py", "pip", "npm", "npx", "pnpm", "yarn", "node",
    "dotnet", "uv", "cargo", "go", "poetry", "pytest",
}


class Decision(enum.Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


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


def is_chained(command: str) -> bool:
    return any(tok in command for tok in _CHAIN_TOKENS)


@dataclass
class SessionPermissions:
    """Kullanıcının bu oturum için verdiği kalıcı izinler (bellekte)."""

    allow_all_writes: bool = False
    command_prefixes: set[str] = field(default_factory=set)

    def command_allowed(self, command: str) -> bool:
        if is_chained(command):
            return False
        cmd = command.strip()
        for prefix in self.command_prefixes:
            if cmd == prefix or cmd.startswith(prefix + " "):
                return True
        return False


def decide(mode: str, kind: str, perms: SessionPermissions,
           command: str | None = None) -> tuple[Decision, str]:
    if kind in (READ, META):
        return Decision.ALLOW, ""
    if mode == "plan":
        what = "dosya değiştirilemez" if kind == WRITE else "komut çalıştırılamaz"
        return Decision.DENY, (
            f"Plan modunda {what}. Önce planı sun; kullanıcı modu "
            "değiştirirse uygulayabilirsin."
        )
    if kind == WRITE:
        if mode == "otomatik" or perms.allow_all_writes:
            return Decision.ALLOW, ""
        return Decision.ASK, ""
    if kind == EXEC:
        if command and perms.command_allowed(command):
            return Decision.ALLOW, ""
        return Decision.ASK, ""
    return Decision.DENY, "Bilinmeyen araç türü."
