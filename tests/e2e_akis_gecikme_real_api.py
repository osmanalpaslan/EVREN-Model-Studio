"""EVREN akış gecikmesi ölçümü — Auto Pro "yanıt vermeme" eşikleri için (A2; R-07). pytest toplamaz.

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_akis_gecikme_real_api.py [tekrar=3]

Her motora gerçek bir ajan isteği (ajan sistem istemi + araç şemaları + küçük proje sorusu) akışlı gönderilir;
ilk parça süresi (içerik, düşünme veya araç çağrısı) ve parçalar arası EN UZUN sessizlik ölçülür.
Eşik = gözlenen en kötü değerin birkaç katı olmalı; aksi hâlde düşünen model yanlışlıkla "dondu" sayılır.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import httpx  # noqa: E402

from evren_studio.agent import prompts  # noqa: E402
from evren_studio.agent.tools import TOOL_SPECS  # noqa: E402
from evren_studio.config import DEFAULT_BASE_URL  # noqa: E402
from evren_studio.secrets import load_api_key  # noqa: E402

MODELLER = ["deepseek-v4.1-flash", "qwen3.8-flash-next", "gemma-4-31b"]
SORU = ("Bu projede `hesapla(a, b)` fonksiyonunu ekleyip bölmede sıfır kontrolü yapan bir Python modülü ve unittest "
        "testi yazmam gerekiyor. Önce hangi dosyaları oluşturacağını ve testin nasıl görüneceğini planla, sonra "
        "ilk dosyayı write_file ile yaz.")


def olc(key: str, model: str) -> dict:
    tools = [s.openai_schema() for s in TOOL_SPECS]
    sistem = getattr(prompts, "AGENT_RULES", "Sen bir kod ajanısın.")
    body = {"model": model, "stream": True, "tools": tools, "tool_choice": "auto",
            "messages": [{"role": "system", "content": sistem}, {"role": "user", "content": SORU}]}
    t0 = time.monotonic()
    ilk = None
    son = t0
    en_uzun = 0.0
    parca = 0
    with httpx.Client(timeout=httpx.Timeout(30.0, read=300.0)) as c:
        with c.stream("POST", f"{DEFAULT_BASE_URL.rstrip('/')}/chat/completions", json=body,
                      headers={"Authorization": f"Bearer {key}", "Accept": "text/event-stream"}) as r:
            basliklar = time.monotonic() - t0
            r.raise_for_status()
            for line in r.iter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    ch = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                d = ((ch.get("choices") or [{}])[0].get("delta") or {})
                if not (d.get("content") or d.get("reasoning") or d.get("reasoning_content") or d.get("tool_calls")):
                    continue
                now = time.monotonic()
                parca += 1
                if ilk is None:
                    ilk = now - t0
                else:
                    en_uzun = max(en_uzun, now - son)
                son = now
    return {"basliklar_sn": round(basliklar, 1), "ilk_parca_sn": round(ilk or -1, 1),
            "en_uzun_sessizlik_sn": round(en_uzun, 1), "toplam_sn": round(son - t0, 1), "parca": parca}


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
    tekrar = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    ozet = {}
    for m in MODELLER:
        satir = []
        for i in range(tekrar):
            try:
                r = olc(key, m)
            except Exception as exc:                       # ölçüm: hatayı da kaydet
                r = {"hata": f"{type(exc).__name__}: {exc}"[:160]}
            satir.append(r)
            print(m, i + 1, r, flush=True)
        ok = [x for x in satir if "hata" not in x]
        if ok:
            ozet[m] = {"ilk_parca_en_kotu": max(x["ilk_parca_sn"] for x in ok),
                       "ilk_parca_ortanca": statistics.median(x["ilk_parca_sn"] for x in ok),
                       "sessizlik_en_kotu": max(x["en_uzun_sessizlik_sn"] for x in ok),
                       "hata": len(satir) - len(ok)}
    print("ÖZET", json.dumps(ozet, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
