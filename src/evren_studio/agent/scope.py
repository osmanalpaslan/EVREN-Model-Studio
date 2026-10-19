"""Kapsam denetimi: bir turda yapılan dosya değişiklikleri kullanıcının isteğiyle uyumlu mu?

Kullanıcı bildirimi (2026-10-17): "simgeyi değiştir" dediğinde ajan, istenmediği
hâlde arayüz tasarımını değiştirip simgeleri başka yerlere de ekledi. Sistem
istemindeki kural (prompts.AGENT_RULES) bunu çoğu zaman önler ama zayıf modeller
kurala her zaman uymuyor (bkz. LOOP_ANALYSIS.md). Bu modül tur bitince hızlı bir
modele isteği + değişiklikleri gösterip kapsam dışı olanları işaretletir; arayüz
uyarı kartı ve tek tıkla geri alma sunar. ONAY İSTEMEZ, yalnız bildirir.

Qt kullanmaz; arayüz bunu arka plan iş parçacığında çağırır (R-04).
"""
from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from typing import Any

MAX_DIFF_LINES = 60           # dosya başına modele gösterilen fark satırı
MAX_TOTAL_CHARS = 14_000      # tüm farkların üst sınırı
MAX_REQUESTS = 3              # bağlam için son kullanıcı mesajı sayısı

SCOPE_SYSTEM = (
    "Sen bir kod değişikliği kapsam denetçisisin. Kullanıcının isteği ve bir kod "
    "ajanının bu istek için yaptığı dosya değişiklikleri verilecek. Görevin: istenmemiş, "
    "isteğin kapsamı DIŞINDA kalan değişiklikleri bulmak (ör. istenmeyen tasarım/arayüz "
    "değişikliği, isteğe ilgisiz dosyalar, istenmemiş ek özellikler). İsteği yerine "
    "getirmek için GEREKLİ olan destek değişiklikleri (ilgili test, içe aktarma, isteğin "
    "doğal parçası olan belge güncellemesi) kapsam İÇİDİR. Emin değilsen kapsam içi say. "
    "Yalnız şu JSON'u yaz, başka hiçbir şey yazma:\n"
    '{"kapsam_disi": [{"dosya": "<yol>", "neden": "<kısa Türkçe gerekçe>"}]}\n'
    'Kapsam dışı yoksa: {"kapsam_disi": []}'
)


@dataclass
class OutOfScope:
    path: str
    reason: str


# ---- adı geçen ama projede olmayan dosyalar (tur başı denetimi) -------------------------
# Zorluk paketi (2026-10-19): "ayarlar.yaml'daki timeout'u 30 yap" denince dosya yoktu;
# modeller benzer ayar.ini'yi sormadan değiştirdi. İstem kuralı tek başına yetmedi.

FILE_EXTS = ("py|pyw|js|mjs|cjs|ts|tsx|jsx|json|jsonc|yaml|yml|toml|ini|cfg|conf|env|md|txt|csv|tsv|"
             "html|htm|css|scss|xml|sql|sh|bat|cmd|ps1|log|java|kt|cs|go|rs|c|cc|cpp|h|hpp|php|rb|"
             "vue|svelte|lock|gradle|properties|ipynb|r|lua|dart|swift")
_MENTION_RE = re.compile(r"(?<![\w.@/\\-])((?:[\w.\-]+[/\\])*[\w\-]+(?:\.[\w\-]+)*\.(?:" + FILE_EXTS + r"))(?![\w.])",
                         re.IGNORECASE)
_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build", ".idea", ".vs"}


def mentioned_files(text: str) -> list[str]:
    """Kullanıcı metninde uzantısıyla anılan dosya yolları (URL'ler hariç)."""
    text = re.sub(r"https?://\S+", " ", text or "")
    seen: list[str] = []
    for m in _MENTION_RE.finditer(text):
        name = m.group(1).replace("\\", "/").strip("./")
        if name and name not in seen:
            seen.append(name)
    return seen


