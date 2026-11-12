"""Derin Mod gerçek API ölçümü (EVREN anahtarı gerekir; pytest toplamaz).

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_derin_real_api.py

Ölçülen (uygulama fazı Proje ajanıdır, o ayrıca tests\\e2e_proje_real_api.py ile ölçülür):
1. ANLA: paralel salt okunur alt ajanlar <bulgu> bloğu veriyor mu, süre, kota kapısı.
2. PLANLA: iki farklı EVREN modeli geçerli <plan> veriyor mu; yargıç (ai_chat, yalnız EVREN) seçiyor mu.
3. DOĞRULA (R-25 kabul denetimi sınaması): BİLİNEN YANLIŞ bir değişiklikte (bölme sıfır kontrolü
   yok, istenen hata fırlatılmıyor) onaylanmış sorun bulunmalı; BİLİNEN DOĞRU değişiklikte
   "yüksek" sorun çıkmamalı.

2026-11-12 (uygulamayla aynı): alt ajanlar proje haritasını alır; doğrulamadan önce testler GERÇEKTEN çalışır.
A/B bayrakları: --haritasiz (eski: harita yok) · --testsiz (eski: test kanıtı yok) · --yalniz-anla (yalnız 1. aşama).
Her alt ajanın araç çağrısı sayısı ve süresi yazdırılır (EVREN hızından bağımsız karşılaştırma ölçüsü).
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

BAD_CALC = BASE_CALC + "\n\ndef div(a, b):\n    return a / b\n"
BAD_TEST = BASE_TEST + "\n    def test_div(self):\n        self.assertEqual(div(6, 3), 2)\n"
GOOD_CALC = BASE_CALC + ('\n\ndef div(a, b):\n    if b == 0:\n        raise ValueError("b sıfır olamaz")\n'
                         "    return a / b\n")
GOOD_TEST = (BASE_TEST.replace("from calc import add, sub", "from calc import add, div, sub")
             + "\n    def test_div(self):\n        self.assertEqual(div(6, 3), 2)\n"
             + "\n    def test_div_zero(self):\n        self.assertRaises(ValueError, div, 1, 0)\n")

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
    # --paralel N (varsayılan: ayarın varsayılanı; 2026-11-07'den beri 3) — önce/sonra karşılaştırması için
    from evren_studio.config import Settings

    par = int(sys.argv[sys.argv.index("--paralel") + 1]) if "--paralel" in sys.argv else Settings().deep_parallel
    print(f"paralellik: {par}")
    gate = QuotaGate(quota, max_parallel=par)
    tmp = Path(tempfile.mkdtemp(prefix="derin_"))
    (tmp / "calc.py").write_text(BASE_CALC, encoding="utf-8")
    (tmp / "test_calc.py").write_text(BASE_TEST, encoding="utf-8")

    def chain(role):
        r = ctx.ai_route(role)
        return [m for m in [r.model] + r.fallbacks if ctx.provider_of(m) == "evren"]

    harita = "--haritasiz" not in sys.argv
    adimlar: list[tuple[str, int, float]] = []          # (etiket, araç çağrısı, süre sn)
    print(f"proje haritası: {'AÇIK' if harita else 'KAPALI'} · test kanıtı: "
          f"{'KAPALI' if '--testsiz' in sys.argv else 'AÇIK'}", flush=True)

    def sub_for(model_chain):
        def run(prompt, marker, label=""):
            c = ctx.make_client()
            try:
                res = dp.run_subagent(client=c, model=model_chain[0], fallbacks=model_chain[1:], root=tmp,
                                      prompt=prompt, marker=marker, gate=gate, runner_kw={"project_map": harita})
                adimlar.append((label or marker, int(res.tools or 0), float(res.seconds or 0.0)))
                return res
            finally:
                c.close()
        return run
    ok = True
    try:
        st = dp.DeepState(goal=GOAL, kind=dp.classify(GOAL))
        t0 = time.monotonic()
        dp.understand(st, sub_for(chain("kod")), gate, gate.max_parallel, lambda t: print("  ", t, flush=True))
        got = [f["angle"] for f in st.findings if f.get("data")]
        print(f"1 ANLA: {len(got)}/{len(st.findings)} bulgu ({', '.join(got)}) · {time.monotonic() - t0:.0f} sn "
              f"· durum: {[f['stopped'] for f in st.findings]}", flush=True)
        anla = [a for a in adimlar if a[0].startswith("anla")]
        print(f"   araç çağrısı: {[a[1] for a in anla]} (toplam {sum(a[1] for a in anla)}) · alt ajan süreleri "
              f"{[round(a[2]) for a in anla]} sn", flush=True)
        print(f"   net istekte sorular ({len(st.questions)}): {st.questions}", flush=True)
        if "--yalniz-anla" in sys.argv:
            print("SONUÇ:", "GEÇTİ" if (ok and len(got) >= 2) else "KALDI")
            return 0 if (ok and len(got) >= 2) else 1
        ok &= len(st.questions) == 0                     # R-22: net istekte soru kartı çıkmamalı
        ok &= len(got) >= 2

        # Belirsiz istek + eksik veri: soru ÇIKMALI (2026-10-21 hesap kapama oturumu)
        amb = Path(tempfile.mkdtemp(prefix="derin_soru_"))
        try:
            (amb / "musteriler.csv").write_text("id;ad;sehir\n1;Ayşe;İzmir\n2;Mehmet;Ankara\n", encoding="utf-8")
            (amb / "RAPOR_KURALLARI.md").write_text(
                "# Aylık satış raporu\n\n- Kaynak: satislar.xlsx (müşteri id, tutar, tarih) ve musteriler.csv\n"
                "- Bölge eşlemesi bolgeler.tsv dosyasından yapılır (şehir → bölge)\n"
                "- Çıktı: Excel, sayfa başına bir bölge\n", encoding="utf-8")
            ast = dp.DeepState(goal="RAPOR_KURALLARI.md'ye göre aylık satış raporunu Excel olarak oluştur.",
                               kind="is")

            def sub_amb(prompt, marker, label=""):
                c = ctx.make_client()
                try:
                    ch = chain("kod")
                    return dp.run_subagent(client=c, model=ch[0], fallbacks=ch[1:], root=amb, prompt=prompt,
                                           marker=marker, gate=gate, runner_kw={"project_map": harita})
                finally:
                    c.close()
            t0 = time.monotonic()
            dp.understand(ast, sub_amb, gate, gate.max_parallel, lambda t: None)
            print(f"1b ANLA (eksik veri, belirsiz): {len(ast.questions)} soru · {time.monotonic() - t0:.0f} sn",
                  flush=True)
            for q in ast.questions:
                print("     ?", q[:160], flush=True)
            ok &= len(ast.questions) >= 1
        finally:
            shutil.rmtree(amb, ignore_errors=True)

        t0 = time.monotonic()
        plan_models = chain("plan")[:2]
        subs = {m: sub_for([m] + [x for x in chain("plan") if x != m]) for m in plan_models}

        def judge(messages):
            text, model = ctx.ai_chat("inceleme", messages, max_tokens=600, evren_only=True)
            print("   yargıç:", model, text[:160].replace("\n", " "), flush=True)
            return text
        tasks = dp.plan(st, lambda m, p, k: subs[m](p, k), plan_models, judge, gate, gate.max_parallel,
                        lambda t: print("  ", t, flush=True))
        print(f"2 PLANLA: modeller {plan_models}; geçerli plan {len(st.plans)}; seçilen {st.chosen} "
              f"({len(tasks)} görev) · {time.monotonic() - t0:.0f} sn", flush=True)
        for t in tasks:
            print(f"     {t.idx}. {t.title} — {t.criteria[:90]}", flush=True)
        ok &= len(st.plans) >= 1 and len(tasks) >= 1

        verifier = [sub_for(chain("inceleme")), sub_for(chain("kod"))]
        n = {"i": 0}

        def vsub(prompt, marker, label=""):
            n["i"] += 1
            return verifier[n["i"] % 2](prompt, marker)
        files = {"YANLIŞ": (BAD_CALC, BAD_TEST), "DOĞRU": (GOOD_CALC, GOOD_TEST)}
        for name, diff, expect_issue in (("YANLIŞ", BAD_DIFF, True), ("DOĞRU", GOOD_DIFF, False)):
            t0 = time.monotonic()
            # gerçek akıştaki gibi değişiklik DİSKTE (denetçi nihai çıktıyı dosyadan doğrular)
            (tmp / "calc.py").write_text(files[name][0], encoding="utf-8")
            (tmp / "test_calc.py").write_text(files[name][1], encoding="utf-8")
            vst = dp.DeepState(goal=GOAL)
            with_tests = "--testsiz" not in sys.argv
            tests = dp.project_tests(tmp) if with_tests else None
            if with_tests:
                print(f"   gerçek test: {tests['durum'] if tests else 'yok'} ({tests['komut'] if tests else '-'})",
                      flush=True)
            issues = dp.verify(vst, diff, vsub, gate, gate.max_parallel, lambda t: None, tests=tests,
                               with_tests=with_tests)
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
