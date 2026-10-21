"""Hesap kapama raporu — gerçek iş süreci ölçümü (EVREN anahtarı gerekir; pytest toplamaz).

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_hesap_kapama_real_api.py [model] [--dakika 10] [--skill <klasör>]

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
    kosu = ROOT / "build" / "hk" / f"kosu-{model}-{stamp}"
    kosu.mkdir(parents=True)
    subprocess.run(py.split(" ") + [str(VERI), "uret", str(kosu)], check=True, capture_output=True)
    shutil.copytree(skill, kosu / "hesap-kapama-raporu")
    print(f"Klasör: {kosu}\nModel: {model} (yedek {fallbacks}) · sınır {dakika:g} dk", flush=True)

    store = MemoryStore()
    history = [{"id": 0, "role": "user", "content": ISTEM.format(dakika=int(dakika))}]
    store.messages.append(history[0])
    olay = Olay()
    cancel = CancelToken()
    zamanlayici = threading.Timer(dakika * 60, cancel.cancel)
    client = ctx.make_client()
    info = ctx.model_info(model)
    runner = AgentRunner(client, model, session_id=0, store=store, events=olay, workspace=Workspace(kosu),
                         mode="auto", stream=True, cancel=cancel, max_steps=150, fallback_models=fallbacks,
                         context_tokens=getattr(info, "context_length", None), plan_guard=True,
                         command_timeout=600)
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
    if not hedef.is_file():
        adaylar = [p for p in kosu.glob("*.xlsx") if "rapor" in p.name.lower()]
        hedef = adaylar[0] if adaylar else hedef
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
             "cikti": hedef.name if hedef.is_file() else None, "puan": denetim.get("puan")}
    (kosu / "denetim.json").write_text(json.dumps(denetim, ensure_ascii=False, indent=1), encoding="utf-8")
    (kosu / "olcum.json").write_text(json.dumps(olcum, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n=== ÖLÇÜM", json.dumps(olcum, ensure_ascii=False), flush=True)
    print("=== DENETİM", denetim.get("puan"), flush=True)
    for h in denetim.get("hatalar", []):
        print("   ✗", h[:300], flush=True)
    for h in olay.hatalar[:12]:
        print("   araç hatası:", h[:200], flush=True)
    print("=== AJANIN SON ÖZETİ\n" + (son or "(yok)")[:3000], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
