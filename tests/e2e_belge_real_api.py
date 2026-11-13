"""PDF / Word okumanın gerçek API denemesi (Madde 20 A3, R-07; pytest toplamaz).

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_belge_real_api.py

1. Sohbet eki: Word tablosundaki bir değeri model doğru söylüyor mu?
2. Ajan: proje klasöründeki PDF'i kendisi read_file ile okuyup tutarı buluyor mu?
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
from gecici import klasor  # noqa: E402

os.environ["EVREN_STUDIO_DATA_DIR"] = str(klasor("evren-belge-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pump(app, sec):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.05)


def run(app, w, model, ws, text, files=()):
    s = w.session
    s.new_session()
    s.welcome._choose(str(ws) if ws else None)
    s.composer.set_model(model, emit=True)
    if ws:
        s.set_mode("auto")
    if files:
        s.add_files([str(f) for f in files])
    s.composer.set_text(text)
    t0 = time.monotonic()
    s.composer._submit()
    pump(app, 1.0)
    while s.running and time.monotonic() - t0 < 300:
        pump(app, 0.3)
    msgs = w.ctx.db.get_session_messages(s.session_id)
    final = next((m["content"] for m in reversed(msgs) if m["role"] == "assistant" and m["content"]), "")
    tools = [c["name"] for m in msgs if m["role"] == "assistant" for c in (m.get("tool_calls") or [])]
    return final, tools, time.monotonic() - t0


def main() -> int:
    from evren_studio.secrets import load_api_key

    if not load_api_key():
        print("FAIL: EVREN API anahtarı yok")
        return 1
    from PySide6.QtWidgets import QApplication

    from tests.test_belgeler import make_docx, make_pdf

    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.start_background_loads()  # uygulamayla aynı açılış: canlı model listesi + kullanım (app.py)
    w.show()
    w.ctx.settings.suggest_project = False
    model = sys.argv[1] if len(sys.argv) > 1 else "auto"
    d = klasor("belge-ek-")
    docx_path = make_docx(d / "rapor.docx")
    ok = True
    final, _tools, dur = run(app, w, model, None, "Ekteki raporda Üsküdar şubesinin cirosu kaç? Yalnız sayıyı yaz.",
                             [docx_path])
    passed = "98.500" in final or "98500" in final
    ok &= passed
    print(f"{'GEÇTİ' if passed else 'KALDI'} | sohbet eki (Word tablo) · {dur:.0f} sn · yanıt: {final[:80]!r}")
    proj = klasor("belge-proje-")
    make_pdf(proj / "teklif.pdf", ["Teklif No 77 Toplam tutar 45.000 TL Ödeme 30 gün"])
    final, tools, dur = run(app, w, model, proj, "teklif.pdf dosyasındaki toplam tutar ne kadar? Kısaca söyle.")
    passed = ("45.000" in final or "45000" in final) and "read_file" in tools
    ok &= passed
    print(f"{'GEÇTİ' if passed else 'KALDI'} | ajan PDF okudu · {dur:.0f} sn · araçlar {tools} · yanıt: {final[:80]!r}")
    w.close()
    print("SONUÇ:", "GEÇTİ" if ok else "KALDI")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
