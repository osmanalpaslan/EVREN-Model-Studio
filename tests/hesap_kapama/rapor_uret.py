#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hesap Kapama Raporu uretici (her ay tekrar calistirilabilir).

Kullanim:
    python rapor_uret.py <kaynak_klasor> <cikti.xlsx>

Kurallar:
  * hesap-kapama-raporu/SKILL.md ve KURAL_NETLESTIRMELERI.md uygulanir.
  * Kaynak dosyalar ADINDAN degil basliklarindan taninir; sutunlar BASLIK ADIYLA
    eslesir (buyuk/kucuk harf, i/i, bosluk ve Turkce karakter farklari tolere edilir).
    Sutun SIRASI kullanilmaz.
  * Veriye ozel sabit deger YOKTUR: kullanici sozlugu kaynak klasordeki
    kullanici_listesi.tsv dosyasindan okunur.
  * Ham kaynak dosyalara ve skill klasorune yazilmaz, gecici dosya birakilmaz.

Cikis kodlari:
  0 basarili
  1 kullanim hatasi / beklenmeyen durum
  2 zorunlu bir sutun/dosya bulunamadi (tahmin yurutulmedi)
  3 dogrulama (§5) tutmadi veya hedef dosya kilitli -> dosya yazilmadi
"""

import io
import os
import re
import sys
import datetime
from collections import Counter, OrderedDict, defaultdict

try:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
except ImportError:  # pragma: no cover
    print("HATA: openpyxl bulunamadi. 'pip install openpyxl' gerekiyor.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Sabit kurallar (SKILL.md / KURAL_NETLESTIRMELERI.md'den; veriye ozel degil)
# ---------------------------------------------------------------------------

LOG_TEXT = (
    "Musteri odeme asamasinda sistemden cikmistir. Faaliyet disi kaydi nedeniyle "
    "tum urunler icin otomatik olarak is acilmistir."
)

# SKILL.md 3.1 - Acilis Kaynagi
KAYNAK_LOG = "Log"
KAYNAK_HESAP_UYUM = "HesapUyum"
KAYNAK_ESKI_DESTEK = "Eski Destek Merkezi"
KAYNAK_MANUEL = "Manuel"
KAYNAK_SIRASI = [KAYNAK_LOG, KAYNAK_HESAP_UYUM, KAYNAK_ESKI_DESTEK, KAYNAK_MANUEL]

# SKILL.md 3.2 - Acilma Turu
ACILMA_OTOMATIK = "Otomatik açılan iş"
ACILMA_MANUEL = "Manuel açılan iş"

# SKILL.md 3.4 + netlestirme 1 - Kapama Turu (" / " iceren deger uretilmez)
KAPAMA_ACIK = "(iş açık)"
KAPAMA_MANUEL = "Manuel"
# SKILL.md 3.4'teki sabit etiketler (veriye ozel degil, kural degeri)
KAPAMA_OTO = "oto hesapkapama"
KAPAMA_WEBSERVIS = "webservis"

# SKILL.md 3.5 - Acik sayilan firsaat statuleri (opportunity_type = 1)
# "Kazanildi" sistemde kapalidir ama bu raporda ACIK sayilir.
ACIK_DURUMLAR = {"yeni", "devamediyor", "ertelendi", "teklifverildi", "demo", "kazanildi"}

# SKILL.md 3.8 - kapsam disi (yalnizca "Kaybetme Nedeni" icin)
KAPSAM_DISI_NEDENLER = {"postakutusukapanisi", "subekapanisi"}

# SKILL.md 3.6 - sozlesme id olmayan degerler
GECERSIZ_ID = {"", "0", "-", "#N/A", "#YOK", "#DEĞER!", "#REF!", "YOK", "NA", "N/A"}

KISMI_OZET_BASLIKLARI = [
    "İş ID",
    "İş Kodu",
    "Oluşturma Tarihi",
    "Müşteri Adı",
    "VKN/TCKN",
    "Ürün",
    "Fırsat Kodu",
    "Açılış Kaynağı",
    "Açılma Türü",
    "Açan Kullanıcı",
    "İş Sonucu",
    "İş Durumu",
    "Kapama Türü",
    "Kapatan Kullanıcı",
    "Kaybetme Nedeni",
    "Müşteri Kaybetme Nedeni",
    "Fırsat Durumu",
    "Fırsat Durum Kodu",
    "Sözleşme Durumu",
    "Sözleşme ID",
    "CRS'de Ürün Kapalı mı?",
    "CRS Kapanan Ürün",
    "CRS Kapanış Tarihi",
    "Kapanması Gereken",
    "Analiz Önceliği",
]

PRIO_YUKSEK = "1 - Yüksek"
PRIO_ORTA = "2 - Orta"
PRIO_YOK = "3 - Sorun yok"

HEADER_FILL = PatternFill("solid", fgColor="1F3864")
HEADER_FONT = Font(color="FFFFFF", bold=True)
SECTION_FILL = PatternFill("solid", fgColor="D9E1F2")
SECTION_FONT = Font(bold=True, color="1F3864")
DATE_FORMAT = "DD.MM.YYYY"
MAX_WIDTH = 42


# ---------------------------------------------------------------------------
# Metin / deger yardimcilari
# ---------------------------------------------------------------------------

TR_MAP = str.maketrans({
    "ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ğ": "g", "Ğ": "G",
    "ü": "u", "Ü": "U", "ö": "o", "Ö": "O", "ç": "c", "Ç": "C",
    "â": "a", "Â": "A", "î": "i", "Î": "I", "û": "u", "Û": "U",
})


def norm(s):
    """Baslik/deger normalizasyonu: Turkce karakter + isim farklarini tolere eder."""
    if s is None:
        return ""
    t = str(s).translate(TR_MAP).lower()
    return re.sub(r"[^a-z0-9]", "", t)


LOG_KEY = norm(LOG_TEXT)


def clean(v):
    """Hucre degerini guvenli metne cevirir (sekme/satir sonu temizligi - tuzak 5)."""
    if v is None:
        return None
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v
    s = str(v).replace("\t", " ").replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s if s != "" else None


def parse_bool(v):
    n = norm(v)
    return n in {"true", "1", "evet", "e", "dogru", "x"}


def to_date(v):
    if v is None or v == "":
        return None
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    if isinstance(v, (int, float)):
        if 20000 <= float(v) <= 80000:  # Excel seri tarihi
            base = datetime.date(1899, 12, 30)
            return base + datetime.timedelta(days=int(v))
        return None
    s = str(v).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S",
                "%d.%m.%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def digits_key(v):
    """VKN/TCKN karsilastirma anahtari: bastaki sifirlar atilir."""
    s = re.sub(r"\D", "", str(v or ""))
    return s.lstrip("0") or "0"


def is_valid_id(v):
    """Gecerli sozlesme ID'si mi (SKILL.md 3.6)."""
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return float(v) > 0
    s = str(v).strip()
    if s.upper() in GECERSIZ_ID or s in GECERSIZ_ID:
        return False
    return s != "" and s.upper() not in {g.upper() for g in GECERSIZ_ID}


