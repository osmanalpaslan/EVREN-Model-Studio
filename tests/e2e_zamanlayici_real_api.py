"""Zamanlanmış görev — gerçek EVREN API ile uçtan uca (Madde 12c; anahtar gerekir). pytest toplamaz.

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_zamanlayici_real_api.py [model]

Geçici bir projede "Elle" sıklıklı görev oluşturur, "Şimdi çalıştır" ile zamanlayıcı motoruna verir; görev görünmez
(gözetimsiz) oturumda Auto Pro ile çalışır. Kabul (modelin görmediği): topla.py doğru, unittest geçer, çalıştırma
"tamamlandi", oturum göreve bağlı, kullanıcının görünümü/varsayılanları değişmedi.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from gecici import klasor  # noqa: E402 — geçici klasörler çıkışta silinir (2026-11-11 disk sızıntısı)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("EVREN_GOZLEM_KAYNAK", "e2e")
os.environ["EVREN_STUDIO_DATA_DIR"] = str(klasor("evren-zaman-"))

PROMPT = ("topla.py dosyasında topla(a, b) fonksiyonunu yaz (iki sayının toplamını döndürsün) ve "
          "tests/test_topla.py içinde unittest ile 3 test yaz; testleri çalıştırıp geçtiğini doğrula.")


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from evren_studio.secrets import load_api_key

    if not load_api_key():
        print("FAIL: EVREN API anahtarı yok")
        return 1
    model = sys.argv[1] if len(sys.argv) > 1 else "auto-pro"
    app = QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    proj = klasor("zaman-proje-")
    s = w.ctx.settings
    s.default_model, s.agent_mode = "deepseek-v4.1-flash", "manuel"
    user_view = w.session.session_id
    tid = w.ctx.db.create_scheduled_task(name="gercek-test", prompt=PROMPT, workspace=str(proj), model=model,
                                         mode="auto", kind="manual")
    t0 = time.monotonic()
    w.scheduler.run_now(tid)
    final = None
    while time.monotonic() - t0 < 15 * 60:
        app.processEvents()
        time.sleep(0.05)
        run = w.ctx.db.list_scheduled_runs(tid)[0]
        if run["status"] in ("tamamlandi", "hata", "yarim", "durduruldu", "atlandi"):
            final = run
            break
    dur = time.monotonic() - t0
    checks = []
    checks.append(("çalıştırma tamamlandı", bool(final) and final["status"] == "tamamlandi",
                   (final["status"], final["reason"]) if final else "zaman aşımı"))
    src = proj / "topla.py"
    ok_fn = False
    if src.exists():
        r = subprocess.run([sys.executable, "-c", "import topla; assert topla.topla(2, 3) == 5 and "
                            "topla.topla(-1, 1) == 0 and topla.topla(2.5, 0.5) == 3.0"],
                           cwd=proj, capture_output=True, text=True)
        ok_fn = r.returncode == 0
    checks.append(("topla doğru", ok_fn, ""))
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=proj,
                       capture_output=True, text=True)
    checks.append(("unittest geçer", r.returncode == 0 and "OK" in (r.stderr + r.stdout), r.stderr[-120:]))
    sess = w.ctx.db.get_session(final["session_id"]) if final and final["session_id"] else None
    checks.append(("oturum göreve bağlı", bool(sess) and sess["scheduled_task_id"] == tid, ""))
    checks.append(("kullanıcı görünümü değişmedi", w.session.session_id == user_view, ""))
    checks.append(("varsayılanlar değişmedi", (s.default_model, s.agent_mode) == ("deepseek-v4.1-flash", "manuel"),
                   (s.default_model, s.agent_mode)))
    msgs = w.ctx.db.get_session_messages(final["session_id"]) if sess else []
    steps = sum(1 for m in msgs if m["role"] == "assistant")
    models = sorted({m["model"] for m in msgs if m["role"] == "assistant" and m["model"]})
    for name, ok, info in checks:
        print(f"{'GEÇTİ' if ok else 'KALDI'} | {name}" + (f" | {info}" if info and not ok else ""))
    passed = sum(1 for _n, ok, _i in checks if ok)
    print(f"SONUÇ: {passed}/{len(checks)} · {dur:.0f} sn · {steps} asistan yanıtı · modeller {models}")
    w.close()
    return 0 if passed == len(checks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
