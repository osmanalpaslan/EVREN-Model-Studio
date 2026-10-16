"""Gerçek EVREN API ile kod ajanı uçtan uca testi (API anahtarı gerekir).

pytest tarafından toplanmaz (dosya adı test_ ile başlamaz). Çalıştırma:
    .\\.venv\\Scripts\\python.exe -u tests\\e2e_agent_real_api.py [model ...]

Her model için geçici bir projede, PLAN modunda (yalnızca okuma araçları,
onay gerekmez) şu görev verilir: app.py'yi oku ve GIZLI_SAYI değerini yaz.
Ölçülenler: yerel araç çağrısı (tools) kullanıldı mı, metin protokolüne
geçildi mi, read_file çalıştı mı, son yanıtta doğru değer var mı, süre.
Sonuç docs/knowledge/MODEL_CAPABILITIES.md'ye elle işlenmelidir.
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evren_studio.agent.runner import AgentEvents, AgentRunner  # noqa: E402
from evren_studio.agent.tools import Workspace  # noqa: E402
from evren_studio.api.client import EvrenClient  # noqa: E402
from evren_studio.api.errors import ApiError  # noqa: E402
from evren_studio.config import DEFAULT_BASE_URL  # noqa: E402
from evren_studio.db import Database  # noqa: E402
from evren_studio.secrets import load_api_key  # noqa: E402

DEFAULT_MODELS = ["glm-5.3", "deepseek-v4.1-flash", "qwen3.8-flash-next"]
SECRET = "4217"
TASK = ("app.py dosyasını read_file aracıyla oku ve içindeki GIZLI_SAYI değişkeninin "
        "değerini tek cümleyle yaz.")


class Log(AgentEvents):
    def __init__(self):
        self.protocol_changes: list[str] = []
        self.tools: list[str] = []

    def protocol_changed(self, protocol, reason):
        self.protocol_changes.append(f"{protocol}: {reason}")

    def tool_finished(self, call, result):
        self.tools.append(f"{call.name}({'ok' if result.ok else 'hata'})")


def run_model(client: EvrenClient, model: str, protocol: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "app.py").write_text(f'"""Deneme."""\nGIZLI_SAYI = {SECRET}\n', encoding="utf-8")
        db = Database(root / "e2e.db")
        sid = db.create_session(model, str(root), "plan")
        db.add_session_message(sid, "user", TASK)
        events = Log()
        runner = AgentRunner(client, model, session_id=sid, store=db, events=events,
                             workspace=Workspace(root), mode="plan", protocol=protocol,
                             stream=True, max_steps=6, context_tokens=None)
        t0 = time.monotonic()
        try:
            outcome = runner.run(db.get_session_messages(sid))
            error = None
        except ApiError as exc:
            outcome, error = None, f"{exc.kind.value} HTTP {exc.status}: {exc.message[:160]}"
        dur = time.monotonic() - t0
        msgs = db.get_session_messages(sid)
        db.close()
    native_calls = any(m.get("tool_calls") for m in msgs if m["role"] == "assistant")
    final = next((m["content"] for m in reversed(msgs) if m["role"] == "assistant" and m["content"]), "")
    read_ok = any(t.startswith("read_file(ok") for t in events.tools)
    return {
        "model": model,
        "istenen_protokol": protocol,
        "son_protokol": outcome.protocol if outcome else "-",
        "protokol_degisimi": events.protocol_changes,
        "arac_cagrisi_var": native_calls,
        "araclar": events.tools,
        "read_file_ok": read_ok,
        "dogru_deger": SECRET in final,
        "adim": outcome.steps if outcome else 0,
        "durum": outcome.stopped if outcome else "hata",
        "hata": error,
        "sure_sn": round(dur, 1),
        "son_yanit": final.strip().replace("\n", " ")[:160],
    }


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    key = load_api_key()
    if not key:
        print("FAIL: API anahtarı yok (Ayarlar'dan girin)")
        return 1
    models = sys.argv[1:] or DEFAULT_MODELS
    client = EvrenClient(DEFAULT_BASE_URL, key, timeout=180.0, max_retries=1)
    results = []
    try:
        for model in models:
            for protocol in ("native", "text"):
                r = run_model(client, model, protocol)
                results.append(r)
                ok = r["read_file_ok"] and r["dogru_deger"]
                print(f"{'GEÇTİ' if ok else 'KALDI'} | {model} | protokol {protocol}→{r['son_protokol']} | "
                      f"araç çağrısı={r['arac_cagrisi_var']} | araçlar={r['araclar']} | "
                      f"adım={r['adim']} | {r['sure_sn']} sn | durum={r['durum']}")
                if r["protokol_degisimi"]:
                    print(f"      protokol değişimi: {r['protokol_degisimi']}")
                if r["hata"]:
                    print(f"      hata: {r['hata']}")
                print(f"      yanıt: {r['son_yanit']}")
    finally:
        client.close()
    passed = sum(1 for r in results if r["read_file_ok"] and r["dogru_deger"])
    print(f"\nSONUÇ: {passed}/{len(results)} senaryo geçti")
    return 0 if passed == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
