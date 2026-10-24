"""E6 kendini güncelleyen proje hafızası (Qt'siz): turdan "ders" çıkar → EVREN.md "Öğrenilenler" bölümüne ÖNERİ.

Kural (R-22): sıradan turda model çağrılmaz ve öneri çıkmaz. Yalnız ders sinyali varsa:
- bir komut başarısız olup turda daha sonra BAŞKA bir komut başarılı olduysa (çalışan yol bulundu),
- install_program kullanıldıysa (ortam kuruldu),
- test bekçisi testleri düşürmüşse (tuzak).
Sinyal varsa kısa bir model çağrısı en çok 3 ders yazar ya da "YOK" der; ders kullanıcıya kartla sorulur, onaysız
dosyaya YAZILMAZ. Bölüm `MAX_LINES` satırla sınırlı (eskiler atılır) — EVREN.md her turda sistem istemine girer.
"""
from __future__ import annotations

import re
from pathlib import Path

SECTION = "## Öğrenilenler"
MAX_LINES = 30                  # bölümdeki en çok madde
MAX_ITEM_CHARS = 220
MAX_ITEMS = 3
SYSTEM = (
    "Bir kod ajanının bu projede yaptığı turun araç kaydını okuyacaksın. Bu projede GELECEKTE işe yarayacak, "
    "projeye özgü en çok 3 kısa ders çıkar: çalışan komut (ör. testler `python -m unittest` ile koşuyor, pytest "
    "yok), ortam tuzağı (ör. dosya cp1254 kodlu), kalıcı karar. Genel programlama bilgisi, bu tura özgü geçici "
    "ayrıntı, dosya içeriği veya gizli bilgi YAZMA. Her ders `- ` ile başlayan tek satır, Türkçe, en çok 200 "
    "karakter. Kayda değer ders yoksa yalnız YOK yaz.")


def _calls(messages: list[dict]) -> list[tuple[str, dict, bool, str]]:
    """[(araç adı, argümanlar, başarılı mı, sonuç başı)] — mesaj sırasıyla."""
    import json

    results = {m.get("tool_call_id"): m for m in messages if m.get("role") == "tool"}
    out = []
    for m in messages:
        for c in m.get("tool_calls") or []:
            try:
                args = json.loads(c.get("arguments") or "{}") or {}
            except (ValueError, TypeError):
                args = {}
            r = results.get(c.get("id")) or {}
            ok = not (r.get("meta") or {}).get("error")
            out.append((c.get("name") or "", args if isinstance(args, dict) else {}, ok,
                        str(r.get("content") or "")[:400]))
    return out


def signals(messages: list[dict], events: list[str] | None = None) -> list[str]:
    """Ders sinyalleri (boş → model çağrılmaz)."""
    calls = _calls(messages)
    out: list[str] = []
    cmds = [(i, a.get("command", ""), ok) for i, (n, a, ok, _r) in enumerate(calls) if n == "run_command"]
    failed = [(i, c) for i, c, ok in cmds if not ok]
    for i, c in failed:
        later = [c2 for j, c2, ok in cmds if j > i and ok and c2.strip() != c.strip()]
        if later:
            out.append(f"başarısız komut: `{c[:120]}` → sonra çalışan: `{later[0][:120]}`")
            break
    if any(n == "install_program" and ok for n, _a, ok, _r in calls):
        out.append("program kuruldu")
    if "test_break" in (events or []):            # koşucunun kalite olayı (test bekçisi dürttü)
        out.append("testler değişiklikten sonra düştü")
    return out


def transcript(messages: list[dict], limit: int = 6000) -> str:
    """Model için kısa araç kaydı (komutlar ve sonuçların başı; dosya içerikleri gönderilmez)."""
    lines = []
    for name, args, ok, res in _calls(messages):
        if name in ("run_command", "install_program", "start_job"):
            what = args.get("command") or args.get("name") or ""
            lines.append(f"[{'OK' if ok else 'HATA'}] {name}: {what[:200]}\n    → {res[:300]}")
        elif name in ("write_file", "edit_file"):
            lines.append(f"[{'OK' if ok else 'HATA'}] {name}: {args.get('path', '')}")
    text = "\n".join(lines)
    return text[-limit:]


def parse(text: str) -> list[str]:
    """Model yanıtından ders maddeleri ("YOK" → [])."""
    t = (text or "").strip()
    if not t or re.fullmatch(r"(?is)\W*yok\W*", t):
        return []
    items = []
    for ln in t.splitlines():
        m = re.match(r"\s*(?:[-*•]|\d+[.)])\s+(.+)", ln)
        if m:
            item = m.group(1).strip()
            if item and not re.fullmatch(r"(?i)yok\.?", item):
                items.append(item[:MAX_ITEM_CHARS])
    return items[:MAX_ITEMS]


def append(root: Path, items: list[str], name: str = "EVREN.md") -> Path:
    """Maddeleri EVREN.md'deki "Öğrenilenler" bölümüne ekler (yoksa oluşturur); aynısı varsa eklemez; bölüm
    MAX_LINES madde ile sınırlı (en eskiler atılır). Dosya BOM'suz UTF-8, satır sonu korunur."""
    p = Path(root) / name
    raw = p.read_bytes() if p.exists() else b""
    text = raw.decode("utf-8-sig", errors="replace")
    crlf = "\r\n" in text
    text = text.replace("\r\n", "\n")
    if SECTION in text:
        head, rest = text.split(SECTION, 1)
        m = re.search(r"\n## ", rest)
        body, tail = (rest[:m.start()], rest[m.start():]) if m else (rest, "")
    else:
        head = (text.rstrip("\n") + "\n\n") if text.strip() else "# EVREN proje notları\n\n"
        body, tail = "\n", ""
    old = [ln for ln in body.splitlines() if ln.startswith("- ")]
    new = list(old)
    for i in items:
        if f"- {i}" not in new:                     # eski ve aynı çağrıdaki yinelenen madde eklenmez
            new.append(f"- {i}")
    new = new[-MAX_LINES:]
    out = head + SECTION + "\n" + "\n".join(new) + "\n" + tail
    if crlf:
        out = out.replace("\n", "\r\n")
    p.write_bytes(out.encode("utf-8"))
    return p
