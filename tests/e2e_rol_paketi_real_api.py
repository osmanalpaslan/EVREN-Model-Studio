"""Auto Pro iş türü rolleri (A7) ve planlayan + yazan (A13) ölçüm paketleri — gerçek API, anahtar gerekir.

pytest tarafından toplanmaz. Zorluk paketinin sürücüsünü kullanır (görünmez pencere, gerçek arayüz, modelin
GÖRMEDİĞİ kontroller):
    .\\.venv\\Scripts\\python.exe -u tests\\e2e_rol_paketi_real_api.py <paket> <model> [görev ...] [--mimar]

Paketler: veri, web, oyun, metin (klasörsüz sohbet), zor (A13 açık/kapalı ölçümü için çok dosyalı işler).
Örnek: `... e2e_rol_paketi_real_api.py veri deepseek-v4.1-flash` · `... zor auto-pro --mimar`
Sonuçlar: build/rol_<paket>/<model>/rapor.json; özet docs/knowledge/CHALLENGE_RESULTS.md "Rol paketleri".
"""
from __future__ import annotations

import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e2e_zorluk_real_api as z  # noqa: E402

# ---- veri ---------------------------------------------------------------------------------------

BOLGELER = ["Marmara", "Ege", "Akdeniz", "İç Anadolu", "Karadeniz"]


