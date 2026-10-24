"""A10 ölçümü: EVREN motorları `seed` + `temperature` ile aynı istemde aynı yanıtı veriyor mu? (R-07; pytest toplamaz)

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_tutarlilik_real_api.py [tekrar=3]

Her motora aynı istem `tekrar` kez gönderilir: (a) varsayılan, (b) temperature=0 + seed=42. Kaç farklı yanıt
çıktığı sayılır. (b) tek yanıtta kalıyorsa tutarlılık modu rapor işlerinde açılabilir.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evren_studio.api.client import EvrenClient  # noqa: E402
from evren_studio.config import DEFAULT_BASE_URL  # noqa: E402
from evren_studio.secrets import load_api_key  # noqa: E402

MODELLER = ["deepseek-v4.1-flash", "qwen3.8-flash-next", "gemma-4-31b"]
ISTEM = ("Aşağıdaki işleri açılış kaynağına göre say ve yalnız JSON yaz: {\"Log\": n, \"HesapUyum\": n, "
         "\"Manuel\": n}. Kural: açıklamada 'otomatik olarak iş açılmıştır' geçiyorsa Log; değilse Hesap Uyum "
         "True ise HesapUyum; değilse Manuel. Ardından tek cümlelik Türkçe bir yorum ekle.\n"
         "1) HU=True, açıklama: 'otomatik olarak iş açılmıştır'\n2) HU=True, açıklama: 'müşteri aradı'\n"
         "3) HU=False, açıklama: 'kapama talebi'\n4) HU=True, açıklama: 'ödeme sonrası'\n"
         "5) HU=False, açıklama: 'otomatik olarak iş açılmıştır'")


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
    c = EvrenClient(DEFAULT_BASE_URL, key, timeout=180.0, max_retries=1)
    sonuc = {}
    try:
        for m in MODELLER:
            sonuc[m] = {}
            for ad, ek in (("varsayılan", None), ("seed+t0", {"temperature": 0, "seed": 42})):
                yanitlar = []
                for _ in range(tekrar):
                    try:
                        r = c.chat(m, [{"role": "user", "content": ISTEM}], extra_body=ek)
                        yanitlar.append((r.content or "").strip())
                    except Exception as exc:  # ölçüm: hatayı da kaydet
                        yanitlar.append(f"HATA {type(exc).__name__}: {exc}"[:80])
                farkli = len(set(yanitlar))
                sonuc[m][ad] = {"farkli_yanit": farkli, "tekrar": tekrar, "ornek": yanitlar[0][:120]}
                print(m, ad, f"{farkli}/{tekrar} farklı", "|", yanitlar[0][:100].replace("\n", " "), flush=True)
    finally:
        c.close()
    print("ÖZET", json.dumps({m: {k: v["farkli_yanit"] for k, v in d.items()} for m, d in sonuc.items()},
                             ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
