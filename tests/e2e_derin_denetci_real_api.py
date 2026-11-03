"""Derin Mod denetçi karşılaştırması: hangi EVREN modeli (ve düşünme seviyesi) doğrulama aşamasında en doğru?
(gerçek API; pytest toplamaz). DEVIR Madde 8, 2026-11-03.

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_derin_denetci_real_api.py mevcut deepseek-v4.1-flash qwen3.8-flash-next:high ...

Yapılandırma: `model` ya da `model:effort` (reasoning_effort, ör. high); `mevcut` = bugünkü üretim eşleşmesi
(inceleme + kod rolünün ilk modelleri). Tek model verilince İKİ denetçi bakış açısı da o modelle koşar (gerçek
`dp.verify` + `confirmed_issues` kararı). Her yapılandırma 6 değişikliği denetler: 3 BİLİNEN HATALI (sorun
bulunmalı) + 3 BİLİNEN DOĞRU ("yüksek" sorun çıkmamalı). Değişiklik diskte de vardır (gerçek akıştaki gibi).

Ölçü: hatalı yakalama x/3, doğruda temiz x/3, toplam süre, sonuç bloğu eksik denetçi sayısı.
Sonuç docs/knowledge/CHALLENGE_RESULTS.md "Derin Mod denetçi karşılaştırması" bölümüne elle işlenir.
"""
from __future__ import annotations

import difflib
import json
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

# ---- vakalar: (ad, istek, temel dosyalar, hatalı dosyalar, doğru dosyalar) ---------------------------------

_CALC = '"""Basit hesap makinesi."""\n\n\ndef add(a, b):\n    return a + b\n'
_CALC_T = ("import unittest\n\nfrom calc import add\n\n\nclass T(unittest.TestCase):\n"
           "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n")

_SON = '"""Liste yardımcıları."""\n\n\ndef ilk(lst, n):\n    return lst[:n]\n'
_SON_T = ("import unittest\n\nfrom liste import ilk\n\n\nclass T(unittest.TestCase):\n"
          "    def test_ilk(self):\n        self.assertEqual(ilk([1, 2, 3], 2), [1, 2])\n")

_KUL = '"""Kullanıcı kaydı."""\nimport re\n\n\ndef kaydet(ad):\n    return {"ad": ad}\n'

VAKALAR = [
    ("bolme", "calc.py'ye div(a, b) ekle: b sıfırsa ValueError fırlatsın; test_calc.py'ye testini yaz.",
     {"calc.py": _CALC, "test_calc.py": _CALC_T},
     {"calc.py": _CALC + "\n\ndef div(a, b):\n    return a / b\n",
      "test_calc.py": _CALC_T.replace("from calc import add", "from calc import add, div")
      + "\n    def test_div(self):\n        self.assertEqual(div(6, 3), 2)\n"},
     {"calc.py": _CALC + '\n\ndef div(a, b):\n    if b == 0:\n        raise ValueError("b sıfır olamaz")\n'
                         "    return a / b\n",
      "test_calc.py": _CALC_T.replace("from calc import add", "from calc import add, div")
      + "\n    def test_div(self):\n        self.assertEqual(div(6, 3), 2)\n"
      + "\n    def test_div_sifir(self):\n        self.assertRaises(ValueError, div, 1, 0)\n"}),
    ("son_n", "liste.py'ye son(lst, n) ekle: listenin son n elemanını döndürsün; n 0 ise boş liste dönsün. "
              "Testini test_liste.py'ye yaz.",
     {"liste.py": _SON, "test_liste.py": _SON_T},
     {"liste.py": _SON + "\n\ndef son(lst, n):\n    return lst[-n:]\n",
      "test_liste.py": _SON_T.replace("from liste import ilk", "from liste import ilk, son")
      + "\n    def test_son(self):\n        self.assertEqual(son([1, 2, 3], 2), [2, 3])\n"},
     {"liste.py": _SON + "\n\ndef son(lst, n):\n    if n <= 0:\n        return []\n    return lst[-n:]\n",
      "test_liste.py": _SON_T.replace("from liste import ilk", "from liste import ilk, son")
      + "\n    def test_son(self):\n        self.assertEqual(son([1, 2, 3], 2), [2, 3])\n"
      + "\n    def test_son_sifir(self):\n        self.assertEqual(son([1, 2, 3], 0), [])\n"}),
    ("kullanici_adi", "kullanici.py'de kaydet(ad) kullanıcı adını doğrulasın: yalnız harf, rakam ve alt çizgi, "
                      "3-16 karakter; geçersizse ValueError fırlatsın.",
     {"kullanici.py": _KUL},
     {"kullanici.py": _KUL.replace('    return {"ad": ad}',
                                   '    if not re.match(r"[A-Za-z0-9_]{3,16}", ad):\n'
                                   '        raise ValueError("geçersiz kullanıcı adı")\n    return {"ad": ad}')},
     {"kullanici.py": _KUL.replace('    return {"ad": ad}',
                                   '    if not re.fullmatch(r"[A-Za-z0-9_]{3,16}", ad):\n'
                                   '        raise ValueError("geçersiz kullanıcı adı")\n    return {"ad": ad}')}),
]


