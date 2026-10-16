"""Metin tabanlı araç protokolü.

Yerel function calling desteği doğrulanmamış veya reddeden modeller için
araç çağrıları düz metin içinde şu blokla yapılır:

    <arac_cagrisi>
    {"name": "read_file", "arguments": {"path": "src/app.py"}}
    </arac_cagrisi>

Sonuçlar modele `<arac_sonucu ad="..." durum="ok|hata">` bloklarıyla döner.
Model çıktısı hiçbir zaman doğrudan komut olarak çalıştırılmaz; bloklar
ayrıştırılır, araç adı ve parametreleri doğrulanır ve izin politikasından
geçer.
"""
from __future__ import annotations

import json
import re
import uuid

OPEN = "<arac_cagrisi>"
CLOSE = "</arac_cagrisi>"
_BLOCK_RE = re.compile(r"<arac_cagrisi>\s*(.*?)\s*</arac_cagrisi>", re.S)
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$")


def new_call_id() -> str:
    return "call_" + uuid.uuid4().hex[:12]


def _parse_block(body: str) -> tuple[str | None, dict | None, str | None]:
    body = _FENCE_RE.sub("", body.strip())
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        return None, None, f"Araç bloğu geçerli JSON değil: {exc.msg} (konum {exc.pos})"
    if not isinstance(data, dict) or not isinstance(data.get("name"), str):
        return None, None, "Araç bloğunda 'name' alanı eksik."
    args = data.get("arguments", {})
    if isinstance(args, str):
        try:
            args = json.loads(args) if args.strip() else {}
        except json.JSONDecodeError:
            return data["name"], None, "'arguments' geçerli JSON nesnesi değil."
    if not isinstance(args, dict):
        return data["name"], None, "'arguments' bir JSON nesnesi olmalı."
    return data["name"], args, None


def parse_tool_calls(text: str) -> tuple[str, list[dict], list[str]]:
    """Metinden araç çağrılarını ayıklar.

    Dönüş: (bloklar çıkarılmış metin, çağrılar, hata mesajları).
    Çağrı: {"id", "name", "arguments" (JSON metni)}.
    """
    calls: list[dict] = []
    errors: list[str] = []
    for m in _BLOCK_RE.finditer(text or ""):
        name, args, err = _parse_block(m.group(1))
        if err:
            errors.append(err)
            continue
        calls.append({
            "id": new_call_id(),
            "name": name,
            "arguments": json.dumps(args, ensure_ascii=False),
        })
    clean = _BLOCK_RE.sub("", text or "")
    # Kapanmamış blok: model yarıda kesildi
    if OPEN in clean:
        idx = clean.index(OPEN)
        errors.append("Araç bloğu kapanmadan yanıt bitti; bloğu tamamlayarak tekrar gönder.")
        clean = clean[:idx]
    return clean.strip(), calls, errors


def display_text(text: str) -> str:
    """Akış sırasında gösterim için: tamam ve yarım blokları gizler."""
    clean = _BLOCK_RE.sub("", text or "")
    if OPEN in clean:
        clean = clean[: clean.index(OPEN)]
    # Açılış etiketinin ilk karakterleri gelmişse onları da gizle
    for i in range(len(OPEN) - 1, 0, -1):
        if clean.endswith(OPEN[:i]):
            clean = clean[:-i]
            break
    return clean


def render_call(name: str, arguments: str) -> str:
    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        args = {}
    payload = json.dumps({"name": name, "arguments": args}, ensure_ascii=False)
    return f"{OPEN}\n{payload}\n{CLOSE}"


def render_result(name: str, content: str, ok: bool) -> str:
    status = "ok" if ok else "hata"
    return f'<arac_sonucu ad="{name}" durum="{status}">\n{content}\n</arac_sonucu>'