# Dosya adının yakınında bu fiiller varsa kullanıcı dosyayı OLUŞTURMAK istiyor demektir:
# uyarı verilmez. 2026-10-19 ölçümü: "kelime_say.py yaz", "EVREN_PLAN.md dosyasına ... yaz"
# isteklerinde uyarı, zayıf modelleri dosyayı yazmak yerine soru sormaya itti.
_CREATE_RE = re.compile(r"\b(yaz|oluştur|olustur|ekle|yarat|hazırla|hazirla|kaydet|üret|uret|aç\s+yeni|yeni)\w*",
                        re.IGNORECASE)
CREATE_WINDOW = 70


def wants_creation(text: str, name: str) -> bool:
    """`name` metinde oluşturma fiiliyle birlikte mi anılıyor? (adın ±CREATE_WINDOW karakteri)"""
    low = text.replace("\\", "/")
    for m in re.finditer(re.escape(name), low, re.IGNORECASE):
        around = low[max(0, m.start() - 25): m.end() + CREATE_WINDOW]
        if _CREATE_RE.search(around):
            return True
    return False


def missing_mentions(text: str, root, limit: int = 20000) -> list[str]:
    """Metinde anılan ama proje klasöründe (yol veya ad olarak) bulunmayan dosyalar.
    Oluşturulması istenen dosyalar (wants_creation) sayılmaz."""
    from pathlib import Path

    names = [n for n in mentioned_files(text) if not wants_creation(text, n)]
    if not names:
        return []
    root = Path(root)
    pending = [n for n in names if not (root / n).exists()]
    if not pending:
        return []
    basenames = {n.rsplit("/", 1)[-1].lower(): n for n in pending}
    found: set[str] = set()
    count = 0
    stack = [root]
    while stack and count < limit and len(found) < len(basenames):
        d = stack.pop()
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for e in entries:
            count += 1
            if e.is_dir():
                if e.name not in _SKIP_DIRS:
                    stack.append(e)
            elif e.name.lower() in basenames:
                found.add(e.name.lower())
    return [n for b, n in basenames.items() if b not in found]


def missing_hint(missing: list[str]) -> str:
    names = ", ".join(f"`{n}`" for n in missing)
    return ("# Uygulama denetimi (bu tur)\n"
            f"Kullanıcının mesajında adı geçen şu dosya(lar) proje klasöründe BULUNAMADI: {names}. "
            "Kullanıcı açıkça yeni dosya oluşturmanı istemiyorsa: bu dosyanın yerine benzer başka bir "
            "dosyayı değiştirme ve kendiliğinden yeni dosya oluşturma; dosyanın bulunamadığını, varsa "
            "benzer adayları yaz ve hangisini kastettiğini kullanıcıya sor.")


# ---- test dosyası koruması -----------------------------------------------------------
# Zorluk paketi `celiski` (2026-10-19) ve LOOP_ANALYSIS #1: çelişen testlerde bazı modeller
# test dosyasını değiştirip "geçti" diyor. Kullanıcı testlerle ilgili bir değişiklik
# istemediyse var olan test dosyasına yazma, modele anında uyarı + kullanıcıya tur notu.

_TEST_VERBS = r"(ekle|yaz|oluştur|olustur|güncelle|guncelle|değiştir|degistir|düzenle|duzenle|düzelt|duzelt|sil|kaldır|kaldir|yeniden)"
_TEST_INTENT = re.compile(
    rf"test\w*\s+(?:\S+\s+){{0,2}}{_TEST_VERBS}|{_TEST_VERBS}\w*\s+(?:\S+\s+){{0,2}}test", re.IGNORECASE)


def user_allows_test_edits(text: str) -> bool:
    """Kullanıcı test dosyalarını değiştirmeyi/eklemeyi açıkça istedi mi? ("test ekle", "testleri güncelle")"""
    return bool(_TEST_INTENT.search(text or ""))


def is_test_path(rel_path: str) -> bool:
    p = rel_path.replace("\\", "/").lower()
    parts = p.split("/")
    name = parts[-1]
    if any(d in ("tests", "test", "__tests__", "spec", "specs") for d in parts[:-1]):
        return True
    return (name.startswith("test_") or name.endswith(("_test.py", "_test.go", "_test.js", "_test.ts"))
            or ".test." in name or ".spec." in name)


