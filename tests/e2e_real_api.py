"""Uçtan uca gerçek API testi (uygulamanın kendi modülleriyle).

Bu betik yalnızca elle çalıştırılır; pytest koleksiyonuna girmez.
Anahtar Credential Manager'dan okunur, hiçbir dosyaya yazılmaz.
"""
import sys

from evren_studio.api.client import CancelToken, EvrenClient
from evren_studio.secrets import load_api_key


def main() -> int:
    key = load_api_key()
    if not key:
        print("FAIL: anahtar yok")
        return 1
    client = EvrenClient("https://evren-llmapi.ssyz.org.tr/v1", key,
                         timeout=180.0, max_retries=2)
    failures = []

    # 1) sağlık
    print("healthz:", client.healthz())
    print("readyz:", client.readyz())

    # 2) model listesi
    models = client.list_models()
    print(f"modeller: {len(models)} adet")
    chat_models = [m.id for m in models if m.supports_chat]
    print("sohbet modelleri:", ", ".join(chat_models))
    if len(models) < 10:
        failures.append("model listesi beklenenden küçük")

    # 3) kota
    q = client.get_quota()
    print(f"kota: seviye={q.level} kalan_cr={q.remaining_cr}")

    # 4) akışsız sohbet (glm-5.3 muhakeme modeli: yüksek max_tokens)
    r = client.chat("glm-5.3",
                    [{"role": "user", "content": "Tek kelimelik Türkçe yanıt: günaydın"}],
                    max_tokens=800)
    print(f"sohbet: finish={r.finish_reason} içerik={r.content[:60]!r} "
          f"yönlendirilen={r.routed_model}")
    if not (r.content or r.reasoning):
        failures.append("sohbet yanıtı boş")

    # 5) akışlı sohbet + parça parça toplama (auto → hızlı yönlendirme)
    parts: list[str] = []
    rs = client.chat("auto",
                     [{"role": "user", "content": "Türkçe tek cümlede kendini tanıt."}],
                     max_tokens=300, stream=True,
                     on_delta=lambda c, f: parts.append(c))
    joined = "".join(parts)
    print(f"akış: {len(parts)} parça, finish={rs.finish_reason}, "
          f"içerik={joined[:60]!r}")
    if not joined and not rs.reasoning:
        failures.append("akış yanıtı boş")

    # 6) belirsiz sonuç sorgusu (daha önceki başarılı istek kimliği ile)
    if r.request_id:
        st = client.resolve_unknown_request(r.request_id)
        print(f"istek durumu: {st.get('execution_terminal')}")

    client.close()
    if failures:
        print("FAIL:", "; ".join(failures))
        return 1
    print("E2E_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
