"""İddia bekçisi (Madde 22 C2, 2026-11-13; Qt'siz): ajanın son yanıtındaki iddiaları bu turun araç kayıtlarıyla karşılaştırır.

Neden: EVREN motorları değişiklikten sonra testi çalıştırmadan "tüm testler geçti", yazma başarısız olduğu hâlde "`x.py`
oluşturuldu" diyebiliyor (R-28: "bitti"yi istenen çıktıya bağla). Bekçi YALNIZ iki somut iddiaya bakar, kanıt yoksa
modele bir kez söyler (tur başına bir kez; koşucu `nudged`):
  1. Testlerin geçtiği: son başarılı yazmadan SONRA çıkış kodu 0 olan bir test komutu ya da test bekçisinin geçişi.
  2. Dosyanın oluşturulduğu/yazıldığı: ters tırnaklı yol diskte var mı.
Olumsuz/temkinli cümleler ("testler çalıştırılmadı", "geçmedi", "doğrulanamadı", "çalıştırmanızı öneririm") iddia
DEĞİLDİR (R-22: gereksiz tetiklenme yok).
"""
from __future__ import annotations

import re
from pathlib import Path

TEST_CMD = re.compile(r"\b(pytest|unittest|npm\s+(run\s+)?test|yarn\s+test|pnpm\s+test|dotnet\s+test|go\s+test|"
                      r"cargo\s+test|jest|vitest|mocha|phpunit|rspec)\b", re.I)
TEST_CLAIM = re.compile(r"(test\w*[^.!?\n]{0,60}?\b(geçti|geçiyor|geçmektedir|başarı(lı|yla)|yeşil|sorunsuz)|"
                        r"\b\d+\s+(test\w*\s+)?(passed|geçti)\b|\ball tests pass)", re.I)
NEGATION = re.compile(r"(geçme(di|yor|z)|geçemedi|çalıştırıl(a)?ma(dı|z)|çalıştıra(ma)?dım|doğrulan(a)?ma(dı|z)|"
                      r"doğrulay(a)?madım|yapılama(dı|z)|edilemedi|olmadı|bulunama(dı|z)|"
                      r"öneririm|önerilir|çalıştırın|çalıştırmanız|çalıştırabilirsiniz|bekleniyor|gerekir|gerekiyor|"
                      r"\bnot\b|failed|fail\b|\?)", re.I)
FILE_CLAIM = re.compile(r"(oluşturdum|oluşturuldu|oluşturulmuştur|yazdım|yazıldı|kaydettim|kaydedildi|ekledim|"
                        r"hazırladım|created|wrote)", re.I)
PATH_TOKEN = re.compile(r"`([^`\s]+\.[A-Za-z0-9]{1,6})`")
WRITE_TOOLS = {"write_file", "edit_file", "apply_patch", "multi_edit"}

TEST_NUDGE = ("⚠ İDDİA BEKÇİSİ: Yanıtında testlerin geçtiğini söylüyorsun ama bu turda (son değişiklikten sonra) "
              "başarılı bir test çalıştırması görünmüyor. Testleri şimdi çalıştır ve gerçek sonucu yaz; çalıştıramıyorsan "
              "yanıtında açıkça 'testler doğrulanmadı' de. Sonucu tahmin etme.")
FILE_NUDGE = ("⚠ İDDİA BEKÇİSİ: Yanıtında şu dosyaları oluşturduğunu/yazdığını söylüyorsun ama diskte YOKLAR: {paths}. "
              "Dosyayı gerçekten yaz ya da yanıtını düzelt.")


def current_turn(history: list[dict]) -> list[dict]:
    """Son GERÇEK kullanıcı mesajından (otomatik devam değil) sonraki mesajlar."""
    for i in range(len(history) - 1, -1, -1):
        m = history[i]
        if m.get("role") == "user" and not (m.get("meta") or {}).get("auto_continue"):
            return history[i + 1:]
    return list(history)


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s.strip()]


def _claims(regex: re.Pattern, text: str) -> list[str]:
    out = []
    for s in _sentences(text):
        if regex.search(s) and not NEGATION.search(s):
            out.append(s)
    return out


def tests_verified(turn: list[dict], gate_passed: bool = False) -> bool:
    if gate_passed:
        return True
    last_write = -1
    for i, m in enumerate(turn):
        if m.get("role") == "tool" and m.get("name") in WRITE_TOOLS and not (m.get("meta") or {}).get("error"):
            last_write = i
    for i, m in enumerate(turn):
        meta = m.get("meta") or {}
        if (i > last_write and m.get("role") == "tool" and m.get("name") == "run_command"
                and meta.get("exit_code") == 0 and TEST_CMD.search(str(meta.get("command") or ""))):
            return True
    return False


def missing_claimed_files(text: str, root: Path) -> list[str]:
    missing = []
    for s in _claims(FILE_CLAIM, text):
        for rel in PATH_TOKEN.findall(s):
            p = Path(rel)
            p = p if p.is_absolute() else Path(root) / rel
            try:
                if not p.exists() and rel not in missing:
                    missing.append(rel)
            except OSError:
                continue
    return missing


def check(content: str, turn: list[dict], root: Path, gate_passed: bool = False) -> str:
    """Kanıtsız iddia varsa modele gidecek dürtme metni, yoksa ""."""
    if _claims(TEST_CLAIM, content) and not tests_verified(turn, gate_passed):
        return TEST_NUDGE
    missing = missing_claimed_files(content, root)
    if missing:
        return FILE_NUDGE.format(paths=", ".join(f"`{p}`" for p in missing[:5]))
    return ""
