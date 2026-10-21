"""Plan bekçisi gerçek API ölçümü: açık/kapalı karşılaştırma ve yanlış tetiklenme (R-22, R-25).

pytest tarafından toplanmaz. Çalıştırma (EVREN anahtarı gerekir):
    .\\.venv\\Scripts\\python.exe -u tests\\e2e_plan_bekcisi_real_api.py [model ...]

Senaryo A (çok fazlı): ajan fazları PLAN.md'ye yazar ve sırayla yürütür. Ölçülen: tur sonunda
PLAN.md'de açık kalan madde, bekçinin dürtme sayısı, fazların gerçek çıktısı (calc.py işlevleri,
testlerin geçmesi), adım ve süre — bekçi AÇIK ve KAPALI.
Senaryo B (yanlış tetiklenme): klasörde ESKİ bir TODO.md (açık maddeli) varken kısa bir soru sorulur;
bekçi dürtmemeli (eski dosya bu turun planı değildir).
Sonuç docs/knowledge/CHALLENGE_RESULTS.md'ye elle işlenir.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evren_studio.agent import planguard  # noqa: E402
from evren_studio.agent.deep import MemoryStore  # noqa: E402
from evren_studio.agent.runner import AgentEvents, AgentRunner  # noqa: E402
from evren_studio.agent.tools import Workspace  # noqa: E402
from evren_studio.api.client import EvrenClient  # noqa: E402
from evren_studio.config import DEFAULT_BASE_URL  # noqa: E402
from evren_studio.secrets import load_api_key  # noqa: E402

MODELS = ["deepseek-v4-flash", "qwen3.8-flash-next"]

TASK_A = """Bu işi fazlara bölerek yürüt. Önce PLAN.md dosyasına fazları `- [ ] Faz N: ...` biçiminde yaz,
her fazı bitirince o satırı `- [x]` yap ve SORMADAN sıradaki faza geç.
Faz 1: calc.py içinde add(a, b) fonksiyonu yaz.
Faz 2: calc.py içine sub(a, b) ve mul(a, b) fonksiyonlarını ekle.
Faz 3: test_calc.py dosyasına unittest ile add, sub ve mul için testler yaz ve `python -m unittest` ile çalıştır.
Faz 4: README.md dosyasına kullanım örneği yaz.
Faz 5: calc.py içine div(a, b) ekle; b == 0 ise ValueError fırlatsın; testini de ekleyip testleri yeniden çalıştır."""

TASK_B = "calc.py içindeki add fonksiyonu ne döndürür? Kısaca yanıtla."

# Senaryo C (kullanıcının anlattığı durum): plan dosyasını KULLANICI yazmış, fazlar büyük; model sık sık
# bir fazı bitirip "devam edeyim mi?" diye turu kapatır.
PLAN_C = """# Envanter uygulaması planı

- [ ] Faz 1: `envanter/model.py` — Urun dataclass'ı (ad, adet, fiyat) ve doğrulama (adet >= 0, fiyat > 0; aksi ValueError)
- [ ] Faz 2: `envanter/depo.py` — Depo sınıfı: ekle, cikar (stok yetmezse ValueError), toplam_deger, ara(ad_parcasi)
- [ ] Faz 3: `envanter/kayit.py` — Depo'yu JSON dosyasına kaydet/yükle (UTF-8, Türkçe karakter korunur)
- [ ] Faz 4: `envanter/rapor.py` — düşük stok raporu (eşik parametreli) ve fiyata göre sıralı liste
- [ ] Faz 5: `tests/` — her modül için unittest testleri; `python -m unittest discover -s tests` geçmeli
- [ ] Faz 6: `cli.py` — argparse ile ekle/cikar/rapor komutları; README.md'ye kullanım
"""
TASK_C = ("PLAN.md'deki fazları sırayla uygula. Her fazı bitirince PLAN.md'de o satırı [x] yap. "
          "Bu çok uzun bir iş, dikkatli ol.")


class Log(AgentEvents):
    def __init__(self):
        self.statuses: list[str] = []
        self.tools: list[str] = []

    def status(self, text):
        self.statuses.append(text)

    def tool_finished(self, call, result):
        self.tools.append(call.name)

    def approval_needed(self, request):
        request.resolve(request.ALLOW)


def run(client, model: str, root: Path, task: str, guard: bool) -> dict:
    store = MemoryStore()
    history = [{"id": 0, "role": "user", "content": task}]
    ev = Log()
    runner = AgentRunner(client, model, session_id=0, store=store, events=ev, workspace=Workspace(root),
                         mode="auto", stream=True, max_steps=60, plan_guard=guard, edit_check=False)
    t0 = time.monotonic()
    out = runner.run(history)
    return {"stopped": out.stopped, "steps": out.steps, "sec": round(time.monotonic() - t0),
            "nudges": sum(1 for s in ev.statuses if s.startswith("Plan bekçisi: planda") and "açık madde var" in s),
            "open_left": list(out.open_plan_items), "tools": len(ev.tools)}


def check_a(root: Path) -> dict:
    plan = (root / "PLAN.md").read_text(encoding="utf-8") if (root / "PLAN.md").is_file() else ""
    calc = (root / "calc.py").read_text(encoding="utf-8") if (root / "calc.py").is_file() else ""
    tests_ok = None
    if (root / "test_calc.py").is_file():
        r = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=root, capture_output=True, text=True,
                           timeout=120)
        tests_ok = r.returncode == 0
    return {"plan_open": len(planguard.open_items_in_text(plan)),
            "funcs": [f for f in ("add", "sub", "mul", "div") if f"def {f}(" in calc],
            "readme": (root / "README.md").is_file(), "tests_ok": tests_ok}


def main() -> int:
    key = load_api_key()
    if not key:
        print("EVREN anahtarı yok")
        return 2
    only_c = "--c" in sys.argv
    models = [a for a in sys.argv[1:] if not a.startswith("--")] or MODELS
    client = EvrenClient(DEFAULT_BASE_URL, key, timeout=300.0, max_retries=2)
    try:
        for model in models if only_c else []:
            for guard in (True, False):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    (root / "PLAN.md").write_text(PLAN_C, encoding="utf-8")
                    r = run(client, model, root, TASK_C, guard)
                    plan = (root / "PLAN.md").read_text(encoding="utf-8")
                    mods = [m for m in ("model", "depo", "kayit", "rapor") if (root / "envanter" / f"{m}.py").is_file()]
                    tests_ok = None
                    if (root / "tests").is_dir():
                        p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=root,
                                           capture_output=True, text=True, timeout=180)
                        tests_ok = p.returncode == 0
                    r.update({"plan_open": len(planguard.open_items_in_text(plan)), "modules": mods,
                              "cli": (root / "cli.py").is_file(), "tests_ok": tests_ok})
                    print(f"C {model} bekçi={'açık' if guard else 'kapalı'}: {r}", flush=True)
        for model in [] if only_c else models:
            for guard in (True, False):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    r = run(client, model, root, TASK_A, guard)
                    r.update(check_a(root))
                    print(f"A {model} bekçi={'açık' if guard else 'kapalı'}: {r}", flush=True)
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
                (root / "TODO.md").write_text("# Eski yapılacaklar\n- [ ] Faz 1: eski iş\n- [ ] Faz 2: eski iş\n",
                                              encoding="utf-8")
                r = run(client, model, root, TASK_B, True)
                print(f"B {model} (eski TODO, soru) bekçi açık: {r}", flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
