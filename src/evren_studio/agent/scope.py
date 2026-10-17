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
