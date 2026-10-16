"""Gerçek EVREN API ile özet (compact) kalitesi testi (API anahtarı gerekir).

pytest tarafından toplanmaz. Çalıştırma:
    .\\.venv\\Scripts\\python.exe -u tests\\e2e_compact_real_api.py [model ...]

Ajan oturumuna benzeyen bir geçmiş özetlenir; özetin kritik bilgileri
(dosya yolu, karar, açık iş, hata) koruyup korumadığı ve araç çağırmadığı denetlenir.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evren_studio.agent.compaction import summarize  # noqa: E402
from evren_studio.api.client import EvrenClient  # noqa: E402
from evren_studio.config import DEFAULT_BASE_URL  # noqa: E402
from evren_studio.secrets import load_api_key  # noqa: E402

HISTORY = [
    {"role": "user", "content": "src/hesap.py içindeki bol fonksiyonu sıfıra bölünce çöküyor, düzelt ve test ekle."},
    {"role": "assistant", "content": "Önce dosyayı okuyorum.",
     "tool_calls": [{"id": "a", "name": "read_file", "arguments": json.dumps({"path": "src/hesap.py"})}]},
    {"role": "tool", "tool_call_id": "a", "name": "read_file",
     "content": "src/hesap.py (6 satır)\n1\tdef bol(a, b):\n2\t    return a / b\n" + ("# dolgu satırı\n" * 400)},
    {"role": "assistant", "content": "b == 0 için ValueError ekliyorum.",
     "tool_calls": [{"id": "b", "name": "edit_file", "arguments": json.dumps({"path": "src/hesap.py"})}]},
    {"role": "tool", "tool_call_id": "b", "name": "edit_file", "content": "Düzenlendi: src/hesap.py (+2 −0 satır)."},
    {"role": "assistant", "content": "Testleri çalıştırıyorum.",
     "tool_calls": [{"id": "c", "name": "run_command", "arguments": json.dumps({"command": "python -m pytest -q"})}]},
    {"role": "tool", "tool_call_id": "c", "name": "run_command",
     "content": "Çıkış kodu: 1\nFAILED tests/test_hesap.py::test_bol_sifir - ModuleNotFoundError: No module named 'hesap'"},
    {"role": "assistant", "content": "Test, modül yolu yüzünden düştü; tests/conftest.py ile src yolunu ekleyeceğim. "
                                     "Kullanıcı ayrıca hata mesajının Türkçe olmasını istedi."},
]
MUST = ["hesap.py", "ValueError", "conftest", "ModuleNotFound"]


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    key = load_api_key()
    if not key:
        print("FAIL: API anahtarı yok")
        return 1
    models = sys.argv[1:] or ["deepseek-v4-flash", "glm-5.3"]
    client = EvrenClient(DEFAULT_BASE_URL, key, timeout=180.0, max_retries=1)
    passed = 0
    try:
        for model in models:
            t0 = time.monotonic()
            try:
                res = summarize(client, model, HISTORY, focus="açık işler ve dosya yolları")
            except Exception as exc:  # ApiError dahil: raporla, diğer modellere geç
                print(f"KALDI | {model} | {time.monotonic() - t0:.1f} sn | hata: {exc}")
                continue
            dur = time.monotonic() - t0
            text = res.content or ""
            missing = [w for w in MUST if w.lower() not in text.lower()]
            ok = bool(text.strip()) and not missing and "<arac_cagrisi>" not in text
            passed += ok
            print(f"{'GEÇTİ' if ok else 'KALDI'} | {model} | {dur:.1f} sn | {len(text)} karakter"
                  + (f" | eksik: {missing}" if missing else ""))
            print("      " + text.strip().replace("\n", " ⏎ ")[:300])
    finally:
        client.close()
    print(f"\nSONUÇ: {passed}/{len(models)} özet geçti")
    return 0 if passed == len(models) else 2


if __name__ == "__main__":
    raise SystemExit(main())
