"""Proje ajanı uçtan uca (gerçek arayüz + gerçek EVREN API, anahtar gerekir).

pytest tarafından toplanmaz. Çalıştırma:
    .\\.venv\\Scripts\\python.exe -u tests\\e2e_proje_real_api.py [model] [--cikti klasör]

Varsayılan model: auto-pro (Auto Pro). Geçici bir git deposunda `/proje <hedef>` ile
plan istenir, plan kartı onaylanır, görevler gözetimsiz yürür. Sonunda modelin
GÖRMEDİĞİ kabul testleri programı dışarıdan dener; git commit'leri, EVREN_PLAN.md,
EVREN_RAPOR.md ve Windows bildirimi denetlenir. Ekran görüntüleri: <cikti>/*.png
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PY = sys.executable
LIMIT = 40 * 60

HEDEF = ("Python standart kütüphanesiyle bir sıcaklık dönüştürücü yap. donustur.py dosyasında "
         "c2f(c) ve f2c(f) fonksiyonları olsun (sonuç 2 ondalığa yuvarlanmış float). Komut satırı: "
         "`python donustur.py c2f 100` tam olarak `212.0` yazsın, `python donustur.py f2c 32` tam olarak "
         "`0.0` yazsın; bilinmeyen komut veya sayı olmayan değer için hata mesajı yazıp çıkış kodu 2 olsun. "
         "tests/ klasöründe unittest testleri olsun ve `python -m unittest discover -s tests` geçsin. "
         "Son olarak README.md'ye kullanım örnekleri yaz.")

# Madde 20 B3 (2026-11-11): birbirinden BAĞIMSIZ parçalı hedef — paralel görevler (ayrı git çalışma kopyaları) ile
# sıralı yürütmeyi aynı hedefte karşılaştırmak için: `--hedef paralel --paralel 3` / `--paralel 1`
HEDEF_PAR = ("Python standart kütüphanesiyle birbirinden bağımsız üç küçük modül yap. "
             "(1) metin.py: kelime_say(s) boşluklarla ayrılmış kelime sayısını döndürür (birden çok boşluk tek "
             "ayırıcıdır), ters(s) metni ters çevirir. "
             "(2) sayi.py: asal_mi(n) n asal ise True (n < 2 için False), faktoriyel(n) n! döndürür, n < 0 ise "
             "ValueError fırlatır. "
             "(3) tarih.py: artik_yil(y) artık yıl ise True (Gregoryen kural: 400'e bölünen artık, 100'e bölünen "
             "değil, 4'e bölünen artık), ay_gun(y, m) o aydaki gün sayısını döndürür, m 1-12 dışındaysa ValueError. "
             "Her modülün tests/ klasöründe kendi unittest dosyası olsun (test_metin.py, test_sayi.py, "
             "test_tarih.py) ve `python -m unittest discover -s tests` geçsin. "
             "Son olarak README.md'ye üç modülün kullanım örneklerini yaz.")

KABUL_PAR = r"""
import metin, sayi, tarih
def hata(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False
r = {
 "kelime_say": metin.kelime_say("bir iki  üç") == 3, "ters": metin.ters("abc") == "cba",
 "asal_mi": sayi.asal_mi(7) and not sayi.asal_mi(1) and not sayi.asal_mi(9),
 "faktoriyel": sayi.faktoriyel(5) == 120 and sayi.faktoriyel(0) == 1 and hata(sayi.faktoriyel, -1),
 "artik_yil": tarih.artik_yil(2024) and tarih.artik_yil(2000) and not tarih.artik_yil(1900),
 "ay_gun": tarih.ay_gun(2024, 2) == 29 and tarih.ay_gun(2023, 2) == 28 and tarih.ay_gun(2023, 4) == 30
           and hata(tarih.ay_gun, 2023, 13),
}
print(" ".join(k + "=" + ("1" if v else "0") for k, v in r.items()))
"""


def run(cmd, cwd, timeout=60):
    # Kabul, kullanıcının normal ortamında çalışır: bu betiği çalıştırırken verilen
    # PYTHONIOENCODING alt süreçlere sızarsa üretilen testler yapay olarak düşer (2026-10-19).
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return -9, "zaman aşımı"


def kabul(p: Path) -> list[tuple[str, bool, str]]:
    r = []
    c, o = run([PY, "donustur.py", "c2f", "100"], p)
    r.append(("c2f 100 → 212.0", c == 0 and o.splitlines()[-1:] == ["212.0"], o[-80:]))
    c, o = run([PY, "donustur.py", "f2c", "32"], p)
    r.append(("f2c 32 → 0.0", c == 0 and o.splitlines()[-1:] == ["0.0"], o[-80:]))
    c, o = run([PY, "donustur.py", "f2c", "abc"], p)
    r.append(("hatalı değer çıkış 2", c == 2, f"çıkış {c}"))
    c, o = run([PY, "-m", "unittest", "discover", "-s", "tests"], p, timeout=120)
    r.append(("kendi testleri geçiyor", c == 0, (o.splitlines() or [''])[-1][:80]))
    readme = (p / "README.md").read_text(encoding="utf-8", errors="replace") if (p / "README.md").exists() else ""
    r.append(("README kullanım örneği", "c2f" in readme and "f2c" in readme, ""))
    return r


def kabul_par(p: Path) -> list[tuple[str, bool, str]]:
    c, o = run([PY, "-c", KABUL_PAR], p)
    got = dict(x.split("=", 1) for x in (o.splitlines()[-1:] or [""])[0].split() if "=" in x) if c == 0 else {}
    r = [(f"{k}", got.get(k) == "1", "" if c == 0 else o[-120:])
         for k in ("kelime_say", "ters", "asal_mi", "faktoriyel", "artik_yil", "ay_gun")]
    c, o = run([PY, "-m", "unittest", "discover", "-s", "tests"], p, timeout=120)
    r.append(("kendi testleri geçiyor", c == 0, (o.splitlines() or [''])[-1][:80]))
    readme = (p / "README.md").read_text(encoding="utf-8", errors="replace") if (p / "README.md").exists() else ""
    r.append(("README üç modül", all(m in readme for m in ("metin", "sayi", "tarih")), ""))
    return r


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = sys.argv[1:]
    out = ROOT / "build" / "e2e_proje"
    if "--cikti" in args:
        i = args.index("--cikti")
        out = Path(args[i + 1])
        del args[i:i + 2]
    hedef, par = "tek", None
    if "--hedef" in args:
        i = args.index("--hedef")
        hedef = args[i + 1]
        del args[i:i + 2]
    if "--paralel" in args:
        i = args.index("--paralel")
        par = int(args[i + 1])
        del args[i:i + 2]
    model = args[0] if args else "auto-pro"
    base = out.resolve() / (model + ("" if hedef == "tek" else f"-{hedef}") + ("" if par is None else f"-p{par}"))
    shutil.rmtree(base, ignore_errors=True)
    proj = base / "proje"
    proj.mkdir(parents=True)
    os.environ["EVREN_STUDIO_DATA_DIR"] = str(base / "data")
    env = {**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "T",
           "GIT_COMMITTER_EMAIL": "t@t"}
    for a in (["init", "-q", "-b", "master"],):
        subprocess.run(["git", *a], cwd=proj, env=env, check=True)
    (proj / "README.md").write_text("# Sıcaklık\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=proj, env=env, check=True)
    subprocess.run(["git", "-c", "core.hooksPath=", "commit", "-q", "-m", "ilk"], cwd=proj, env=env, check=True)

    from PySide6.QtWidgets import QApplication, QMessageBox

    from evren_studio.secrets import load_api_key

    if not load_api_key():
        print("FAIL: EVREN API anahtarı yok")
        return 1
    errors: list[str] = []
    sys.excepthook = lambda t, v, tb: errors.append(f"{t.__name__}: {v}")
    app = QApplication(sys.argv)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
    from evren_studio.ui.main_window import MainWindow
    from evren_studio.ui.project_ui import PlanCard

    w = MainWindow()
    w.start_background_loads()  # uygulamayla aynı açılış: canlı model listesi + kullanım (app.py)
    w.resize(1440, 900)
    w.show()
    notes: list[tuple[str, str]] = []
    w.session.notify.connect(lambda t, x: notes.append((t, x)))

    def pump(sec):
        end = time.monotonic() + sec
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.03)

    def wait(cond, limit):
        end = time.monotonic() + limit
        while time.monotonic() < end:
            app.processEvents()
            if cond():
                return True
            time.sleep(0.05)
        return cond()

    if par is not None:
        w.ctx.settings.project_parallel = par
    s = w.session
    s.new_session()
    s.welcome._choose(str(proj))
    s.composer.set_model(model, emit=True)
    t0 = time.monotonic()
    s.send("/proje " + (HEDEF_PAR if hedef == "paralel" else HEDEF))
    ok_plan = wait(lambda: s.findChildren(PlanCard) or (not s.running and not s.project.planning), 15 * 60)
    pump(1)
    cards = s.findChildren(PlanCard)
    w.grab().save(str(base / "1_plan_karti.png"))
    if not cards:
        print("FAIL: plan kartı gelmedi")
        return 1
    st = s.project.state
    plan_s = round(time.monotonic() - t0)
    print(f"[{model}] plan: {len(st.tasks)} görev · {plan_s} sn", flush=True)
    for t in st.tasks:
        print(f"   {t.idx}. {t.title} | ölçüt: {t.criteria[:70]} | doğrulama: {t.check[:50]} | bağımlı: {t.depends}",
              flush=True)
    t_run = time.monotonic()
    cards[-1].approved.emit()
    shot = {"done": False}

    def maybe_shot():
        if not shot["done"] and s.running and s.project.label:
            w.grab().save(str(base / "2_calisirken.png"))
            shot["done"] = True
        return not s.project.active

    finished = wait(maybe_shot, LIMIT)
    pump(2)
    w.grab().save(str(base / "3_bitti.png"))
    st = s.project.state
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=proj, capture_output=True, text=True).stdout.strip()
    # Tam mesaj: commit'in ilk satırı yapay zekâ önerisi olabilir, "EVREN proje görev N" gövdededir
    log = subprocess.run(["git", "log", "--format=%B"], cwd=proj, capture_output=True, text=True,
                         encoding="utf-8").stdout
    checks = kabul_par(proj) if hedef == "paralel" else kabul(proj)
    passed = sum(1 for _n, o, _d in checks if o)
    paralel_log = [x for x in st.log if "AYNI ANDA" in x or "paralel" in x or "sırayla" in x or "gözetmen" in x]
    rapor = {
        "model": model, "hedef": hedef, "paralel": par, "plan_sn": plan_s,
        "yurutme_sn": round(time.monotonic() - t_run), "paralel_gunluk": paralel_log[:20],
        "sure_sn": round(time.monotonic() - t0), "zaman_icinde": finished,
        "durum": st.status, "duraklama": st.pause_reason,
        "gorevler": [{"no": t.idx, "baslik": t.title, "durum": t.status, "deneme": t.attempts,
                      "model": t.model, "commit": t.commit[:8], "not": t.note[:160], "sn": round(t.seconds)}
                     for t in st.tasks],
        "dal": branch, "commit_sayisi": log.count("EVREN proje görev"),
        "plan_dosyasi": (proj / "EVREN_PLAN.md").exists(), "rapor_dosyasi": (proj / "EVREN_RAPOR.md").exists(),
        "bildirim": notes[-1:] if notes else [],
        "kabul": [{"test": n, "gecti": o, "ayrinti": d} for n, o, d in checks], "kabul_skor": f"{passed}/{len(checks)}",
        "yakalanmamis_hata": errors[:5],
    }
    (base / "rapor.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    for x in paralel_log:
        print("   [paralel] " + x[:160], flush=True)
    print(f"[{model}] yürütme {rapor['yurutme_sn']} sn (plan {plan_s} sn)", flush=True)
    print(f"[{model}] durum={st.status} · {rapor['sure_sn']} sn · dal={branch} · commit={rapor['commit_sayisi']} "
          f"· plan/rapor dosyası={rapor['plan_dosyasi']}/{rapor['rapor_dosyasi']} · bildirim={bool(notes)}", flush=True)
    for t in rapor["gorevler"]:
        print(f"   {t['no']}. {t['durum']:9s} deneme={t['deneme']} model={t['model']} {t['sn']} sn {t['not'][:90]}",
              flush=True)
    for n, o, d in checks:
        print(f"   {'GEÇTİ' if o else 'KALDI'} | {n}" + (f" | {d}" if d and not o else ""), flush=True)
    print(f"== SONUÇ {model}: kabul {passed}/{len(checks)} · hata={len(errors)}", flush=True)
    w.close()
    pump(1)
    return 0 if passed == len(checks) and st.status == "bitti" else 1


if __name__ == "__main__":
    raise SystemExit(main())
