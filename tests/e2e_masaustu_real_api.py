"""Masaüstü kontrolü — gerçek EVREN + gerçek Windows masaüstü (Madde 13). pytest toplamaz.

GERÇEK FARE VE KLAVYE KULLANILIR: çalışırken bilgisayara dokunmayın (dokunursanız kontrol size geçer ve test düşer).
Ön koşul: Ayarlar > Bağlayıcılar (MCP) > Masaüstü kontrolü kurulu (veya `--kur` verin; veri klasörü geçicidir).

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_masaustu_real_api.py [ajan|qa|hepsi] [--kur]

ajan: küçük Qt hesap uygulaması; ajan "2 + 3"ü fareyle/klavyeyle yapar. Kabul (modelin görmediği): uygulamanın yazdığı
      sonuc.txt = 5 (ajan gerçekten tıkladı), mcp__masaustu__ araçları çağrıldı, yanıtta 5, uygulama penceresi kapandı.
qa:   /qa-masaustu — bilerek HATALI sürüm (Topla çıkarma yapar) en az bir senaryoda "kaldi" bulmalı; DOĞRU sürüm
      hata bulmamalı (bilinen doğru/yanlış, R-25).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable                     # uygulamanın Python'u (PySide6 kurulu)
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from gecici import klasor  # noqa: E402 — geçici klasörler çıkışta silinir (2026-11-11 disk sızıntısı)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("EVREN_GOZLEM_KAYNAK", "e2e")

# Qt penceresi: kutular, düğme ve sonuç etiketi Windows UI Automation'a ADLARIYLA görünür. İlk deneme (2026-11-05) Tk ile
# yapıldı: Tk pencere içini UIA'ya bildirmiyor (yalnız başlık çubuğu), ajan koordinat tahmin etti → Qt'ye geçildi.
APP = '''import sys
from decimal import Decimal, InvalidOperation, getcontext
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

HATALI = {hatali}
getcontext().prec = 80                  # 30 haneye kadar kesin toplama
app = QApplication(sys.argv)
w = QWidget()
w.setWindowTitle("EVREN Hesap Deneme")
w.setGeometry(200, 200, 360, 220)
lay = QVBoxLayout(w)
a, b = QLineEdit(), QLineEdit()
a.setAccessibleName("Birinci sayı")
b.setAccessibleName("İkinci sayı")
sonuc = QLabel("Sonuç: -")
sonuc.setAccessibleName("Sonuç")


def hata(metin):
    sonuc.setText(metin)
    sonuc.setAccessibleName(metin)


# Gerçek QA 2026-11-07: "doğru" sürümün iki gerçek kusurunu buldu (0.1+0.2 → 0.30000000000000004; 400 haneli sayıda
# yakalanmayan OverflowError, etiket eski kaldı) — doğru sürüm gerçekten kusursuz olmalı ki ölçüm anlamlı olsun.
def topla():
    try:
        x, y = Decimal(a.text().strip()), Decimal(b.text().strip())
    except InvalidOperation:
        hata("Hata: sayı girin")
        return
    if not x.is_finite() or not y.is_finite():
        hata("Hata: sayı girin")
        return
    if max(len(x.as_tuple().digits) + max(x.as_tuple().exponent, 0),
           len(y.as_tuple().digits) + max(y.as_tuple().exponent, 0)) > 30:
        hata("Hata: sayı çok büyük (en fazla 30 hane)")
        return
    r = x - y if HATALI else x + y
    r = format(r.quantize(1) if r == r.to_integral_value() else r.normalize(), "f")
    sonuc.setText(f"Sonuç: {{r}}")
    sonuc.setAccessibleName(f"Sonuç: {{r}}")
    Path(__file__).with_name("sonuc.txt").write_text(str(r), encoding="utf-8")


btn = QPushButton("Topla")
btn.clicked.connect(topla)
for x in (a, b, btn, sonuc):
    lay.addWidget(x)
w.show()
sys.exit(app.exec())
'''


def pump(app, sec):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.05)


def make_window(install: bool):
    from PySide6.QtWidgets import QApplication

    from evren_studio.agent import mcp

    data = klasor("evren-masaustu-")
    os.environ["EVREN_STUDIO_DATA_DIR"] = str(data)
    app = QApplication.instance() or QApplication([])
    # EVREN Studio penceresi görünmez (offscreen) kalsın ama bu ayar masaüstü sunucusuna ve ajanın açtığı test
    # uygulamasına GEÇMESİN: 7. gerçek deneme (2026-11-05) — test uygulaması görünmez çizildi, pencere hiç oluşmadı.
    os.environ.pop("QT_QPA_PLATFORM", None)
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    real = Path(os.environ.get("LOCALAPPDATA", "")) / "EVREN-Model-Studio"
    src = real if mcp.windows_ready(real) else None
    if src is not None:                         # kullanıcının kurulumunu kullan (yeniden indirme yok)
        data_dir = src
    elif install:
        mcp.install_windows_mcp(data, log=print)
        data_dir = data
    else:
        raise SystemExit("FAIL: Masaüstü kontrolü kurulu değil (Ayarlar'dan kurun ya da --kur verin)")
    cfg = mcp.windows_config()
    w.ctx.settings.mcp_enabled = True
    w.ctx.settings.mcp_servers = [cfg.to_dict()]
    w.ctx.settings.suggest_project = False
    w.ctx.mcp.data_dir = Path(data_dir)
    return app, w


def wait_idle(app, w, limit):
    t0 = time.monotonic()
    pump(app, 1.0)
    while time.monotonic() - t0 < limit:
        pump(app, 0.5)
        if not w.session.running and not w.session.qa.active and not w.session.qa.planning:
            pump(app, 3.0)
            if not w.session.running and not w.session.qa.active:
                return True
    return False


def run_agent(app, w) -> int:
    proj = klasor("masaustu-ajan-")
    (proj / "hesap.py").write_text(APP.format(hatali=False), encoding="utf-8")
    w.new_session()
    w.session.welcome._choose(str(proj))
    w.session.set_model("auto-pro")
    w.session.composer.set_model("auto-pro")
    w.session.set_mode("auto")
    msg = (f"Masaüstünde şu uygulamayı aç: \"{PY}\" \"{proj / 'hesap.py'}\" (pencere başlığı: EVREN Hesap Deneme). "
           "İlk kutuya 2, ikinci kutuya 3 yaz, Topla düğmesine bas ve ekranda yazan sonucu söyle. Sonra uygulama "
           "penceresini kapat.")
    t0 = time.monotonic()
    w.session.send(msg)
    finished = wait_idle(app, w, 15 * 60)       # her Snapshot ~16 sn (bu bilgisayar, 2026-11-05)
    dur = time.monotonic() - t0
    msgs = w.ctx.db.get_session_messages(w.session.session_id)
    calls = [c["name"] for m in msgs if m["role"] == "assistant" for c in (m.get("tool_calls") or [])]
    final = next((m["content"] for m in reversed(msgs) if m["role"] == "assistant" and m["content"]), "")
    result = (proj / "sonuc.txt").read_text(encoding="utf-8").strip() if (proj / "sonuc.txt").exists() else ""
    alive = subprocess.run(["tasklist", "/v", "/fo", "csv"], capture_output=True, text=True,
                           errors="replace").stdout.count("EVREN Hesap Deneme")
    checks = [("tur bitti", finished, ""),
              ("masaüstü araçları çağrıldı", any(c.startswith("mcp__masaustu__") for c in calls), calls[:12]),
              ("uygulama gerçekten 5 hesapladı (sonuc.txt)", result == "5", result),
              ("yanıtta 5", "5" in final, final[:120]),
              ("pencere kapandı", alive == 0, alive)]
    for name, ok, info in checks:
        print(f"{'GEÇTİ' if ok else 'KALDI'} | {name}" + (f" | {info}" if not ok else ""))
    passed = sum(1 for _n, ok, _i in checks if ok)
    print(f"AJAN SONUÇ: {passed}/{len(checks)} · {dur:.0f} sn · araçlar {len(calls)} · "
          f"masaüstü {sum(c.startswith('mcp__masaustu__') for c in calls)}")
    return passed == len(checks)


def run_qa(app, w, hatali: bool) -> tuple[bool, dict]:
    proj = klasor(f"masaustu-qa-{'hatali' if hatali else 'dogru'}-")
    (proj / "hesap.py").write_text(APP.format(hatali=hatali), encoding="utf-8")
    (proj / "README.md").write_text(f"# Hesap\nÇalıştırma: `\"{PY}\" hesap.py` (Qt penceresi). İki sayıyı toplar "
                                    "(Topla düğmesi).\n",
                                    encoding="utf-8")
    w.new_session()
    w.session.welcome._choose(str(proj))
    w.session.set_mode("auto")
    w.session.send("/qa-masaustu Topla işlevini test et: iki sayının toplamı doğru mu, harf girilince ne oluyor. "
                   "En fazla 4 senaryo yeter.")
    if not wait_idle(app, w, 10 * 60) or w.session.qa.state is None:
        print("KALDI | QA planı çıkmadı")
        return False, {}
    w.session.qa.start()
    if not wait_idle(app, w, 40 * 60):
        # 2026-11-05 ilk QA koşusu: süre dolunca QA durdurulmadı, arka planda sürdü ve "doğru sürüm" denemesi hiç
        # başlamadı (aynı oturumda hatalı sürüm denenmeye devam etti) → durdur ve bitmesini bekle
        print("   (süre doldu: QA durduruluyor)")
        w.session.qa.stop()
        wait_idle(app, w, 5 * 60)
    st = w.session.qa.state
    counts = st.counts()
    print(f"QA ({'HATALI' if hatali else 'DOĞRU'} sürüm): {counts} · senaryo {len(st.scenarios)}")
    for s in st.scenarios:
        print(f"   {s.status:10} {s.title[:60]} | {s.actual[:80]}")
    ok = counts.get("kaldi", 0) >= 1 if hatali else counts.get("kaldi", 0) == 0
    return ok, counts


def main() -> int:
    from evren_studio.secrets import load_api_key

    if not load_api_key():
        print("FAIL: EVREN API anahtarı yok")
        return 1
    what = next((a for a in sys.argv[1:] if not a.startswith("--")), "ajan")
    app, w = make_window("--kur" in sys.argv)
    ok = True
    try:
        if what in ("ajan", "hepsi"):
            ok &= bool(run_agent(app, w))
        if what in ("qa", "hepsi", "qa-hatali"):
            bad, _c1 = run_qa(app, w, hatali=True)
            print(f"{'GEÇTİ' if bad else 'KALDI'} | QA hatalı sürümde hatayı buldu")
            ok &= bad
        if what in ("qa", "hepsi", "qa-dogru"):
            good, _c2 = run_qa(app, w, hatali=False)
            print(f"{'GEÇTİ' if good else 'KALDI'} | QA doğru sürümde hata uydurmadı")
            ok &= good
    finally:
        w.close()
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
