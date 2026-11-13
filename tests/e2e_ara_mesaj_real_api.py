"""Madde 23 a — iş sürerken gönderilen ara mesaj: gerçek EVREN + gerçek arayüz akışı. pytest toplamaz.

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_ara_mesaj_real_api.py [model]     (varsayılan: auto)

Senaryo: ajana birkaç adımlı bir iş verilir (iki dosya). İlk araç çağrısı görülünce kullanıcı (test) ara mesaj yazar:
"c.txt'yi de oluştur". Ayrıca ikinci bir mesaj sıraya alınıp hemen GERİ ÇEKİLİR. Kabul (modelin görmediği):
  - a.txt ve b.txt istenen içerikte (asıl iş bozulmadı)
  - c.txt = "üç" (ara mesaj ajana ULAŞTI ve uygulandı)
  - ara mesaj kayıtta kullanıcı mesajı (meta steer) olarak duruyor, AYNI turda işlendi (yeni tur açılmadı)
  - geri çekilen mesaj hiçbir yere gitmedi (kayıtta yok, d.txt yok) ve yazma kutusuna döndü
  - sıra boş, tur bitti
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from gecici import klasor  # noqa: E402

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("EVREN_GOZLEM_KAYNAK", "e2e")


def pump(app, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)


def main() -> int:
    model = next((a for a in sys.argv[1:] if not a.startswith("-")), "auto")
    os.environ["EVREN_STUDIO_DATA_DIR"] = str(klasor("evren-ara-mesaj-"))
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.start_background_loads()
    w.show()
    if not w.ctx.has_api_key():
        print("FAIL: EVREN API anahtarı yok (Ayarlar)")
        return 2
    proj = klasor("ara-mesaj-proje-")
    (proj / "README.md").write_text("# Deneme\n", encoding="utf-8")
    s = w.session
    s.new_session()
    s.welcome._choose(str(proj))
    s.set_model(model)
    s.composer.set_model(model)
    s.set_mode("auto")
    t0 = time.monotonic()
    s.send("Bu klasörde a.txt dosyasını oluştur ve içine yalnız 'bir' yaz. Sonra b.txt dosyasını oluştur ve içine "
           "yalnız 'iki' yaz. Her dosyayı ayrı bir adımda oluştur. Bitince kısaca ne yaptığını söyle.")
    steered = withdrawn = False
    deadline = t0 + 8 * 60
    while time.monotonic() < deadline:
        pump(app, 0.3)
        msgs = s.ctx.db.get_session_messages(s.session_id) if s.session_id else []
        called = any(m["role"] == "assistant" and m.get("tool_calls") for m in msgs)
        if called and not steered and s.running:
            s.composer.set_text("Bu arada c.txt dosyasını da oluştur, içine yalnız 'üç' yaz.")
            s.composer._submit()
            s.send("Bunu geri çekeceğim: d.txt oluştur.")
            item = next((p for p in s.inbox.items() if "d.txt" in p.text), None)
            if item is not None:
                s.composer.withdraw_requested.emit(item.id)
                withdrawn = True
            steered = True
            print(f"ara mesaj gönderildi ({time.monotonic() - t0:.0f}. sn); geri çekme: {withdrawn}")
        if steered and not s.running and not s.inbox:
            pump(app, 2.0)
            if not s.running:
                break
    dur = time.monotonic() - t0
    msgs = s.ctx.db.get_session_messages(s.session_id)
    users = [m for m in msgs if m["role"] == "user"]
    steer = [m for m in users if (m.get("meta") or {}).get("steer")]

    def read(name):
        p = proj / name
        return p.read_text(encoding="utf-8").strip() if p.exists() else None
    checks = [
        ("ara mesaj gönderildi (iş sürerken)", steered, ""),
        ("tur bitti, sıra boş", not s.running and not s.inbox, f"running={s.running} sıra={len(s.inbox)}"),
        ("a.txt = bir", read("a.txt") == "bir", repr(read("a.txt"))),
        ("b.txt = iki", read("b.txt") == "iki", repr(read("b.txt"))),
        ("c.txt = üç (ara mesaj uygulandı)", read("c.txt") == "üç", repr(read("c.txt"))),
        ("ara mesaj kayıtta steer, aynı tur (2 kullanıcı mesajı)", len(steer) == 1 and len(users) == 2,
         f"kullanıcı={len(users)} steer={len(steer)}"),
        ("geri çekilen gitmedi (d.txt yok, kayıtta yok)", withdrawn and read("d.txt") is None
         and not any("d.txt" in (m.get("content") or "") for m in users), ""),
        ("geri çekilen kutuya döndü", "d.txt" in s.composer.edit.toPlainText(), s.composer.edit.toPlainText()[:60]),
    ]
    for name, ok, info in checks:
        print(f"{'GEÇTİ' if ok else 'KALDI'} | {name}" + (f" | {info}" if not ok else ""))
    passed = sum(1 for _n, ok, _i in checks if ok)
    calls = [c["name"] for m in msgs if m["role"] == "assistant" for c in (m.get("tool_calls") or [])]
    print(f"SONUÇ: {passed}/{len(checks)} · {dur:.0f} sn · model {model} · araçlar {len(calls)}: {', '.join(calls)}")
    w.close()
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
