"""Rol paketi kontrolleri (tests/e2e_rol_paketi_real_api.py) bilinen DOĞRU ve bilinen YANLIŞ çözümle sınanır (R-25):
gerçek API ölçümünden önce kontrolün kendisinin hatalı olmadığı gösterilir. Ağ yok."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e2e_rol_paketi_real_api as rp  # noqa: E402


def gecti(checks) -> bool:
    return all(ok for _n, ok, _d in checks)


def _w(p: Path, name: str, text: str) -> None:
    f = p / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def dogru_veri_ozet(p, s):
    _w(p, "hesapla.py", "import csv\nt={}\nfor r in csv.DictReader(open('satis.csv',encoding='utf-8'),delimiter=';'):\n"
                        "    t[r['bolge']]=t.get(r['bolge'],0)+int(r['adet'])*float(r['birim_fiyat'].replace(',','.'))\n"
                        "open('rapor.md','w',encoding='utf-8').write('| bölge | toplam |\\n|---|---|\\n'+''.join("
                        "f'| {b} | {v:.2f} |\\n' for b,v in t.items()))\n")
    rp.z.run([rp.z.PY, "hesapla.py"], p)


def yanlis_veri_ozet(p, s):
    _w(p, "rapor.md", "".join(f"| {b} | {v + 1:.2f} |\n" for b, v in s["toplam"].items()))


def dogru_veri_json(p, s):
    _w(p, "say.py", "print(1)\n")
    _w(p, "ozet.json", json.dumps(s["ilk3"], ensure_ascii=False))


def yanlis_veri_json(p, s):
    # iptalleri de sayan yanlış çözüm
    import csv

    say = defaultdict(int)
    for r in csv.DictReader((p / "siparisler.csv").open(encoding="utf-8")):
        say[r["musteri"]] += 1
    _w(p, "ozet.json", json.dumps(dict(sorted(say.items(), key=lambda kv: -kv[1])[:3]), ensure_ascii=False))


FORM = """<!doctype html><html><body><form id="f"><input id="ad" name="ad" required>
<input type="email" name="eposta" required><button>Gönder</button></form><p id="hata"></p>
<script>document.getElementById('f').addEventListener('submit',e=>{if(!document.getElementById('ad').value.trim()){
e.preventDefault();document.getElementById('hata').textContent='Ad zorunlu';}});</script></body></html>"""


def dogru_web_form(p, s):
    _w(p, "index.html", FORM)


def yanlis_web_form(p, s):
    _w(p, "index.html", FORM.replace('type="email" name="eposta" required', 'type="text" name="eposta"'))


def dogru_web_duzelt(p, s):
    _w(p, "app.js", rp.WEB_JS.replace('"artir-btn"', '"arttir-btn"'))


def yanlis_web_duzelt(p, s):
    _w(p, "style.css", "body { color: red; }\n")


OYUN = """def kazanan(t):
    hatlar = [r for r in t] + [[t[i][j] for i in range(3)] for j in range(3)]
    hatlar += [[t[i][i] for i in range(3)], [t[i][2 - i] for i in range(3)]]
    for h in hatlar:
        if h[0] != " " and h.count(h[0]) == 3:
            return h[0]
    return "berabere" if all(c != " " for r in t for c in r) else None
