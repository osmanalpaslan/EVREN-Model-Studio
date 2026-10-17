"""Çalışma modları ve izin politikası (Claude Code'un modlarına denk).

| Anahtar  | Ad                       | Sormadan                         | Sorar / engeller                     |
|----------|--------------------------|----------------------------------|--------------------------------------|
| manuel   | Manuel                   | okuma                            | her düzenleme ve komut               |
| kabul    | Düzenlemeleri kabul et   | okuma + proje içi düzenleme      | komutlar, korumalı dosyalar          |
| plan     | Plan                     | okuma                            | düzenleme ve komut ENGELLİ           |
| auto     | Otomatik                 | her şey (okuma, düzenleme, komut)| hiçbir şey sorulmaz                  |

Otomatik mod (kullanıcı kararı, 2026-10-17): HİÇBİR işlem için onay
istenmez — riskli/tanınmayan komut, korumalı dosyaya yazma ve gizli dosya
okuma dahil. commands.py sınıflandırması yalnız bilgi amaçlı gerekçe olarak
karta yazılır. Proje klasörü dışına yazma yine engellidir (tools.py). Model
çıktısı hiçbir modda doğrudan çalıştırılmaz; araçlardan geçer.

Manuel ve "Düzenlemeleri kabul et" modlarında geçerli korumalar:
- Korumalı dosyalara (.env, anahtar dosyaları, .vscode/, .github/workflows/ …)
  yazma her zaman sorulur.
- Gizli bilgi taşıyabilecek dosyaları (.env, *.pem, id_rsa …) OKUMAK her zaman
  sorulur; içerikleri EVREN'e gönderilir.

ESKİ ANAHTARLAR: 0.2.0'da "onayli" = manuel, "otomatik" = kabul anlamındaydı.
`normalize_mode` eski değeri asla daha yetkili bir moda çevirmez (bkz. R-14).
"""
from __future__ import annotations

import enum
import fnmatch
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from .commands import classify_command
from .tools import EXEC, META, READ, WRITE

MODES: dict[str, str] = {
    "manuel": "Manuel",
    "kabul": "Düzenlemeleri kabul et",
    "plan": "Plan",
    "auto": "Otomatik",
}
MODE_HINTS: dict[str, str] = {
    "manuel": "Her dosya değişikliği ve komut için onayınızı ister.",
    "kabul": "Proje içindeki dosyaları onaysız düzenler; komutlar için onay ister.",
    "plan": "Yalnızca okur ve plan çıkarır; dosya değiştirmez, komut çalıştırmaz.",
    "auto": "Hiçbir şey için onay istemez: tüm düzenlemeler, komutlar ve dosya "
            "okumaları onaysız çalışır.",
}
DEFAULT_MODE = "manuel"
_LEGACY = {"onayli": "manuel", "otomatik": "kabul"}

# Yazılması her zaman sorulan yollar (proje köküne göre, küçük harf)
PROTECTED_WRITE = (
    ".env", ".env.*", "*.pem", "*.key", "*.pfx", "*.p12", "id_rsa*", "id_ed25519*",
    ".npmrc", ".pypirc", ".gitconfig", ".vscode/*", ".idea/*", ".claude/*",
    ".github/workflows/*", ".kilocode/*", ".cursor/*",
)
# Okunması her zaman sorulan (gizli bilgi taşıyabilecek) dosyalar
SENSITIVE_READ = (
    ".env", ".env.*", "*.pem", "*.key", "*.pfx", "*.p12", "id_rsa*", "id_ed25519*",
    ".npmrc", ".pypirc", "*credentials*.json", "*.kdbx",
)
# .env.example gibi örnek dosyalar gizli sayılmaz
_SAFE_EXAMPLES = ("*.example", "*.sample", "*.template", "*.dist")


class Decision(enum.Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


def normalize_mode(mode: str | None) -> str:
    """Eski/bilinmeyen değerleri güvenli moda çevirir (asla daha yetkiliye değil)."""
    if mode in MODES:
        return mode
    return _LEGACY.get(mode or "", DEFAULT_MODE)


def _matches(rel_path: str, patterns: tuple[str, ...]) -> bool:
    rel = rel_path.replace("\\", "/").lower()
    while rel.startswith("./"):
        rel = rel[2:]
    name = PurePosixPath(rel).name
    for pat in patterns:
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(name, pat):
            return True
        if pat.endswith("/*") and (rel + "/").startswith(pat[:-1]):
            return True
    return False


def is_protected_write(rel_path: str) -> bool:
    return _matches(rel_path, PROTECTED_WRITE)


def is_sensitive_read(rel_path: str) -> bool:
    return _matches(rel_path, SENSITIVE_READ) and not _matches(rel_path, _SAFE_EXAMPLES)


# Geriye uyumluluk: önceki sürümde burada tanımlıydı
def command_prefix(command: str) -> str:
    from .commands import command_prefix as _cp

    return _cp(command)


def is_chained(command: str) -> bool:
    from .commands import is_chained as _ic

    return _ic(command)


@dataclass
class SessionPermissions:
    """Kullanıcının bu oturum için verdiği kalıcı izinler (yalnız bellekte)."""

    allow_all_writes: bool = False
    allow_sensitive_reads: bool = False
    allow_installs: bool = False       # "bu oturumda program kurulumlarına izin ver"
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
           command: str | None = None, path: str | None = None,
           root=None) -> tuple[Decision, str]:
    """(karar, gerekçe). Gerekçe arayüzde ve modele giden mesajda kullanılır."""
    mode = normalize_mode(mode)
    if kind == META:
        return Decision.ALLOW, ""
    if mode == "auto" and kind in (READ, WRITE, EXEC):
        # Kullanıcı kararı (2026-10-17): Otomatik modda hiçbir işlem sorulmaz.
        if kind == EXEC and command:
            return Decision.ALLOW, f"Otomatik mod: {classify_command(command, root).reason}"
        return Decision.ALLOW, ""
    if kind == READ:
        if path and is_sensitive_read(path) and not perms.allow_sensitive_reads:
            return Decision.ASK, "Gizli bilgi taşıyabilecek dosya; içeriği EVREN'e gönderilecek."
        return Decision.ALLOW, ""
    if mode == "plan":
        what = "dosya değiştirilemez" if kind == WRITE else "komut çalıştırılamaz"
        return Decision.DENY, (
            f"Plan modunda {what}. Önce planı sun; kullanıcı modu "
            "değiştirirse uygulayabilirsin."
        )
    if kind == WRITE:
        if path and is_protected_write(path):
            return Decision.ASK, "Korumalı dosya (yapılandırma veya gizli bilgi); her modda sorulur."
        if mode in ("kabul", "auto") or perms.allow_all_writes:
            return Decision.ALLOW, ""
        return Decision.ASK, ""
    if kind == EXEC:
        if command and perms.command_allowed(command):
            return Decision.ALLOW, "oturum izni"
        if mode == "auto" and command:
            verdict = classify_command(command, root)
            if verdict.safe:
                return Decision.ALLOW, f"Otomatik mod: {verdict.reason}"
            return Decision.ASK, f"Otomatik mod sordu: {verdict.reason}"
        return Decision.ASK, ""
    return Decision.DENY, "Bilinmeyen araç türü."