# ---------------------------------------------------------------------------
# Sutun tanima - adiyla, icerigi dislamadan
# ---------------------------------------------------------------------------

ROLE_ALIASES = {
    "isler": {
        "is_id": (["id", "işid", "isid", "işkayıtno", "kayıtno", "işkayıtno"], False),
        "is_no": (["işno", "isno", "işkodu", "iskodu", "işnumarası", "isnumarasi"], True),
        "olusturma_tarihi": (["oluşturmatarihi", "olusturmatarihi", "oluşturmatarih",
                             "oluşturulmatarihi", "kayıttarihi", "kayıtolusturmatarihi"], True),
        "musteri_adi": (["müşteriadı", "musteriadi", "müşteriunvanı", "musteriunvani",
                         "unvan", "müşteriünvanı"], True),
        "tckn": (["tckimlikno", "tckn", "kimlikno", "tckimlikno"], True),
        "vkn": (["vergino", "vkn", "verginumarası", "verginumarasi", "vergiidentify"],
                True),
        "urun": (["ürün", "urun", "ürünadı", "urunadi", "ürünkod", "urunkod"], True),
        "firsat_kodu": (["fırsatkodu", "firsatkodu", "fırsatno", "firsatno",
                         "fırsatıd", "firsatid", "fırsatnumarası", "firsatnumarasi"], True),
        "ekleyen": (["ekleyen", "ekleyenkullanıcı", "ekleyenid", "ekleyenkullanici",
                     "ekleyenkullanıcıid"], True),
        "hesap_uyum": (["hesapuyum", "hesapuyumdanoluşmuştur", "hesapuyumdanolusmustur"],
                       True),
        "is_sonucu": (["işsonucu", "issonucu", "sonuç", "sonuc", "işsonuç"], True),
        "aciklama": (["açıklama", "aciklama", "description", "işdetaı", "detay"], True),
        "kaybetme_nedeni": (["kaybetmenedeni", "kaybetmeneden"], False),
        "musteri_kaybetme_nedeni": (["müşterikaybetmenedeni", "musterikaybetmenedeni"],
                                    False),
        "son_degistiren": (["sondeğiştiren", "sondegistiren", "sondeğiştirenkullanıcı",
                            "sondegistirenkullanici", "değiştiren", "degistiren"], True),
        "durum": (["durum", "işdurumu", "isdurumu", "status"], True),
    },
    "firsat": {
        "firsat_no": (["fırsatno", "firsatno", "fırsatkodu", "firsatkodu",
                       "fırsatnumarası", "fırsatid", "firsatid"], True),
        "durum_kodu": (["durumkod", "durumkodu", "fırsatdurumu", "firsatdurumu",
                        "durum", "statü", "statu"], True),
        "urun": (["ürünkod", "urunkod", "ürün", "urun", "ürünadı", "urunadi"], True),
        "tckn_vkn": (["tcknvkn", "tckn", "vkn", "vergino", "tckimlikno",
                      "vergino/tckimlikno"], True),
    },
    "sozlesme": {
        "firsat_kodu": (["fırsatkodu", "firsatkodu", "fırsatno", "firsatno",
                         "fırsatıd", "firsatid"], True),
        "sozlesme_id": (["sözleşmeıd", "sozlesmeid", "sözleşmeid", "sozlesmekodu",
                         "sözleşmekodu", "sözleşmeno", "sozlesmeno", "sözleşmenumarası",
                         "sozlesmenumarasi"], True),
        "urun": (["ürün", "urun", "ürünkod", "urunkod", "ürünadı", "urunadi"], True),
    },
    "crs": {
        "tckn_vkn": (["identifytaxno", "tcknvkn", "vkn", "vergino", "tckimlikno"], True),
        "type": (["type", "tip", "işlemkodu", "islemkodu", "crsislemkodu"], True),
        "islem_tarihi": (["executiondate", "işlemtarihi", "islemtarihi", "tarih",
                          "kapanıştarihi", "kapanistarihi"], True),
    },
    "sayac": {
        "urun": (["sayaçtipadı", "sayactipadi", "ürünadı", "urunadi", "ürün", "urun",
                  "tipadı", "tipadi"], True),
        "crs_acilis": (["crssayaçtipi", "crssayactipi", "crsaçılışsayaçtipi",
                        "crsacilissayactipi", "crsaçılış", "crsacilis"], True),
        "crs_kapanis": (["crskapanışsayaçtipi", "crskapanissayactipi",
                         "crskapanış", "crskapanis"], False),
    },
}


class EksikSutun(Exception):
    pass


def col_index(headers_norm, aliases, fallback=True):
    """Baslik adindan sutun indeksi. Bulamazsa None; birden fazla aday varsa None."""
    for alias in aliases:
        a = norm(alias)
        hits = [i for i, h in enumerate(headers_norm) if h == a]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            return None
    if fallback:
        for alias in aliases:
            a = norm(alias)
            if len(a) < 6:
                continue
            hits = [i for i, h in enumerate(headers_norm) if a in h]
            if len(hits) == 1:
                return hits[0]
    return None


def map_role(headers_norm, role):
    mapping = {}
    for key, (aliases, fallback) in ROLE_ALIASES[role].items():
        idx = col_index(headers_norm, aliases, fallback)
        if idx is not None:
            mapping[key] = idx
    return mapping


def detect_role(headers_norm):
    hset = set(headers_norm)
    has = lambda *names: any(norm(n) in hset for n in names)
    if has("Ekleyen") and has("Hesap Uyum", "Hesap Uyumdan Oluşmuştur") and \
            has("İş Sonucu", "Sonuç"):
        return "isler"
    if has("DURUM KOD", "Durum Kodu", "Fırsat Durumu") and \
            has("FIRSAT NO", "Fırsat No", "Fırsat Kodu"):
        return "firsat"
    if has("Sözleşme ID", "sözleşme ıd", "Sözleşme Id", "Sözleşme Kodu", "Sözleşme No"):
        return "sozlesme"
    if has("IDENTIFY_TAX_NO", "TCKN/VKN") and has("TYPE"):
        return "crs"
    if has("Sayaç Tip Adı", "Sayaç Tipi Adı") and \
            has("CRS Sayaç Tipi", "Crs Sayaç Tipi", "CRS Sayaç Tipi Kodu"):
        return "sayac"
    return None


# ---------------------------------------------------------------------------
# Kaynak dosya okuma
# ---------------------------------------------------------------------------

