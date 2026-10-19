"""MCP (Serena) gerçek API uçtan uca ölçümü — arayüz üzerinden, gerçek EVREN modeliyle.

Kullanım:
    .\\.venv\\Scripts\\python.exe tests\\e2e_mcp_real_api.py [model] [--serena-veri KLASÖR]

Serena önceden kurulmuş olmalı (Ayarlar > MCP > "Serena'yı kur" veya
`mcp.install_serena(KLASÖR)`); varsayılan KLASÖR: build/mcp_data.

Her görev iki kez koşulur: Serena AÇIK ve KAPALI (karşılaştırma). Proje, metin aramasını
yanıltan tuzaklar içerir: `vergi_hesapla_eski` adlı başka fonksiyon ve adı geçen bir not dosyası.
Ölçülen: görev sonucu (kabul denetimi), adım, süre, çağrılan araçlar (MCP sayısı).
"""
from __future__ import annotations

import ast
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

FILES = {
    "hesap.py": (
        "def vergi_hesapla(tutar, oran=0.2):\n"
        "    \"\"\"Tutarın vergisini döndürür.\"\"\"\n"
        "    return round(tutar * oran, 2)\n\n\n"
        "class Fatura:\n"
        "    def __init__(self, tutar):\n"
        "        self.tutar = tutar\n\n"
        "    def toplam(self):\n"
        "        return self.tutar + vergi_hesapla(self.tutar)\n"),
    "siparis.py": (
        "from hesap import vergi_hesapla\n\n\n"
        "def siparis_toplami(kalemler):\n"
        "    ara = sum(kalemler)\n"
        "    return ara + vergi_hesapla(ara, oran=0.1)\n"),
    "rapor.py": (
        "from hesap import Fatura\n\n\n"
        "def rapor(tutarlar):\n"
        "    return [Fatura(t).toplam() for t in tutarlar]\n"),
    "eski.py": (
        "def vergi_hesapla_eski(tutar):\n"
        "    # eski sürüm: vergi_hesapla yerine bu kullanılıyordu\n"
        "    return tutar * 0.18\n\n\n"
        "def eski_rapor(t):\n"
        "    return vergi_hesapla_eski(t)\n"),
    "ana.py": (
        "from hesap import vergi_hesapla\n"
        "from rapor import rapor\n"
        "from siparis import siparis_toplami\n\n"
        "print(vergi_hesapla(100))\n"
        "print(siparis_toplami([10, 20]))\n"
        "print(rapor([50]))\n"),
    "notlar.md": "# Notlar\n\nvergi_hesapla fonksiyonu KDV için kullanılır. vergi_hesapla(100) = 20.\n",
    "tests/test_hesap.py": (
        "import sys, unittest\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
        "import hesap, siparis, rapor, eski\n\n\n"
        "class T(unittest.TestCase):\n"
        "    def test_hepsi(self):\n"
        "        v = getattr(hesap, 'kdv_hesapla', None) or hesap.vergi_hesapla\n"
        "        self.assertEqual(v(100), 20.0)\n"
        "        self.assertEqual(siparis.siparis_toplami([10, 20]), 33.0)\n"
        "        self.assertEqual(rapor.rapor([50]), [60.0])\n"
        "        self.assertEqual(eski.vergi_hesapla_eski(100), 18.0)\n\n\n"
        "if __name__ == '__main__':\n    unittest.main()\n"),
}


def _force_remove(func, path, _exc) -> None:
    os.chmod(path, 0o700)
    func(path)


def kur(p: Path) -> None:
    for rel, text in FILES.items():
        f = p / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    kur_git(p)


def kur_git(p: Path) -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "T",
           "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q", "-b", "master"], cwd=p, env=env, check=True)
    subprocess.run(["git", "add", "-A"], cwd=p, env=env, check=True)
    subprocess.run(["git", "-c", "core.hooksPath=", "commit", "-q", "-m", "ilk"], cwd=p, env=env, check=True)


def _calls(src: str, name: str) -> int:
    tree = ast.parse(src)
    return sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == name)


