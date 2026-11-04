"""Gözlem ajanı: uygulama çalışırken görülen hata ve anormallikleri kaydeder, projenin GitHub deposuna
gönderir (Qt'siz). Geliştirici motoru `tools/ai_memory.py baslangic` ile bunları görür ve kullanıcıya bildirir.

Neden (kullanıcı kararı 2026-11-03): sorunlar yalnız test yaparken değil, uygulamayı kullanırken ve
geliştirirken de gözlemlensin; sonraki geliştirme oturumu düzeltilecekleri hazır bulsun.

Akış:
1. `kaydet(...)` — çökme, Qt uyarısı, görev hatası, beklenmeyen API hatası, ajan anormalliği. İçerik
   TEMİZLENİR (depo herkese açık): anahtar, kullanıcı adı, dosya yolu, e-posta, uzun token gitmez; sohbet
   içeriği hiç alınmaz. Aynı imza tek kayıtta toplanır (sayaç), yerel kuyruk: <veri>/gozlem/kuyruk.json.
2. `gonder(...)` — kuyruğu depodaki `gozlem-kayitlari` dalına yazar (veri klasöründe AYRI bir klon;
   kullanıcının çalışma kopyasına dokunulmaz). Her makine yalnız kendi `olay-<makine>.json` dosyasını
   yazar, `kayit.md` yalnız yoksa oluşturulur → makineler arasında çakışma olmaz.

Dal düzeni:
    gozlemler/<imza>/kayit.md            insan için kayıt (durum: acik | cozuldu | kabul-edildi)
    gozlemler/<imza>/olay-<makine>.json  o makinedeki sayaç, ilk/son görülme, sürümler
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import threading
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BRANCH = "gozlem-kayitlari"
ONEMLER = ("kritik", "yuksek", "orta", "dusuk")
TURLER = ("cokme", "gorev_hatasi", "qt_uyari", "api_hatasi", "ajan_anomali", "tur_sonu", "e2e_basarisiz",
          "gelistirici")
MAX_KAYIT = 300                 # kuyruktaki farklı imza üst sınırı (en eski düşük önemliler atılır)
DUSUK_ESIK = 3                  # düşük önemli "ortam" gözlemi bu sayıya ulaşmadan gönderilmez (gürültü)
MAX_METIN = 200
_PKG = Path(__file__).resolve().parent              # src/evren_studio
SOURCE_ROOT = _PKG.parents[1]                       # depo kökü (kaynaktan çalışırken)
_LOCK = threading.RLock()
_IN_KAYDET = threading.local()


# Ayarlar > Geliştirici gözlemi (Settings.gozlem_enabled); ana pencere açılışta ve kaydedince ayarlar
AYAR_ACIK = True


def etkin() -> bool:
    """EVREN_GOZLEM=0 her şeyi kapatır (pytest bunu ayarlar); ayar kapalıysa da kayıt yok."""
    return AYAR_ACIK and os.environ.get("EVREN_GOZLEM", "1") != "0"


def gercek_veri_dizini() -> Path:
    """Uygulamanın kalıcı veri klasörü. Gerçek API betikleri EVREN_STUDIO_DATA_DIR'i geçici klasöre
    çevirse de gözlemler kullanıcının asıl kuyruğuna yazılsın (uygulama onları gönderir)."""
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "EVREN-Model-Studio"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---- temizleme (depo herkese açık) ---------------------------------------------------------------

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# Yol: sürücü harfi (önünde harf yok: "https:" yol değildir), UNC veya ev klasörü (~). Yollar boşluk
# içerebildiği için tırnağa/satır sonuna kadar alınır: tırnaksız yoldan sonraki metin de gider (gizlilik önce).
_WINPATH = re.compile(r"(?:(?<![A-Za-z])[A-Za-z]:|\\\\[^\\\s]+|~)[\\/][^'\"<>|\n]*")
_POSIXHOME = re.compile(r"/(?:home|Users)/[^/\s'\"]+")
_LONG = re.compile(r"[A-Za-z0-9_\-+=]{32,}")
_QUERY = re.compile(r"(https?://[^\s?'\"]+)\?[^\s'\"]*")
_USERS_DIR = re.compile(r"([\\/])Users([\\/])[^\\/\s'\"]+", re.IGNORECASE)


def _rel_source(path: str) -> str | None:
    """Uygulamanın kendi kaynağındaki yol → depo göreli yol; değilse None."""
    try:
        p = Path(path).resolve()
        return p.relative_to(SOURCE_ROOT).as_posix()
    except (ValueError, OSError):
        return None


def temizle(text: Any, limit: int = MAX_METIN) -> str:
    """Herkese açık depoya gidecek metni temizler. Bilinmeyen her yol `<yol>` olur."""
    from .secrets import mask_secret

    s = mask_secret(str(text or ""))
    s = _QUERY.sub(r"\1?<sorgu>", s)
    s = _EMAIL.sub("<eposta>", s)
    # Uygulamanın kendi kaynağı ev klasörünün ALTINDA olabilir (C:\Users\Ad Soyad\Projects\...): ev klasörü "~"
    # yapılmadan önce depo içi yolları göreli yaz; yoksa "~\..." bilinmeyen yol sayılıp <yol> oluyordu (2026-11-04).
    root = str(SOURCE_ROOT)
    for variant in {root, root.replace("\\", "/")}:
        s = re.sub(re.escape(variant) + r"[\\/]((?!\.\.)[^'\"<>|\s]*)",
                   lambda m: m.group(1).replace("\\", "/"), s, flags=re.IGNORECASE)
    # Ev klasörü boşluk içerebilir ("C:\Users\Ad Soyad"): yol deseninden ÖNCE bütün olarak sil
    for home in {str(Path.home()), os.environ.get("USERPROFILE", "")}:
        if len(home) >= 4:
            for variant in {home, home.replace("\\", "/")}:
                s = re.sub(re.escape(variant), "~", s, flags=re.IGNORECASE)

    def _path(m: re.Match) -> str:
        raw = m.group(0).rstrip()
        rel = None if raw.startswith("~") else _rel_source(raw.rstrip(".,;:)"))
        return rel if rel and not rel.startswith("..") else "<yol>"

    s = _WINPATH.sub(_path, s)
    s = _USERS_DIR.sub(r"\1Users\2<kullanici>", s)
    s = _POSIXHOME.sub("/<kullanici>", s)
    s = _IPV4.sub("<ip>", s)
    s = _LONG.sub("<uzun>", s)
    names = {os.environ.get("USERNAME", ""), os.environ.get("USER", ""), Path.home().name}
    parts = {p for n in names for p in re.split(r"[\s._-]+", n) if len(p) >= 4}
    for name in sorted(names | parts, key=len, reverse=True):     # önce tam ad, sonra parçaları
        if len(name) >= 3:
            s = re.sub(r"(?<![\w])" + re.escape(name) + r"(?![\w])", "<kullanici>", s, flags=re.IGNORECASE)
    host = socket.gethostname()
    if len(host) >= 3:
        s = re.sub(re.escape(host), "<makine>", s, flags=re.IGNORECASE)
    s = " ".join(s.split())
    return s[:limit] + ("…" if len(s) > limit else "")


_AYRINTI_IZINLI = {"model", "rol", "olay", "http", "hata_kodu", "hata_turu", "durma", "protokol", "istisna",
                   "islem", "gorev", "sonuc", "adim", "sure_sn", "mod", "saglayici", "kaynak_betik",
                   "acik_plan"}


def _ayrinti_temizle(d: dict | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in (d or {}).items():
        if k not in _AYRINTI_IZINLI or v is None or v == "":
            continue
        out[k] = v if isinstance(v, (int, float, bool)) else temizle(v, 120)
    return out


def kendi_cerceveler(tb) -> list[str]:
    """Traceback'ten yalnız uygulamanın kendi çerçeveleri (dosya:satır işlev), en içteki 6."""
    out = []
    for fr in traceback.extract_tb(tb) if tb is not None else []:
        rel = _rel_source(fr.filename)
        if rel and rel.startswith("src/evren_studio/"):
            out.append(f"{rel}:{fr.lineno} {fr.name}")
    return out[-6:]