TEST_EDIT_WARNING = ("\n⚠ Var olan bir TEST dosyasını değiştirdin ({path}). Kullanıcı testlerin değiştirilmesini "
                     "istemedi; testi değiştirerek geçirmek isteği karşılamaz. Bu değişikliği geri al (dosyayı "
                     "eski hâline döndür). Testler birbiriyle veya istekle çelişiyorsa durup kullanıcıya hangisinin "
                     "doğru olduğunu sor.")


def _diff(path: str, before: str | None, after: str | None) -> str:
    a = (before or "").splitlines()
    b = (after or "").splitlines()
    if before is None:
        head = f"YENİ DOSYA: {path}"
    elif after is None:
        head = f"SİLİNEN DOSYA: {path}"
    else:
        head = f"DEĞİŞEN DOSYA: {path}"
    lines = list(difflib.unified_diff(a, b, lineterm="", n=1))[2:]
    shown = lines[:MAX_DIFF_LINES]
    more = len(lines) - len(shown)
    body = "\n".join(shown) + (f"\n… (+{more} satır daha)" if more > 0 else "")
    return f"{head}\n{body}"


def build_messages(requests: list[str], changes: list[dict[str, Any]]) -> list[dict[str, str]]:
    """requests: son kullanıcı mesajları (eskiden yeniye); changes: {path, before_text, after_text}."""
    reqs = [r.strip() for r in requests if r and r.strip()][-MAX_REQUESTS:]
    if not reqs:
        reqs = ["(istek metni yok)"]
    ctx = ""
    if len(reqs) > 1:
        ctx = "Önceki kullanıcı mesajları (bağlam):\n" + "\n".join(f"- {r[:600]}" for r in reqs[:-1]) + "\n\n"
    # Aynı dosyanın turdaki ilk "önce" ve son "sonra" hâli
    merged: dict[str, list] = {}
    for c in changes:
        p = c["path"]
        if p not in merged:
            merged[p] = [c.get("before_text"), c.get("after_text")]
        else:
            merged[p][1] = c.get("after_text")
    parts, total = [], 0
    for p, (before, after) in merged.items():
        d = _diff(p, before, after)
        if total + len(d) > MAX_TOTAL_CHARS:
            parts.append(f"DEĞİŞEN DOSYA: {p}\n(fark çok uzun; yalnız adı gösterildi)")
            continue
        parts.append(d)
        total += len(d)
    user = (f"{ctx}KULLANICININ İSTEĞİ:\n{reqs[-1][:2000]}\n\n"
            f"AJANIN YAPTIĞI DEĞİŞİKLİKLER ({len(merged)} dosya):\n\n" + "\n\n".join(parts))
    return [{"role": "system", "content": SCOPE_SYSTEM}, {"role": "user", "content": user}]


def parse_response(text: str, paths: set[str]) -> list[OutOfScope]:
    """Model yanıtından kapsam dışı dosyalar (yalnız gerçekten değişen yollar kabul edilir)."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out: list[OutOfScope] = []
    norm = {p.replace("\\", "/").lower(): p for p in paths}
    for item in data.get("kapsam_disi") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("dosya") or "").replace("\\", "/").lower().lstrip("./")
        real = norm.get(key) or next((v for k, v in norm.items() if k.endswith("/" + key) or key.endswith("/" + k)), None)
        if real and all(o.path != real for o in out):
            out.append(OutOfScope(real, str(item.get("neden") or "").strip()[:300]))
    return out


def check(client: Any, model: str, requests: list[str], changes: list[dict[str, Any]],
          extra_body: dict | None = None) -> list[OutOfScope]:
    """Kapsam denetimini çalıştırır (arka plan iş parçacığında)."""
    if not changes:
        return []
    kwargs = {"extra_body": extra_body} if extra_body else {}
    result = client.chat(model, build_messages(requests, changes), stream=False, max_tokens=1500, **kwargs)
    return parse_response(result.content or "", {c["path"] for c in changes})
