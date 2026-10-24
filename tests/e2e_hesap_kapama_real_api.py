"""Hesap kapama raporu — gerçek iş süreci ölçümü (EVREN anahtarı gerekir; pytest toplamaz).

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_hesap_kapama_real_api.py [model] [--dakika 10] [--skill <klasör>]
    .\\.venv\\Scripts\\python.exe -u tests\\e2e_hesap_kapama_real_api.py --betik [--dakika 15]
    ... [--f3-kapali]   F3 verimlilik özellikleri KAPALI (proje haritası, Python paket bilgisi, read_table) —
                        R-25 açık/kapalı karşılaştırması için

--betik: ajan raporu doğrudan üretmek yerine TEKRAR ÇALIŞTIRILABİLİR `rapor_uret.py` yazar (skill + düzeltme
önerileri). Betik sonra ajansız sınanır: (a) aynı veri, (b) aynı veri ikinci kez → çıktı birebir aynı mı,
(c) 96 işlik, sütun ve satır sırası karışık ikinci veri seti. Her çıktı denetçiden geçer.

1. `tests/hesap_kapama/hk_veri.py` ile SAHTE ama gerçek yapıda 6 dosya + kullanıcı sözlüğü üretilir
   (her SKILL kuralı için tuzak satırı; beklenen sonuç kurallardan hesaplanır).
2. Kullanıcının skill klasörü (SKILL.md + references) kopyalanır; uygulamanın ajanı (Otomatik mod, plan
   bekçisi + hata bekçisi açık) raporu üretir. Süre sınırında tur iptal edilir.
3. Çıktı Excel'i hücre hücre denetlenir (denetçi R-25 ile bilinen doğru/yanlış raporla sınandı).
Çıktılar `build/hk/kosu-…/` altında: döküm (transcript.md), denetim.json, ölçüm.json.
openpyxl proje venv'inde yok: veri ve denetim sistem Python'uyla (openpyxl'li) çalıştırılır.
"""
from __future__ import annotations

import json
import shutil
from collections import Counter
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evren_studio.agent.deep import MemoryStore, transcript_of  # noqa: E402
from evren_studio.agent.runner import AgentEvents, AgentRunner  # noqa: E402
from evren_studio.agent.tools import Workspace  # noqa: E402
from evren_studio.api.client import CancelToken  # noqa: E402
from evren_studio.ui.app_context import AppContext  # noqa: E402

VERI = ROOT / "tests" / "hesap_kapama" / "hk_veri.py"
ONERILER = ROOT / "tests" / "hesap_kapama" / "SKILL_DUZELTME_ONERILERI.md"
SKILL_VARSAYILAN = Path(r"C:\Users\Osman Alpaslan\OneDrive - Uyumsoft\Masaüstü\Hesap kapama Raporları\Yeni"
                        r"\hesap-kapama-raporu")
ISTEM = """hesap-kapama-raporu klasöründeki skill'i (SKILL.md ve references) uygula: bu klasördeki kaynak dosyalardan
Hesap Kapama Raporu'nu Excel olarak üret ve "Hesap Kapama Raporu.xlsx" adıyla bu klasöre kaydet.

- Kullanıcı sözlüğü bu klasörde: kullanici_listesi.tsv. CRS aktivasyon ve sayaç tipleri dosyaları da burada.
- Sütun başlıkları standart; eşlemeyi içerikten kendin doğrula. Sütun eşlemesi için ONAYIM VAR: sormadan
  devam et, eşlemeyi ve varsayımlarını sonunda özetle.
- Süre sınırı {dakika} dakika; gereksiz keşif yapma.
- Kullanıcının açık Excel dosyaları olabilir: `Stop-Process -Name EXCEL` veya `Get-Process EXCEL | Stop-Process`
  KULLANMA; yalnız kendi açtığın Excel nesnesini Quit et ve COM nesnesini serbest bırak.
- Bitince skill'in §7'sindeki özeti ver (sayılar, dağılımlar, kapanması gereken, kapsam dışı, varsayımlar)."""