def kabul_soru(p: Path, cevap: str) -> list[tuple[str, bool]]:
    c = cevap.lower()
    # vergi_hesapla_eski geçiyorsa yakınında (tablo başlığı/özet dahil) "çağrı değil" ayrımı olmalı.
    # İlk sürüm satır satır bakıyordu; doğru cevaptaki tablo satırlarını yanlışlıkla düşürdü.
    keys = ("farklı", "ayrı", "değil", "sayılma", "hariç", "benzer", "dahil edilm")
    idx = [i for i in range(len(c)) if c.startswith("vergi_hesapla_eski", i)]
    ayirdi = not idx or any(any(k in c[max(0, i - 300):i + 300] for k in keys) for i in idx)
    return [
        ("siparis.py çağrısı bulundu", "siparis.py" in c),
        ("Fatura.toplam (hesap.py) çağrısı bulundu", "toplam" in c),
        ("ana.py çağrısı bulundu", "ana.py" in c),
        ("eski.py / notlar.md çağrı sayılmadı", ayirdi),
    ]


def kabul_duzenle(p: Path) -> list[tuple[str, bool]]:
    src = {rel: (p / rel).read_text(encoding="utf-8") for rel in FILES if rel.endswith(".py")}
    r = subprocess.run([PY, "-m", "unittest", "discover", "-s", "tests"], cwd=p, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    kalan = sum(_calls(s, "vergi_hesapla") for s in src.values())
    return [
        ("hesap.py'de kdv_hesapla tanımı var", "def kdv_hesapla(" in src["hesap.py"]),
        ("vergi_hesapla çağrısı kalmadı", kalan == 0 and "def vergi_hesapla(" not in src["hesap.py"]),
        ("eski.py'ye dokunulmadı", src["eski.py"] == FILES["eski.py"]),
        ("notlar.md'ye dokunulmadı", (p / "notlar.md").read_text(encoding="utf-8") == FILES["notlar.md"]),
        ("testler geçiyor", r.returncode == 0),
        ("ana.py çalışıyor", subprocess.run([PY, "ana.py"], cwd=p, capture_output=True).returncode == 0),
    ]


BUYUK_HEDEF = "estimate_tokens"


def kur_buyuk(p: Path) -> None:
    """Büyük proje: uygulamanın kendi kaynağının kopyası (~17 bin satır)."""
    shutil.copytree(ROOT / "src" / "evren_studio", p / "evren_studio",
                    ignore=shutil.ignore_patterns("__pycache__"))
    kur_git(p)


def gercek_cagiranlar(p: Path, target: str) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for f in (p / "evren_studio").rglob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for n in ast.walk(node):
                    if isinstance(n, ast.Call) and target in (getattr(n.func, "id", None), getattr(n.func, "attr", None)):
                        out.add((f.name, node.name))
    return out


def kabul_buyuk(p: Path, cevap: str) -> list[tuple[str, bool]]:
    c = cevap.lower()
    truth = gercek_cagiranlar(p, BUYUK_HEDEF)
    checks = [("tanım yeri (runner.py) doğru", "runner.py" in c)]
    for fname, func in sorted(truth):
        checks.append((f"{fname} · {func}", fname.lower() in c and func.lower() in c))
    return checks


WEB_FILES = {
    "index.html": ('<!doctype html><html><head><meta charset="utf-8"><title>Sayaç</title></head><body>\n'
                   '<h1>Sayaç</h1><p id="deger">0</p>\n<button id="art">Artır</button>\n'
                   '<script src="sayac.js"></script></body></html>\n'),
    "sayac.js": ("let n = 0;\n"
                 "document.getElementById('art').addEventListener('click', () => {\n"
                 "  n += 1;\n"
                 "  document.getElementById('degr').textContent = String(n);\n"
                 "});\n"),
}

TS_FILES = {
    "package.json": '{"name":"ornek","version":"1.0.0"}\n',
    "tsconfig.json": '{"compilerOptions":{"strict":true,"target":"es2020","module":"commonjs"}}\n',
    "src/hesap.ts": "export function vergiHesapla(t: number, oran = 0.2): number {\n  return Math.round(t * oran * 100) / 100;\n}\n"
                    "export function vergiHesaplaEski(t: number): number {\n  return t * 0.18;\n}\n",
    "src/fatura.ts": "import { vergiHesapla } from './hesap';\n\nexport class Fatura {\n  constructor(public tutar: number) {}\n"
                     "  toplam(): number {\n    return this.tutar + vergiHesapla(this.tutar);\n  }\n}\n",
    "src/siparis.ts": "import { vergiHesapla } from './hesap';\n\nexport function siparisToplami(k: number[]): number {\n"
                      "  const ara = k.reduce((a, b) => a + b, 0);\n  return ara + vergiHesapla(ara, 0.1);\n}\n",
    "src/rapor.ts": "import { Fatura } from './fatura';\nimport { vergiHesaplaEski } from './hesap';\n\n"
                    "export const rapor = (t: number[]) => t.map((x) => new Fatura(x).toplam());\n"
                    "export const eski = (t: number) => vergiHesaplaEski(t);\n",
    "src/ana.ts": "import { vergiHesapla } from './hesap';\nimport { rapor } from './rapor';\n\n"
                  "console.log(vergiHesapla(100), rapor([50]));\n",
    "NOTLAR.md": "vergiHesapla KDV hesaplar.\n",
}


def kur_dosyalar(p: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        f = p / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    kur_git(p)


def kabul_web(p: Path, cevap: str) -> list[tuple[str, bool]]:
    js = (p / "sayac.js").read_text(encoding="utf-8")
    html = (p / "index.html").read_text(encoding="utf-8")
    node = shutil.which("node") or r"C:\Program Files\nodejs\node.exe"
    sim = ("const els={art:{l:null,addEventListener(e,f){this.l=f}},deger:{textContent:'0'}};"
           "global.document={getElementById:(i)=>els[i]||null};"
           f"{js}\nels.art.l();els.art.l();console.log(els.deger.textContent)")
    r = subprocess.run([node, "-e", sim], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [
        ("tıklayınca sayaç artıyor (2 tık → 2)", r.returncode == 0 and r.stdout.strip() == "2"),
        ("yanlış kimlik 'degr' kalmadı", "'degr'" not in js and '"degr"' not in js),
        ("index.html'deki kimlik korunmuş", 'id="deger"' in html),
    ]


def kabul_ts(p: Path, cevap: str) -> list[tuple[str, bool]]:
    src = {rel: (p / rel).read_text(encoding="utf-8") for rel in TS_FILES if rel.endswith(".ts")}
    allsrc = "\n".join(src.values())
    import re as _re

    kalan = len(_re.findall(r"\bvergiHesapla\b", allsrc))
    return [
        ("hesap.ts'de kdvHesapla tanımı", "export function kdvHesapla(" in src["src/hesap.ts"]),
        ("vergiHesapla kalmadı (eski hariç)", kalan == 0),
        ("vergiHesaplaEski korunmuş", src["src/hesap.ts"].count("vergiHesaplaEski") == 1
         and "vergiHesaplaEski" in src["src/rapor.ts"]),
        ("NOTLAR.md'ye dokunulmadı", (p / "NOTLAR.md").read_text(encoding="utf-8") == TS_FILES["NOTLAR.md"]),
        ("fatura/siparis/ana güncel", all("kdvHesapla" in src[f] for f in ("src/fatura.ts", "src/siparis.ts", "src/ana.ts"))),
    ]


GOREVLER = {
    "soru": ("vergi_hesapla fonksiyonu nerede TANIMLI ve onu gerçekten ÇAĞIRAN yerler hangileri? "
             "Her birini dosya, satır ve hangi fonksiyonun/metodun içinde olduğu ile listele. Benzer adlı "
             "başka fonksiyonları ve yorum/metin geçişlerini çağrı sayma. Dosya değiştirme."),
    "duzenle": ("vergi_hesapla fonksiyonunun adını kdv_hesapla yap: tanımı ve onu çağıran/içe aktaran "
                "TÜM yerleri güncelle. vergi_hesapla_eski fonksiyonuna, notlar.md'ye ve tests/ klasörüne "
                "dokunma. Sonunda `python -m unittest discover -s tests` çalıştırıp sonucu söyle."),
    "web": ("index.html'deki Artır butonuna basınca sayaç artmıyor. Sayfayı tarayıcıda açıp butona bas, "
            "konsoldaki hatayı bul, düzelt ve tarayıcıda tekrar deneyip çalıştığını doğrula."),
    "ts": ("TypeScript projesinde vergiHesapla fonksiyonunun adını kdvHesapla yap: tanımı ve onu kullanan/içe "
           "aktaran TÜM yerleri güncelle. vergiHesaplaEski fonksiyonuna ve NOTLAR.md'ye dokunma."),
    "buyuk": (f"{BUYUK_HEDEF} fonksiyonu nerede TANIMLI ve hangi dosyalarda, HANGİ fonksiyon/metotların "
              "içinde gerçekten ÇAĞRILIYOR? Her çağrıyı dosya ve çağıran fonksiyon/metot adıyla listele; "
              "import satırlarını, yorumları ve metinleri sayma. Dosya değiştirme."),
}


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = sys.argv[1:]
    serena_data = ROOT / "build" / "mcp_data"
    if "--serena-veri" in args:
        i = args.index("--serena-veri")
        serena_data = Path(args[i + 1])
        del args[i:i + 2]
    model = args[0] if args else "auto-pro"
    secim = args[1:] or list(GOREVLER)
    from evren_studio.agent import mcp

    if not mcp.serena_ready(serena_data):
        print(f"FAIL: Serena kurulu değil: {serena_data} (önce mcp.install_serena)")
        return 1
    base = (ROOT / "build" / "e2e_mcp" / model).resolve()
    if base.exists():
        shutil.rmtree(base, onerror=_force_remove)  # git nesneleri Windows'ta salt okunur
    base.mkdir(parents=True)
    os.environ["EVREN_STUDIO_DATA_DIR"] = str(base / "data")

    from PySide6.QtWidgets import QApplication, QMessageBox

    from evren_studio.secrets import load_api_key

    if not load_api_key():
        print("FAIL: EVREN API anahtarı yok")
        return 1
    errors: list[str] = []
    sys.excepthook = lambda t, v, tb: errors.append(f"{t.__name__}: {v}")
    app = QApplication(sys.argv)
    for name in ("question", "information", "warning"):
        setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.Yes))

    import evren_studio.ui.session_view as sv
    from evren_studio.agent.runner import AgentRunner
    from evren_studio.ui.main_window import MainWindow
    from evren_studio.ui.transcript import ApprovalWidget

    calls: list[str] = []
    outcomes: list[dict] = []
    notes: list[str] = []

    bekci: list[str] = []

    class RecordingRunner(AgentRunner):
        def _execute(self, call):
            calls.append(call.name)
            res = super()._execute(call)
            if "HATA BEKÇİSİ" in (res.content or ""):
                bekci.append(call.name)
            return res

        def run(self, history):
            t0 = time.monotonic()
            o = super().run(history)
            outcomes.append({"stopped": o.stopped, "steps": o.steps, "sure": round(time.monotonic() - t0, 1)})
            return o

    sv.AgentRunner = RecordingRunner
    orig_note = sv.SessionView._note
    sv.SessionView._note = lambda self, text, icon_name="dot": (notes.append(text), orig_note(self, text, icon_name))[1]

    w = MainWindow()
    w.resize(1440, 900)
    w.show()

    # Serena kurulu klasör uygulamanın veri klasöründen farklı: yönetici oraya bakar
    w.ctx.mcp.data_dir = serena_data
    serena_cfg = mcp.serena_config().to_dict()
    playwright_cfg = mcp.playwright_config().to_dict()

    def pump(sec):
        end = time.monotonic() + sec
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.03)

    def wait_turn(limit) -> bool:
        end = time.monotonic() + limit
        pump(1.0)
        while time.monotonic() < end:
            app.processEvents()
            for b in [b for b in w.session.findChildren(ApprovalWidget) if b.isVisible() and not b.request.resolved]:
                b._decide("allow")
            if not w.session.running:
                pump(2.0)
                if not w.session.running:
                    return True
            time.sleep(0.05)
        return False

    rows = []
    print(f"== MCP (Serena {mcp.SERENA_VERSION}) ölçümü · model={model}", flush=True)
    for gorev in secim:
        mesaj = GOREVLER[gorev]
        for serena in (True, False):
            etiket = f"{gorev}/{'serena' if serena else 'serenasiz'}"
            proj = base / etiket.replace("/", "_")
            proj.mkdir()
            {"buyuk": kur_buyuk, "web": lambda q: kur_dosyalar(q, WEB_FILES),
             "ts": lambda q: kur_dosyalar(q, TS_FILES)}.get(gorev, kur)(proj)
            w.ctx.settings.mcp_enabled = serena
            w.ctx.settings.mcp_servers = [dict(serena_cfg), dict(playwright_cfg)] if serena else []
            n_calls, n_out, n_notes, n_bekci = len(calls), len(outcomes), len(notes), len(bekci)
            w.new_session()
            w.session.welcome._choose(str(proj))
            w.session.composer.set_model(model, emit=True)
            w.session.composer.set_mode("auto", emit=True)
            t0 = time.monotonic()
            w.session.send(mesaj)
            ok = wait_turn(15 * 60)
            sure = round(time.monotonic() - t0, 1)
            tur = outcomes[n_out:]
            used = calls[n_calls:]
            mcp_used = [c for c in used if c.startswith("mcp__")]
            msgs = w.ctx.db.get_session_messages(w.session.session_id)
            cevap = next((m["content"] for m in reversed(msgs) if m["role"] == "assistant" and m["content"]), "")
            checks = {"soru": lambda: kabul_soru(proj, cevap), "duzenle": lambda: kabul_duzenle(proj),
                      "buyuk": lambda: kabul_buyuk(proj, cevap), "web": lambda: kabul_web(proj, cevap),
                      "ts": lambda: kabul_ts(proj, cevap)}[gorev]()
            if gorev == "buyuk":
                checks.append(("dosya değişmedi", not subprocess.run(
                    ["git", "status", "--porcelain", "--", "evren_studio"], cwd=proj, capture_output=True,
                    text=True).stdout.strip()))
            checks.append((".serena proje klasörüne yazılmadı", not (proj / ".serena").exists()))
            if gorev == "soru":
                checks.append(("dosya değişmedi", all((proj / r).read_text(encoding="utf-8") == t
                                                      for r, t in FILES.items())))
            passed = sum(1 for _n, o in checks if o)
            steps = sum(o["steps"] for o in tur)
            print(f"[{'TAMAM' if passed == len(checks) and ok else 'KALDI'}] {etiket:20} {passed}/{len(checks)} · "
                  f"{sure:6.1f} sn · adım {steps:2} · araç {len(used):2} (MCP {len(mcp_used)}) · "
                  f"durma={[o['stopped'] for o in tur]} · bekçi {len(bekci) - n_bekci}", flush=True)
            for n, o in checks:
                if not o:
                    print(f"     KALDI | {n}", flush=True)
            if mcp_used:
                print(f"     MCP: {', '.join(sorted(set(mcp_used)))}", flush=True)
            for n in notes[n_notes:]:
                if "MCP" in n or "serena" in n.lower():
                    print(f"     not: {n[:200]}", flush=True)
            rows.append((etiket, passed, len(checks), sure, steps, len(used), len(mcp_used)))
            (base / f"{etiket.replace('/', '_')}_cevap.md").write_text(cevap, encoding="utf-8")
    w.close()
    pump(1.0)
    tam = sum(1 for r in rows if r[1] == r[2])
    print(f"== SONUÇ {model}: {tam}/{len(rows)} koşu tam · yakalanmamış hata={len(errors)}", flush=True)
    for e in errors[:5]:
        print("   hata:", e)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