"""


def dogru_oyun_mantik(p, s):
    _w(p, "oyun.py", OYUN)
    _w(p, "tests/test_oyun.py", "import sys, unittest\nsys.path.insert(0, '.')\nfrom oyun import kazanan\n"
                                "class T(unittest.TestCase):\n    def test_x(self):\n"
                                "        self.assertEqual(kazanan([['X']*3,[' ']*3,[' ']*3]), 'X')\n")


def yanlis_oyun_mantik(p, s):
    _w(p, "oyun.py", OYUN.replace('[[t[i][i] for i in range(3)], [t[i][2 - i] for i in range(3)]]', '[]'))


CANVAS = """<!doctype html><html><body><canvas id="c" width="400" height="400"></canvas><p>Skor: <span id="skor">0</span></p>
<script>let skor=0;document.addEventListener('keydown',e=>{if(e.key==='ArrowUp'){}if(e.key==='ArrowLeft'){}
if(e.key==='ArrowDown'){}if(e.key==='ArrowRight'){}});function ye(){skor++;document.getElementById('skor').textContent=skor;}
function bitti(){document.body.insertAdjacentText('beforeend','Oyun bitti');}</script></body></html>"""


def dogru_oyun_canvas(p, s):
    _w(p, "oyun.html", CANVAS)


def yanlis_oyun_canvas(p, s):
    _w(p, "oyun.html", CANVAS.replace("<canvas", "<script src=\"https://cdn.example/x.js\"></script><canvas"))


DURUMLAR = {
    "veri_ozet": (dogru_veri_ozet, yanlis_veri_ozet),
    "veri_json": (dogru_veri_json, yanlis_veri_json),
    "web_form": (dogru_web_form, yanlis_web_form),
    "web_duzelt": (dogru_web_duzelt, yanlis_web_duzelt),
    "oyun_mantik": (dogru_oyun_mantik, yanlis_oyun_mantik),
    "oyun_canvas": (dogru_oyun_canvas, yanlis_oyun_canvas),
}


def _gorev(ad):
    for paket in rp.PAKETLER.values():
        if ad in paket:
            return paket[ad]
    raise KeyError(ad)


@pytest.mark.parametrize("ad", sorted(DURUMLAR))
def test_kontrol_dogruyu_gecirir_yanlisi_ve_bosu_yakalar(ad, tmp_path):
    g = _gorev(ad)
    dogru, yanlis = DURUMLAR[ad]
    for etiket, coz, beklenen in (("dogru", dogru, True), ("yanlis", yanlis, False), ("bos", None, False)):
        p = tmp_path / etiket
        p.mkdir()
        s = g["kur"](p)
        if coz is not None:
            coz(p, s)
        checks = g["kontrol"](p, s, "")
        assert gecti(checks) is beklenen, (etiket, [c for c in checks if not c[1]] if beklenen else checks)


def test_canvas_eski_keycode_ve_score_degiskeni_kabul(tmp_path):
    eski = CANVAS.replace("e.key==='ArrowUp'", "e.keyCode==38").replace("e.key==='ArrowLeft'", "e.keyCode==37")
    eski = eski.replace("e.key==='ArrowDown'", "e.keyCode==40").replace("e.key==='ArrowRight'", "e.keyCode==39")
    eski = eski.replace("skor++", "score += 10").replace("let skor=0", "let score=0")
    _w(tmp_path, "oyun.html", eski)
    assert gecti(rp.kontrol_oyun_canvas(tmp_path, {}, ""))
    _w(tmp_path, "oyun.html", eski.replace("score += 10", "score = 10"))
    assert not gecti(rp.kontrol_oyun_canvas(tmp_path, {}, ""))                # skor hiç artmıyor


def test_bomlu_json_dogru_sayilsa_da_yakalanir(tmp_path):
    s = rp.kur_veri_json(tmp_path)
    (tmp_path / "ozet.json").write_bytes(b"\xef\xbb\xbf" + json.dumps(s["ilk3"], ensure_ascii=False).encode("utf-8"))
    checks = {n: ok for n, ok, _d in rp.kontrol_veri_json(tmp_path, s, "")}
    assert checks["sayılar doğru (iptaller hariç)"] and not checks["BOM'suz UTF-8"]


def test_metin_kontrolleri():
    eposta = ("Konu: Siparişinizin teslimatı hakkında\n\nSayın Müşterimiz,\n\nSiparişinizin teslimatı 3 gün gecikecektir. "
              "Yaşattığımız aksaklık için özür dileriz. Yeni teslim tarihi: [TARİH].\n\nSaygılarımızla")
    assert gecti(rp.kontrol_metin_eposta(Path("."), {}, eposta))
    assert not gecti(rp.kontrol_metin_eposta(Path("."), {}, eposta.replace("[TARİH]", "5 Kasım")))
    assert not gecti(rp.kontrol_metin_eposta(Path("."), {}, eposta + " Dear customer, sorry for the delay."))
    assert not gecti(rp.kontrol_metin_eposta(Path("."), {}, eposta + " kelime" * 140))
    duz = "Yarınki toplantı saat 10'da başlayacak. Herkesin katılması önemlidir, lütfen geç kalmayın."
    assert gecti(rp.kontrol_metin_duzelt(Path("."), {}, duz))
    assert gecti(rp.kontrol_metin_duzelt(Path("."), {}, duz.replace("'", "’")))
    assert not gecti(rp.kontrol_metin_duzelt(Path("."), {}, duz.replace("Yarınki", "Yarın ki")))
    assert gecti(rp.kontrol_metin_duzelt(Path("."), {}, duz.replace("10'da", "10.00'da")))
    assert not gecti(rp.kontrol_metin_duzelt(Path("."), {}, duz.replace("10'da", "10 da")))


TODO = {
    "gorev.py": "class Gorev:\n    def __init__(self, numara, baslik, tamamlandi=False):\n"
                "        self.numara, self.baslik, self.tamamlandi = numara, baslik, tamamlandi\n",
    "depo.py": "import json, os\nfrom gorev import Gorev\nDOSYA = 'gorevler.json'\n"
               "def yukle():\n    if not os.path.exists(DOSYA):\n        return []\n"
               "    return [Gorev(**d) for d in json.load(open(DOSYA, encoding='utf-8'))]\n"
               "def kaydet(gs):\n    json.dump([g.__dict__ for g in gs], open(DOSYA, 'w', encoding='utf-8'), ensure_ascii=False)\n",
    "cli.py": "import sys\nfrom depo import yukle, kaydet\nfrom gorev import Gorev\ngs = yukle()\nk = sys.argv[1]\n"
              "if k == 'ekle':\n    gs.append(Gorev(len(gs) + 1, sys.argv[2]))\nelif k == 'tamamla':\n"
              "    for g in gs:\n        if g.numara == int(sys.argv[2]):\n            g.tamamlandi = True\n"
              "elif k == 'listele':\n    for g in gs:\n        print(('[x] ' if g.tamamlandi else '[ ] ') + g.baslik)\n"
              "kaydet(gs)\n",
    "tests/test_gorev.py": "import sys, unittest\nsys.path.insert(0, '.')\nfrom gorev import Gorev\n"
                           "class T(unittest.TestCase):\n    def test_g(self):\n        self.assertFalse(Gorev(1, 'a').tamamlandi)\n",
}


def test_zor_kontrolleri(tmp_path):
    iyi = tmp_path / "iyi"
    iyi.mkdir()
    for n, t in TODO.items():
        _w(iyi, n, t)
    assert gecti(rp.kontrol_zor_todo(iyi, {}, ""))
    kotu = tmp_path / "kotu"
    kotu.mkdir()
    for n, t in TODO.items():
        _w(kotu, n, t.replace("g.tamamlandi = True", "pass"))
    assert not gecti(rp.kontrol_zor_todo(kotu, {}, ""))
    # logging
    lg = tmp_path / "lg"
    lg.mkdir()
    s = rp.kur_zor_logging(lg)
    assert not gecti(rp.kontrol_zor_logging(lg, s, ""))                      # dokunulmamış proje
    for m in ("fatura", "stok", "musteri", "rapor"):
        f = lg / f"{m}.py"
        t = f.read_text(encoding="utf-8").replace('"""\n\n\n', '"""\nimport logging\n\nlog = logging.getLogger(__name__)\n\n\n', 1)
        f.write_text(t.replace("print(", "log.info("), encoding="utf-8")
    t = (lg / "fatura.py").read_text(encoding="utf-8")
    assert "print(" not in t
    checks = rp.kontrol_zor_logging(lg, s, "")
    assert gecti(checks), checks