def kur_veri_ozet(p: Path) -> dict:
    rnd = random.Random(7)
    toplam: dict[str, float] = defaultdict(float)
    with (p / "satis.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["tarih", "bolge", "urun", "adet", "birim_fiyat"])
        for i in range(240):
            b = rnd.choice(BOLGELER)
            adet, fiyat = rnd.randint(1, 20), round(rnd.uniform(10, 500), 2)
            toplam[b] += adet * fiyat
            w.writerow([f"2026-09-{1 + i % 30:02d}", b, f"U{rnd.randint(1, 12)}", adet, f"{fiyat:.2f}".replace(".", ",")])
    return {"toplam": {k: round(v, 2) for k, v in toplam.items()}}


def kontrol_veri_ozet(p: Path, s: dict, yanit: str) -> list:
    r = p / "rapor.md"
    if not r.is_file():
        return [("rapor.md yazıldı", False, "")]
    t = r.read_text(encoding="utf-8", errors="replace")
    sayilar = {b: [float(x.replace(".", "").replace(",", ".")) if "," in x else float(x)
                   for x in re.findall(r"[\d.,]+\d", line)]
               for line in t.splitlines() for b in BOLGELER if b in line}
    dogru = [b for b, v in s["toplam"].items() if any(abs(n - v) < 0.011 for n in sayilar.get(b, []))]
    # Görev metni betik istemiyor → puana girmez; Auto Pro veri talimatının (ROLE_HINTS) etkisi için BİLGİ
    betik = [x.name for x in p.iterdir() if x.suffix in (".py", ".ps1")]
    return [("rapor.md yazıldı", True, ""),
            ("5 bölgenin hepsi var", all(b in t for b in BOLGELER), ""),
            ("toplamlar kuruşu kuruşuna doğru", len(dogru) == 5,
             f"{len(dogru)}/5 doğru · kalan betik: {', '.join(betik)[:60] or 'yok'}")]


def kur_veri_json(p: Path) -> dict:
    rnd = random.Random(11)
    musteriler = ["Ayşe", "Ömer", "Çağla", "İsmail", "Şule", "Gökhan", "Ünal"]
    say: Counter = Counter()
    with (p / "siparisler.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["siparis_no", "musteri", "durum", "tutar"])
        for i in range(150):
            m = rnd.choice(musteriler)
            d = rnd.choice(["teslim", "teslim", "teslim", "iptal", "kargoda"])
            if d != "iptal":
                say[m] += 1
            w.writerow([1000 + i, m, d, rnd.randint(50, 900)])
    ilk3 = sorted(say.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    return {"ilk3": dict(ilk3), "tam": dict(say)}


def kontrol_veri_json(p: Path, s: dict, yanit: str) -> list:
    f = p / "ozet.json"
    if not f.is_file():
        return [("ozet.json yazıldı", False, "")]
    raw = f.read_bytes()
    try:
        d = json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        return [("ozet.json geçerli JSON", False, str(exc)[:80])]
    # RFC 8259: JSON'a BOM eklenmez; Python json.load(open(.., encoding="utf-8")) BOM'lu dosyayı reddeder
    # (2026-10-24: deepseek PowerShell ConvertTo-Json | Out-File ile BOM'lu yazdı)
    return [("ozet.json geçerli JSON", True, ""),
            ("BOM'suz UTF-8", not raw.startswith(b"\xef\xbb\xbf"), ""),
            ("tam 3 müşteri", isinstance(d, dict) and len(d) == 3, str(d)[:120]),
            ("sayılar doğru (iptaller hariç)", isinstance(d, dict) and d == s["ilk3"], f"beklenen {s['ilk3']}"),
            ("Türkçe adlar bozulmadı", isinstance(d, dict) and all(k in s["tam"] for k in d), "")]


# ---- web ----------------------------------------------------------------------------------------

def kur_web_form(p: Path) -> dict:
    return {}


def kontrol_web_form(p: Path, s: dict, yanit: str) -> list:
    f = p / "index.html"
    if not f.is_file():
        return [("index.html yazıldı", False, "")]
    t = f.read_text(encoding="utf-8", errors="replace")
    inputs = re.findall(r"<input\b[^>]*>", t, re.I)
    ad = [i for i in inputs if re.search(r"(name|id)=[\"']ad[\"']", i)]
    ep = [i for i in inputs if re.search(r"type=[\"']email[\"']", i)]
    return [("index.html yazıldı", True, ""),
            ("ad alanı zorunlu", bool(ad) and "required" in ad[0], ""),
            ("e-posta alanı type=email ve zorunlu", bool(ep) and "required" in ep[0], ""),
            ("#hata öğesi var", bool(re.search(r"id=[\"']hata[\"']", t)), ""),
            ("'Ad zorunlu' mesajı betikte", "Ad zorunlu" in t and "<script" in t.lower(), ""),
            ("harici kütüphane yok", not re.search(r"<script[^>]+src=[\"']https?:", t, re.I), "")]


WEB_HTML = """<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><title>Sayaç</title><link rel="stylesheet" href="style.css"></head>
<body>
  <h1>Ziyaretçi sayacı</h1>
  <p>Sayı: <span id="sayi">0</span></p>
  <button id="arttir-btn">Arttır</button>
  <script src="app.js"></script>
</body></html>
"""
WEB_JS = """// Sayaç
let sayi = 0;
const dugme = document.getElementById("artir-btn");
dugme.addEventListener("click", () => {
  sayi += 1;
  document.getElementById("sayi").textContent = sayi;
});
"""


def kur_web_duzelt(p: Path) -> dict:
    (p / "index.html").write_text(WEB_HTML, encoding="utf-8")
    (p / "app.js").write_text(WEB_JS, encoding="utf-8")
    (p / "style.css").write_text("body { font-family: sans-serif; }\n", encoding="utf-8")
    return {"css": z.sha(p / "style.css")}


def kontrol_web_duzelt(p: Path, s: dict, yanit: str) -> list:
    html = (p / "index.html").read_text(encoding="utf-8", errors="replace")
    js = (p / "app.js").read_text(encoding="utf-8", errors="replace") if (p / "app.js").is_file() else ""
    ids = set(re.findall(r"id=[\"']([\w-]+)[\"']", html))
    used = re.findall(r"getElementById\([\"']([\w-]+)[\"']\)", js + html)
    return [("betikteki kimlikler sayfada var", bool(used) and all(u in ids for u in used), f"{used} / {sorted(ids)}"),
            ("sayaç hâlâ artıyor (+= 1)", "+= 1" in js or "++" in js, ""),
            ("style.css'e dokunulmadı", z.sha(p / "style.css") == s["css"], "")]


# ---- oyun ---------------------------------------------------------------------------------------

def kur_oyun_mantik(p: Path) -> dict:
    return {}


KABUL_OYUN = """
import sys, json
sys.path.insert(0, ".")
from oyun import kazanan
E = " "
tahtalar = [
    ([["X","X","X"],["O","O",E],[E,E,E]], "X"),
    ([["O","X","X"],["O","X",E],["O",E,E]], "O"),
    ([["X","O",E],["O","X",E],[E,E,"X"]], "X"),
    ([[E,"O","X"],["O","X",E],["X",E,E]], "X"),
    ([["X","O","X"],["X","O","O"],["O","X","X"]], "berabere"),
    ([["X","O",E],[E,E,E],[E,E,E]], None),
]
print(json.dumps([kazanan(t) == b for t, b in tahtalar]))
"""


def kontrol_oyun_mantik(p: Path, s: dict, yanit: str) -> list:
    if not (p / "oyun.py").is_file():
        return [("oyun.py var", False, "")]
    k = p / "_kabul_oyun.py"
    k.write_text(KABUL_OYUN, encoding="utf-8")
    c, o = z.run([z.PY, str(k)], p)
    k.unlink(missing_ok=True)
    try:
        sonuc = json.loads(o.strip().splitlines()[-1])
    except Exception:
        sonuc = []
    ok, info = z.unittest_ok(p)
    return [("satır/sütun/çapraz kazananlar", sonuc[:4] == [True] * 4, o.strip()[-120:]),
            ("berabere", len(sonuc) > 4 and sonuc[4], ""),
            ("bitmemiş oyunda None", len(sonuc) > 5 and sonuc[5], ""),
            ("kendi testleri geçiyor", ok, info)]


def kur_oyun_canvas(p: Path) -> dict:
    return {}


def kontrol_oyun_canvas(p: Path, s: dict, yanit: str) -> list:
    f = p / "oyun.html"
    if not f.is_file():
        return [("oyun.html yazıldı", False, "")]
    t = f.read_text(encoding="utf-8", errors="replace")
    return [("oyun.html yazıldı", True, ""),
            ("canvas var", "<canvas" in t.lower(), ""),
            # ok tuşları: e.key ("ArrowUp") veya eski keyCode 37-40 — ikisi de çalışır (2026-10-24 gemma keyCode)
            ("ok tuşları dinleniyor", "keydown" in t and (("ArrowUp" in t and "ArrowLeft" in t)
                                                          or all(f"{k}" in t for k in (37, 38, 39, 40))), ""),
            ("#skor öğesi ve artış", bool(re.search(r"id=[\"']skor[\"']", t))
             and re.search(r"\b\w*(?:skor|score|puan)\w*\s*(?:\+\+|\+=)", t, re.I) is not None, ""),
            ("'Oyun bitti' mesajı", "Oyun bitti" in t, ""),
            ("tek dosya, harici kütüphane yok", not re.search(r"src=[\"']https?:", t, re.I), "")]


# ---- metin (klasörsüz sohbet) -------------------------------------------------------------------

def kur_bos(p: Path) -> dict:
    return {}


def kontrol_metin_eposta(p: Path, s: dict, yanit: str) -> list:
    kelime = len(re.findall(r"\w+", yanit))
    ingilizce = re.findall(r"\b(?:the|and|your|order|delay|sorry|dear)\b", yanit, re.I)
    return [("konu satırı", bool(re.search(r"^\W*konu\W", yanit, re.I | re.M)), ""),
            ("[TARİH] yer tutucusu korundu", "[TARİH]" in yanit, ""),
            ("özür diliyor", bool(re.search(r"özür|üzgünüz|kusura bakmayın", yanit, re.I)), ""),
            ("en çok ~140 kelime", kelime <= 140, f"{kelime} kelime"),
            ("İngilizce karışmadı", not ingilizce, ", ".join(ingilizce)[:60])]


def kontrol_metin_duzelt(p: Path, s: dict, yanit: str) -> list:
    t = yanit.replace("’", "'")
    return [("Yarınki (bitişik)", re.search(r"\byarınki\b", t, re.I) is not None, ""),
            ("saat 10'da", re.search(r"10(?:[.:]00)?'da", t) is not None, ""),   # TDK: 10.00'da da doğru
            ("başlayacak / önemlidir", "başlayacak" in t and "önemlidir" in t, ""),
            ("geç kalmayın", re.search(r"geç kalmayın", t, re.I) is not None, ""),
            ("anlam korunmuş (toplantı, katılım)", "toplantı" in t.lower() and "katıl" in t.lower(), "")]


# ---- zor (A13 ölçümü) ---------------------------------------------------------------------------

def kontrol_zor_todo(p: Path, s: dict, yanit: str) -> list:
    dosyalar = [p / n for n in ("gorev.py", "depo.py", "cli.py")]
    if not all(f.is_file() for f in dosyalar):
        return [("üç dosya var", False, ", ".join(f.name for f in dosyalar if not f.is_file()))]
    c1, o1 = z.run([z.PY, "cli.py", "ekle", "Süt al"], p)
    c2, o2 = z.run([z.PY, "cli.py", "listele"], p)
    c3, o3 = z.run([z.PY, "cli.py", "tamamla", "1"], p)
    c4, o4 = z.run([z.PY, "cli.py", "listele"], p)
    ok, info = z.unittest_ok(p)
    return [("üç dosya var", True, ""),
            ("ekle + listele", c1 == 0 and c2 == 0 and "Süt al" in o2, o2.strip()[-100:]),
            ("tamamla çalışıyor ve listede görünüyor", c3 == 0 and c4 == 0 and o4 != o2, o4.strip()[-100:]),
            ("JSON'da kalıcı", any(x.suffix == ".json" for x in p.iterdir()), ""),
            ("kendi testleri geçiyor", ok, info)]


ZOR_MODUL = '''"""{ad} modülü."""


def {fn}(x):
    print("{ad}: işleniyor", x)
    sonuc = x * {k}
    print("{ad}: bitti")
    return sonuc
'''


def kur_zor_logging(p: Path) -> dict:
    for ad, fn, k in (("fatura", "fatura_hesapla", 2), ("stok", "stok_say", 3), ("musteri", "puan", 4),
                      ("rapor", "rapor_yap", 5)):
        (p / f"{ad}.py").write_text(ZOR_MODUL.format(ad=ad, fn=fn, k=k), encoding="utf-8")
    (p / "tests").mkdir()
    (p / "tests" / "test_moduller.py").write_text(
        "import sys, unittest\nsys.path.insert(0, '.')\nimport fatura, stok, musteri, rapor\n\n"
        "class T(unittest.TestCase):\n    def test_hepsi(self):\n"
        "        self.assertEqual(fatura.fatura_hesapla(2), 4)\n        self.assertEqual(stok.stok_say(2), 6)\n"
        "        self.assertEqual(musteri.puan(2), 8)\n        self.assertEqual(rapor.rapor_yap(2), 10)\n\n"
        "if __name__ == '__main__':\n    unittest.main()\n", encoding="utf-8")
    return {"test": z.sha(p / "tests" / "test_moduller.py")}


def kontrol_zor_logging(p: Path, s: dict, yanit: str) -> list:
    mods = ["fatura", "stok", "musteri", "rapor"]
    txt = {m: (p / f"{m}.py").read_text(encoding="utf-8", errors="replace") for m in mods if (p / f"{m}.py").is_file()}
    ok, info = z.unittest_ok(p)
    return [("print kalmadı", len(txt) == 4 and not any("print(" in t for t in txt.values()), ""),
            ("logging kullanılıyor", len(txt) == 4 and all("logging" in t for t in txt.values()), ""),
            ("Türkçe mesajlar korundu", all("işleniyor" in t for t in txt.values()), ""),
            ("testlere dokunulmadı", z.sha(p / "tests" / "test_moduller.py") == s["test"], ""),
            ("testler geçiyor", ok, info)]


PAKETLER: dict[str, dict[str, dict]] = {
    "veri": {
        "veri_ozet": {"kur": kur_veri_ozet, "kontrol": kontrol_veri_ozet,
                      "mesaj": "satis.csv dosyasından bölge bazında toplam satış tutarını (adet × birim_fiyat) hesapla "
                               "ve rapor.md dosyasına `bölge | toplam` biçiminde bir tablo olarak yaz; tutarlar 2 "
                               "ondalık basamaklı olsun."},
        "veri_json": {"kur": kur_veri_json, "kontrol": kontrol_veri_json,
                      "mesaj": "siparisler.csv'de iptal edilen siparişleri hariç tutarak en çok sipariş veren 3 "
                               "müşteriyi bul ve ozet.json dosyasına {\"müşteri adı\": sipariş sayısı} biçiminde yaz."},
    },
    "web": {
        "web_form": {"kur": kur_web_form, "kontrol": kontrol_web_form,
                     "mesaj": "index.html dosyasında bir kayıt formu yap: ad (zorunlu, id=\"ad\"), e-posta (type=email, "
                              "zorunlu) ve gönder düğmesi. Form gönderilince JavaScript ile ad boşsa id=\"hata\" olan "
                              "öğeye 'Ad zorunlu' yazsın. Tek dosya, harici kütüphane kullanma."},
        "web_duzelt": {"kur": kur_web_duzelt, "kontrol": kontrol_web_duzelt,
                       "mesaj": "Web sayfasındaki Arttır düğmesine basınca sayı artmıyor. Hatayı bul ve düzelt."},
    },
    "oyun": {
        "oyun_mantik": {"kur": kur_oyun_mantik, "kontrol": kontrol_oyun_mantik,
                        "mesaj": "Yalnız standart kütüphaneyle tic-tac-toe oyun mantığı yaz: oyun.py içinde "
                                 "kazanan(tahta) fonksiyonu 3x3 liste alsın (hücreler 'X', 'O' veya ' ') ve 'X', 'O', "
                                 "tahta doluysa ve kazanan yoksa 'berabere', oyun sürüyorsa None döndürsün. tests/ "
                                 "altında unittest testleri yaz ve `python -m unittest discover -s tests` ile çalıştır."},
        "oyun_canvas": {"kur": kur_oyun_canvas, "kontrol": kontrol_oyun_canvas,
                        "mesaj": "Tek dosyalık bir HTML5 canvas yılan oyunu yap: oyun.html. Ok tuşlarıyla yön "
                                 "değişsin, yem yiyince id=\"skor\" öğesindeki skor artsın, duvara veya kendine "
                                 "çarpınca ekrana 'Oyun bitti' yazsın. Harici kütüphane kullanma."},
    },
    "metin": {
        "metin_eposta": {"kur": kur_bos, "kontrol": kontrol_metin_eposta, "klasorsuz": True,
                         "mesaj": "Müşteriye, siparişinin 3 gün gecikeceğini bildiren kısa ve nazik bir e-posta yaz. "
                                  "Konu satırı olsun, 120 kelimeyi geçmesin, özür dile ve yeni teslim tarihini [TARİH] "
                                  "olarak bırak."},
        "metin_duzelt": {"kur": kur_bos, "kontrol": kontrol_metin_duzelt, "klasorsuz": True,
                         "mesaj": "Şu metnin yazım ve noktalama hatalarını düzelterek yeniden yaz, anlamını "
                                  "değiştirme: 'yarin ki toplantı saat 10 da baslayacak herkesin katılması onemlidir "
                                  "lütfen gec kalmayın'"},
    },
    "zor": {
        "zor_todo": {"kur": kur_bos, "kontrol": kontrol_zor_todo,
                     "mesaj": "Yalnız standart kütüphaneyle bir yapılacaklar uygulaması yaz: gorev.py (Gorev sınıfı: "
                              "numara, başlık, tamamlandı), depo.py (görevleri gorevler.json dosyasında sakla ve yükle), "
                              "cli.py (`python cli.py ekle \"başlık\"`, `python cli.py listele`, `python cli.py "
                              "tamamla <numara>`; listede tamamlananlar [x], diğerleri [ ] ile gösterilsin). tests/ "
                              "altında unittest testleri yaz ve `python -m unittest discover -s tests` ile çalıştırıp "
                              "geçtiğini göster."},
        "zor_logging": {"kur": kur_zor_logging, "kontrol": kontrol_zor_logging,
                        "mesaj": "Tüm projede print çağrılarını logging modülüne çevir (her modül kendi logger'ını "
                                 "kullansın, mesaj metinleri aynı kalsın). Testlere dokunma; sonunda "
                                 "`python -m unittest discover -s tests` ile testlerin geçtiğini göster."},
    },
}


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in PAKETLER:
        print(__doc__)
        raise SystemExit(2)
    paket = sys.argv.pop(1)
    raise SystemExit(z.main(PAKETLER[paket], baslik=f"Rol paketi · {paket}", alt=f"rol_{paket}"))
