"""OpenAI / Anthropic gerçek API doğrulaması (ÜCRETLİ — elle çalıştırılır).

pytest koleksiyonuna girmez. Anahtarlar Credential Manager'dan okunur
(Ayarlar > Sağlayıcılar); hiçbir dosyaya yazılmaz. Ücretli olduğu için
`--evet` bayrağı olmadan istek göndermez. En ucuz modeller kullanılır;
tahmini toplam maliyet birkaç sentin altındadır.

    .\\.venv\\Scripts\\python.exe tests\\e2e_providers_real_api.py --evet [openai] [anthropic]

Geçerse: api/providers.py içinde ilgili sağlayıcının `verified=True`
yapılabilir; sonucu docs/knowledge/MODEL_CAPABILITIES.md ve oturum
günlüğüne yazın (R-07).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from evren_studio.api.anthropic_client import AnthropicClient  # noqa: E402
from evren_studio.api.errors import ApiError  # noqa: E402
from evren_studio.api.openai_client import OpenAIClient  # noqa: E402
from evren_studio.api.providers import estimate_cost  # noqa: E402
from evren_studio.secrets import load_api_key  # noqa: E402

CHEAP = {"openai": "gpt-6-luna", "anthropic": "claude-haiku-5-5"}
TOOLS = [{"type": "function", "function": {
    "name": "topla", "description": "İki sayıyı toplar.",
    "parameters": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                   "required": ["a", "b"]}}}]


def check(provider: str) -> list[str]:
    key = load_api_key(provider)
    if not key:
        print(f"[{provider}] ATLANDI: anahtar yok (Ayarlar > Sağlayıcılar)")
        return []
    cls = OpenAIClient if provider == "openai" else AnthropicClient
    client = cls(key, timeout=120.0, max_retries=1)
    model = CHEAP[provider]
    fails: list[str] = []
    cost = 0.0
    try:
        models = client.list_models()
        print(f"[{provider}] modeller (katalogla kesişim): {[m.id for m in models]}")
        if model not in [m.id for m in models]:
            fails.append(f"{model} listede yok")

        r = client.chat(model, [{"role": "user", "content": "Tek kelimeyle yanıtla: günaydın"}],
                        max_tokens=200)
        cost += estimate_cost(model, r.token_usage())
        print(f"[{provider}] akışsız: {r.content!r} · {r.token_usage()}")
        if not r.content.strip():
            fails.append("akışsız yanıt boş")

        parts: list[str] = []
        r = client.chat(model, [{"role": "user", "content": "1'den 5'e kadar say."}], stream=True,
                        max_tokens=200, on_delta=lambda t, _: parts.append(t))
        cost += estimate_cost(model, r.token_usage())
        print(f"[{provider}] akış: {''.join(parts)!r} · {r.token_usage()}")
        if not parts or not r.token_usage().get("output_tokens"):
            fails.append("akış metni veya kullanım bilgisi yok")

        msgs = [{"role": "system", "content": "Hesap için her zaman topla aracını kullan."},
                {"role": "user", "content": "17 ile 25'i topla."}]
        r = client.chat(model, msgs, tools=TOOLS, stream=True, max_tokens=500)
        cost += estimate_cost(model, r.token_usage())
        if not r.tool_calls:
            fails.append(f"araç çağrısı gelmedi: {r.content[:100]!r}")
        else:
            c = r.tool_calls[0]
            args = json.loads(c["arguments"] or "{}")
            print(f"[{provider}] araç çağrısı: {c['name']}({args})")
            msgs.append({"role": "assistant", "content": r.content,
                         "tool_calls": [{"id": c["id"], "type": "function",
                                         "function": {"name": c["name"], "arguments": c["arguments"]}}],
                         "_provider_state": r.provider_state})
            msgs.append({"role": "tool", "tool_call_id": c["id"],
                         "content": str(float(args.get("a", 0)) + float(args.get("b", 0)))})
            r2 = client.chat(model, msgs, tools=TOOLS, stream=True, max_tokens=500)
            cost += estimate_cost(model, r2.token_usage())
            print(f"[{provider}] araç sonrası yanıt: {r2.content!r}")
            if "42" not in r2.content:
                fails.append("araç sonucu yanıta yansımadı")
    except ApiError as exc:
        fails.append(f"API hatası: {exc} · {exc.message}")
    finally:
        client.close()
    print(f"[{provider}] tahmini maliyet: ${cost:.5f}")
    return fails


def main(argv: list[str]) -> int:
    if "--evet" not in argv:
        print("Bu betik ÜCRETLİ istek gönderir. Onaylıyorsanız --evet ile çalıştırın.")
        return 2
    providers = [p for p in argv if p in CHEAP] or list(CHEAP)
    all_fails = {p: check(p) for p in providers}
    bad = {p: f for p, f in all_fails.items() if f}
    for p, f in bad.items():
        print(f"FAIL [{p}]: " + " | ".join(f))
    print("SONUÇ:", "BAŞARISIZ" if bad else "GEÇTİ (anahtarı olmayanlar atlandı)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