ISTEM_BETIK = """Bu klasördeki hesap-kapama-raporu skill'ini (SKILL.md ve references) ve KURAL_NETLESTIRMELERI.md'deki
netleştirmeleri uygulayan, HER AY TEKRAR ÇALIŞTIRILABİLİR bir Python betiği yaz: rapor_uret.py

Kullanım: python rapor_uret.py <kaynak_klasör> <çıktı.xlsx>
- Yalnız standart kütüphane + openpyxl kullan (bu bilgisayarda Python 3.12 ve openpyxl var).
- Kaynak dosyaları klasörde ADINDAN değil içerik/başlıktan bul; sütunları BAŞLIK ADIYLA bul (büyük/küçük harf,
  ı/i, boşluk ve Türkçe karakter farklarını tolere et). Sütun SIRASI her ay değişebilir: sütun numarasıyla
  eşleme YAPMA. Zorunlu bir sütun bulunamazsa ne eksik olduğunu yazıp çıkış kodu 2 ile dur; tahmin etme.
- Kuralları SKILL.md ve KURAL_NETLESTIRMELERI.md'den uygula. Betiğe veriye özel sabit değer (İş ID, fırsat kodu,
  satır sayısı vb.) YAZMA; kullanıcı sözlüğü kaynak klasördeki kullanici_listesi.tsv'den okunur.
- §5 doğrulamalarını betiğin içinde yap; tutmazsa dosyayı yazma, nedenini yazdırıp çıkış kodu 3 ile dur.
- Ham kaynak dosyalara ve skill klasörüne YAZMA. Geçici dosya bırakma.
- Sonra betiği bu klasördeki veriyle çalıştır, "Hesap Kapama Raporu.xlsx" üret ve özetini ver.
Süre sınırı {dakika} dakika."""

def sistem_python() -> str:
    for cand in ([sys.executable], ["py", "-3.12"], ["py", "-3"],
                 [r"C:\Users\Osman Alpaslan\AppData\Local\Programs\Python\Python312\python.exe"]):
        try:
            r = subprocess.run(cand + ["-c", "import openpyxl"], capture_output=True, timeout=30)
            if r.returncode == 0:
                return " ".join(cand) if len(cand) > 1 else cand[0]
        except (OSError, subprocess.TimeoutExpired):
            continue
    raise SystemExit("openpyxl'li Python bulunamadı (veri üretimi ve denetim için gerekli)")


def excel_pids() -> set[int]:
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq EXCEL.EXE", "/FO", "CSV", "/NH"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    out = set()
    for line in r.stdout.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) > 1 and parts[1].isdigit():
            out.add(int(parts[1]))
    return out


