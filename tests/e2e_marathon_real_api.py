"""Proje maratonu: gerçek arayüz + gerçek EVREN API ile baştan sona proje (API anahtarı gerekir).

pytest tarafından toplanmaz. Çalıştırma:
    .\\.venv\\Scripts\\python.exe -u tests\\e2e_marathon_real_api.py <A|B|C|D|E> <model> <cikti_klasoru>

Bir "sanal kullanıcı" uygulamaya (görünmez pencerede, Otomatik mod) birkaç mesajlık
gerçek bir proje yaptırır: ilk istek, ardından ek özellikler. Tur adım sınırı,
döngü veya boş yanıtla biterse en fazla 2 kez "devam et" yazar. Sonunda modelin
görmediği KABUL TESTLERİ projeyi dışarıdan dener.

Projeler:
  A  Python komut satırı harcama takibi (SQLite, unittest) — kurulum yok
  B  Flask not uygulaması (REST + HTML) — proje içinde .venv kurup flask yüklemeli
  C  Node + TypeScript metin istatistiği, pnpm ile — pnpm kurulu değilse kurmalı
  D  Flask kişisel kütüphane — UZUN oturum (7 mesaj): bağlam büyümesi/otomatik özet ölçümü
  E  Çevrimdışı harcama PWA (manifest, service worker, gerçek PNG ikon, node:test)

MARATON_OZET_ESIK=<token> ortam değişkeni otomatik özet eşiğini düşürür (uzun oturum benzetimi).
MARATON_KOTA_TESTI=<mesaj>:<adım> kota bitince otomatik devamı ölçer: o mesajda ajan <adım> araç sonucu ürettikten
sonra günlük kota "bitmiş" gösterilir (QuotaGate.daily_low) → tur güvenli noktada durmalı, kota kartı ve kalıcı plan
çıkmalı; ardından kota "yenilenir" ve gerçek yoklamayla (_resume_probe) kaldığı yerden sürmeli; kabul yine tam olmalı.

Ölçülenler (rapor JSON): mesaj başına adım, süre, durma nedeni (done/loop/max_steps/
context_limit/…), otomatik özet sayısı, onay istendi mi (Otomatik modda 0 olmalı),
araç çağrısı tekrarları, hata kartları, arayüz notları, kabul testi sonuçları.
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

TURN_TIMEOUT = 45 * 60          # tek kullanıcı mesajı için üst sınır (sn)
MAX_CONTINUES = 2               # tur yarım kalırsa "devam et" sayısı
CONTINUE_TEXT = "devam et"

# ---- proje tanımları ------------------------------------------------------------------

PROJECTS: dict[str, dict] = {
    "A": {
        "ad": "Python CLI harcama takibi",
        "mesajlar": [
            "Bu boş klasörde Python 3 ile komut satırından çalışan bir harcama takip programı yaz. "
            "Dosya adı harcama.py olsun, yalnız standart kütüphane kullan, veriler SQLite'ta dursun. "
            "Veritabanı yolu HARCAMA_DB ortam değişkeninden okunsun, yoksa harcama.db kullanılsın. Komutlar:\n"
            "- `python harcama.py ekle <tutar> <kategori> [açıklama]` → çıktı tam olarak `Eklendi: #<id>`\n"
            "- `python harcama.py liste` → her kayıt bir satır: `#<id> <YYYY-AA-GG> <tutar 2 ondalık> <kategori> <açıklama>`\n"
            "- `python harcama.py ozet` → kategori başına toplam, büyükten küçüğe, satır biçimi `<kategori>: <toplam 2 ondalık>`\n"
            "Tutar negatif veya sayı değilse hata mesajı yaz ve çıkış kodu 1 olsun. "
            "tests/ klasöründe unittest testleri yaz ve `python -m unittest discover -s tests -v` ile çalıştırıp geçtiğini göster.",
            "Şimdi iki komut ekle: `python harcama.py sil <id>` (çıktı `Silindi: #<id>`, olmayan id için hata ve "
            "çıkış kodu 1) ve `python harcama.py disa-aktar <dosya.csv>` (başlık satırı `id,tarih,tutar,kategori,aciklama`, "
            "UTF-8). İkisi için de test ekle ve tüm testleri çalıştır.",
            "`ozet` komutuna isteğe bağlı `--ay YYYY-AA` seçeneği ekle; verilirse yalnız o ayın kayıtları özetlensin. "
            "Test ekle, tüm testleri çalıştır.",
            "Son olarak README.md yaz: kurulum, tüm komutlar ve örnekler, testlerin nasıl çalıştırılacağı. "
            "Bitince tüm testleri bir kez daha çalıştır ve ne yaptığını özetle.",
        ],
    },
    "B": {
        "ad": "Flask not uygulaması",
        "mesajlar": [
            "Bu boş klasörde Flask ile küçük bir not uygulaması yap. Proje klasöründe `.venv` adlı bir Python sanal "
            "ortamı oluştur ve flask'ı oraya kur (requirements.txt de yaz). Uygulama app.py içinde `create_app(db_path)` "
            "fonksiyonu olsun ve SQLite kullansın. REST uç noktaları:\n"
            "- `GET /api/notlar` → JSON liste `[{\"id\", \"baslik\", \"icerik\", \"olusturma\"}]`, en yeni önce\n"
            "- `POST /api/notlar` (JSON `baslik`, `icerik`) → 201 ve oluşan not; baslik boşsa 400 ve `{\"hata\": ...}`\n"
            "- `DELETE /api/notlar/<id>` → 204; yoksa 404\n"
            "Flask test istemcisiyle tests/ klasöründe testler yaz ve `.venv` içindeki python ile çalıştırıp geçtiğini göster.",
            "`GET /` adresinde notları listeleyen, yeni not eklenebilen ve silinebilen tek sayfalık bir HTML arayüzü ekle "
            "(templates/index.html veya static dosyalar; JavaScript fetch ile API'yi kullansın). Ana sayfa için test ekle.",
            "`GET /api/notlar?ara=<kelime>` ile başlık veya içerikte (büyük/küçük harf duyarsız) arama ekle ve "
            "`PUT /api/notlar/<id>` ile not güncelleme ekle (yoksa 404). Testlerini yaz, tümünü çalıştır.",
            "README.md yaz (kurulum, çalıştırma, API) ve tüm testleri son kez çalıştırıp ne yaptığını özetle.",
        ],
    },
    "C": {
        "ad": "Node + TypeScript metin istatistiği (pnpm)",
        "mesajlar": [
            "Bu boş klasörde Node.js + TypeScript ile bir komut satırı aracı yap; paket yöneticisi olarak pnpm kullan "
            "(bilgisayarda yoksa kur). `pnpm build` ile `dist/index.js` üretilsin. Kullanım: `node dist/index.js <dosya.txt>`. "
            "Çıktı tam olarak şu satırlar olsun:\n"
            "`satir: <satır sayısı>`\n`kelime: <kelime sayısı>`\n`en_sik: <kelime1>=<adet>, <kelime2>=<adet>, <kelime3>=<adet>`\n"
            "Kelimeler Türkçe küçük harfe çevrilsin (İ→i, I→ı), noktalama yok sayılsın; en sık 3 kelime adet azalan, "
            "eşitlikte alfabetik. Dosya yoksa hata yazıp çıkış kodu 1. vitest ile testler yaz, `pnpm test` ile çalıştır.",
            "`--json` seçeneği ekle: verilirse çıktı `{\"satir\":..,\"kelime\":..,\"en_sik\":[[\"kelime\",adet],...]}` biçiminde "
            "tek satır JSON olsun. Test ekle, build al ve testleri çalıştır.",
            "README.md yaz (kurulum, build, kullanım, test) ve son kez build + test çalıştırıp ne yaptığını özetle.",
        ],
    },
    "D": {
        "ad": "Flask kişisel kütüphane (uzun oturum, 7 mesaj)",
        "mesajlar": [
            "Bu boş klasörde Flask + SQLite ile kişisel kütüphane uygulaması yap. Proje klasöründe `.venv` sanal "
            "ortamı oluştur, flask'ı kur, requirements.txt yaz. app.py içinde `create_app(db_path)` olsun. Kitap: "
            "id, baslik, yazar, yil (tamsayı, isteğe bağlı), isbn (isteğe bağlı, benzersiz), eklenme. Uç noktalar:\n"
            "- `GET /api/kitaplar` → JSON liste, baslik'e göre alfabetik\n"
            "- `POST /api/kitaplar` (JSON) → 201 + kitap; baslik veya yazar boşsa 400 `{\"hata\": ...}`; aynı isbn ikinci "
            "kez gelirse 409\n- `GET /api/kitaplar/<id>` → kitap ya da 404\nTestleri tests/ altında pytest ile yaz, .venv'e "
            "pytest kur, çalıştırıp geçtiğini göster.",
            "`PUT /api/kitaplar/<id>` (kısmi güncelleme: gönderilen alanlar değişir, yoksa 404; baslik boşsa 400) ve "
            "`DELETE /api/kitaplar/<id>` (204, yoksa 404) ekle. Testlerini yaz ve tümünü çalıştır.",
            "Arama ekle: `GET /api/kitaplar?ara=<metin>` başlık VEYA yazarda büyük/küçük harf duyarsız arasın (Türkçe "
            "İ/ı dahil: 'istanbul' araması 'İstanbul'u bulmalı). `?yazar=<ad>` tam eşleşme filtresi de olsun. Test ekle.",
            "Ödünç takibi ekle: `POST /api/kitaplar/<id>/odunc` (JSON `kime`) → kitap ödünçteyse 409; "
            "`POST /api/kitaplar/<id>/iade` → ödünçte değilse 409. `GET /api/kitaplar` her kitapta `odunc` alanı "
            "(null ya da {\"kime\", \"tarih\"}) dönsün. `GET /api/odunctekiler` yalnız ödünçteki kitapları versin. Test ekle.",
            "`GET /api/istatistik` → `{\"toplam\": n, \"odunc\": n, \"yazar_sayisi\": n, \"en_cok_kitabi_olan_yazar\": "
            "\"...\"}` ekle (eşitlikte alfabetik ilk yazar; kitap yoksa null). Test ekle.",
            "CSV ekle: `GET /api/disa-aktar` → text/csv, başlık satırı tam olarak `id,baslik,yazar,yil,isbn`; "
            "`POST /api/ice-aktar` (gövde CSV metni) → `{\"eklenen\": n, \"atlanan\": n}`; aynı isbn'li ya da baslik/yazar "
            "boş satırlar atlanır. Test ekle, tüm testleri çalıştır.",
            "`GET /` adresine bu API'yi fetch ile kullanan tek sayfalık arayüz ekle (liste, arama kutusu, ekleme formu, "
            "ödünç/iade düğmeleri). Ana sayfa için test ekle. README.md yaz (kurulum, çalıştırma, tüm uç noktalar). "
            "Son olarak tüm testleri çalıştırıp neyi yaptığını özetle.",
        ],
    },
    "E": {
        "ad": "Çevrimdışı harcama PWA (manifest + service worker + mantık modülü)",
        "mesajlar": [
            "Bu boş klasörde çevrimdışı çalışan bir harcama takip PWA'sı yap (çerçeve yok: düz HTML/CSS/JS). Dosyalar: "
            "index.html, style.css, app.js, logic.js, manifest.webmanifest, sw.js, icons/icon-192.png ve icon-512.png "
            "(gerçek PNG; gerekirse küçük bir betikle üret). logic.js tarayıcıda da Node'da da çalışsın: "
            "`module.exports` ile `ekle(liste, kayit)`, `toplam(liste)`, `kategoriOzet(liste)` ({kategori: toplam}), "
            "`ayFiltre(liste, 'YYYY-AA')` dışa aktarılsın. Tutar sayı değilse veya <=0 ise `ekle` hata fırlatsın. "
            "Veriler localStorage'da dursun. Node ile çalışan testleri tests/logic.test.js içine `node:test` ile yaz ve "
            "`node --test` ile çalıştırıp geçtiğini göster (Node 24: klasör adı verme, testleri kendisi bulur).",
            "manifest.webmanifest: name, short_name, start_url, display \"standalone\", theme_color, background_color ve iki "
            "ikon (192 ve 512, type image/png) içersin. sw.js kurulumda index.html, style.css, app.js, logic.js, manifest ve "
            "ikonları önbelleğe alsın (cache-first), eski önbellekleri activate'te silsin. index.html manifest'e bağlansın "
            "ve service worker'ı kaydetsin. Bir doğrulama betiği tools/dogrula.js yaz: manifest alanlarını, ikonların "
            "gerçek PNG ve doğru boyutta olduğunu, sw.js önbellek listesindeki her dosyanın var olduğunu denetlesin.",
            "Kategori özetini gösteren basit bir çubuk grafik (canvas ya da div) ve CSV dışa aktarma düğmesi ekle. "
            "CSV üreten `csvUret(liste)` fonksiyonunu logic.js'e koy (başlık `tarih,kategori,tutar,aciklama`, virgül "
            "veya tırnak içeren açıklamalar doğru kaçışlanmalı) ve test et. README.md yaz; tüm testleri ve doğrulama "
            "betiğini son kez çalıştırıp özetle.",
        ],
    },
}


# ---- kabul testleri (model görmez) ------------------------------------------------------


def _run(cmd, cwd, env=None, timeout=120):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env, shell=isinstance(cmd, str))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return -9, "zaman aşımı"
    except OSError as exc:
        return -8, str(exc)


def accept_A(proj: Path) -> list[tuple[str, bool, str]]:
    r: list[tuple[str, bool, str]] = []
    py = sys.executable
    env = dict(os.environ, HARCAMA_DB=str(proj / "_kabul.db"), PYTHONIOENCODING="utf-8")
    (proj / "_kabul.db").unlink(missing_ok=True)
    c, o = _run([py, "harcama.py", "ekle", "120.5", "market", "ekmek ve süt"], proj, env)
    r.append(("ekle çıktısı", c == 0 and o.strip().startswith("Eklendi: #"), o.strip()[:80]))
    _run([py, "harcama.py", "ekle", "30", "ulasim"], proj, env)
    _run([py, "harcama.py", "ekle", "79.5", "market"], proj, env)
    c, o = _run([py, "harcama.py", "ozet"], proj, env)
    lines = [x.strip() for x in o.strip().splitlines() if x.strip()]
    r.append(("ozet doğru ve sıralı", c == 0 and lines[:2] == ["market: 200.00", "ulasim: 30.00"], " | ".join(lines)[:120]))
    c, o = _run([py, "harcama.py", "liste"], proj, env)
    r.append(("liste 3 kayıt", c == 0 and len([x for x in o.splitlines() if x.strip().startswith("#")]) == 3, o.strip()[:120]))
    c, o = _run([py, "harcama.py", "ekle", "-5", "market"], proj, env)
    r.append(("negatif tutar reddedilir", c == 1, f"çıkış {c}"))
    c, o = _run([py, "harcama.py", "sil", "1"], proj, env)
    r.append(("sil", c == 0 and "Silindi: #1" in o, o.strip()[:80]))
    c, o = _run([py, "harcama.py", "sil", "999"], proj, env)
    r.append(("olmayan id silinemez", c == 1, f"çıkış {c}"))
    csv_path = proj / "_kabul.csv"
    c, o = _run([py, "harcama.py", "disa-aktar", str(csv_path)], proj, env)
    head = csv_path.read_text(encoding="utf-8-sig").splitlines()[0] if csv_path.exists() else ""
    r.append(("disa-aktar başlık", c == 0 and head.strip() == "id,tarih,tutar,kategori,aciklama", head[:80]))
    ay = time.strftime("%Y-%m")
    c, o = _run([py, "harcama.py", "ozet", "--ay", ay], proj, env)
    c2, o2 = _run([py, "harcama.py", "ozet", "--ay", "1999-01"], proj, env)
    r.append(("ozet --ay", c == 0 and "market: 79.50" in o and "market" not in o2, (o.strip() + " || " + o2.strip())[:120]))
    c, o = _run([py, "-m", "unittest", "discover", "-s", "tests"], proj, env, timeout=300)
    r.append(("kendi testleri geçiyor", c == 0, o.strip().splitlines()[-1][:80] if o.strip() else ""))
    r.append(("README var", (proj / "README.md").is_file() and "ozet" in (proj / "README.md").read_text(encoding="utf-8", errors="ignore"), ""))
    for f in ("_kabul.db", "_kabul.csv"):
        (proj / f).unlink(missing_ok=True)
    return r


def accept_B(proj: Path) -> list[tuple[str, bool, str]]:
    r: list[tuple[str, bool, str]] = []
    py = proj / ".venv" / "Scripts" / "python.exe"
    r.append(("proje .venv var", py.is_file(), ""))
    if not py.is_file():
        return r
    script = r'''
import json, sys, tempfile, os
sys.path.insert(0, os.getcwd())
from app import create_app
d = tempfile.mkdtemp()
app = create_app(os.path.join(d, "k.db"))
c = app.test_client()
out = {}
out["bos_liste"] = c.get("/api/notlar").get_json() == []
a = c.post("/api/notlar", json={"baslik": "Alışveriş", "icerik": "ekmek al"})
b = c.post("/api/notlar", json={"baslik": "İş", "icerik": "rapor YAZ"})
out["post_201"] = a.status_code == 201 and b.status_code == 201
out["post_bos_400"] = c.post("/api/notlar", json={"baslik": "", "icerik": "x"}).status_code == 400
lst = c.get("/api/notlar").get_json()
out["liste_en_yeni_once"] = len(lst) == 2 and lst[0]["baslik"] == "İş"
ara = c.get("/api/notlar?ara=rapor").get_json()
out["arama"] = isinstance(ara, list) and len(ara) == 1
ida = a.get_json()["id"]
out["put"] = c.put(f"/api/notlar/{ida}", json={"baslik": "Market", "icerik": "süt"}).status_code in (200, 204)
out["put_404"] = c.put("/api/notlar/99999", json={"baslik": "x", "icerik": "y"}).status_code == 404
out["delete_204"] = c.delete(f"/api/notlar/{ida}").status_code == 204
out["delete_404"] = c.delete(f"/api/notlar/{ida}").status_code == 404
h = c.get("/")
out["ana_sayfa_html"] = h.status_code == 200 and b"<html" in h.data.lower()
print(json.dumps(out))
'''
    c, o = _run([str(py), "-c", script], proj, timeout=120)
    try:
        res = json.loads(o.strip().splitlines()[-1])
        for k, v in res.items():
            r.append((k, bool(v), ""))
    except (json.JSONDecodeError, IndexError):
        r.append(("API kabul betiği çalıştı", False, o.strip()[-200:]))
    c, o = _run([str(py), "-m", "pytest", "-q"], proj, timeout=300)
    if c in (-8,) or "No module named pytest" in o:
        c, o = _run([str(py), "-m", "unittest", "discover", "-s", "tests"], proj, timeout=300)
    r.append(("kendi testleri geçiyor", c == 0, o.strip().splitlines()[-1][:80] if o.strip() else ""))
    r.append(("README var", (proj / "README.md").is_file(), ""))
    return r


def accept_C(proj: Path) -> list[tuple[str, bool, str]]:
    r: list[tuple[str, bool, str]] = []
    r.append(("pnpm kurulu", shutil.which("pnpm") is not None, shutil.which("pnpm") or ""))
    r.append(("pnpm-lock.yaml var", (proj / "pnpm-lock.yaml").is_file(), ""))
    sample = proj / "_kabul.txt"
    # 4 satır (biri boş), 10 kelime; eşitlik yok: elma=3, armut=2, son=2 (armut<son alfabetik)
    sample.write_text("Elma armut. elma, İstanbul\nISPARTA ıspanak armut elma\n\nson son", encoding="utf-8")
    dist = proj / "dist" / "index.js"
    r.append(("dist/index.js var", dist.is_file(), ""))
    if dist.is_file():
        c, o = _run(["node", "dist/index.js", str(sample)], proj)
        lines = [x.strip() for x in o.strip().splitlines()]
        r.append(("satir", "satir: 4" in lines, " | ".join(lines)[:150]))
        r.append(("kelime", "kelime: 10" in lines, ""))
        r.append(("en_sik", "en_sik: elma=3, armut=2, son=2" in lines, ""))
        c, o = _run(["node", "dist/index.js", str(sample), "--json"], proj)
        try:
            j = json.loads(o.strip().splitlines()[-1])
            ok = j.get("satir") == 4 and j.get("kelime") == 10 and j.get("en_sik", [])[:1] == [["elma", 3]]
        except (json.JSONDecodeError, IndexError):
            ok = False
        r.append(("--json", ok, o.strip()[:120]))
        c, o = _run(["node", "dist/index.js", str(proj / "yok.txt")], proj)
        r.append(("olmayan dosya çıkış 1", c == 1, f"çıkış {c}"))
    if shutil.which("pnpm"):
        c, o = _run("pnpm test", proj, timeout=300)
        r.append(("kendi testleri geçiyor", c == 0, o.strip().splitlines()[-1][:80] if o.strip() else ""))
    r.append(("README var", (proj / "README.md").is_file(), ""))
    sample.unlink(missing_ok=True)
    return r


def accept_D(proj: Path) -> list[tuple[str, bool, str]]:
    r: list[tuple[str, bool, str]] = []
    py = proj / ".venv" / "Scripts" / "python.exe"
    r.append(("proje .venv var", py.is_file(), ""))
    if not py.is_file():
        return r
    script = r'''
import json, sys, tempfile, os, logging
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.getcwd())
o = {}
try:
    from app import create_app
    app = create_app(os.path.join(tempfile.mkdtemp(), "k.db"))
    c = app.test_client()
except Exception as exc:
    print(json.dumps({"uygulama_kurulur": False}))
    raise SystemExit(0)
S = {}
def post(u, j=None, data=None):
    return c.post(u, json=j) if j is not None else c.post(u, data=data, content_type="text/csv")
def js(resp):
    try:
        return resp.get_json() or {}
    except Exception:
        return {}
def kur():
    S["a"] = post("/api/kitaplar", {"baslik": "Zeytin", "yazar": "Ahmet", "yil": 1999, "isbn": "111"})
    S["b"] = post("/api/kitaplar", {"baslik": "Ankara", "yazar": "Mehmet", "isbn": "222"})
    S["k3"] = post("/api/kitaplar", {"baslik": "İstanbul Hatırası", "yazar": "Ahmet"})
    S["ida"] = js(S["a"]).get("id")
    return all(S[k].status_code == 201 for k in ("a", "b", "k3"))
def odunc_alani():
    od = [x for x in c.get("/api/kitaplar").get_json() if x["id"] == S["ida"]][0].get("odunc")
    return isinstance(od, dict) and od.get("kime") == "Ayşe"
def istatistik():
    st = js(c.get("/api/istatistik"))
    return (st.get("toplam") == 3 and st.get("odunc") == 1 and st.get("yazar_sayisi") == 2
            and st.get("en_cok_kitabi_olan_yazar") == "Ahmet")
def csv_baslik():
    d = c.get("/api/disa-aktar")
    return d.status_code == 200 and "csv" in d.content_type and \
        d.get_data(as_text=True).splitlines()[0].strip() == "id,baslik,yazar,yil,isbn"
def ice_aktar():
    res = post("/api/ice-aktar", data="baslik,yazar,yil,isbn\nYeni Kitap,Zeynep,2020,333\nKopya,K,2000,111\n,BosBaslik,,\n")
    j = js(res)
    return res.status_code in (200, 201) and j.get("eklenen") == 1 and j.get("atlanan") == 2
def put_kismi():
    ok = c.put(f"/api/kitaplar/{S['ida']}", json={"yil": 2001}).status_code in (200, 204)
    k = js(c.get(f"/api/kitaplar/{S['ida']}"))
    return ok and k.get("yil") == 2001 and k.get("baslik") == "Zeytin"
KONTROLLER = [
    ("post_201", kur),
    ("bos_baslik_400", lambda: post("/api/kitaplar", {"baslik": "", "yazar": "x"}).status_code == 400),
    ("isbn_409", lambda: post("/api/kitaplar", {"baslik": "Kopya", "yazar": "y", "isbn": "111"}).status_code == 409),
    ("liste_alfabetik", lambda: [x["baslik"] for x in c.get("/api/kitaplar").get_json()][:1] == ["Ankara"]),
    ("tek_404", lambda: c.get("/api/kitaplar/99999").status_code == 404),
    ("put_kismi", put_kismi),
    ("put_bos_400", lambda: c.put(f"/api/kitaplar/{S['ida']}", json={"baslik": ""}).status_code == 400),
    ("arama_turkce_i", lambda: len(c.get("/api/kitaplar?ara=istanbul").get_json()) == 1),
    ("arama_yazar", lambda: len(c.get("/api/kitaplar?ara=AHMET").get_json()) == 2),
    ("yazar_filtre", lambda: len(c.get("/api/kitaplar?yazar=Mehmet").get_json()) == 1),
    ("odunc", lambda: post(f"/api/kitaplar/{S['ida']}/odunc", {"kime": "Ayşe"}).status_code in (200, 201)),
    ("odunc_tekrar_409", lambda: post(f"/api/kitaplar/{S['ida']}/odunc", {"kime": "Ali"}).status_code == 409),
    ("odunc_alani", odunc_alani),
    ("odunctekiler", lambda: len(c.get("/api/odunctekiler").get_json()) == 1),
    ("istatistik", istatistik),
    ("iade", lambda: post(f"/api/kitaplar/{S['ida']}/iade", {}).status_code in (200, 204)),
    ("iade_tekrar_409", lambda: post(f"/api/kitaplar/{S['ida']}/iade", {}).status_code == 409),
    ("csv_baslik", csv_baslik),
    ("ice_aktar", ice_aktar),
    ("delete_204", lambda: c.delete(f"/api/kitaplar/{S['ida']}").status_code == 204),
    ("delete_404", lambda: c.delete(f"/api/kitaplar/{S['ida']}").status_code == 404),
    ("ana_sayfa", lambda: c.get("/").status_code == 200 and b"<html" in c.get("/").data.lower()),
]
for ad, f in KONTROLLER:
    try:
        o[ad] = bool(f())
    except Exception:
        o[ad] = False                  # bir kontrolün çökmesi diğerlerini düşürmez
print(json.dumps(o))
'''
    c, o = _run([str(py), "-c", script], proj, timeout=180)
    try:
        res = json.loads(o.strip().splitlines()[-1])
        for k, v in res.items():
            r.append((k, bool(v), ""))
    except (json.JSONDecodeError, IndexError):
        r.append(("API kabul betiği çalıştı", False, o.strip()[-300:]))
    c, o = _run([str(py), "-m", "pytest", "-q"], proj, timeout=300)
    r.append(("kendi testleri geçiyor", c == 0, o.strip().splitlines()[-1][:80] if o.strip() else ""))
    r.append(("README var", (proj / "README.md").is_file(), ""))
    return r


def _png_size(path: Path) -> tuple[int, int] | None:
    try:
        b = path.read_bytes()[:24]
    except OSError:
        return None
    if b[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    import struct
    return struct.unpack(">II", b[16:24])


def accept_E(proj: Path) -> list[tuple[str, bool, str]]:
    r: list[tuple[str, bool, str]] = []
    if not (proj / "logic.js").is_file():
        return [("logic.js var", False, "")]
    js = r'''
const L = require(process.cwd() + "/logic.js");
const o = {};
let liste = [];
try { liste = L.ekle(liste, {tarih: "2026-10-05", kategori: "market", tutar: 120.5, aciklama: "ekmek"}); } catch (e) {}
try { liste = L.ekle(liste, {tarih: "2026-10-07", kategori: "ulasim", tutar: 30, aciklama: "otobüs, tren"}); } catch (e) {}
try { liste = L.ekle(liste, {tarih: "2026-11-01", kategori: "market", tutar: 79.5, aciklama: 'dedi ki "süt"'}); } catch (e) {}
o.ekle = Array.isArray(liste) && liste.length === 3;
let hata = 0;
for (const t of [-5, 0, "abc"]) { try { L.ekle([], {tarih: "2026-10-01", kategori: "x", tutar: t}); } catch (e) { hata++; } }
o.gecersiz_tutar_hata = hata === 3;
o.toplam = Math.abs(L.toplam(liste) - 230) < 1e-9;
const oz = L.kategoriOzet(liste);
o.kategori_ozet = Math.abs(oz.market - 200) < 1e-9 && Math.abs(oz.ulasim - 30) < 1e-9;
o.ay_filtre = L.ayFiltre(liste, "2026-10").length === 2;
const csv = (L.csvUret ? L.csvUret(liste) : "").split(/\r?\n/);
o.csv_baslik = csv[0] === "tarih,kategori,tutar,aciklama";
o.csv_kacis = csv.some(s => s.includes('"otobüs, tren"')) && csv.some(s => s.includes('"dedi ki ""süt"""'));
console.log(JSON.stringify(o));
'''
    c, o = _run(["node", "-e", js], proj, timeout=60)
    try:
        for k, v in json.loads(o.strip().splitlines()[-1]).items():
            r.append((k, bool(v), ""))
    except (json.JSONDecodeError, IndexError):
        r.append(("mantık kabul betiği çalıştı", False, o.strip()[-300:]))
    try:
        m = json.loads((proj / "manifest.webmanifest").read_text(encoding="utf-8"))
        ok = all(m.get(k) for k in ("name", "short_name", "start_url", "theme_color", "background_color")) \
            and m.get("display") == "standalone"
        sizes = {i.get("sizes") for i in m.get("icons", []) if i.get("type") == "image/png"}
        r.append(("manifest alanları", ok, ""))
        r.append(("manifest ikonları", {"192x192", "512x512"} <= sizes, str(sizes)))
    except (OSError, json.JSONDecodeError) as exc:
        r.append(("manifest okunur", False, str(exc)[:80]))
    r.append(("ikon 192 gerçek PNG", _png_size(proj / "icons" / "icon-192.png") == (192, 192), ""))
    r.append(("ikon 512 gerçek PNG", _png_size(proj / "icons" / "icon-512.png") == (512, 512), ""))
    sw = (proj / "sw.js").read_text(encoding="utf-8", errors="ignore") if (proj / "sw.js").is_file() else ""
    r.append(("sw önbellek + activate", all(s in sw for s in ("index.html", "logic.js", "caches")) and "activate" in sw, ""))
    def oku(name: str) -> str:
        f = proj / name
        return f.read_text(encoding="utf-8", errors="ignore") if f.is_file() else ""

    html, appjs = oku("index.html"), oku("app.js")
    r.append(("index manifest bağlantısı", "manifest" in html, ""))
    r.append(("service worker kaydı", "serviceWorker" in (html + appjs), ""))
    c, o = _run("node --test", proj, timeout=120)        # Node 24: "node --test <klasör>" klasörü dosya sanıp kalıyor
    r.append(("kendi testleri geçiyor", c == 0, o.strip().splitlines()[-1][:80] if o.strip() else ""))
    if (proj / "tools" / "dogrula.js").is_file():
        c, o = _run(["node", "tools/dogrula.js"], proj, timeout=60)
        r.append(("doğrulama betiği geçiyor", c == 0, o.strip()[-120:]))
    else:
        r.append(("doğrulama betiği var", False, ""))
    r.append(("README var", (proj / "README.md").is_file(), ""))
    return r


ACCEPT = {"A": accept_A, "B": accept_B, "C": accept_C, "D": accept_D, "E": accept_E}


# ---- sürücü ---------------------------------------------------------------------------------


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    key, model, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    spec = PROJECTS[key]
    tag = f"{key}_{model}"
    base = out / tag
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    proj = base / "proje"
    proj.mkdir(parents=True)
    os.environ["EVREN_STUDIO_DATA_DIR"] = str(base / "data")

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
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)

    import evren_studio.ui.session_view as sv
    from evren_studio.agent.runner import AgentRunner
    from evren_studio.ui.main_window import MainWindow
    from evren_studio.ui.transcript import ApprovalWidget, ErrorCard

    outcomes: list[dict] = []
    notes: list[str] = []

    class RecordingRunner(AgentRunner):
        def run(self, history):
            t0 = time.monotonic()
            o = super().run(history)
            outcomes.append({"stopped": o.stopped, "steps": o.steps, "protocol": o.protocol,
                             "sure": round(time.monotonic() - t0, 1)})
            return o

    sv.AgentRunner = RecordingRunner
    orig_note = sv.SessionView._note

    def rec_note(self, text, icon_name="dot"):
        notes.append(text)
        return orig_note(self, text, icon_name)

    sv.SessionView._note = rec_note

    w = MainWindow()
    w.resize(1440, 900)
    w.show()

    def pump(sec):
        end = time.monotonic() + sec
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.03)

    approvals = 0

    def wait_turn(limit) -> bool:
        nonlocal approvals
        end = time.monotonic() + limit
        pump(1.0)
        while time.monotonic() < end:
            app.processEvents()
            for b in [b for b in w.session.findChildren(ApprovalWidget) if b.isVisible() and not b.request.resolved]:
                approvals += 1
                b._decide("allow")
            if not w.session.running:           # özetleme sırasında da running=True kalır
                pump(2.0)                       # otomatik özet → otomatik devam zinciri
                if not w.session.running:
                    return True
            time.sleep(0.05)
        return False

    deadline_ok = True
    w.ctx.settings.agent_mode = "auto"
    # Uzun oturum benzetimi: düşük özet eşiğiyle otomatik özet + otomatik devam zinciri denenir.
    esik = os.environ.get("MARATON_OZET_ESIK")
    if esik:
        w.ctx.settings.auto_compact_max_tokens = int(esik)
    kota_testi = os.environ.get("MARATON_KOTA_TESTI")
    kota = {"aktif": False, "durdu": 0, "kart": 0, "plan": 0, "surdu": 0, "mesaj": 0, "adim": 0}
    if kota_testi:
        from evren_studio.agent.quota import QuotaGate

        _orig_low = QuotaGate.daily_low

        def _low(self):
            return (True, None) if kota["aktif"] else _orig_low(self)
        QuotaGate.daily_low = _low
        w.ctx.settings.auto_resume = True
        kota["mesaj"], kota["adim"] = (int(x) for x in kota_testi.split(":"))

    def tool_count() -> int:
        sid_ = w.session.session_id
        return sum(1 for m in w.ctx.db.get_session_messages(sid_) if m["role"] == "tool") if sid_ else 0
    w.new_session()
    w.session.welcome._choose(str(proj))
    w.session.set_model(model)
    w.session.composer.set_model(model)
    w.session.set_mode("auto")
    w.session.composer.set_mode("auto")
    turns: list[dict] = []
    t_all = time.monotonic()
    for i, msg in enumerate(spec["mesajlar"], 1):
        n_out, n_notes = len(outcomes), len(notes)
        n_err = len(w.session.findChildren(ErrorCard))
        t0 = time.monotonic()
        n_tool0 = tool_count()
        w.session.send(msg)
        if kota_testi and i == kota["mesaj"]:
            end = time.monotonic() + TURN_TIMEOUT
            while w.session.running and tool_count() < n_tool0 + kota["adim"] and time.monotonic() < end:
                pump(0.3)
            kota["aktif"] = True                    # bir sonraki model çağrısından önce kota "bitti"
        finished = wait_turn(TURN_TIMEOUT)
        if kota_testi and i == kota["mesaj"] and finished:
            from evren_studio.agent import resume as _resume
            from evren_studio.ui.transcript import QuotaResumeCard

            last = outcomes[-1] if len(outcomes) > n_out else None
            kota["durdu"] = int(bool(last and last["stopped"] == "quota_daily"))
            kota["kart"] = len(w.session.findChildren(QuotaResumeCard))
            kota["plan"] = int(w.ctx.db.get_meta(_resume.META_KEY) is not None)
            kota["araç_durunca"] = tool_count() - n_tool0
            print(f"[{tag}] KOTA TESTİ: durdu={kota['durdu']} kart={kota['kart']} plan={kota['plan']} "
                  f"(durmadan önce {kota['araç_durunca']} araç sonucu)", flush=True)
            kota["aktif"] = False                   # kota "yenilendi": gerçek yoklama ile devam
            n_before = len(outcomes)
            w.session._resume_probe()
            end = time.monotonic() + 60
            while len(outcomes) == n_before and not w.session.running and time.monotonic() < end:
                pump(0.3)
            finished = wait_turn(TURN_TIMEOUT)
            kota["surdu"] = int(len(outcomes) > n_before)
            print(f"[{tag}] KOTA TESTİ: devam turu={kota['surdu']} · plan silindi="
                  f"{int(w.ctx.db.get_meta(_resume.META_KEY) is None)}", flush=True)
        continues = 0
        while finished and continues < MAX_CONTINUES:
            last = outcomes[-1] if len(outcomes) > n_out else None
            new_err = len(w.session.findChildren(ErrorCard)) > n_err
            if last and last["stopped"] in ("done", "cancelled") and not new_err:
                break
            continues += 1
            n_err = len(w.session.findChildren(ErrorCard))
            w.session.send(CONTINUE_TEXT)
            finished = wait_turn(TURN_TIMEOUT)
        if not finished:
            deadline_ok = False
            w.session.cancel_token.cancel() if getattr(w.session, "cancel_token", None) else None
            pump(5)
        turn = {"mesaj": i, "sure": round(time.monotonic() - t0, 1), "devam_et": continues,
                "zaman_asimi": not finished, "kosular": outcomes[n_out:], "notlar": notes[n_notes:],
                "hata_karti": len(w.session.findChildren(ErrorCard)) - n_err}
        turns.append(turn)
        print(f"[{tag}] mesaj {i}: {turn['sure']} sn, koşular={[(o['stopped'], o['steps']) for o in turn['kosular']]}, "
              f"devam={continues}, notlar={len(turn['notlar'])}", flush=True)
        if not finished:
            break

    # geçmiş analizi
    sid = w.session.session_id
    msgs = w.ctx.db.get_session_messages(sid) if sid else []
    sigs: dict[str, int] = {}
    tool_calls = 0
    for m in msgs:
        for c in (m.get("tool_calls") or []):
            tool_calls += 1
            k = c.get("name", "") + " " + (c.get("arguments") or "")
            sigs[k] = sigs.get(k, 0) + 1
    repeated = {k[:120]: v for k, v in sigs.items() if v >= 3}
    summaries = sum(1 for m in msgs if m.get("role") == "summary")
    w.grab().save(str(base / "son_ekran.png"))
    w.close()
    pump(1)

    accept = ACCEPT[key](proj)
    passed = sum(1 for _n, ok, _d in accept if ok)
    report = {
        "proje": key, "ad": spec["ad"], "model": model, "toplam_sure_sn": round(time.monotonic() - t_all, 1),
        "zaman_icinde_bitti": deadline_ok, "mesajlar": turns, "onay_istendi": approvals,
        "arac_cagrisi": tool_calls, "uc_ve_ustu_tekrar": repeated, "otomatik_ozet": summaries,
        "kota_testi": kota if kota_testi else None,
        "kabul": [{"test": n, "gecti": ok, "ayrinti": d} for n, ok, d in accept],
        "kabul_skor": f"{passed}/{len(accept)}",
        "qt_uyari": [m for m in warnings if "thread" in m.lower()][:5], "yakalanmamis_hata": errors[:5],
    }
    (base / "rapor.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{tag}] SONUÇ kabul {passed}/{len(accept)} · {report['toplam_sure_sn']} sn · onay={approvals} · "
          f"özet={summaries} · çağrı={tool_calls} · 3+tekrar={len(repeated)} · hata={len(errors)}", flush=True)
    for n, ok, d in accept:
        print(f"   {'GEÇTİ' if ok else 'KALDI'} | {n}" + (f" | {d}" if d and not ok else ""), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