def _norm_mesaj(s: str) -> str:
    s = re.sub(r"'[^']*'|\"[^\"]*\"", "<s>", s)
    s = re.sub(r"\d+", "#", s)
    return s.lower()[:120]


def imza_hesapla(tur: str, baslik: str, istisna: str = "", cerceveler: list[str] | None = None,
                 mesaj: str = "") -> str:
    """Kararlı imza: satır numaraları ve sayılar değişince değişmez (dosya + işlev kullanılır)."""
    yer = [re.sub(r":\d+ ", " ", c) for c in (cerceveler or [])[-2:]]
    ham = "|".join([tur, _norm_mesaj(baslik), istisna, *yer, _norm_mesaj(mesaj)])
    return hashlib.sha1(ham.encode("utf-8")).hexdigest()[:12]


_SURUM: str | None = None


def surum() -> str:
    """`0.2.0+abc1234` — kaynaktan çalışırken git commit'i eklenir."""
    global _SURUM
    if _SURUM is None:
        from . import __version__

        _SURUM = __version__
        if (SOURCE_ROOT / ".git").exists():
            try:
                r = subprocess.run(["git", "-C", str(SOURCE_ROOT), "rev-parse", "--short", "HEAD"],
                                   capture_output=True, text=True, timeout=5,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if r.returncode == 0 and r.stdout.strip():
                    _SURUM += "+" + r.stdout.strip()
            except (OSError, subprocess.TimeoutExpired):
                pass
    return _SURUM


def makine_kimligi() -> str:
    """Geri çözülemeyen kısa makine kimliği (bilgisayar + kullanıcı adının özeti)."""
    ham = f"{socket.gethostname()}|{os.environ.get('USERNAME') or os.environ.get('USER') or ''}"
    return hashlib.sha256(ham.lower().encode("utf-8")).hexdigest()[:8]


# ---- yerel kuyruk ---------------------------------------------------------------------------------

@dataclass
class Gozlem:
    imza: str
    tur: str
    baslik: str
    onem: str
    alan: str
    kaynak: str = "uygulama"           # uygulama | e2e | motor
    istisna: str = ""
    mesaj: str = ""
    cerceveler: list[str] = field(default_factory=list)
    ayrinti: dict[str, Any] = field(default_factory=dict)
    ilk: str = ""
    son: str = ""
    sayac: int = 0
    surumler: list[str] = field(default_factory=list)
    gonderilen: int = 0                # depoya yazılmış sayaç

    def gonderilmeli(self) -> bool:
        if self.sayac <= self.gonderilen:
            return False
        return not (self.onem == "dusuk" and self.alan == "ortam" and self.sayac < DUSUK_ESIK)


class Kuyruk:
    def __init__(self, veri_dizini: Path):
        self.dir = Path(veri_dizini) / "gozlem"
        self.path = self.dir / "kuyruk.json"

    def oku(self) -> dict[str, Gozlem]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        out = {}
        for k, v in (raw.get("gozlemler") or {}).items():
            try:
                out[k] = Gozlem(**{f: v[f] for f in Gozlem.__dataclass_fields__ if f in v})
            except TypeError:
                continue
        return out

    def yaz(self, items: dict[str, Gozlem], **ek: Any) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        meta = self.meta()
        meta.update(ek)
        data = {"surum": 1, **meta, "gozlemler": {k: asdict(v) for k, v in items.items()}}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    def meta(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return {k: v for k, v in raw.items() if k not in ("gozlemler", "surum")}


def _budama(items: dict[str, Gozlem]) -> None:
    if len(items) <= MAX_KAYIT:
        return
    sira = sorted(items.values(), key=lambda g: (-ONEMLER.index(g.onem), g.son))
    for g in sira[: len(items) - MAX_KAYIT]:
        items.pop(g.imza, None)


def kaydet(tur: str, baslik: str, *, onem: str = "orta", alan: str = "genel", exc: BaseException | None = None,
           tb=None, mesaj: str = "", ayrinti: dict | None = None, kaynak: str | None = None,
           veri_dizini: Path | None = None) -> str | None:
    """Gözlem ekler/sayar; imzayı döndürür. ASLA hata fırlatmaz (kayıt sorunu uygulamayı bozmasın).
    kaynak verilmezse EVREN_GOZLEM_KAYNAK (gerçek API betikleri "e2e" yapar), yoksa "uygulama"."""
    if not etkin() or getattr(_IN_KAYDET, "on", False):
        return None
    _IN_KAYDET.on = True
    kaynak = kaynak or os.environ.get("EVREN_GOZLEM_KAYNAK") or "uygulama"
    try:
        if exc is not None and tb is None:
            tb = exc.__traceback__
        istisna = type(exc).__name__ if exc is not None else ""
        cerceveler = kendi_cerceveler(tb)
        temiz_mesaj = temizle(mesaj or (str(exc) if exc is not None else ""))
        temiz_baslik = temizle(baslik, 100)
        imza = imza_hesapla(tur, temiz_baslik, istisna, cerceveler, temiz_mesaj)
        k = Kuyruk(veri_dizini or gercek_veri_dizini())
        with _LOCK:
            items = k.oku()
            g = items.get(imza)
            now = _now()
            if g is None:
                g = Gozlem(imza=imza, tur=tur if tur in TURLER else "gelistirici", baslik=temiz_baslik,
                           onem=onem if onem in ONEMLER else "orta", alan=alan, kaynak=kaynak,
                           istisna=istisna, mesaj=temiz_mesaj, cerceveler=cerceveler,
                           ayrinti=_ayrinti_temizle(ayrinti), ilk=now)
                items[imza] = g
            g.sayac += 1
            g.son = now
            v = surum()
            if v not in g.surumler:
                g.surumler = (g.surumler + [v])[-5:]
            _budama(items)
            k.yaz(items)
        return imza
    except Exception:
        return None
    finally:
        _IN_KAYDET.on = False


# ---- kaynaklara göre sınıflandırma (hangi olay ne kadar önemli; neyin kaydedilMEdiği) -------------

# Kullanıcının/hesabın durumu, uygulama hatası değil: kaydedilmez (R-22: gereksiz gözlem gürültüdür)
_API_ATLA = {"kimlik_doğrulama", "kota_sınırı", "kredi_bitti"}
_API_ORTAM = {"sunucu_kullanılamıyor", "sunucu_hatası", "zaman_aşımı", "ağ_hatası", "belirsiz_sonuç"}


def api_hatasi(err: Any, islem: str = "") -> str | None:
    """ApiError → gözlem. Sunucu/ağ sorunları düşük önemli 'ortam' (3 kez görülmeden gönderilmez);
    geçersiz istek (400/422) uygulama ile API sözleşmesi bozulduğu için yüksek."""
    kind = getattr(getattr(err, "kind", None), "value", "") or ""
    if kind in _API_ATLA:
        return None
    if kind in _API_ORTAM:
        onem, alan = "dusuk", "ortam"
    elif kind in ("geçersiz_istek", "istek_çok_büyük"):
        onem, alan = "yuksek", "api"
    else:
        onem, alan = "orta", "api"
    status = getattr(err, "status", None)
    return kaydet("api_hatasi", f"API hatası: {kind or 'bilinmeyen'}" + (f" (HTTP {status})" if status else ""),
                  onem=onem, alan=alan, mesaj=getattr(err, "message", "") or "",
                  ayrinti={"model": getattr(err, "model", None), "http": status,
                           "hata_kodu": getattr(err, "code", None), "hata_turu": kind,
                           "islem": islem or getattr(err, "operation", None)})


# Koşucunun kalite olayları (runner._quality / _record): modelin hatalı davranışı ya da bekçinin devreye girmesi
_AJAN_OLAY = {"loop": ("Döngü bekçisi turu durdurdu", "orta"),
              "plan_stall": ("Plan bekçisi: plan ilerlemeden takıldı", "orta"),
              "test_break": ("Test bekçisi: değişiklikten sonra testler bozuldu", "orta"),
              "test_edit": ("Ajan istenmeden test dosyasını değiştirdi", "orta")}


def ajan_olayi(rec: dict) -> str | None:
    """AppContext.record_model_call kaydı → gözlem (yalnız anormallikler; başarılı çağrılar değil)."""
    ev = rec.get("event")
    if ev in _AJAN_OLAY:
        baslik, onem = _AJAN_OLAY[ev]
        return kaydet("ajan_anomali", baslik, onem=onem, alan="ajan",
                      ayrinti={"model": rec.get("model"), "rol": rec.get("role"), "olay": ev})
    if ev == "switch":
        return kaydet("ajan_anomali", "Auto Pro yedek modele geçti", onem="dusuk", alan="ortam",
                      ayrinti={"model": rec.get("model"), "rol": rec.get("role"), "olay": ev})
    if rec.get("empty"):
        return kaydet("ajan_anomali", "Model boş yanıt döndü", onem="dusuk", alan="ortam",
                      ayrinti={"model": rec.get("model"), "rol": rec.get("role")})
    return None


_TUR_SONU = {"max_steps": ("Tur adım sınırında bitti", "orta"),
             "context_limit": ("Tur bağlam sınırında durdu", "orta"),
             "loop": ("Tur döngü nedeniyle durdu", "orta"),
             "error": ("Tur hatayla bitti", "orta")}


def tur_sonu(stopped: str, *, model: str = "", rol: str = "", adim: int | None = None,
             mod: str = "") -> str | None:
    """Ajan turu normal dışı bittiyse (iptal ve "done" kaydedilmez)."""
    if stopped not in _TUR_SONU:
        return None
    baslik, onem = _TUR_SONU[stopped]
    return kaydet("tur_sonu", baslik, onem=onem, alan="ajan",
                  ayrinti={"durma": stopped, "model": model, "rol": rol, "adim": adim, "mod": mod})


# Kullanıcının asıl şikâyeti (kayıt 2026-10-21-ajan-cok-fazli-iste-faz-bitince-sonrakine-gecmeyi-unutuyor):
# ajan "bitti" deyip durur, kullanıcı "devam" yazmak zorunda kalır. Gerçek API'de üretilemedi (2026-11-03,
# maraton F, 3 özetle 17/17) → gerçek kullanımda olursa burada yakalanır.
_DEVAM = re.compile(r"^(?:devam(?: et| edin| ediniz| edelim)?|sürdür|kaldığın yerden devam(?: et)?|devam lütfen|"
                    r"lütfen devam(?: et)?|devam ?\.+|go on|continue)[.!\s]*$", re.IGNORECASE)


def devam_zorunlu(metin: str, onceki_durma: str, son_yanit: str, *, model: str = "", rol: str = "",
                  acik_plan: int = 0) -> str | None:
    """Kullanıcı, ajanın kendi isteğiyle ("done") bitirdiği turdan sonra yalnız "devam" yazdıysa gözlem.
    Ajan soru sorduysa / SORU: / ENGEL: dediyse kullanıcının yanıtıdır, kaydedilmez (R-22)."""
    if onceki_durma != "done" or not _DEVAM.match((metin or "").strip()):
        return None
    son = (son_yanit or "").strip()
    if not son or "SORU:" in son or "ENGEL:" in son or son.rstrip("*_` \n").endswith("?"):
        return None
    return kaydet("ajan_anomali", "Ajan turu bitirdi, kullanıcı 'devam' yazmak zorunda kaldı",
                  onem="orta", alan="ajan",
                  ayrinti={"model": model, "rol": rol, "olay": "devam_zorunlu", "acik_plan": acik_plan or None})


# Windows/Qt'nin zararsız, sık uyarıları (gözlem değeri yok)
_QT_ZARARSIZ = ("QWindowsWindow::setGeometry", "Unable to set geometry", "QFont::setPointSize",
                "propagateSizeHints", "OpenType support missing", "QSocketNotifier: Can only be used")


def qt_mesaji(seviye: str, mesaj: str) -> str | None:
    """Qt ileti işleyicisinden: uyarı (warning) ve üstü. seviye: warning | critical | fatal."""
    if any(z in (mesaj or "") for z in _QT_ZARARSIZ):
        return None
    onem = {"warning": "dusuk", "critical": "orta", "fatal": "kritik"}.get(seviye)
    if onem is None:
        return None
    return kaydet("qt_uyari", f"Qt {seviye}: {_norm_mesaj(temizle(mesaj, 80))}", onem=onem, alan="ui",
                  mesaj=mesaj)


def durum(veri_dizini: Path | None = None) -> dict[str, Any]:
    """Ayarlar kartı için: toplam, gönderilmeyi bekleyen, son gönderim, son hata."""
    k = Kuyruk(veri_dizini or gercek_veri_dizini())
    items = k.oku()
    meta = k.meta()
    return {"toplam": len(items), "bekleyen": sum(1 for g in items.values() if g.gonderilmeli()),
            "son_gonderim": meta.get("son_gonderim", ""), "son_hata": meta.get("son_hata", ""),
            "depo": depo_url() or ""}


# ---- depoya gönderim ------------------------------------------------------------------------------

def depo_url(ayar: str | None = None) -> str | None:
    """Gönderilecek depo: ayar > uygulamanın kendi kaynağının origin'i (yalnız EVREN-Model-Studio)."""
    if ayar:
        return ayar
    if not (SOURCE_ROOT / ".git").exists():
        return None
    try:
        r = subprocess.run(["git", "-C", str(SOURCE_ROOT), "remote", "get-url", "origin"], capture_output=True,
                           text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired):
        return None
    url = r.stdout.strip()
    return url if r.returncode == 0 and "evren-model-studio" in url.lower() else None


def _git(cwd: Path, *args: str, timeout: float = 60) -> tuple[int, str]:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
    try:
        r = subprocess.run(["git", "-c", "core.hooksPath=" + str(cwd / ".git" / "bos-kancalar"),
                            "-c", "core.autocrlf=false", *args], cwd=str(cwd), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, env=env,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


README = """# Gözlem kayıtları (otomatik)

Bu dal EVREN Studio'nun **gözlem ajanı** tarafından yazılır; elle düzenleme. Uygulama çalışırken görülen
hata ve anormallikler temizlenmiş olarak buraya gelir (anahtar, kullanıcı adı, dosya yolu, sohbet içeriği
yoktur). Geliştirici motoru `tools/ai_memory.py baslangic` ile açık gözlemleri görür ve kullanıcıya bildirir;
`ai_memory.py gozlem kayda-donustur <imza>` → düzeltme → `ai_memory.py gozlem kapat <imza> --kayit <id>`.

- `gozlemler/<imza>/kayit.md`: gözlemin insan için kaydı (durum: acik | cozuldu | kabul-edildi)
- `gozlemler/<imza>/olay-<makine>.json`: o makinedeki sayaç, ilk/son görülme, uygulama sürümleri
"""


def kayit_md(g: Gozlem) -> str:
    satirlar = [
        "---",
        f"id: {g.imza}",
        f"baslik: {g.baslik}",
        f"tur: {g.tur}",
        f"onem: {g.onem}",
        f"alan: {g.alan}",
        "durum: acik                # acik | cozuldu | kabul-edildi",
        f"kaynak: {g.kaynak}",
        f"ilk_gorulme: {g.ilk}",
        "cozuldu_tarih:",
        "cozum_kaydi:",
        "---",
        "",
        f"# {g.baslik}",
        "",
        "## Belirti (otomatik)",
        f"{g.tur}" + (f" · {g.istisna}" if g.istisna else "") + (f": {g.mesaj}" if g.mesaj else ""),
        "",
        "## Konum (otomatik)",
        *([f"- `{c}`" for c in g.cerceveler] or ["- (yığın izi yok)"]),
        "",
        "## Ayrıntı (otomatik)",
        *([f"- {k}: {v}" for k, v in g.ayrinti.items()] or ["- —"]),
        "",
        "## Ne yapılmalı",
        "Geliştirici motoru: kullanıcıya bildir; onaylarsa `python tools/ai_memory.py gozlem kayda-donustur "
        f"{g.imza}` ile docs/ai-memory/incidents altına kayıt aç, kök nedeni bul ve düzelt, sonra "
        f"`python tools/ai_memory.py gozlem kapat {g.imza} --kayit <kayit-id>`.",
        "",
    ]
    return "\n".join(satirlar)


def _olay_json(g: Gozlem, makine: str) -> str:
    return json.dumps({"imza": g.imza, "makine": makine, "sayac": g.sayac, "ilk": g.ilk, "son": g.son,
                       "surumler": g.surumler, "kaynak": g.kaynak}, ensure_ascii=False, indent=1) + "\n"


def _yaz_dosyalar(depo: Path, items: list[Gozlem], makine: str) -> None:
    (depo / "README.md").write_text(README, encoding="utf-8", newline="\n")
    for g in items:
        d = depo / "gozlemler" / g.imza
        d.mkdir(parents=True, exist_ok=True)
        if not (d / "kayit.md").exists():          # durum geliştirici tarafında değişir; üzerine yazılmaz
            (d / "kayit.md").write_text(kayit_md(g), encoding="utf-8", newline="\n")
        (d / f"olay-{makine}.json").write_text(_olay_json(g, makine), encoding="utf-8", newline="\n")


def _hazirla(depo: Path, url: str) -> tuple[bool, str]:
    """Ayrı klonu uzak dalın son hâline getirir; dal yoksa yetim dal açar."""
    if not (depo / ".git").exists():
        depo.mkdir(parents=True, exist_ok=True)
        for args in (("init", "-q"), ("remote", "add", "origin", url)):
            code, out = _git(depo, *args)
            if code != 0:
                return False, out
    else:
        _git(depo, "remote", "set-url", "origin", url)
    code, out = _git(depo, "fetch", "-q", "--depth", "1", "origin", BRANCH, timeout=90)
    if code == 0:
        code, out = _git(depo, "checkout", "-q", "-B", BRANCH, "FETCH_HEAD")
        if code == 0:
            code, out = _git(depo, "reset", "-q", "--hard", "FETCH_HEAD")
        return code == 0, out
    if "couldn't find remote ref" in out.lower() or "remote ref" in out.lower():
        code, out = _git(depo, "checkout", "-q", "--orphan", BRANCH)
        if code != 0 and "already exists" not in out:
            return False, out
        _git(depo, "rm", "-rq", "--cached", ".")
        return True, "yeni dal"
    return False, out


def gonder(veri_dizini: Path | None = None, url: str | None = None, deneme: int = 3) -> str:
    """Bekleyen gözlemleri depoya gönderir; kısa Türkçe sonuç döndürür. Arka plan iş parçacığında çağır."""
    if not etkin():
        return "Gözlem kapalı."
    k = Kuyruk(veri_dizini or gercek_veri_dizini())
    url = url or depo_url()
    if not url:
        return "Gönderilecek depo yok (uygulama kaynaktan çalışmıyor); gözlemler yalnız bu bilgisayarda."
    with _LOCK:
        items = k.oku()
    bekleyen = [g for g in items.values() if g.gonderilmeli()]
    if not bekleyen:
        return "Gönderilecek yeni gözlem yok."
    depo = k.dir / "depo"
    makine = makine_kimligi()
    son = ""
    for _ in range(max(1, deneme)):
        ok, son = _hazirla(depo, url)
        if not ok:
            break
        _yaz_dosyalar(depo, bekleyen, makine)
        _git(depo, "add", "-A")
        code, out = _git(depo, "diff", "--cached", "--quiet")
        if code == 0:
            son = "değişiklik yok"
        else:
            yeni = sum(1 for g in bekleyen if g.gonderilen == 0)
            code, out = _git(depo, "-c", "user.name=EVREN Studio gözlem ajanı",
                             "-c", "user.email=gozlem@evren-studio.invalid", "commit", "-q", "-m",
                             f"gözlem: {yeni} yeni, {len(bekleyen) - yeni} güncellenen ({makine})")
            if code != 0:
                son = out
                break
            code, out = _git(depo, "push", "-q", "origin", f"HEAD:{BRANCH}", timeout=120)
            if code != 0:
                son = out
                continue                      # başka makine önce gönderdi: yeniden çek, yeniden yaz
        with _LOCK:
            items = k.oku()
            for g in bekleyen:
                if g.imza in items:
                    items[g.imza].gonderilen = max(items[g.imza].gonderilen, g.sayac)
            k.yaz(items, son_gonderim=_now(), son_hata="")
        return f"{len(bekleyen)} gözlem depoya gönderildi ({BRANCH})."
    hata = temizle(son, 160) or "bilinmeyen hata"
    with _LOCK:
        k.yaz(k.oku(), son_hata=hata)
    return f"Gönderilemedi: {hata}"
