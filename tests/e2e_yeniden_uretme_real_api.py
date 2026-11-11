"""Hata düzeltmede yeniden üretme testi — gerçek API (Madde 20 B1; pytest toplamaz).

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_yeniden_uretme_real_api.py

Hatalı küçük proje (div sıfırda ZeroDivisionError ile çöküyor) + hata düzeltme isteği. Derin Mod'un iki planlayıcısı
(plan rolü zinciri) plan yazar. Beklenen: her geçerli planın 1. görevi hatayı yeniden üreten ve ŞU AN KALAN bir test
(ölçütte "kal/başarısız/fail/ZeroDivision" ve "test" geçer); düzeltme sonraki görevde.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
from gecici import klasor  # noqa: E402

os.environ["EVREN_STUDIO_DATA_DIR"] = str(klasor("evren-repro-"))

from e2e_derin_real_api import BAD_CALC, BAD_TEST  # noqa: E402

from evren_studio.agent import deep as dp  # noqa: E402
from evren_studio.agent.quota import QuotaGate  # noqa: E402
from evren_studio.ui.app_context import AppContext  # noqa: E402

GOAL = "div(1, 0) çağrısı ZeroDivisionError ile çöküyor; sıfıra bölmede ValueError fırlatmalı. Hatayı düzelt."
_FAIL = re.compile(r"kal[ıi]|başarısız|basarisiz|fail|zerodivision|hata ver|kırmızı", re.I)


def main() -> int:
    from evren_studio.secrets import load_api_key

    if not load_api_key():
        print("FAIL: EVREN API anahtarı yok")
        return 1
    ctx = AppContext()
    def quota():
        c = ctx.make_client()
        try:
            return c.get_quota()
        finally:
            c.close()
    gate = QuotaGate(quota, max_parallel=2)
    proj = klasor("repro-proje-")
    (proj / "calc.py").write_text(BAD_CALC, encoding="utf-8")
    (proj / "test_calc.py").write_text(BAD_TEST.replace("from calc import add, sub", "from calc import add, div, sub"),
                                       encoding="utf-8")

    def chain(role):
        r = ctx.ai_route(role)
        return [m for m in [r.model] + r.fallbacks if ctx.provider_of(m) == "evren"]

    def sub_for(models):
        def run(prompt, marker, label=""):
            c = ctx.make_client()
            try:
                return dp.run_subagent(client=c, model=models[0], fallbacks=models[1:], root=proj, prompt=prompt,
                                       marker=marker, gate=gate)
            finally:
                c.close()
        return run

    plan_models = chain("plan")[:2]
    subs = {m: sub_for([m] + [x for x in chain("plan") if x != m]) for m in plan_models}
    st = dp.DeepState(goal=GOAL, kind=dp.classify(GOAL))
    t0 = time.monotonic()
    dp.plan(st, lambda m, p, k: subs[m](p, k), plan_models,
            lambda msgs: ctx.ai_chat("inceleme", msgs, max_tokens=400, evren_only=True)[0], gate, 2, print)
    ok = bool(st.plans)
    for p in st.plans:
        first = p["tasks"][0] if p["tasks"] else {}
        text = f"{first.get('title', '')} {first.get('criteria', '')}"
        good = "test" in text.lower() and bool(_FAIL.search(text))
        ok &= good
        print(f"{'GEÇTİ' if good else 'KALDI'} | {p['model']}: 1. görev = {first.get('title', '')[:90]!r} — ölçüt: "
              f"{first.get('criteria', '')[:110]!r}")
    print(f"SONUÇ: {'GEÇTİ' if ok else 'KALDI'} · {len(st.plans)} plan · {time.monotonic() - t0:.0f} sn")
    ctx.close()                                   # veritabanı kapansın: geçici klasör silinebilsin
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
