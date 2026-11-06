"""Motor karnesi (Madde 14) — belirlenmiş ölçüm günlerinde motorlara gerçek puan verir.

Kullanıcı 2026-11-06: "Gerçek kalite için birkaç gün belirleyelim, motorları EN İYİ çalıştıkları günde ölçelim ve her
motora puan verelim." Uygulama Auto Pro sırasında bu puanı kullanır (agent/karne.py · router.choose(scores=...)).

    .\\.venv\\Scripts\\python.exe tools\\motor_karnesi.py goster
    .\\.venv\\Scripts\\python.exe tools\\motor_karnesi.py olc <model> [<model> ...] [--zorla]
    .\\.venv\\Scripts\\python.exe tools\\motor_karnesi.py iceri-al <rapor.json> <model> [--iyi-gun | --kotu-gun]

`olc` GERÇEK API kullanır (anahtar gerekir, motor başına ~10-15 dk): önce hafif yoklama yapar; motor bugün "iyi"
değilse ölçmez ("ertelendi"; --zorla ile yine ölçer ama sonuç "iyi gün değil" diye kaydedilir ve gerçek puana
katılmaz). Sonra zorluk paketini (tests/e2e_zorluk_real_api.py) o motorla koşar ve puanı uygulamanın veritabanına yazar.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SUITE = "zorluk"


def _db():
    from evren_studio.config import ConfigStore, default_data_dir
    from evren_studio.db import Database

    settings = ConfigStore(default_data_dir()).load()
    return settings, Database(settings.resolved_data_dir() / "evren.db")


def karar(state: str, zorla: bool) -> tuple[bool, bool]:
    """(ölçülsün mü, iyi gün sayılsın mı). "ilk": geçmişsiz ama sağlıklı motor — ölçülür ve sayılır (karne.day_state)."""
    if state in ("iyi", "ilk"):
        return True, True
    return (True, False) if zorla else (False, False)


def iceri_al(db, rapor: dict, model: str, good_day: bool) -> dict:
    from evren_studio.agent import karne

    s = karne.score_report(rapor)
    db.add_model_score(model, SUITE, s["score"], good_day=good_day, details=json.dumps(s, ensure_ascii=False))
    return s


def goster(db) -> str:
    from evren_studio.agent import karne

    rows = karne.card(db.model_scores(karne.SCORE_DAYS))
    if not rows:
        return "Henüz ölçüm yok. Ölçüm günü: tools\\motor_karnesi.py olc <model>"
    lines = [f"{'Motor':28} {'Gerçek puan':>11}  İyi gün/Ölçüm  Son ölçüm"]
    for r in rows:
        p = f"{r['puan']:.1f}" if r["puan"] is not None else "—"
        lines.append(f"{r['model']:28} {p:>11}  {r['iyi']:>3}/{r['toplam']:<9}  {r['son'][:16]}")
    return "\n".join(lines)


PROBE_MSG = [{"role": "user", "content": "Yalnız tek kelime yaz: tamam"}]


def probe_chat(client, model: str):
    """Kısa yoklama isteği: düşünme kapalı; motor bu alanı desteklemiyorsa (400 geçersiz istek) alansız bir kez daha.
    İlk gerçek ölçüm (2026-11-06): gemma-4-31b `reasoning_effort` alanını reddetti, araç onu haksız yere "zayıf" saydı."""
    from evren_studio.api.errors import ApiError, ErrorKind

    try:
        return client.chat(model, PROBE_MSG, max_tokens=32, stream=True, extra_body={"reasoning_effort": "none"})
    except ApiError as exc:
        if exc.kind != ErrorKind.VALIDATION:
            raise
        return client.chat(model, PROBE_MSG, max_tokens=32, stream=True)


def _probe(settings, db, model: str) -> None:
    """Uygulamanın yoklamasıyla aynı kısa istek (agent/app_context._probe_one) — sonucu veritabanına yazar."""
    from evren_studio.api.client import EvrenClient
    from evren_studio.api.errors import ApiError
    from evren_studio.secrets import load_api_key

    t0 = time.monotonic()
    client = EvrenClient(base_url=settings.base_url, api_key=load_api_key() or "", timeout=30.0, max_retries=0,
                         stream_idle_timeout=20.0)
    try:
        r = probe_chat(client, model)
        db.add_model_call(model, role="yoklama", ok=True, duration_s=round(time.monotonic() - t0, 2),
                          first_chunk_s=r.first_chunk_s)
    except ApiError as exc:
        db.add_model_call(model, role="yoklama", ok=False, error_kind=exc.kind.value,
                          duration_s=round(time.monotonic() - t0, 2), detail=(exc.message or "")[:200])
    finally:
        client.close()


def olc(models: list[str], zorla: bool) -> int:
    from evren_studio.agent import karne

    settings, db = _db()
    rc = 0
    for model in models:
        _probe(settings, db, model)
        state, why = karne.day_state(db.recent_model_calls(24 * db.MODEL_CALLS_KEEP_DAYS), model)
        go, good = karar(state, zorla)
        print(f"== {model}: bugün {state} ({why})", flush=True)
        if not go:
            print("   ERTELENDİ: motor bugün en iyi durumunda değil (gerçek puan iyi günde ölçülür). "
                  "--zorla ile yine ölçülür ama puana katılmaz.", flush=True)
            rc = 3
            continue
        out = ROOT / "build" / "motor_karnesi"
        proc = subprocess.run([sys.executable, "-u", str(ROOT / "tests" / "e2e_zorluk_real_api.py"), model,
                               "--cikti", str(out)], cwd=ROOT)
        rapor_yolu = out / model.replace("/", "_") / "rapor.json"
        if not rapor_yolu.exists():
            print(f"   HATA: rapor yok ({rapor_yolu}); çıkış kodu {proc.returncode}", flush=True)
            rc = 1
            continue
        s = iceri_al(db, json.loads(rapor_yolu.read_text(encoding="utf-8")), model, good)
        print(f"   PUAN {s['score']:.1f} ({'iyi gün' if good else 'iyi gün DEĞİL — puana katılmaz'}) · "
              f"kontrol {s.get('kontrol')} · tam geçen {s.get('tam_gecen')}/{s.get('gorev')}", flush=True)
    print(goster(db))
    return rc


def main(argv: list[str]) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    if not argv or argv[0] not in ("goster", "olc", "iceri-al"):
        print(__doc__)
        return 2
    cmd, rest = argv[0], [a for a in argv[1:]]
    if cmd == "goster":
        print(goster(_db()[1]))
        return 0
    if cmd == "olc":
        models = [a for a in rest if not a.startswith("--")]
        if not models:
            print("Motor adı verin (ör. qwen3.8-flash-next).")
            return 2
        return olc(models, "--zorla" in rest)
    pos = [a for a in rest if not a.startswith("--")]
    if len(pos) != 2:
        print("Kullanım: iceri-al <rapor.json> <model> [--iyi-gun | --kotu-gun]")
        return 2
    _settings, db = _db()
    s = iceri_al(db, json.loads(Path(pos[0]).read_text(encoding="utf-8")), pos[1], "--kotu-gun" not in rest)
    print(f"{pos[1]}: puan {s['score']:.1f}")
    print(goster(db))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