def _diff(base: dict, new: dict) -> str:
    out = []
    for name in sorted(set(base) | set(new)):
        a, b = base.get(name, ""), new.get(name, "")
        if a != b:
            out.append("".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), f"a/{name}", f"b/{name}")))
    return "\n".join(out)


def _high(issues: list[dict]) -> list[dict]:
    return [i for i in issues if str(i.get("ciddiyet", "")).lower().startswith(("yuk", "yük"))]


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    configs = sys.argv[1:] or ["mevcut"]
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

    def chain(role):
        r = ctx.ai_route(role)
        return [m for m in [r.model] + r.fallbacks if ctx.provider_of(m) == "evren"]

    rapor = []
    for cfg in configs:
        if cfg == "mevcut":
            m1 = chain("inceleme")[0]
            m2 = next(m for m in chain("kod") + chain("inceleme") if m != m1)
            models, body = [m1, m2], None
        elif "+" in cfg:                       # "m1+m2[:effort2]": iki farklı denetçi, effort yalnız ikinciye
            m1, rest = cfg.split("+", 1)
            m2, _, effort = rest.partition(":")
            models, body = [m1, m2], None
            bodies = [None, {"reasoning_effort": effort} if effort else None]
        else:
            model, _, effort = cfg.partition(":")
            models, body = [model, model], ({"reasoning_effort": effort} if effort else None)
        if "+" not in cfg:
            bodies = [body, body]
        sonuc = {"yapilandirma": cfg, "modeller": models, "hatali_yakalandi": 0, "dogru_temiz": 0, "sure_sn": 0.0,
                 "blok_yok": 0, "vakalar": []}
        for ad, istek, temel, hatali, dogru in VAKALAR:
            for tur, dosyalar, beklenen_sorun in (("hatalı", hatali, True), ("doğru", dogru, False)):
                tmp = Path(tempfile.mkdtemp(prefix="denetci_"))
                try:
                    for name, text in {**temel, **dosyalar}.items():
                        (tmp / name).write_text(text, encoding="utf-8")
                    n = {"i": 0}
                    eksik = {"n": 0}

                    def vsub(prompt, marker, label="", tmp=tmp):
                        i = 1 if label.endswith("2") else 0
                        c = ctx.make_client()
                        try:
                            res = dp.run_subagent(client=c, model=models[i], fallbacks=[], root=tmp, prompt=prompt,
                                                  marker=marker, gate=gate, base_body=bodies[i])
                        finally:
                            c.close()
                        if marker not in (res.text or ""):
                            eksik["n"] += 1
                        n["i"] += 1
                        return res
                    t0 = time.monotonic()
                    issues = dp.verify(dp.DeepState(goal=istek), _diff(temel, dosyalar), vsub, gate, 2)
                    sure = time.monotonic() - t0
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
                ok = bool(issues) if beklenen_sorun else not _high(issues)
                sonuc["hatali_yakalandi" if beklenen_sorun else "dogru_temiz"] += int(ok)
                sonuc["sure_sn"] += sure
                sonuc["blok_yok"] += eksik["n"]
                sonuc["vakalar"].append({"vaka": ad, "tur": tur, "gecti": ok, "sorun": len(issues),
                                         "yuksek": len(_high(issues)), "sure_sn": round(sure, 1),
                                         "ornek": [str(i.get("aciklama"))[:120] for i in issues[:2]]})
                print(f"  [{cfg}] {ad:14s} {tur:6s} {'✓' if ok else '✗'} sorun={len(issues)} yüksek={len(_high(issues))}"
                      f" · {sure:.0f} sn" + (f" · blok yok {eksik['n']}" if eksik["n"] else ""), flush=True)
        sonuc["sure_sn"] = round(sonuc["sure_sn"], 1)
        rapor.append(sonuc)
        print(f"== {cfg}: hatalı yakalandı {sonuc['hatali_yakalandi']}/3 · doğruda temiz {sonuc['dogru_temiz']}/3 · "
              f"{sonuc['sure_sn']:.0f} sn · blok yok {sonuc['blok_yok']}", flush=True)
    out = ROOT / "build" / "derin" / f"denetci_{int(time.time())}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Rapor:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