def read_xlsx(path):
    """[(sayfa_adi, headers, rows)] dondurur. Kilitliyse kopyadan okur (tuzak 8)."""
    try:
        wb = load_workbook(filename=path, data_only=True, read_only=True)
    except PermissionError:
        with open(path, "rb") as fh:
            wb = load_workbook(filename=io.BytesIO(fh.read()), data_only=True,
                               read_only=True)
    sheets = []
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        # ilk dolu satir = baslik
        start = None
        for i, r in enumerate(rows):
            if any(c is not None and str(c).strip() != "" for c in r):
                start = i
                break
        if start is None:
            continue
        headers = [clean(c) for c in rows[start]]
        data = []
        for r in rows[start + 1:]:
            if all(c is None or str(c).strip() == "" for c in r):
                continue
            data.append(list(r))
        sheets.append((ws.title, headers, data))
    wb.close()
    return sheets


def read_kullanici_sozlugu(folder, uyarilar):
    """kullanici_listesi.tsv -> {id: TAM AD} sozlugu (UTF-8)."""
    candidates = [
        os.path.join(folder, "kullanici_listesi.tsv"),
        os.path.join(folder, "Kullanici_Listesi.tsv"),
    ]
    path = next((p for p in candidates if os.path.isfile(p)), None)
    if path is None:
        found = [f for f in os.listdir(folder)
                 if f.lower().endswith(".tsv") and "kullanici" in norm(f)]
        if found:
            path = os.path.join(folder, found[0])
    if path is None:
        uyarilar.append("kullanici_listesi.tsv bulunamadi; kullanici adlari yazilamadi.")
        return {}, {}

    raw = open(path, "rb").read()
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp1254"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")
        uyarilar.append("kullanici_listesi.tsv kodlamasi cozulemedi; bozuk karakter olabilir.")

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        uyarilar.append("kullanici_listesi.tsv bos.")
        return {}, {}

    header = [norm(c) for c in lines[0].split("\t")]
    i_id = col_index(header, ["kullaniciid", "id", "kullanıcııd"], fallback=False)
    i_tam = col_index(header, ["tamad", "adsoyad", "tamadı"], fallback=False)
    i_ad = col_index(header, ["adi"], fallback=False)
    i_soyad = col_index(header, ["soyadi"], fallback=False)
    i_kod = col_index(header, ["kullanıcıkodu", "kullanicikodu", "kod"], fallback=False)
    if i_id is None:
        uyarilar.append("kullanici_listesi.tsv icinde 'KULLANICI ID' sutunu bulunamadi.")
        return {}, {}

    adlar, kodlar = {}, {}
    for ln in lines[1:]:
        parts = ln.split("\t")
        if len(parts) <= i_id:
            continue
        kullanici_id = re.sub(r"\D", "", parts[i_id])
        if not kullanici_id:
            continue
        tam = None
        if i_tam is not None and i_tam < len(parts):
            tam = clean(parts[i_tam])
        if not tam and i_ad is not None and i_soyad is not None and \
                i_ad < len(parts) and i_soyad < len(parts):
            tam = clean((parts[i_ad] + " " + parts[i_soyad]).strip())
        if tam:
            adlar[int(kullanici_id)] = tam
        if i_kod is not None and i_kod < len(parts):
            kodlar[int(kullanici_id)] = clean(parts[i_kod])
    return adlar, kodlar


# ---------------------------------------------------------------------------
# Kaynak dosyalari rolune gore bul
# ---------------------------------------------------------------------------

def discover_sources(folder):
    sources = defaultdict(list)
    unrecognized = []
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith((".xlsx", ".xlsm")) or name.startswith("~$"):
            continue
        path = os.path.join(folder, name)
        for sheet_name, headers, rows in read_xlsx(path):
            hnorm = [norm(h) for h in headers]
            role = detect_role(hnorm)
            if role is None:
                unrecognized.append("%s / %s" % (name, sheet_name))
                continue
            sources[role].append({
                "dosya": name,
                "sayfa": sheet_name,
                "headers": headers,
                "rows": rows,
                "mapping": map_role(hnorm, role),
            })
    return sources, unrecognized


# ---------------------------------------------------------------------------
# Ana islem
# ---------------------------------------------------------------------------

