"""Gerçek arayüz + gerçek EVREN API uçtan uca testi (API anahtarı gerekir).

pytest tarafından toplanmaz. Çalıştırma:
    .\\.venv\\Scripts\\python.exe -u tests\\e2e_ui_real_api.py [model] [cikti_klasoru]

Senaryo (geçici veri klasörü ve geçici proje; kullanıcının verilerine dokunmaz):
1. Klasörsüz sohbet: akışlı yanıt, çalışma çubuğunda model + süre, yanıt altında süre.
2. Kod ajanı (Onaylı mod): hesap.py'deki bol() fonksiyonuna sıfıra bölme kontrolü
   eklenmesi istenir; çıkan her onay kutusu onaylanır; dosyanın değiştiği,
   Değişiklikler panelinin dolduğu ve geri almanın çalıştığı doğrulanır.
3. /model listesi ve Ayarlar → Varsayılanlara döndür tıklanır.
Her adımda ekran görüntüsü alınır; Qt iş parçacığı uyarısı ve yakalanmamış hata aranır.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    model = sys.argv[1] if len(sys.argv) > 1 else "deepseek-v4-flash"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "build" / "shots"
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="evren-e2e-"))
    os.environ["EVREN_STUDIO_DATA_DIR"] = str(tmp / "data")
    proj = tmp / "proje"
    proj.mkdir()
    original = "def bol(a, b):\n    return a / b\n\n\ndef topla(a, b):\n    return a + b\n"
    (proj / "hesap.py").write_text(original, encoding="utf-8")

    from PySide6.QtCore import qInstallMessageHandler
    from PySide6.QtWidgets import QApplication, QMessageBox

    from evren_studio.secrets import load_api_key

    if not load_api_key():
        print("FAIL: API anahtarı yok")
        return 1
    errors: list[str] = []
    warnings: list[str] = []
    sys.excepthook = lambda t, v, tb: errors.append(f"{t.__name__}: {v}")
    app = QApplication(sys.argv)
    qInstallMessageHandler(lambda mode, ctx, msg: warnings.append(msg))
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)

    from evren_studio.ui.main_window import MainWindow
    from evren_studio.ui.transcript import ApprovalWidget, AssistantMessageWidget

    w = MainWindow()
    w.resize(1440, 900)
    w.show()
    results: list[tuple[str, bool, str]] = []

    def wait(cond, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            app.processEvents()
            if cond():
                return True
            time.sleep(0.05)
        return cond()

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        print(f"{'GEÇTİ' if ok else 'KALDI'} | {name}" + (f" | {detail}" if detail else ""))

    def shot(name: str) -> None:
        app.processEvents()
        w.grab().save(str(out / f"real_{name}.png"))

    # canlı model listesi
    check("canlı model listesi", wait(lambda: w.ctx.models_live, 30),
          f"{len(w.ctx.chat_models())} sohbet modeli")

    # 1) sohbet
    w.session.set_model(model)
    w.session.composer.set_model(model)
    w.session.welcome._choose(None)
    w.session.send("Bir cümleyle kendini tanıt.")
    saw_bar = wait(lambda: w.session.composer.run_bar.isVisible(), 10)
    bar_text = w.session.composer.run_text.text()
    shot("sohbet_calisiyor")
    check("çalışma çubuğu model+süre gösteriyor", saw_bar and model in bar_text and "sn" in bar_text, bar_text)
    done = wait(lambda: not w.session.running, 180)
    footers = [a.footer.text() for a in w.session.findChildren(AssistantMessageWidget) if a.footer.text()]
    check("sohbet yanıtı tamamlandı", done)
    check("yanıt altında model ve süre", bool(footers) and "sn" in footers[-1], footers[-1] if footers else "")
    shot("sohbet_bitti")

    # 2) kod ajanı, onaylı mod
    w.new_session()
    w.session.welcome._choose(str(proj))
    w.session.set_model(model)
    w.session.composer.set_model(model)
    w.session.set_mode("onayli")
    w.session.send("hesap.py dosyasındaki bol fonksiyonuna, b sıfır olduğunda anlaşılır bir "
                   "ValueError fırlatan kontrol ekle. Başka dosyaya dokunma; komut çalıştırma.")
    approvals = 0
    shot_taken = False
    end = time.monotonic() + 300
    while time.monotonic() < end and (w.session.running or approvals == 0):
        app.processEvents()
        boxes = [b for b in w.session.findChildren(ApprovalWidget) if b.isVisible() and not b.request.resolved]
        for b in boxes:
            if not shot_taken:
                shot("ajan_onay")
                shot_taken = True
            b._decide("allow")
            approvals += 1
        if not w.session.running and approvals:
            break
        time.sleep(0.05)
    wait(lambda: not w.session.running, 120)
    new_text = (proj / "hesap.py").read_text(encoding="utf-8")
    check("ajan onay istedi", approvals >= 1, f"{approvals} onay")
    check("dosya değişti ve kontrol eklendi", new_text != original and "ValueError" in new_text,
          new_text.replace("\n", "⏎")[:140])
    rows = w.panel.changes.rows
    check("Değişiklikler paneli doldu", len(rows) >= 1, f"{len(rows)} değişiklik")
    w.panel.show_tab("changes")
    shot("ajan_bitti")
    if rows:
        for r in reversed(rows):
            w.panel.changes._revert(r, ask_force=False)
        check("geri alma özgün dosyayı döndürdü",
              (proj / "hesap.py").read_text(encoding="utf-8") == original)

    # 3) /model listesi ve ayarlar
    comp = w.session.composer
    comp.set_text("/model ")
    app.processEvents()
    check("/model listesi açılıyor", comp.popup_visible() and comp.popup.count() >= 5, f"{comp.popup.count()} model")
    shot("model_listesi")
    comp.hide_popup()
    comp.edit.clear()
    w.show_page("settings")
    w.pages["settings"].timeout.setValue(300)
    w.pages["settings"].save_all()
    w.pages["settings"].reset_defaults()
    check("varsayılanlara döndür", w.ctx.settings.timeout_seconds == 120)
    shot("ayarlar")

    for key in ("home", "models", "connection", "usage", "errors", "monitor", "help"):
        w.show_page(key)
        wait(lambda: False, 1.5)
        shot(f"sayfa_{key}")
    from PySide6.QtWidgets import QLabel

    conn = w.pages["connection"]
    w.show_page("connection")
    conn.run()
    ok = wait(lambda: "BAĞLANTI SAĞLAM" in conn.result.findChildren(QLabel)[1].text(), 60)
    check("bağlantı testi (gerçek API)", ok,
          "" if ok else conn.result.findChildren(QLabel)[1].text() + " | " + conn.log.toPlainText()[-300:])
    usage = w.pages["usage"]
    w.show_page("usage")
    check("kota sayfası (gerçek API)",
          wait(lambda: usage.level_row.findChildren(QLabel)[1].text() == "ok", 30),
          usage.level_row.findChildren(QLabel)[1].text())

    thread_warn = [m for m in warnings if "thread" in m.lower()]
    check("Qt iş parçacığı uyarısı yok", not thread_warn, "; ".join(thread_warn[:3]))
    check("yakalanmamış hata yok", not errors, "; ".join(errors[:3]))
    w.close()
    passed = sum(1 for _n, ok, _d in results if ok)
    print(f"\nSONUÇ: {passed}/{len(results)} kontrol geçti · ekran görüntüleri: {out}")
    return 0 if passed == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
