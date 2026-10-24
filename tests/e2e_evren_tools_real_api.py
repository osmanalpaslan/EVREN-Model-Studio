"""E8 doğrulaması: EVREN `evren_tools` uzantısı (sunucuda çalışan canlı veri araçları) ne sunuyor? (R-07; pytest toplamaz)

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_evren_tools_real_api.py

Şema (GET /openapi.json, 2026-10-24): `evren_tools: bool` — "opt-in to server-executed live-data tools when `tools`
is not supplied". Her soru `evren_tools` açık ve kapalı sorulur; yanıt, bitiş nedeni ve yanıttaki ek alanlar
(araç izi) yazılır. Kendi `tools` listemizle birlikte KULLANILAMAZ (şema), bu yüzden ajan turunda değil, yalnız
klasörsüz sohbette veya ayrı bir yardımcı çağrıda işe yarar.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import httpx  # noqa: E402

from evren_studio.config import DEFAULT_BASE_URL  # noqa: E402
from evren_studio.secrets import load_api_key  # noqa: E402

MODELLER = ["qwen3.8-flash-next", "deepseek-v4.1-flash"]
SORULAR = [
    "Şu an saat kaç ve bugünün tarihi ne? (UTC olarak)",
    "Bugün Türk lirası ile ABD doları arasındaki güncel kur nedir? Kaynağını belirt.",
    "https://www.python.org adresindeki sayfanın başlığı nedir?",
]


def sor(c: httpx.Client, key: str, model: str, soru: str, acik: bool) -> dict:
    body = {"model": model, "messages": [{"role": "user", "content": soru}], "max_tokens": 600}
    if acik:
        body["evren_tools"] = True
    r = c.post(f"{DEFAULT_BASE_URL.rstrip('/')}/chat/completions", json=body,
               headers={"Authorization": f"Bearer {key}"})
    d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"ham": r.text[:300]}
    ch = (d.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    ek = {k: v for k, v in d.items() if k not in ("id", "object", "created", "model", "choices", "usage",
                                                  "system_fingerprint")}
    return {"http": r.status_code, "bitis": ch.get("finish_reason"), "yanit": (msg.get("content") or "")[:260],
            "mesaj_ek": {k: v for k, v in msg.items() if k not in ("role", "content", "reasoning_content",
                                                                    "reasoning")},
            "ust_ek": ek, "usage_ek": {k: v for k, v in (d.get("usage") or {}).items()
                                       if k not in ("prompt_tokens", "completion_tokens", "total_tokens")}}


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    key = load_api_key()
    if not key:
        print("EVREN anahtarı yok")
        return 2
    with httpx.Client(timeout=180.0) as c:
        for m in MODELLER:
            for soru in SORULAR:
                for acik in (False, True):
                    try:
                        r = sor(c, key, m, soru, acik)
                    except Exception as exc:  # ölçüm: hatayı da yaz
                        r = {"hata": f"{type(exc).__name__}: {exc}"[:200]}
                    print(f"[{m} · evren_tools={'açık' if acik else 'kapalı'}] {soru[:40]}…", flush=True)
                    print("   " + json.dumps(r, ensure_ascii=False)[:900], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
