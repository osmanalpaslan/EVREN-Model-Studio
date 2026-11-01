"""Web araması (web_search) gerçek ölçümü — R-25 açık/kapalı karşılaştırması (EVREN anahtarı gerekir; pytest toplamaz).

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_websearch_real_api.py <model> [görev ...] [--kapali] [--cikti klasör]

Örnek: `... e2e_websearch_real_api.py auto-pro` ve `... e2e_websearch_real_api.py auto-pro --kapali`
(--kapali: web_search ajana HİÇ sunulmaz; yalnız eski yollar — web_fetch, komut — kalır).

Görevler güncel bilgi ister; doğru cevap koşu anında kaynağından (PyPI, endoflife.date) okunur, yani model
eğitim bilgisinden ezbere yazarsa kalır. `gereksiz` görevi internet gerektirmez: orada arama YAPILMAMALI (R-22).
Tavily anahtarı Ayarlar'dan (Credential Manager) okunur; yoksa anahtarsız zincir kullanılır.
Sürücü zorluk paketininkidir (tests/e2e_zorluk_real_api.py main): rapor <cikti>/<model>/rapor.json.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))


def _pypi(paket: str) -> str:
    import httpx

    return httpx.get(f"https://pypi.org/pypi/{paket}/json", timeout=20).json()["info"]["version"]


def _python_son() -> str:
    import httpx

    rows = httpx.get("https://endoflife.date/api/python.json", timeout=20).json()
    return rows[0]["latest"]           # en yeni dal ilk sırada


def _kontrol_surum(proj: Path, _durum, yanit: str):
    f = proj / "requirements.txt"
    txt = f.read_text(encoding="utf-8", errors="ignore") if f.is_file() else ""
    out = [("requirements.txt var", bool(txt), "")]
    for paket in ("flask", "requests"):
        dogru = _pypi(paket)
        m = re.search(rf"(?im)^\s*{paket}\s*==\s*([0-9][0-9a-z.\-]*)", txt)
        yazilan = m.group(1) if m else ""
        out.append((f"{paket} güncel sürüm", yazilan == dogru, f"yazılan={yazilan or '-'} doğru={dogru}"))
    return out


def _kontrol_python(proj: Path, _durum, yanit: str):
    f = proj / "notlar.md"
    txt = f.read_text(encoding="utf-8", errors="ignore") if f.is_file() else ""
    dogru = _python_son()
    return [("notlar.md var", bool(txt), ""),
            ("Python son sürümü", dogru in txt, f"doğru={dogru}"),
            ("kaynak adresi", "http" in txt, "")]


def _kontrol_gereksiz(proj: Path, _durum, yanit: str):
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "."], cwd=proj,
                       capture_output=True, text=True, timeout=60)
    return [("topla.py var", (proj / "topla.py").is_file(), ""),
            ("testler geçiyor", r.returncode == 0 and "OK" in (r.stderr + r.stdout), r.stderr[-120:])]


GOREVLER = {
    "surum": {"kur": lambda p: None, "kontrol": _kontrol_surum,
              "mesaj": "Bu klasörde requirements.txt oluştur: flask ve requests paketlerini PyPI'daki EN SON kararlı "
                       "sürümlerine `==` ile sabitle (örn. `flask==X.Y.Z`). Sürümleri ezberden yazma, güncel "
                       "bilgiyi doğrula. Sonunda sürümleri nereden doğruladığını yaz."},
    "python": {"kur": lambda p: None, "kontrol": _kontrol_python,
               "mesaj": "notlar.md dosyası oluştur: Python programlama dilinin şu an yayımlanmış en son kararlı "
                        "sürüm numarasını (ör. 3.x.y biçiminde) ve yayın tarihini yaz, bilgiyi aldığın kaynağın "
                        "adresini ekle. Güncel bilgiyi doğrula."},
    "gereksiz": {"kur": lambda p: None, "kontrol": _kontrol_gereksiz,
                 "mesaj": "topla.py yaz: iki sayıyı toplayan `topla(a, b)` fonksiyonu olsun. test_topla.py içinde "
                          "unittest ile 3 test yaz ve `python -m unittest` ile çalıştırıp geçtiğini göster."},
}


if __name__ == "__main__":
    args = sys.argv[1:]
    kapali = "--kapali" in args
    if kapali:
        sys.argv.remove("--kapali")
        if "--cikti" in sys.argv:         # açık koşunun raporunu ezmesin (aynı <cikti>/<model> klasörü)
            i = sys.argv.index("--cikti") + 1
            sys.argv[i] = str(Path(sys.argv[i]) / "kapali")
        from evren_studio.agent.runner import AgentRunner

        _orig = AgentRunner._specs
        AgentRunner._specs = lambda self: [s for s in _orig(self) if s.name != "web_search"]
    import e2e_zorluk_real_api as z

    raise SystemExit(z.main(GOREVLER, "Web araması" + (" (web_search KAPALI)" if kapali else ""),
                            "websearch-kapali" if kapali else "websearch"))
