"""QA ajanı gerçek API uçtan uca ölçümü — arayüz üzerinden, gerçek EVREN modeli, gerçek tarayıcı.

Kullanım:
    .\\.venv\\Scripts\\python.exe tests\\e2e_qa_real_api.py [--mcp-veri build/mcp_data]

Playwright (ve isteğe bağlı Serena) önceden kurulmuş olmalı (Ayarlar > MCP). Küçük bir web uygulaması
kurulur: sunucusu var (`python server.py`, port 8765) ve 3 BİLİNEN hata içerir:
  1. "Artır" butonu yanlış öğe kimliği yüzünden JS hatası verir (sayaç artmaz).
  2. Ad alanı boş gönderilince "Ad gerekli" uyarısı çıkmaz (doğrulama yok).
  3. /api/topla toplama yerine çıkarma yapar (2+3 → -1).
Ölçülen: plan, kaç bilinen hatanın "kaldi" bulunduğu, yanlış alarm, servis kullanımı, proje dosyalarına
dokunulmaması, rapor, süre.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FILES = {
    "README.md": "# Mini Uygulama\n\nÇalıştırma: `python server.py` → http://127.0.0.1:8765/\n\n"
                 "İşlevler: sayaç (Artır), selamlama formu (ad boşsa 'Ad gerekli' uyarısı), iki sayıyı toplama (API).\n",
    "server.py": (
        "import json\nfrom http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer\n"
        "from urllib.parse import urlparse, parse_qs\n\n\n"
        "class H(SimpleHTTPRequestHandler):\n"
        "    def do_GET(self):\n"
        "        u = urlparse(self.path)\n"
        "        if u.path == '/api/topla':\n"
        "            q = parse_qs(u.query)\n"
        "            a, b = float(q.get('a', ['0'])[0]), float(q.get('b', ['0'])[0])\n"
        "            body = json.dumps({'sonuc': a - b}).encode()\n"
        "            self.send_response(200)\n"
        "            self.send_header('Content-Type', 'application/json')\n"
        "            self.end_headers()\n"
        "            self.wfile.write(body)\n"
        "            return\n"
        "        return super().do_GET()\n\n\n"
        "if __name__ == '__main__':\n"
        "    print('Sunucu: http://127.0.0.1:8765/', flush=True)\n"
        "    ThreadingHTTPServer(('127.0.0.1', 8765), H).serve_forever()\n"),
    "index.html": (
        '<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>Mini Uygulama</title></head><body>\n'
        '<main>\n<h1>Mini Uygulama</h1>\n'
        '<section><h2>Sayaç</h2><p id="deger">0</p><button id="art">Artır</button></section>\n'
        '<section><h2>Selamlama</h2><input id="ad" placeholder="Adınız"> <button id="selamla">Selamla</button>'
        '<p id="mesaj"></p></section>\n'
        '<section><h2>Toplama</h2><input id="a" value="2"> + <input id="b" value="3"> '
        '<button id="topla">Topla</button> = <span id="sonuc"></span></section>\n'
        '</main>\n<script src="app.js"></script></body></html>\n'),
    "app.js": (
        "let n = 0;\n"
        "document.getElementById('art').addEventListener('click', () => {\n"
        "  n += 1;\n  document.getElementById('degr').textContent = String(n);\n});\n"
        "document.getElementById('selamla').addEventListener('click', () => {\n"
        "  const ad = document.getElementById('ad').value.trim();\n"
        "  document.getElementById('mesaj').textContent = ad ? 'Merhaba ' + ad + '!' : '';\n});\n"
        "document.getElementById('topla').addEventListener('click', async () => {\n"
        "  const a = document.getElementById('a').value, b = document.getElementById('b').value;\n"
        "  const r = await fetch('/api/topla?a=' + encodeURIComponent(a) + '&b=' + encodeURIComponent(b));\n"
        "  document.getElementById('sonuc').textContent = (await r.json()).sonuc;\n});\n"),
}
BUGS = {
    "sayaç/Artır": ("sayaç", "artır", "degr", "deger"),
    "boş ad uyarısı": ("gerekli", "boş", "uyarı"),
    "toplama yanlış": ("topla", "-1", "çıkar", "yanlış"),
}


def _force_remove(func, path, _exc) -> None:
    os.chmod(path, 0o700)
    func(path)


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = sys.argv[1:]
    mcp_data = ROOT / "build" / "mcp_data"
    if "--mcp-veri" in args:
        i = args.index("--mcp-veri")
        mcp_data = Path(args[i + 1])
    from evren_studio.agent import mcp

    if not mcp.playwright_ready(mcp_data):
        print(f"FAIL: Playwright kurulu değil: {mcp_data}")
        return 1
    base = (ROOT / "build" / "e2e_qa").resolve()
    if base.exists():
        shutil.rmtree(base, onerror=_force_remove)
    proj = base / "proje"
    proj.mkdir(parents=True)
    for rel, text in FILES.items():
        (proj / rel).write_text(text, encoding="utf-8")
    env = {**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "T",
           "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q", "-b", "master"], cwd=proj, env=env, check=True)
    subprocess.run(["git", "add", "-A"], cwd=proj, env=env, check=True)
    subprocess.run(["git", "-c", "core.hooksPath=", "commit", "-q", "-m", "ilk"], cwd=proj, env=env, check=True)
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

    import evren_studio.ui.session_view as sv_mod
    from evren_studio.agent.runner import AgentRunner
    from evren_studio.ui.main_window import MainWindow
    from evren_studio.ui.qa_ui import QaDoneCard, QaPlanCard

    calls: list[str] = []

    class RecordingRunner(AgentRunner):
        def _execute(self, call):
            calls.append(call.name)
            return super()._execute(call)

    sv_mod.AgentRunner = RecordingRunner
    w = MainWindow()
    w.resize(1440, 900)
    w.show()
    w.ctx.mcp.data_dir = mcp_data
    w.ctx.settings.mcp_enabled = True
    w.ctx.settings.mcp_servers = [mcp.playwright_config().to_dict()]

    def pump(sec):
        end = time.monotonic() + sec
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.03)

    def wait(cond, limit) -> bool:
        end = time.monotonic() + limit
        while time.monotonic() < end:
            app.processEvents()
            if cond():
                return True
            time.sleep(0.05)
        return cond()

    t0 = time.monotonic()
    w.new_session()
    w.session.welcome._choose(str(proj))
    w.session.send("/qa sayaç, selamlama formu ve toplama işlevlerini test et")
    pump(1)
    planned = wait(lambda: not w.session.qa.planning and not w.session.running, 15 * 60)
    cards = w.session.findChildren(QaPlanCard)
    st = w.session.qa.state
    print(f"[PLAN] {'tamam' if planned and cards else 'YOK'} · {round(time.monotonic() - t0)} sn · "
          f"{len(st.scenarios) if st else 0} senaryo · çalıştırma: {st.run_hint if st else '-'}", flush=True)
    if not (cards and st):
        print("== SONUÇ: plan çıkmadı")
        return 1
    for s in st.scenarios:
        print(f"   {s.idx}. {s.title} — beklenen: {s.expected[:80]}", flush=True)
    w.session.transcript.scroll_to_bottom()
    pump(1)
    w.grab().save(str(base / "qa_1_plan.png"))
    t1 = time.monotonic()
    cards[-1].ok_btn.click()
    pump(2)
    finished = wait(lambda: not w.session.qa.active, 60 * 60)
    pump(3)
    w.session.transcript.scroll_to_bottom()
    pump(1)
    w.grab().save(str(base / "qa_2_sonuc.png"))
    st = w.session.qa.state
    print(f"[TEST] {'bitti' if finished else 'ZAMAN AŞIMI'} · {round(time.monotonic() - t1)} sn · durum={st.status}",
          flush=True)
    for s in st.scenarios:
        print(f"   [{s.status:10}] {s.idx}. {s.title} · {round(s.seconds)} sn — {(s.summary or s.actual)[:140]}", flush=True)
    text_of = {s.idx: f"{s.title} {s.expected} {s.actual} {s.summary} {s.evidence}".lower() for s in st.scenarios}
    found = {}
    for bug, keys in BUGS.items():
        found[bug] = any(s.status == "kaldi" and sum(k in text_of[s.idx] for k in keys) >= 1
                         and (bug != "sayaç/Artır" or any(k in text_of[s.idx] for k in ("sayaç", "artır")))
                         and (bug != "boş ad uyarısı" or any(k in text_of[s.idx] for k in ("boş", "gerekli")))
                         and (bug != "toplama yanlış" or "topla" in text_of[s.idx])
                         for s in st.scenarios)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=proj, capture_output=True, text=True).stdout
    changed = [ln for ln in status.splitlines() if "EVREN_QA_RAPORU.md" not in ln]
    checks = [(f"bilinen hata bulundu: {b}", ok) for b, ok in found.items()]
    checks += [("proje dosyalarına dokunulmadı", not changed),
               ("rapor yazıldı", (proj / "EVREN_QA_RAPORU.md").exists()),
               ("start_service kullanıldı", "start_service" in calls),
               ("tarayıcı kullanıldı", any(c.startswith("mcp__playwright__") for c in calls)),
               ("bitiş kartı", bool(w.session.findChildren(QaDoneCard))),
               ("servisler kapatıldı", not any(sm.running() for sm in w.session._services.values()))]
    for n, ok in checks:
        print(f"   {'GEÇTİ' if ok else 'KALDI'} | {n}", flush=True)
    used = {c: calls.count(c) for c in sorted(set(calls))}
    print(f"   araçlar: {used}", flush=True)
    passed = sum(1 for _n, ok in checks if ok)
    w.close()
    pump(1)
    print(f"== SONUÇ QA: {passed}/{len(checks)} · bilinen hata {sum(found.values())}/{len(BUGS)} · "
          f"toplam {round(time.monotonic() - t0)} sn · yakalanmamış hata={len(errors)}", flush=True)
    for e in errors[:5]:
        print("   hata:", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
