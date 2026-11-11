"""`auto` (sunucunun seçtiği motor) ile Auto Pro (uygulamanın yönlendiricisi) hız karşılaştırması — gerçek pencere yolu.

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_hiz_auto_karsilastirma_real_api.py [tur=1] [--motorlar auto,qwen3.8-flash-next]

Madde 19 sonrası (2026-11-07) Auto Pro seçilebilir motor değil ("auto-pro" → auto); varsayılan yalnız `auto` ölçülür
(önce/sonra karşılaştırması: kısa ve öz yanıt, güvenlik ağı).

Kullanıcı (2026-11-07): "auto motoru auto pro motorundan daha hızlı yanıtlar verebiliyor ... uygulama hiç hızlı
değil." Aynı istekler, aynı saatte, sıra her turda değiştirilerek iki motorla gönderilir (send → koşucu → tur sonu).
Ölçülen: turun toplam süresi, model çağrısı sayısı (tur içi + iç işler), çağrı başına ilk parça ve süre, kullanılan
motor. Sonuç docs/knowledge/CHALLENGE_RESULTS.md'ye işlenir. pytest toplamaz.
"""
from __future__ import annotations

import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from gecici import klasor  # noqa: E402 — geçici klasörler çıkışta silinir (2026-11-11 disk sızıntısı)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SOHBET = [
    "Merhaba, bugün nasılsın? Tek cümleyle cevap ver.",
    "Python'da liste ile demet (tuple) arasındaki fark nedir? Kısa anlat.",
    "Bir e-ticaret sitesinde sepetten vazgeçmeyi azaltmak için 3 öneri ver.",
]
AJAN = [
    "hesap.py dosyasına iki sayıyı çarpan carp(a, b) fonksiyonu ekle.",
    "Projede kaç Python dosyası var ve her biri ne işe yarıyor? Kısaca söyle.",
]


def pump(app, sec):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.05)


def wait_idle(app, w, limit):
    t0 = time.monotonic()
    pump(app, 0.5)
    while time.monotonic() - t0 < limit:
        pump(app, 0.2)
        if not w.session.running:
            return True
    return False


def calls_since(db, since_iso):
    return [dict(r) for r in db.conn.execute(
        "select model, role, duration_s, first_chunk_s, out_tokens, ok, event from model_calls where at >= ? "
        "order by id", (since_iso,))] if hasattr(db, "conn") else []


def run_one(app, w, model, msg, proj):
    from datetime import datetime, timezone

    w.new_session()
    w.session.set_model(model)
    w.session.composer.set_model(model)
    w.session.welcome._choose(str(proj) if proj else None)
    if proj:
        w.session.set_mode("auto")
    since = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pump(app, 1.0)
    t0 = time.monotonic()
    w.session.send(msg)
    ok = wait_idle(app, w, 600)
    dur = time.monotonic() - t0
    pump(app, 3.0)                      # tur sonu iç işleri (başlık, öneri) kayda düşsün
    rows = calls_since(w.ctx.db, since)
    msgs = w.ctx.db.get_session_messages(w.session.session_id)
    final = next((m["content"] for m in reversed(msgs) if m["role"] == "assistant" and m["content"]), "")
    return {"model": model, "ok": ok, "dur": dur, "rows": rows, "final": final[:80].replace("\n", " ")}


def main() -> int:
    from evren_studio.secrets import load_api_key

    if not load_api_key():
        print("FAIL: EVREN API anahtarı yok")
        return 1
    args = sys.argv[1:]
    motorlar = ["auto"]
    if "--motorlar" in args:
        i = args.index("--motorlar")
        motorlar = [m for m in args[i + 1].split(",") if m]
        del args[i:i + 2]
    tur = int(args[0]) if args else 1
    os.environ["EVREN_STUDIO_DATA_DIR"] = str(klasor("evren-hiz-"))
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    w.ctx.settings.suggest_project = False
    pump(app, 2.0)
    results = []
    for t in range(tur):
        for i, (kind, msg) in enumerate([("sohbet", m) for m in SOHBET] + [("ajan", m) for m in AJAN]):
            order = motorlar if (i + t) % 2 == 0 else list(reversed(motorlar))
            for model in order:
                proj = None
                if kind == "ajan":
                    proj = klasor("hiz-proje-")
                    (proj / "hesap.py").write_text("def topla(a, b):\n    return a + b\n", encoding="utf-8")
                    (proj / "test_hesap.py").write_text(
                        "from hesap import topla\n\n\ndef test_topla():\n    assert topla(2, 3) == 5\n",
                        encoding="utf-8")
                r = run_one(app, w, model, msg, proj)
                r["kind"], r["msg"] = kind, msg
                results.append(r)
                used = ", ".join(f"{x['model']}/{x['role'] or '-'} {x['duration_s']:.1f}s (ilk {x['first_chunk_s'] or 0:.1f})"
                                 for x in r["rows"])
                print(f"[{kind}] {model:8} {r['dur']:6.1f} sn · çağrı {len(r['rows'])} · {used} · {r['final']}",
                      flush=True)
    print("\n=== ÖZET (ortanca tur süresi, sn) ===")
    for kind in ("sohbet", "ajan"):
        for model in motorlar:
            ds = [r["dur"] for r in results if r["kind"] == kind and r["model"] == model and r["ok"]]
            cs = [len(r["rows"]) for r in results if r["kind"] == kind and r["model"] == model]
            if ds:
                print(f"{kind:7} {model:8} ortanca {statistics.median(ds):6.1f} · toplam {sum(ds):6.1f} · "
                      f"ort. çağrı {statistics.mean(cs):.1f} · n={len(ds)}")
    w.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