class Olay(AgentEvents):
    def __init__(self):
        self.araclar: list[str] = []
        self.hatalar: list[str] = []
        self.notlar: list[str] = []

    def tool_finished(self, call, result):
        self.araclar.append(call.name)
        if not result.ok:
            self.hatalar.append(f"{call.name}: {str(result.content)[:160]}")
        print(f"   · {call.name}{'' if result.ok else ' ✗'}", flush=True)

    def status(self, text):
        self.notlar.append(text)
        print(f"   [not] {text[:160]}", flush=True)

    def approval_needed(self, request):
        request.resolve(request.ALLOW)


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = sys.argv[1:]
    dakika = 10.0
    if "--dakika" in args:
        i = args.index("--dakika")
        dakika = float(args[i + 1])
        del args[i:i + 2]
    f3_kapali = "--f3-kapali" in args
    if f3_kapali:
        args.remove("--f3-kapali")
        from evren_studio.agent import environment

        environment.python_packages = lambda *a, **k: {}
    betik = "--betik" in args
    if betik:
        args.remove("--betik")
        if "--dakika" not in sys.argv:
            dakika = 15.0
    skill = SKILL_VARSAYILAN
    if "--skill" in args:
        i = args.index("--skill")
        skill = Path(args[i + 1])
        del args[i:i + 2]
    ctx = AppContext()
    if not ctx.has_api_key():
        print("EVREN anahtarı yok")
        return 2
    r = ctx.ai_route("kod")
    chain = [m for m in [r.model] + r.fallbacks if ctx.provider_of(m) == "evren"]
    model = args[0] if args else chain[0]
    fallbacks = [m for m in chain if m != model]
    py = sistem_python()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    kosu = ROOT / "build" / "hk" / f"{'betik' if betik else 'kosu'}-{model}{'-f3kapali' if f3_kapali else ''}-{stamp}"
    kosu.mkdir(parents=True)
    subprocess.run(py.split(" ") + [str(VERI), "uret", str(kosu)], check=True, capture_output=True)
    shutil.copytree(skill, kosu / "hesap-kapama-raporu")
    if betik:
        shutil.copy(ONERILER, kosu / "KURAL_NETLESTIRMELERI.md")
    print(f"Klasör: {kosu}\nModel: {model} (yedek {fallbacks}) · sınır {dakika:g} dk", flush=True)

    store = MemoryStore()
    history = [{"id": 0, "role": "user", "content": (ISTEM_BETIK if betik else ISTEM).format(dakika=int(dakika))}]
    store.messages.append(history[0])
    olay = Olay()
    cancel = CancelToken()
    zamanlayici = threading.Timer(dakika * 60, cancel.cancel)
    client = ctx.make_client()
    info = ctx.model_info(model)
    runner = AgentRunner(client, model, session_id=0, store=store, events=olay, workspace=Workspace(kosu),
                         mode="auto", stream=True, cancel=cancel, max_steps=150, fallback_models=fallbacks,
                         context_tokens=getattr(info, "context_length", None), plan_guard=True,
                         command_timeout=600, project_map=not f3_kapali)
    if f3_kapali:
        _specs = runner._specs
        runner._specs = lambda: [sp for sp in _specs() if sp.name not in ("read_table", "web_fetch")]
    excel_once = excel_pids()
    t0 = time.monotonic()
    zamanlayici.start()
    try:
        out = runner.run(history)
    finally:
        zamanlayici.cancel()
        client.close()
    sure = time.monotonic() - t0
    excel_sonra = excel_pids()
    (kosu / "transcript.md").write_text(transcript_of(history, limit=4000), encoding="utf-8")
    hedef = kosu / "Hesap Kapama Raporu.xlsx"
    yanlis_yer = None
    if not hedef.is_file():
        adaylar = [p for p in kosu.glob("*.xlsx") if "rapor" in p.name.lower()]
        # 2026-10-24: ajan raporu skill alt klasörüne kaydetti; düzenek yalnız kökte arıyordu → "çıktı yok"
        # sanıldı. Alt klasördeki rapor da denetlenir ama "yanlış yerde" olarak işaretlenir.
        alt = [p for p in kosu.rglob("*.xlsx") if "rapor" in p.name.lower() and p.parent != kosu]
        hedef = adaylar[0] if adaylar else (alt[0] if alt else hedef)
        if not adaylar and alt:
            yanlis_yer = str(alt[0].relative_to(kosu))
    d = subprocess.run(py.split(" ") + [str(VERI), "denetle", str(kosu), str(hedef)], capture_output=True,
                       text=True, encoding="utf-8")
    try:
        denetim = json.loads(d.stdout)
    except json.JSONDecodeError:
        denetim = {"hatalar": [f"denetçi çalışmadı: {d.stderr[-400:]}"], "gecen": [], "puan": "?"}
    son = next((m.get("content") for m in reversed(history) if m.get("role") == "assistant"
                and (m.get("content") or "").strip()), "")
    olcum = {"model": model, "kullanilan_model": runner.model, "sure_sn": round(sure), "durma": out.stopped,
             "adim": out.steps, "arac": len(olay.araclar), "hatali_arac": len(olay.hatalar),
             "excel_oldurulen": sorted(excel_once - excel_sonra), "excel_kalan": sorted(excel_sonra - excel_once),
             "cikti": hedef.name if hedef.is_file() else None, "puan": denetim.get("puan"),
             "f3": not f3_kapali, "yanlis_yer": yanlis_yer, "arac_sayim": dict(sorted(Counter(olay.araclar).items(), key=lambda kv: -kv[1]))}
    (kosu / "denetim.json").write_text(json.dumps(denetim, ensure_ascii=False, indent=1), encoding="utf-8")
    (kosu / "olcum.json").write_text(json.dumps(olcum, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n=== ÖLÇÜM", json.dumps(olcum, ensure_ascii=False), flush=True)
    print("=== DENETİM", denetim.get("puan"), flush=True)
    for h in denetim.get("hatalar", []):
        print("   ✗", h[:300], flush=True)
    for h in olay.hatalar[:12]:
        print("   araç hatası:", h[:200], flush=True)
    print("=== AJANIN SON ÖZETİ\n" + (son or "(yok)")[:3000], flush=True)
    if betik:
        betik_sina(py, kosu, olcum)
    return 0


def _degerler(py: str, xlsx: Path) -> str:
    kod = ("import sys,openpyxl;wb=openpyxl.load_workbook(sys.argv[1],data_only=True);"
           "print(repr([[ [c for c in r] for r in ws.iter_rows(values_only=True)] for ws in wb]))")
    r = subprocess.run(py.split(" ") + ["-c", kod, str(xlsx)], capture_output=True, text=True, encoding="utf-8")
    return r.stdout


def betik_sina(py: str, kosu: Path, olcum: dict) -> None:
    """Ajanın yazdığı rapor_uret.py'yi AJANSIZ sınar: tekrar, tekrarlanabilirlik, ikinci veri seti."""
    script = kosu / "rapor_uret.py"
    sonuc: dict = {"betik": script.is_file()}
    if not script.is_file():
        print("=== BETİK YOK", flush=True)
        (kosu / "betik_sinama.json").write_text(json.dumps(sonuc, ensure_ascii=False), encoding="utf-8")
        return
    sinama = kosu / "sinama"
    for ad, varyant in (("veri1", 1), ("veri2", 2)):
        subprocess.run(py.split(" ") + [str(VERI), "uret", str(sinama / ad), str(varyant)], check=True,
                       capture_output=True)
    satirlar = []
    for etiket, klasor, cikti in (("A: aynı veri", "veri1", "a.xlsx"), ("B: aynı veri tekrar", "veri1", "b.xlsx"),
                                  ("C: 96 iş, karışık sütun/satır", "veri2", "c.xlsx")):
        t0 = time.monotonic()
        r = subprocess.run(py.split(" ") + [str(script), str(sinama / klasor), str(sinama / cikti)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        sure = time.monotonic() - t0
        d = subprocess.run(py.split(" ") + [str(VERI), "denetle", str(sinama / klasor), str(sinama / cikti)],
                           capture_output=True, text=True, encoding="utf-8")
        try:
            den = json.loads(d.stdout)
        except json.JSONDecodeError:
            den = {"puan": "?", "hatalar": [d.stderr[-300:]]}
        satirlar.append({"durum": etiket, "cikis": r.returncode, "sure_sn": round(sure, 1), "puan": den.get("puan"),
                         "hatalar": den.get("hatalar", []), "cikti_sonu": (r.stdout + r.stderr)[-600:]})
        print(f"=== BETİK {etiket}: çıkış {r.returncode} · {sure:.1f} sn · denetim {den.get('puan')}", flush=True)
        for h in den.get("hatalar", []):
            print("   ✗", h[:240], flush=True)
        if r.returncode != 0:
            print("   betik çıktısı:", (r.stdout + r.stderr)[-400:], flush=True)
    a, b = sinama / "a.xlsx", sinama / "b.xlsx"
    ayni = a.is_file() and b.is_file() and _degerler(py, a) == _degerler(py, b)
    print(f"=== BETİK tekrarlanabilir (A ve B hücre değerleri aynı): {ayni}", flush=True)
    sonuc.update({"sinamalar": satirlar, "tekrarlanabilir": ayni, "ajan": olcum})
    (kosu / "betik_sinama.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
