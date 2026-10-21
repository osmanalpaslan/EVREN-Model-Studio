"""Plan bekçisi: model fazlara ayırdığı bir işi bitirmeden turu kapatmasın (Qt'siz).

Neden (kullanıcı bildirimi 2026-10-21): uzun istemde model planı dosyaya yazıp bir fazı bitiriyor,
"Faz 1 tamamlandı" deyip DURUYOR; kullanıcı "devam" deyince sürdürüyor. Kök neden (analiz +
doğrulama): koşucu araçsız yanıtı plan/görev listesine bakmadan "done" sayıyordu; niyet
algılayıcısı yalnız kısa "…geçiyorum" cümlelerini yakalıyor, dürtme tur başına bir kez.

Kaynaklar (yalnız SON GERÇEK kullanıcı mesajından bu yana — eski TODO dosyaları tetiklemez, R-20):
1. update_todos ile verilen son listede pending / in_progress maddeler (yapısal, öncelikli).
2. Bu mesajdan sonra yazılan/düzenlenen, adı plana benzeyen .md/.txt dosyasındaki açık maddeler
   ("- [ ]", "[~]", "Durum: bekliyor", tabloda "bekliyor/yapılacak/⏳").
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PLAN_NUDGE_MAX = 8                 # tur başına en çok dürtme
NO_PROGRESS_STOP = 2               # art arda bu kadar ilerlemesiz denetimde dur
_PLAN_NAME = re.compile(r"(plan|faz|todo|gorev|görev|yol.?harita|roadmap|asama|aşama|checklist|surec|süreç)",
                        re.I)
_OPEN_BOX = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s*\[(?: |~|-|/)\]\s*(.+)$")
_DONE_WORDS = ("tamamlandı", "tamamlandi", "bitti", "✅", "done", "[x]")
_OPEN_WORDS = ("bekliyor", "yapılacak", "yapilacak", "devam ediyor", "sırada", "sirada", "⏳", "todo", "pending")
_STATUS_LINE = re.compile(r"durum\s*[:：]\s*(.+)$", re.I)


def is_plan_file(rel_path: str) -> bool:
    p = Path(rel_path)
    return p.suffix.lower() in (".md", ".txt") and bool(_PLAN_NAME.search(p.stem))


def open_items_in_text(text: str, limit: int = 40) -> list[str]:
    """Plan metnindeki açık maddeler (en çok `limit`)."""
    out: list[str] = []
    heading = ""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            heading = line.lstrip("#").strip()[:80]
            continue
        m = _OPEN_BOX.match(line)
        if m:
            out.append(m.group(1).strip()[:120])
        elif line.startswith("|") and line.count("|") >= 3:
            low = line.lower()
            if any(w in low for w in _OPEN_WORDS) and not any(w in low for w in _DONE_WORDS):
                cells = [c.strip() for c in line.strip("|").split("|") if c.strip()]
                out.append(" · ".join(cells[:2])[:120])
        else:
            s = _STATUS_LINE.search(line)
            if s:
                val = s.group(1).lower()
                if any(w in val for w in _OPEN_WORDS) and not any(w in val for w in _DONE_WORDS):
                    out.append((heading or line)[:120])
        if len(out) >= limit:
            break
    return out


def _is_genuine_user(m: dict) -> bool:
    return m.get("role") == "user" and not (m.get("meta") or {}).get("auto_continue")


# "Yalnız plan yaz, henüz uygulama" istekleri: plan dosyasındaki açık maddeler İSTENEN sonuçtur, iş değil.
# Zorluk paketi "planlama" görevi (2026-10-21): bekçi bu istekte ajanı planı uygulamaya itti (R-22).
_PLAN_ONLY = re.compile(
    r"kod(?:u)?\s+yazma(?![a-zçğıöşü])|uygulamaya\s+(?:başlama|baslama|geçme|gecme)(?![a-zçğıöşü])"
    r"|dosyalara\s+dokunma(?![a-zçğıöşü])|(?:sadece|yalnız|yalniz|yalnızca|yalnizca)\b[^\n]{0,80}?plan"
    r"|\b(?:only|just)\b[^\n]{0,40}?\bplan|don'?t\s+(?:implement|write\s+(?:any\s+)?code)",
    re.I)


def plan_only_request(history: list[dict]) -> bool:
    """Son gerçek kullanıcı mesajı "yalnız plan çıkar, uygulama" mı? O turda bekçi çalışmaz."""
    user = next((m for m in reversed(history) if _is_genuine_user(m)), None)
    return bool(user and _PLAN_ONLY.search(str(user.get("content") or "")))


def turn_messages(history: list[dict]) -> list[dict]:
    """Son GERÇEK kullanıcı mesajından sonraki mesajlar (özet sonrası otomatik devamlar dahil)."""
    idx = max((i for i, m in enumerate(history) if _is_genuine_user(m)), default=-1)
    return history[idx + 1:]


def open_todos(history: list[dict]) -> list[str]:
    """Bu mesajdan beri verilen SON update_todos listesindeki bitmemiş maddeler."""
    last = None
    for m in turn_messages(history):
        if m.get("role") == "tool" and m.get("name") == "update_todos":
            todos = (m.get("meta") or {}).get("todos")
            if isinstance(todos, list):
                last = todos
    if not last:
        return []
    return [str(t.get("content", ""))[:120] for t in last
            if isinstance(t, dict) and t.get("status") in ("pending", "in_progress")]


def plan_files(history: list[dict]) -> list[str]:
    """Bu mesajdan beri yazılan/düzenlenen plan benzeri dosyalar (göreli yol)."""
    seen: list[str] = []
    for m in turn_messages(history):
        if m.get("role") != "tool" or m.get("name") not in ("write_file", "edit_file"):
            continue
        meta = m.get("meta") or {}
        path = meta.get("path")
        if path and not meta.get("error") and is_plan_file(path) and path not in seen:
            seen.append(path)
    return seen


def open_items(history: list[dict], root: Path | None) -> tuple[list[str], str]:
    """(açık maddeler, kaynak). Önce görev listesi, yoksa plan dosyası."""
    todos = open_todos(history)
    if todos:
        return todos, "görev listesi (update_todos)"
    if root is None:
        return [], ""
    for rel in plan_files(history):
        try:
            text = (Path(root) / rel).read_text(encoding="utf-8", errors="replace")[:65536]
        except OSError:
            continue
        items = open_items_in_text(text)
        if items:
            return items, rel
    return [], ""


def nudge_text(items: list[str], source: str) -> str:
    shown = "\n".join(f"- {x}" for x in items[:6]) + (f"\n- … ve {len(items) - 6} madde daha" if len(items) > 6 else "")
    return ("⚠ PLAN BEKÇİSİ: Planında hâlâ açık maddeler var (" + source + "):\n" + shown + "\n\n"
            "Kullanıcıya SORMADAN sıradaki maddeye geç ve çalışmaya devam et; bitirdikçe planı/görev "
            "listesini güncelle. Fazlar arasında onay isteme. Yalnız kullanıcının kararını gerektiren gerçek "
            "bir engel varsa yanıtına `ENGEL: <neden>` yazıp dur. Tüm maddeler gerçekten bittiyse planı "
            "güncelle ve kısa bir özetle bitir.")


def system_section(items: list[str], source: str) -> str:
    if not items:
        return ""
    return ("# Açık plan maddeleri (" + source + ")\n" + "\n".join(f"- {x}" for x in items[:10])
            + "\nBunlar bitmeden turu bitirme; sıradakine sormadan geç (gerçek engelde `ENGEL:` yaz).")


def looks_multi_phase(text: str) -> bool:
    """Proje ajanı önerisi için: çok aşamalı, uzun istem mi? (sezgisel)"""
    t = (text or "").strip()
    low = t.lower()
    phase_words = sum(low.count(w) for w in ("faz", "aşama", "asama", "adım adım", "sırayla", "fazlara"))
    numbered = len(re.findall(r"(?m)^\s*(?:\d+[.)]|[-*•])\s+\S", t))
    return (len(t) >= 1500 and (phase_words >= 1 or numbered >= 5)) or (phase_words >= 2 and numbered >= 4) \
        or (len(t) >= 800 and numbered >= 8)


def dumps(items: list[str]) -> str:
    return json.dumps(items, ensure_ascii=False)
