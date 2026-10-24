"""F6 / E4 kullanıcı kuralları (hook'lar; Qt'siz): proje klasöründeki `.evren/kurallar.json`.

    {"kurallar": [
      {"olay": "duzenleme_sonrasi", "eslesme": "*.py", "komut": "python -m py_compile {dosya}", "zaman_asimi": 60},
      {"olay": "komut_oncesi", "eslesme": "git push*", "komut": "echo push yasak & exit 1"},
      {"olay": "tur_sonu", "komut": "python -m unittest discover -s tests"}
    ]}

- duzenleme_sonrasi: ajan bir dosyayı yazınca/düzenleyince (eslesme dosya adına uyarsa) çalışır; çıktısı araç
  sonucuna not olarak eklenir. {dosya} → değişen dosyanın proje göreli yolu.
- komut_oncesi: ajanın komutu (eslesme komut metnine uyarsa) ÇALIŞMADAN önce çalışır; çıkış kodu 0 değilse ajanın
  komutu engellenir ve çıktı gerekçe olarak modele gider.
- tur_sonu: ajan dosya değiştirdiği bir turu bitirmek üzereyken çalışır; başarısızsa model bir kez dürtülür
  (test bekçisi gibi), başarılıysa yalnız durum notu.
Güvenlik: yalnız proje klasöründe çalışır, her komutun zaman aşımı vardır (varsayılan 60, en çok 600 sn); kural dosyası
ilk kullanımda ve İÇERİĞİ HER DEĞİŞTİĞİNDE kullanıcıya bir kez sorulur (onaylanan özet ayarda saklanır). Yerleşik
bekçilerle (test, hata) çakışmaz: onlardan sonra ve ayrı not olarak çalışır.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

RULES_FILE = ".evren/kurallar.json"
EVENTS = {"duzenleme_sonrasi": "düzenlemeden sonra", "komut_oncesi": "komuttan önce", "tur_sonu": "tur bitince"}
DEFAULT_TIMEOUT = 60
MAX_TIMEOUT = 600
OUT_LIMIT = 3000
MAX_RULES = 20


class RulesError(Exception):
    pass


@dataclass
class Rule:
    event: str
    command: str
    pattern: str = "*"
    timeout: int = DEFAULT_TIMEOUT

    def describe(self) -> str:
        return f"{EVENTS.get(self.event, self.event)}" + (f" ({self.pattern})" if self.pattern != "*" else "") + \
            f": {self.command}"


def load(root: Path) -> tuple[list[Rule], str]:
    """(kurallar, dosya özeti). Dosya yoksa ([], ""). Bozuksa RulesError (arayüz kullanıcıya gösterir)."""
    f = Path(root) / RULES_FILE
    if not f.is_file():
        return [], ""
    raw = f.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()[:16]
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise RulesError(f"{RULES_FILE} okunamadı: {exc}") from exc
    items = data.get("kurallar") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise RulesError(f'{RULES_FILE}: "kurallar" listesi yok.')
    rules = []
    for i, it in enumerate(items[:MAX_RULES], 1):
        if not isinstance(it, dict) or it.get("olay") not in EVENTS or not str(it.get("komut") or "").strip():
            raise RulesError(f"{RULES_FILE}: {i}. kural geçersiz (olay: {', '.join(EVENTS)}; komut gerekli).")
        t = int(it.get("zaman_asimi") or DEFAULT_TIMEOUT)
        rules.append(Rule(it["olay"], str(it["komut"]).strip(), str(it.get("eslesme") or "*"),
                          max(1, min(t, MAX_TIMEOUT))))
    return rules, digest


def _run(root: Path, command: str, timeout: int) -> tuple[int, str]:
    from .tools import project_env, shell_argv

    try:
        r = subprocess.run(shell_argv(command), cwd=str(root), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=project_env(Path(root)),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        return r.returncode, out[-OUT_LIMIT:]
    except subprocess.TimeoutExpired:
        return -9, f"zaman aşımı ({timeout} sn)"
    except OSError as exc:
        return -1, f"çalıştırılamadı: {exc}"


@dataclass
class UserRules:
    root: Path
    rules: list[Rule]
    runner: object = None              # testte sahte: (root, komut, zaman_aşımı) → (kod, çıktı)
    log: list[str] = field(default_factory=list)

    def _exec(self, rule: Rule, command: str) -> tuple[int, str]:
        self.log.append(command)
        fn = self.runner or _run
        return fn(self.root, command, rule.timeout)

    def after_edit(self, rel_path: str) -> str:
        notes = []
        name = Path(rel_path).name
        for r in self.rules:
            if r.event != "duzenleme_sonrasi" or not (fnmatch.fnmatch(name, r.pattern)
                                                      or fnmatch.fnmatch(rel_path, r.pattern)):
                continue
            code, out = self._exec(r, r.command.replace("{dosya}", f'"{rel_path}"'))
            notes.append(f"\n\n# Kullanıcı kuralı (düzenlemeden sonra: {r.command}) → çıkış {code}\n{out or '(çıktı yok)'}")
        return "".join(notes)

    def before_command(self, command: str) -> tuple[bool, str]:
        """(engelle, gerekçe)."""
        for r in self.rules:
            if r.event != "komut_oncesi" or not fnmatch.fnmatch(command.strip().lower(), r.pattern.lower()):
                continue
            code, out = self._exec(r, r.command)
            if code != 0:
                return True, (f"Kullanıcı kuralı bu komutu engelledi (komuttan önce: {r.command} → çıkış {code}).\n"
                              f"{out or '(çıktı yok)'}")
        return False, ""

    def turn_end(self) -> tuple[bool, str]:
        """(başarısız, not). Birden çok kural varsa ilk başarısız olan raporlanır."""
        notes = []
        for r in self.rules:
            if r.event != "tur_sonu":
                continue
            code, out = self._exec(r, r.command)
            if code != 0:
                return True, (f"Kullanıcının tur sonu kuralı başarısız: `{r.command}` → çıkış {code}.\n{out}\n"
                              "Sorunu gider ve kuralın geçtiğini göster; gideremiyorsan nedenini açıkla.")
            notes.append(f"{r.command}: geçti")
        return False, "; ".join(notes)

    def has(self, event: str) -> bool:
        return any(r.event == event for r in self.rules)