def main(argv):
    if len(argv) != 3:
        print("Kullanim: python rapor_uret.py <kaynak_klasor> <cikti.xlsx>")
        return 1

    kaynak = os.path.abspath(argv[1])
    hedef = os.path.abspath(argv[2])
    if not os.path.isdir(kaynak):
        print("HATA: kaynak klasor bulunamadi: %s" % kaynak)
        return 1

    uyarilar = []
    eksikler = []

    sources, unrecognized = discover_sources(kaynak)

    # --- zorunlu dosya rolleri -------------------------------------------------
    for role, ad in (("isler", "Acik isler / Kapali isler"),
                     ("firsat", "Firsat listesi"),
                     ("sozlesme", "Sozlesme listesi")):
        if not sources.get(role):
            eksikler.append("%s dosyasi taninamadi (basliklardan rol cikarilamadi)." % ad)
    if sources.get("crs") and not sources.get("sayac"):
        eksikler.append("CRS verisi var ama 'Sayac tipleri' dosyasi taninamadi "
                        "(CRS kapanisi urunle eslestirilemez).")

    # --- zorunlu sutunlar ------------------------------------------------------
    is_zorunlu = ["is_id", "is_sonucu", "ekleyen", "hesap_uyum", "olusturma_tarihi",
                  "musteri_adi", "urun", "firsat_kodu", "aciklama", "kaybetme_nedeni",
                  "son_degistiren"]
    for src in sources.get("isler", []):
        for key in is_zorunlu:
            if key not in src["mapping"]:
                eksikler.append("%s / %s: zorunlu sutun '%s' bulunamadi."
                                % (src["dosya"], src["sayfa"],
                                   ROLE_ALIASES["isler"][key][0][0]))
        if "vkn" not in src["mapping"] and "tckn" not in src["mapping"]:
            eksikler.append("%s / %s: VKN/TCKN sutunu bulunamadi."
                            % (src["dosya"], src["sayfa"]))
        if "is_no" not in src["mapping"]:
            uyarilar.append("%s / %s: 'Is No' sutunu yok, Is Kodu bos birakildi."
                            % (src["dosya"], src["sayfa"]))
        if "durum" not in src["mapping"]:
            uyarilar.append("%s / %s: 'Durum' sutunu yok, Is Durumu bos birakildi."
                            % (src["dosya"], src["sayfa"]))
        if "musteri_kaybetme_nedeni" not in src["mapping"]:
            uyarilar.append("%s / %s: 'Musteri Kaybetme Nedeni' sutunu yok."
                            % (src["dosya"], src["sayfa"]))

    for src in sources.get("firsat", []):
        for key in ("firsat_no", "durum_kodu"):
            if key not in src["mapping"]:
                eksikler.append("%s / %s: zorunlu sutun '%s' bulunamadi."
                                % (src["dosya"], src["sayfa"],
                                   ROLE_ALIASES["firsat"][key][0][0]))

    for src in sources.get("sozlesme", []):
        for key in ("firsat_kodu", "sozlesme_id"):
            if key not in src["mapping"]:
                eksikler.append("%s / %s: zorunlu sutun '%s' bulunamadi."
                                % (src["dosya"], src["sayfa"],
                                   ROLE_ALIASES["sozlesme"][key][0][0]))

    for src in sources.get("crs", []):
        for key in ("tckn_vkn", "type", "islem_tarihi"):
            if key not in src["mapping"]:
                eksikler.append("%s / %s: zorunlu sutun '%s' bulunamadi."
                                % (src["dosya"], src["sayfa"],
                                   ROLE_ALIASES["crs"][key][0][0]))

    for src in sources.get("sayac", []):
        for key in ("urun", "crs_acilis"):
            if key not in src["mapping"]:
                eksikler.append("%s / %s: zorunlu sutun '%s' bulunamadi."
                                % (src["dosya"], src["sayfa"],
                                   ROLE_ALIASES["sayac"][key][0][0]))

    # --- taninan sutunlari yazdir (onay/izlenebilirlik) ------------------------
    print("=" * 78)
    print("TANINAN KAYNAK DOSYALAR VE SUTUNLAR")
    print("=" * 78)
    for role in ("isler", "firsat", "sozlesme", "crs", "sayac"):
        for src in sources.get(role, []):
            print("\n[%s] %s / %s  (%d veri satiri)" % (role, src["dosya"],
                                                        src["sayfa"], len(src["rows"])))
            for key, idx in src["mapping"].items():
                baslik = src["headers"][idx] if idx < len(src["headers"]) else "?"
                print("   - %-26s -> %2d. sutun  '%s'" % (key, idx + 1, baslik))
    if unrecognized:
        print("\nRol verilemeyen sayfalar (kullanilmadi): %s" % ", ".join(unrecognized))

    if eksikler:
        print("\n" + "!" * 78)
        print("DURDURULDU (cikis 2) - tahmin yurutulmedi:")
        for e in eksikler:
            print("  * " + e)
        return 2

    # --- kullanici sozlugu -----------------------------------------------------
    adlar, kodlar = read_kullanici_sozlugu(kaynak, uyarilar)
    api_kullanicilar = {k for k, v in kodlar.items()
                        if norm(v) in {"webservis", "otohesapkapama"}}
    if not api_kullanicilar:
        api_kullanicilar = {12055, 24153}
        uyarilar.append("Sozlukten API kullanicisi cikarilamadi; 12055/24153 varsayildi.")

    def kullanici_etiketi(kullanici_id):
        if kullanici_id is None:
            return None
        if kullanici_id in adlar:
            return "%s - %s" % (kullanici_id, adlar[kullanici_id])
        bilinmeyen_idler.add(kullanici_id)
        return str(kullanici_id)  # netlestirme 4: yalniz id

    bilinmeyen_idler = set()

    # --- is kayitlarini oku ----------------------------------------------------
    isler = []
    is_listesi_headers = []
    is_listesi_rows = []
    for src in sources["isler"]:
        mp = src["mapping"]
        hdrs = [h if h is not None else "Kolon%d" % (i + 1)
                for i, h in enumerate(src["headers"])]
        for h in hdrs:
            if h not in is_listesi_headers:
                is_listesi_headers.append(h)
        for row in src["rows"]:
            get = lambda key: (row[mp[key]] if key in mp and mp[key] < len(row) else None)

            sonuc = norm(get("is_sonucu"))
            if sonuc in {"acik", "open", "acikis", "acikoldu"}:
                acik = True
            elif sonuc in {"kapali", "closed", "kapandi", "kapaliis"}:
                acik = False
            else:
                print("\nDURDURULDU (cikis 3) - 'Is Sonucu' degeri cozulemedi: %r "
                      "(is id %s)" % (get("is_sonucu"), get("is_id")))
                return 3

            vkn = clean(get("vkn"))
            tckn = clean(get("tckn"))
            vkn_tckn = vkn or tckn or ""

            ekleyen_raw = clean(get("ekleyen"))
            ekleyen = int(re.sub(r"\D", "", ekleyen_raw)) if ekleyen_raw and \
                re.sub(r"\D", "", ekleyen_raw) else None
            son_deg_raw = clean(get("son_degistiren"))
            son_deg = int(re.sub(r"\D", "", son_deg_raw)) if son_deg_raw and \
                re.sub(r"\D", "", son_deg_raw) else None

            is_id = get("is_id")
            if isinstance(is_id, float) and is_id == int(is_id):
                is_id = int(is_id)

            aciklama = clean(get("aciklama")) or ""
            hesap_uyum = parse_bool(get("hesap_uyum"))

            # 3.1 Acilis Kaynagi - sira kritik
            if LOG_KEY and LOG_KEY in norm(aciklama):
                acilis_kaynagi = KAYNAK_LOG
            elif hesap_uyum:
                acilis_kaynagi = KAYNAK_HESAP_UYUM
            elif ekleyen is not None and ekleyen in api_kullanicilar and \
                    norm(kodlar.get(ekleyen, "")) == "webservis":
                acilis_kaynagi = KAYNAK_ESKI_DESTEK
            elif ekleyen == 12055:
                acilis_kaynagi = KAYNAK_ESKI_DESTEK
            else:
                acilis_kaynagi = KAYNAK_MANUEL

            # 3.2 Acilma Turu
            acilma_turu = ACILMA_OTOMATIK if ekleyen in api_kullanicilar else ACILMA_MANUEL

            # 3.4 Kapama Turu (netlestirme 1 ve 3)
            if acik:
                kapama_turu = KAPAMA_ACIK
                kapatan = None
            else:
                kod = norm(kodlar.get(son_deg, "")) if son_deg is not None else ""
                if kod == norm(KAPAMA_OTO) or (kod == "" and son_deg == 24153):
                    kapama_turu = KAPAMA_OTO
                elif kod == norm(KAPAMA_WEBSERVIS) or (kod == "" and son_deg == 12055):
                    kapama_turu = KAPAMA_WEBSERVIS
                else:
                    kapama_turu = KAPAMA_MANUEL
                kapatan = kullanici_etiketi(son_deg)

            kaybetme = clean(get("kaybetme_nedeni"))
            mkaybetme = clean(get("musteri_kaybetme_nedeni"))
            kapsam_disi = norm(kaybetme) in KAPSAM_DISI_NEDENLER

            isler.append({
                "is_id": is_id,
                "is_no": clean(get("is_no")),
                "tarih": to_date(get("olusturma_tarihi")),
                "musteri_adi": clean(get("musteri_adi")),
                "vkn_tckn": vkn_tckn,
                "vkn_key": digits_key(vkn_tckn),
                "urun": clean(get("urun")),
                "firsat_kodu": clean(get("firsat_kodu")),
                "acilis_kaynagi": acilis_kaynagi,
                "acilma_turu": acilma_turu,
                "acan": kullanici_etiketi(ekleyen),
                "acik": acik,
                "is_sonucu": clean(get("is_sonucu")),
                "is_durumu": clean(get("durum")),
                "kapama_turu": kapama_turu,
                "kapatan": kapatan,
                "kaybetme_nedeni": kaybetme,
                "musteri_kaybetme_nedeni": mkaybetme,
                "kapsam_disi": kapsam_disi,
                "hedef": None,
                "kaynak_dosya": src["dosya"],
            })
            is_listesi_rows.append([clean(c) for c in row])

    # --- firsaat kayitlari -----------------------------------------------------
    firsat_by_kod = defaultdict(list)
    firsat_ham_headers = []
    firsat_ham_rows = []
    for src in sources["firsat"]:
        mp = src["mapping"]
        hdrs = [h if h is not None else "Kolon%d" % (i + 1)
                for i, h in enumerate(src["headers"])]
        for h in hdrs:
            if h not in firsat_ham_headers:
                firsat_ham_headers.append(h)
        for row in src["rows"]:
            get = lambda k: (row[mp[k]] if k in mp and mp[k] < len(row) else None)
            kod = clean(get("firsat_no"))
            durum = clean(get("durum_kodu"))
            if not kod:
                continue
            urun = clean(get("urun"))
            firsat_by_kod[norm(kod)].append({
                "kod": kod,
                "durum": durum,
                "acik": norm(durum) in ACIK_DURUMLAR,
                "urun": urun,
                "vkn": clean(get("tckn_vkn")),
            })
            firsat_ham_rows.append([clean(c) for c in row])

    # --- sozlesme kayitlari ----------------------------------------------------
    sozlesme_by_kod = defaultdict(list)
    sozlesme_ham_headers = []
    sozlesme_ham_rows = []
    for src in sources["sozlesme"]:
        mp = src["mapping"]
        hdrs = [h if h is not None else "Kolon%d" % (i + 1)
                for i, h in enumerate(src["headers"])]
        for h in hdrs:
            if h not in sozlesme_ham_headers:
                sozlesme_ham_headers.append(h)
        for row in src["rows"]:
            get = lambda k: (row[mp[k]] if k in mp and mp[k] < len(row) else None)
            kod = clean(get("firsat_kodu"))
            sid = get("sozlesme_id")
            sozlesme_ham_rows.append([clean(c) for c in row])
            if not kod:
                continue
            gecerli = is_valid_id(sid)
            sozlesme_by_kod[norm(kod)].append({
                "id": clean(sid) if gecerli else None,
                "aktif": gecerli,
                "urun": clean(get("urun")),
            })

    # tekilleştirme: birebir ayni (firsat kodu + sozlesme id) satirlari
    for kod in list(sozlesme_by_kod.keys()):
        seen, uniq = set(), []
        for rec in sozlesme_by_kod[kod]:
            k = (rec["id"], rec["urun"])
            if k in seen:
                continue
            seen.add(k)
            uniq.append(rec)
        sozlesme_by_kod[kod] = uniq

    # --- CRS + sayac tipleri ---------------------------------------------------
    sayac_map = {}
    sayac_kapanis_map = {}
    kod_urun_adi = {}
    for src in sources.get("sayac", []):
        mp = src["mapping"]
        for row in src["rows"]:
            get = lambda k: (row[mp[k]] if k in mp and mp[k] < len(row) else None)
            urun = clean(get("urun"))
            acilis = get("crs_acilis")
            kapanis = get("crs_kapanis") if "crs_kapanis" in mp else None
            if urun is None:
                continue
            try:
                ac = int(float(str(acilis).replace(",", "."))) if acilis not in (None, "") else 0
            except (TypeError, ValueError):
                ac = 0
            if ac > 0:
                sayac_map[ac] = urun
                kod_urun_adi[ac] = urun
            if kapanis not in (None, ""):
                try:
                    kp = int(float(str(kapanis).replace(",", ".")))
                except (TypeError, ValueError):
                    kp = 0
                if kp > 0:
                    sayac_kapanis_map[kp] = urun

    urun_kodu = {}
    for code, urun in sayac_map.items():
        urun_kodu.setdefault(norm(urun), code)

    crs_kapanis = []          # [(vkn_key, acilis_kodu, tarih, type)]
    crs_kapanis_idx = defaultdict(list)
    eslesmeyen_crs_kodlari = Counter()
    for src in sources.get("crs", []):
        mp = src["mapping"]
        for row in src["rows"]:
            get = lambda k: (row[mp[k]] if k in mp and mp[k] < len(row) else None)
            vkn_key = digits_key(clean(get("tckn_vkn")))
            type_raw = get("type")
            try:
                ttype = int(float(str(type_raw).replace(",", ".")))
            except (TypeError, ValueError):
                continue
            if ttype < 100:
                continue
            acilis_kodu = ttype - 100  # SKILL.md 3.7: kapanis = acilis + 100
            tarih = to_date(get("islem_tarihi"))
            urun = sayac_map.get(acilis_kodu) or sayac_kapanis_map.get(ttype)
            if urun is None:
                eslesmeyen_crs_kodlari[ttype] += 1
            crs_kapanis.append({
                "vkn_key": vkn_key, "type": ttype, "acilis_kodu": acilis_kodu,
                "tarih": tarih, "urun": urun,
                "vkn": clean(get("tckn_vkn")),
            })
            crs_kapanis_idx[(vkn_key, norm(urun))].append(tarih)

    # is bazinda CRS kapanisi
    for is_rec in isler:
        urun = is_rec["urun"]
        code = urun_kodu.get(norm(urun))
        rec = None
        if code is not None:
            tarihler = crs_kapanis_idx.get((is_rec["vkn_key"], norm(sayac_map.get(code))))
            if tarihler:
                rec = {"capali": True, "urun": sayac_map.get(code),
                       "tarih": max([t for t in tarihler if t], default=None)}
        is_rec["crs_kapali"] = rec is not None
        is_rec["crs_urun"] = rec["urun"] if rec else None
        is_rec["crs_tarih"] = rec["tarih"] if rec else None

    # --- Kismi Ozet satirlari --------------------------------------------------
    kismi_rows = []
    kapsam_disi_rows = []
    is_bazinda_kapali = 0
    kapali_ise_sorunlu = set()
    firsaati_acik_kalan = set()
    sozlesmesi_aktif_kalan = set()

    for is_rec in isler:
        if is_rec["kapsam_disi"]:
            kapsam_disi_rows.append([
                is_rec["is_id"], is_rec["is_no"], is_rec["tarih"], is_rec["musteri_adi"],
                is_rec["vkn_tckn"], is_rec["urun"], is_rec["firsat_kodu"],
                is_rec["is_sonucu"], is_rec["acilis_kaynagi"], is_rec["kapama_turu"],
                is_rec["kaybetme_nedeni"], is_rec["musteri_kaybetme_nedeni"],
                is_rec["kaynak_dosya"],
            ])
            continue

        f_kod = norm(is_rec["firsat_kodu"])
        firsatlar = firsat_by_kod.get(f_kod) or [None]
        sozlesmeler = sozlesme_by_kod.get(f_kod) or [None]
        # birebir ayni firsaat kayitlarini tekille
        if firsatlar != [None]:
            seen, uniq = set(), []
            for rec in firsatlar:
                k = (norm(rec["kod"]), norm(rec["durum"]))
                if k in seen:
                    continue
                seen.add(k)
                uniq.append(rec)
            firsatlar = uniq

        for frec in firsatlar:
            for srec in sozlesmeler:
                firsat_acik = bool(frec and frec["acik"])
                sozlesme_aktif = bool(srec and srec["aktif"])

                if is_rec["acik"]:
                    kapanmasi_gereken = "Hayır"
                    oncelik = None
                else:
                    sorun = int(firsat_acik) + int(sozlesme_aktif)
                    kapanmasi_gereken = "Evet" if sorun else "Hayır"
                    oncelik = (PRIO_YUKSEK if sorun >= 2 else
                               PRIO_ORTA if sorun == 1 else PRIO_YOK)
                    if sorun:
                        kapali_ise_sorunlu.add(is_rec["is_id"])
                    if firsat_acik:
                        firsaati_acik_kalan.add(is_rec["is_id"])
                    if sozlesme_aktif:
                        sozlesmesi_aktif_kalan.add(is_rec["is_id"])

                kismi_rows.append([
                    is_rec["is_id"], is_rec["is_no"], is_rec["tarih"],
                    is_rec["musteri_adi"], is_rec["vkn_tckn"], is_rec["urun"],
                    is_rec["firsat_kodu"], is_rec["acilis_kaynagi"],
                    is_rec["acilma_turu"], is_rec["acan"], is_rec["is_sonucu"],
                    is_rec["is_durumu"], is_rec["kapama_turu"], is_rec["kapatan"],
                    is_rec["kaybetme_nedeni"], is_rec["musteri_kaybetme_nedeni"],
                    ("Açık" if firsat_acik else "Kapalı") if frec else None,
                    (frec["durum"] if frec else None),
                    "Aktif" if sozlesme_aktif else "Pasif",
                    (srec["id"] if sozlesme_aktif else None),
                    "Evet" if is_rec["crs_kapali"] else "Hayır",
                    is_rec["crs_urun"], is_rec["crs_tarih"],
                    kapanmasi_gereken, oncelik,
                ])

    # --- dogrulamalar (§5 + netlestirmeler) ------------------------------------
    toplam_is = len(isler)
    acik_is = sum(1 for r in isler if r["acik"])
    kapali_is = toplam_is - acik_is
    kapsam_disi_is = sum(1 for r in isler if r["kapsam_disi"])

    dag_kaynak = Counter(r["acilis_kaynagi"] for r in isler)
    dag_acilma = Counter(r["acilma_turu"] for r in isler)
    dag_kapama = Counter(r["kapama_turu"] for r in isler if not r["acik"])

    hatalar = []
    # 1-2: acilis kaynagi / acilma turu = TUM kaynak isler (netlestirme 2)
    if sum(dag_kaynak.values()) != toplam_is:
        hatalar.append("Acilis kaynagi dagilimi toplami %d != kaynak is sayisi %d"
                       % (sum(dag_kaynak.values()), toplam_is))
    if sum(dag_acilma.values()) != toplam_is:
        hatalar.append("Acilma turu dagilimi toplami %d != kaynak is sayisi %d"
                       % (sum(dag_acilma.values()), toplam_is))
    # 3: kapama turu = TUM kapali isler
    if sum(dag_kapama.values()) != kapali_is:
        hatalar.append("Kapama turu dagilimi toplami %d != kapali is sayisi %d"
                       % (sum(dag_kapama.values()), kapali_is))
    # 4: Kismi Ozet (tekil is) + Kapsam Disi = kaynak is sayisi
    tekil_kismi = len({r[0] for r in kismi_rows})
    if tekil_kismi + len(kapsam_disi_rows) != toplam_is:
        hatalar.append("Kismi Ozet tekil is (%d) + Kapsam Disi (%d) != kaynak is (%d)"
                       % (tekil_kismi, len(kapsam_disi_rows), toplam_is))
    if len(kismi_rows) < tekil_kismi:
        hatalar.append("Kismi Ozet satir sayisi tekil is sayisindan kucuk.")
    # 5: " / " ile birlesmis deger yok
    tum_hucreler = [c for row in kismi_rows for c in row]
    tum_hucreler += [c for row in kapsam_disi_rows for c in row]
    tum_hucreler += [c for row in is_listesi_rows for c in row]
    kirli = [c for c in tum_hucreler if isinstance(c, str) and " / " in c]
    if kirli:
        hatalar.append("%d hucrede ' / ' ile birlesmis deger var (ornek: %r)"
                       % (len(kirli), kirli[0]))
    # 7: Kismi Ozet tam 25 sutun, baslik sirasi birebir
    if len(KISMI_OZET_BASLIKLARI) != 25:
        hatalar.append("Kismi Ozet baslik listesi 25 sutun degil.")
    for row in kismi_rows:
        if len(row) != len(KISMI_OZET_BASLIKLARI):
            hatalar.append("Kismi Ozet satirinda %d hucre var (25 bekleniyor)."
                           % len(row))
            break

    # 8: hedef dosya Excel'de aciksa yazma
    if os.path.exists(hedef):
        kilit = os.path.join(os.path.dirname(hedef), "~$" + os.path.basename(hedef))
        if os.path.exists(kilit):
            print("\nYAZILMADI: hedef dosya Excel'de acik gorunuyor (%s). "
                  "Kapatip tekrar calistir." % hedef)
            return 3

    if hatalar:
        print("\n" + "!" * 78)
        print("DOGRULAMA TUTMADI (cikis 3) - dosya YAZILMADI:")
        for h in hatalar:
            print("  * " + h)
        return 3

    # --- Excel yaz -------------------------------------------------------------
    wb = Workbook()

    def stil_baslik(ws, ncol):
        for c in range(1, ncol + 1):
            cell = ws.cell(row=1, column=c)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.row_dimensions[1].height = 30
        ws.freeze_panes = "A2"
        if ws.max_row > 1:
            ws.auto_filter.ref = "A1:%s%d" % (get_column_letter(ncol), ws.max_row)

    def genislik(ws, headers):
        for i, h in enumerate(headers, start=1):
            uzunluk = max([len(str(h or ""))] + [len(str(ws.cell(row=r, column=i).value))
                                                 for r in range(2, min(ws.max_row, 200) + 1)
                                                 if ws.cell(row=r, column=i).value is not None])
            ws.column_dimensions[get_column_letter(i)].width = min(max(10, uzunluk + 2),
                                                                   MAX_WIDTH)

    def yaz_ve_bicimlendir(ws, headers, rows, tarih_sutunlari=(), metin_sutunlari=()):
        ws.append(headers)
        for row in rows:
            ws.append([None if c == "" else c for c in row])
        for r in range(2, ws.max_row + 1):
            for idx in tarih_sutunlari:
                cell = ws.cell(row=r, column=idx + 1)
                if isinstance(cell.value, (datetime.datetime, datetime.date)):
                    cell.number_format = DATE_FORMAT
            for idx in metin_sutunlari:
                cell = ws.cell(row=r, column=idx + 1)
                if cell.value is not None:
                    cell.number_format = "@"
                    if not isinstance(cell.value, str):
                        cell.value = str(cell.value)
        stil_baslik(ws, len(headers))
        genislik(ws, headers)

    # 1) Yonetim Ozeti ---------------------------------------------------------
    ws = wb.active
    ws.title = "Yönetim Özeti"
    ws.column_dimensions["A"].width = MAX_WIDTH
    ws.column_dimensions["B"].width = 22

    satir = [1]

    def yaz(*degerler, **kw):
        r = satir[0]
        for i, v in enumerate(degerler, start=1):
            ws.cell(row=r, column=i, value=v)
        if kw.get("baslik"):
            ws.cell(row=r, column=1).font = Font(bold=True, size=14)
        if kw.get("bolum"):
            for i in range(1, 3):
                ws.cell(row=r, column=i).fill = SECTION_FILL
                ws.cell(row=r, column=i).font = SECTION_FONT
        if kw.get("alt"):
            ws.cell(row=r, column=1).font = Font(bold=True)
        if kw.get("aciklama"):
            ws.cell(row=r, column=1).font = Font(italic=True, size=9)
        satir[0] += 1

    def bosluk():
        satir[0] += 1

    yaz("Hesap Kapama Raporu - Yönetim Özeti", baslik=True)
    yaz("Kaynak klasör: %s" % kaynak)
    yaz("Üretim tarihi: %s" % datetime.datetime.now().strftime("%d.%m.%Y %H:%M"))
    bosluk()

    yaz("TEMEL SAYILAR", bolum=True)
    yaz("Toplam iş", toplam_is)
    yaz("Açık iş", acik_is)
    yaz("Kapalı iş", kapali_is)
    yaz("Kapsam dışı iş (PostaKutusuKapanışı / ŞubeKapanışı)", kapsam_disi_is)
    bosluk()

    yaz("SORU 1 - Toplam / açık / kapalı iş ve kapsam dışı iş sayısı", bolum=True)
    yaz("Ölçüt", "İş sayısı", alt=True)
    yaz("Toplam iş", toplam_is)
    yaz("Açık iş", acik_is)
    yaz("Kapalı iş", kapali_is)
    yaz("Kapsam dışı iş (ayrı sayfada)", kapsam_disi_is)
    bosluk()

    yaz("SORU 2 - Açılış kaynağı dağılımı (kapsam dışı dahil tüm kaynak işler)", bolum=True)
    yaz("Açılış Kaynağı", "İş sayısı", alt=True)
    for k in KAYNAK_SIRASI:
        yaz(k, dag_kaynak.get(k, 0))
    yaz("Toplam", sum(dag_kaynak.values()), alt=True)
    bosluk()

    yaz("SORU 3 - Açılma türü dağılımı (kapsam dışı dahil tüm kaynak işler)", bolum=True)
    yaz("Açılma Türü", "İş sayısı", alt=True)
    yaz(ACILMA_OTOMATIK, dag_acilma.get(ACILMA_OTOMATIK, 0))
    yaz(ACILMA_MANUEL, dag_acilma.get(ACILMA_MANUEL, 0))
    yaz("Toplam", sum(dag_acilma.values()), alt=True)
    bosluk()

    yaz("SORU 4 - Kapalı işlerde kapama türü dağılımı", bolum=True)
    yaz("Kapama Türü", "Kapalı iş sayısı", alt=True)
    for k in sorted(dag_kapama):
        yaz(k, dag_kapama[k])
    yaz("Toplam", sum(dag_kapama.values()), alt=True)
    bosluk()

    oncelik_dag = Counter(r[24] for r in kismi_rows
                          if r[24] in (PRIO_YUKSEK, PRIO_ORTA, PRIO_YOK))
    crs_kapali_iken_acik = sum(1 for r in isler if r["acik"] and r["crs_kapali"])

    yaz("SORU 5 - Kapalı işlerde fırsat/sözleşme tutarlılığı ve CRS", bolum=True)
    yaz("Analiz Önceliği (kapalı işler, kayıt bazında)", "Kayıt sayısı", alt=True)
    for k in (PRIO_YUKSEK, PRIO_ORTA, PRIO_YOK):
        yaz(k, oncelik_dag.get(k, 0))
    yaz("Toplam kayıt", sum(oncelik_dag.values()), alt=True)
    yaz("Kapanması gereken iş sayısı (tekil)", len(kapali_ise_sorunlu))
    yaz("CRS'te kapalı ama bizde açık iş sayısı", crs_kapali_iken_acik)
    bosluk()

    yaz("KAPANMASI GEREKENLER", bolum=True)
    yaz("Kapanması gereken iş sayısı (tekil)", len(kapali_ise_sorunlu))
    yaz("Kapanması gereken kayıt sayısı", sum(1 for r in kismi_rows if r[23] == "Evet"))
    yaz("Fırsatı açık kalmış kapalı iş sayısı", len(firsaati_acik_kalan))
    yaz("Sözleşmesi aktif kalmış kapalı iş sayısı", len(sozlesmesi_aktif_kalan))
    bosluk()

    yaz("CRS KONTROLÜ", bolum=True)
    yaz("CRS'te ürün kapalı olan iş sayısı (kapsam dışı dahil)",
        sum(1 for r in isler if r["crs_kapali"]))
    yaz("CRS'te ürün kapalı olan satır sayısı (Kısmi Özet)",
        sum(1 for r in kismi_rows if r[20] == "Evet"))
    yaz("CRS'te kapalı ama bizde açık iş sayısı", crs_kapali_iken_acik)
    yaz("CRS kapanış kaydı sayısı (TYPE >= 100)", len(crs_kapanis))
    bosluk()

    yaz("SÖZLÜKTE OLMAYAN KULLANICI ID'LERİ", bolum=True)
    if bilinmeyen_idler:
        yaz(", ".join(str(i) for i in sorted(bilinmeyen_idler)))
    else:
        yaz("Yok.")
    bosluk()

    yaz("Açılış kaynağı ve açılma türü dağılımları kapsam dışı işler dahil tüm kaynak "
        "işler üzerinden; kapama türü tüm kapalı işler üzerinden verilmiştir.", aciklama=True)
    yaz("Fırsat durumu opportunity_type kuralına göre (açık: Yeni, Devam Ediyor, "
        "Ertelendi, Teklif Verildi, Demo) belirlenmiş, 'Kazanıldı' bu raporda açık sayılmıştır.",
        aciklama=True)
    yaz("CRS kapanışı TYPE >= 100 (açılış kodu + 100) ve VKN + ürün eşleşmesiyle "
        "tespit edilmiştir; STATU alanı kapanış göstergesi değildir.", aciklama=True)

    # 2) Kismi Ozet ------------------------------------------------------------
    ws2 = wb.create_sheet("Kısmi Özet")
    yaz_ve_bicimlendir(ws2, KISMI_OZET_BASLIKLARI, kismi_rows,
                       tarih_sutunlari=(2, 22), metin_sutunlari=(4, 19))

    # 3) Is Listesi ------------------------------------------------------------
    ws3 = wb.create_sheet("İş Listesi")
    is_headers = is_listesi_headers + ["Kaynak Dosya"]
    is_rows_out = [row + [None] for row in is_listesi_rows]
    # kaynak dosya bilgisini sirayla ekle
    i = 0
    for src in sources["isler"]:
        for row in src["rows"]:
            if i < len(is_rows_out):
                is_rows_out[i][len(is_listesi_headers)] = src["dosya"]
            i += 1
    yaz_ve_bicimlendir(ws3, is_headers, is_rows_out)

    # 4) Sozlesme --------------------------------------------------------------
    ws4 = wb.create_sheet("Sözleşme")
    yaz_ve_bicimlendir(ws4, sozlesme_ham_headers, sozlesme_ham_rows)

    # 5) Firsat ----------------------------------------------------------------
    ws5 = wb.create_sheet("Fırsat")
    yaz_ve_bicimlendir(ws5, firsat_ham_headers, firsat_ham_rows)

    # 6) CRS Kontrol ----------------------------------------------------------
    ws6 = wb.create_sheet("CRS Kontrol")
    crs_headers = ["VKN/TCKN", "TYPE", "Açılış Kodu (TYPE-100)", "Ürün",
                   "İşlem Tarihi", "Eşleşen İş ID"]
    is_by_vkn_urun = defaultdict(list)
    for r in isler:
        is_by_vkn_urun[(r["vkn_key"], norm(r["urun"]))].append(r["is_id"])
    crs_rows = []
    for rec in sorted(crs_kapanis, key=lambda x: (str(x["vkn_key"]), x["type"])):
        eslesen = is_by_vkn_urun.get((rec["vkn_key"], norm(rec["urun"])), [])
        crs_rows.append([rec["vkn"], rec["type"], rec["acilis_kodu"], rec["urun"],
                         rec["tarih"], ", ".join(str(i) for i in eslesen) or None])
    yaz_ve_bicimlendir(ws6, crs_headers, crs_rows, tarih_sutunlari=(4,),
                       metin_sutunlari=(0,))

    # 7) Kapsam Disi -----------------------------------------------------------
    ws7 = wb.create_sheet("Kapsam Dışı")
    kd_headers = ["İş ID", "İş Kodu", "Oluşturma Tarihi", "Müşteri Adı", "VKN/TCKN",
                  "Ürün", "Fırsat Kodu", "İş Sonucu", "Açılış Kaynağı", "Kapama Türü",
                  "Kaybetme Nedeni", "Müşteri Kaybetme Nedeni", "Kaynak Dosya"]
    yaz_ve_bicimlendir(ws7, kd_headers, kapsam_disi_rows, tarih_sutunlari=(2,))

    # --- kaydet ---------------------------------------------------------------
    out_dir = os.path.dirname(hedef)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    try:
        wb.save(hedef)
    except PermissionError:
        print("\nYAZILMADI: hedef dosya kilitli (Excel'de acik olabilir): %s" % hedef)
        return 3

    # --- rapor ----------------------------------------------------------------
    print("\n" + "=" * 78)
    print("RAPOR ÜRETİLDİ: %s" % hedef)
    print("=" * 78)
    print("Kaynak iş sayısı        : %d  (açık %d / kapalı %d)"
          % (toplam_is, acik_is, kapali_is))
    print("Kısmı Özet satırı       : %d  (tekil iş %d)" % (len(kismi_rows), tekil_kismi))
    print("Kapsam dışı iş          : %d" % kapsam_disi_is)
    print("Açılış kaynağı          : " + ", ".join(
        "%s %d" % (k, dag_kaynak.get(k, 0)) for k in KAYNAK_SIRASI))
    print("Açılma türü             : " + ", ".join(
        "%s %d" % (k, v) for k, v in sorted(dag_acilma.items())))
    print("Kapama türü             : " + ", ".join(
        "%s %d" % (k, v) for k, v in sorted(dag_kapama.items())))
    print("Kapanması gereken       : %d iş / %d kayıt"
          % (len(kapali_ise_sorunlu), sum(1 for r in kismi_rows if r[23] == "Evet")))
    print("CRS'te kapalı, bizde açık: %d iş" % crs_kapali_iken_acik)
    print("CRS kapanış kaydı       : %d" % len(crs_kapanis))
    if eslesmeyen_crs_kodlari:
        print("Ürüne çevrilemeyen CRS kapanış kodları: " + ", ".join(
            "%d (%d kayıt)" % (k, v) for k, v in sorted(eslesmeyen_crs_kodlari.items())))
    if bilinmeyen_idler:
        print("Sözlükte olmayan kullanıcı id'leri: " +
              ", ".join(str(i) for i in sorted(bilinmeyen_idler)))
    if uyarilar:
        print("\nUYARILAR / VARSAYIMLAR:")
        for u in uyarilar:
            print("  - " + u)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
