"""Tek "Sağlayıcılar ve anahtarlar" ekranının GERÇEK sunuculara karşı uçtan uca denemesi (2026-11-12).

Ücretli istek YOK, kişisel veri YOK: yalnız ücretsiz model listesi uçları.
1. EVREN: kullanıcının kasadaki anahtarıyla gerçek model listesi (ücretsiz).
2. Herkese açık listeler (anahtarsız): OpenRouter, Kilo, Hugging Face, Vercel → ekranın "Bağlantıyı dene" yolu
   modelleri gerçekten getirir.
3. Sahte anahtar: OpenAI, Anthropic, Groq, DeepSeek, xAI, Mistral ve Gemini (Gemini geçersiz anahtarda 401 değil 400
   döndürür) → kullanıcıya "Anahtar reddedildi" gösterilir.
4. Çalışmayan yerel sunucu (Ollama/LM Studio kapalı ya da yok) → "ulaşılamadı".

Kullanım: .venv\\Scripts\\python.exe tests\\e2e_saglayici_ekrani_real_api.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("EVREN_STUDIO_DATA_DIR", tempfile.mkdtemp(prefix="evren-e2e-saglayici-"))
os.environ.setdefault("EVREN_STUDIO_NO_PROBE", "1")

from evren_studio import secrets  # noqa: E402
from evren_studio.ui.app_context import AppContext  # noqa: E402
from evren_studio.ui.connections import describe_error, probe  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(("GEÇTİ " if ok else "KALDI ") + name + (f" — {detail}" if detail else ""), flush=True)


def main() -> int:
    ctx = AppContext()
    try:
        key = secrets.load_api_key()
        if key:
            ids = probe(ctx, "evren", key)
            check("EVREN gerçek anahtarla model listesi", len(ids) >= 3, f"{len(ids)} model")
        else:
            check("EVREN anahtarı kasada", False, "anahtar yok — bu bölüm atlandı")
        for tkey, alt in (("openrouter", 100), ("kilo", 100), ("huggingface", 20), ("vercel", 100)):
            try:
                ids = probe(ctx, tkey, "")
                check(f"{tkey} herkese açık model listesi", len(ids) >= alt and all("::" not in i for i in ids),
                      f"{len(ids)} model, örn. {ids[0] if ids else '-'}")
            except Exception as exc:                      # noqa: BLE001 — sonuç rapora yazılır
                check(f"{tkey} herkese açık model listesi", False, describe_error(exc))
        for tkey, fake in (("openai", "sk-proj-SAHTE0000000000"), ("anthropic", "sk-ant-api03-SAHTE0000000000"),
                           ("groq", "gsk_SAHTE0000000000"), ("deepseek", "sk-SAHTE0000000000"),
                           ("xai", "xai-SAHTE0000000000"), ("mistral", "SAHTE0000000000"),
                           ("gemini", "AIzaSAHTE0000000000")):
            try:
                probe(ctx, tkey, fake)
                check(f"{tkey} sahte anahtar reddedilir", False, "sunucu kabul etti?!")
            except Exception as exc:                      # noqa: BLE001
                text = describe_error(exc)
                check(f"{tkey} sahte anahtar reddedilir", text.startswith("Anahtar reddedildi"), text)
        for tkey, base in (("ollama", "http://localhost:11434/v1"), ("lmstudio", "http://localhost:1234/v1")):
            try:
                ids = probe(ctx, tkey, "", base)
                check(f"{tkey} yerel sunucu", True, f"çalışıyor: {len(ids)} model")
            except Exception as exc:                      # noqa: BLE001
                text = describe_error(exc)
                check(f"{tkey} kapalı yerel sunucu → ulaşılamadı", "ulaşılamadı" in text, text)
    finally:
        ctx.close()
    failed = [r for r in results if not r[1]]
    print(f"\nSONUÇ: {len(results) - len(failed)}/{len(results)} geçti")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
