"""Derin Mod gerçek API ölçümü (EVREN anahtarı gerekir; pytest toplamaz).

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_derin_real_api.py

Ölçülen (uygulama fazı Proje ajanıdır, o ayrıca tests\\e2e_proje_real_api.py ile ölçülür):
1. ANLA: paralel salt okunur alt ajanlar <bulgu> bloğu veriyor mu, süre, kota kapısı.
2. PLANLA: iki farklı EVREN modeli geçerli <plan> veriyor mu; yargıç (ai_chat, yalnız EVREN) seçiyor mu.
3. DOĞRULA (R-25 kabul denetimi sınaması): BİLİNEN YANLIŞ bir değişiklikte (bölme sıfır kontrolü
   yok, istenen hata fırlatılmıyor) onaylanmış sorun bulunmalı; BİLİNEN DOĞRU değişiklikte
   "yüksek" sorun çıkmamalı.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evren_studio.agent import deep as dp  # noqa: E402
from evren_studio.agent.quota import QuotaGate  # noqa: E402
from evren_studio.ui.app_context import AppContext  # noqa: E402

GOAL = "calc.py'ye div(a, b) fonksiyonu ekle: b sıfırsa ValueError fırlatsın; test_calc.py'ye testini yaz."

BASE_CALC = '"""Basit hesap makinesi."""\n\n\ndef add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n'
BASE_TEST = ("import unittest\n\nfrom calc import add, sub\n\n\nclass T(unittest.TestCase):\n"
             "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n\n"
             "    def test_sub(self):\n        self.assertEqual(sub(5, 3), 2)\n")

BAD_DIFF = """--- a/calc.py
+++ b/calc.py
@@ -9,0 +10,4 @@
+
+
+def div(a, b):
+    return a / b
--- a/test_calc.py
+++ b/test_calc.py
@@ -11,0 +12,3 @@
+
+    def test_div(self):
+        self.assertEqual(div(6, 3), 2)
"""

GOOD_DIFF = """--- a/calc.py
+++ b/calc.py
@@ -9,0 +10,7 @@
+
+
+def div(a, b):
+    if b == 0:
+        raise ValueError("b sıfır olamaz")
+    return a / b
--- a/test_calc.py
+++ b/test_calc.py
@@ -1,3 +1,3 @@
-from calc import add, sub
+from calc import add, div, sub
@@ -11,0 +12,6 @@
+
+    def test_div(self):
+        self.assertEqual(div(6, 3), 2)
+
+    def test_div_zero(self):
+        self.assertRaises(ValueError, div, 1, 0)
"""


def main() -> int:
    ctx = AppContext()
    if not ctx.has_api_key():
        print("EVREN anahtarı yok")
        return 2

    def quota():
        c = ctx.make_client()
        try:
            return c.get_quota()
        finally:
            c.close()
    gate = QuotaGate(quota, max_parallel=2)
    tmp = Path(tempfile.mkdtemp(prefix="derin_"))
    (tmp / "calc.py").write_text(BASE_CALC, encoding="utf-8")
    (tmp / "test_calc.py").write_text(BASE_TEST, encoding="utf-8")

    def chain(role):
        r = ctx.ai_route(role)
        return [m for m in [r.model] + r.fallbacks if ctx.provider_of(m) == "evren"]

    def sub_for(model_chain):
        def run(prompt, marker):
            c = ctx.make_client()
            try:
                return dp.run_subagent(client=c, model=model_chain[0], fallbacks=model_chain[1:], root=tmp,
                                       prompt=prompt, marker=marker, gate=gate)
            finally:
                c.close()
        return run
    ok = True
    try:
        st = dp.DeepState(goal=GOAL, kind=dp.classify(GOAL))
        t0 = time.monotonic()
        dp.understand(st, sub_for(chain("kod")), gate, 2, lambda t: print("  ", t, flush=True))
        got = [f["angle"] for f in st.findings if f.get("data")]
        print(f"1 ANLA: {len(got)}/{len(st.findings)} bulgu ({', '.join(got)}) · {time.monotonic() - t0:.0f} sn "
              f"· durum: {[f['stopped'] for f in st.findings]}", flush=True)
        ok &= len(got) >= 2

        t0 = time.monotonic()
        plan_models = chain("plan")[:2]
        subs = {m: sub_for([m] + [x for x in chain("plan") if x != m]) for m in plan_models}

        def judge(messages):
            text, model = ctx.ai_chat("inceleme", messages, max_tokens=600, evren_only=True)
            print("   yargıç:", model, text[:160].replace("\n", " "), flush=True)
            return text
        tasks = dp.plan(st, lambda m, p, k: subs[m](p, k), plan_models, judge, gate, 2,
                        lambda t: print("  ", t, flush=True))
        print(f"2 PLANLA: modeller {plan_models}; geçerli plan {len(st.plans)}; seçilen {st.chosen} "
              f"({len(tasks)} görev) · {time.monotonic() - t0:.0f} sn", flush=True)
        for t in tasks:
            print(f"     {t.idx}. {t.title} — {t.criteria[:90]}", flush=True)
        ok &= len(st.plans) >= 1 and len(tasks) >= 1

        verifier = [sub_for(chain("inceleme")), sub_for(chain("kod"))]
        n = {"i": 0}

        def vsub(prompt, marker):
            n["i"] += 1
            return verifier[n["i"] % 2](prompt, marker)
        for name, diff, expect_issue in (("YANLIŞ", BAD_DIFF, True), ("DOĞRU", GOOD_DIFF, False)):
            t0 = time.monotonic()
            vst = dp.DeepState(goal=GOAL)
            issues = dp.verify(vst, diff, vsub, gate, 2, lambda t: None)
            high = [i for i in issues if str(i.get("ciddiyet", "")).lower().startswith(("yuk", "yük"))]
            passed = bool(issues) if expect_issue else not high
            ok &= passed
            print(f"3 DOĞRULA ({name} değişiklik): {len(issues)} onaylı sorun, {len(high)} yüksek → "
                  f"{'BEKLENEN' if passed else 'BEKLENMEYEN'} · {time.monotonic() - t0:.0f} sn", flush=True)
            for i in issues[:4]:
                print(f"     [{i.get('ciddiyet')}] {i.get('dosya')}: {str(i.get('aciklama'))[:120]}", flush=True)
        q = gate.snapshot(fresh=True)
        print(f"Kota: pencere %{int((getattr(q, 'usage_ratio', 0) or 0) * 100)}, "
              f"günlük kalan {getattr(q, 'daily_remaining_tokens', '?')}", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("SONUÇ:", "GEÇTİ" if ok else "KALDI")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
