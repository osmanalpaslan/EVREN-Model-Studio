"""Mesajdaki görselleri sağlayıcı biçimine çevirir (Qt'siz).

Ajan iç mesajlarında görseller metne yazılmaz; kullanıcı mesajında
`_images: [dosya yolu, ...]` iç alanı olarak taşınır (to_api_messages).
İstemci, isteği göndermeden hemen önce bu yolları okuyup base64 veri
adresine çevirir:
- EVREN / OpenAI Chat: content = [{"type":"text"}, {"type":"image_url"}]
  (EVREN'de gerçek API ile doğrulandı, 2026-10-19)
- OpenAI Responses: input_text + input_image (doğrulanmadı)
- Anthropic: text + image{source: base64} (doğrulanmadı)
Dosya silinmişse görsel yerine kısa bir not gönderilir.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
        ".webp": "image/webp", ".bmp": "image/bmp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def load_image(path: str) -> tuple[str, str] | None:
    """(mime, base64) veya dosya yok / çok büyükse None."""
    p = Path(path)
    mime = MIME.get(p.suffix.lower())
    try:
        if mime is None or not p.is_file() or p.stat().st_size > MAX_IMAGE_BYTES:
            return None
        return mime, base64.b64encode(p.read_bytes()).decode("ascii")
    except OSError:
        return None


def missing_note(path: str) -> str:
    return f"[ekli görsel artık bulunamadı: {Path(path).name}]"


def chat_content(text: str, images: list[str]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    notes = []
    for path in images:
        img = load_image(path)
        if img is None:
            notes.append(missing_note(path))
            continue
        mime, b64 = img
        parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
    body = "\n".join([text] + notes) if notes else text
    return [{"type": "text", "text": body or "(görsel)"}] + parts


def expand_chat_images(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`_images` taşıyan mesajları OpenAI Chat çok parçalı içeriğe çevirir."""
    out = []
    for m in messages:
        imgs = m.get("_images")
        if imgs and m.get("role") == "user":
            m = {**m, "content": chat_content(m.get("content") or "", imgs)}
        out.append(m)
    return out


def responses_content(text: str, images: list[str]) -> list[dict[str, Any]]:
    parts = chat_content(text, images)
    out = []
    for p in parts:
        if p["type"] == "text":
            out.append({"type": "input_text", "text": p["text"]})
        else:
            out.append({"type": "input_image", "image_url": p["image_url"]["url"]})
    return out


def anthropic_blocks(text: str, images: list[str]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    notes = []
    for path in images:
        img = load_image(path)
        if img is None:
            notes.append(missing_note(path))
            continue
        mime, b64 = img
        blocks.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}})
    body = "\n".join([text] + notes) if notes else text
    if body:
        blocks.append({"type": "text", "text": body})
    return blocks or [{"type": "text", "text": "(görsel)"}]
