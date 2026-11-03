"""Derin Mod yargıç karşılaştırması: iki plandan doğrusunu hangi model / düşünme seviyesi seçiyor?
(gerçek API; pytest toplamaz). DEVIR Madde 8, 2026-11-03.

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_derin_yargic_real_api.py qwen3.8-flash-next:none qwen3.8-flash-next ...

Yapılandırma `model[:effort]`; effort `none` = bugünkü üretim (ai_chat düşünmeyi kapatır, 600 token).
Her çiftte bir İYİ ve bir KUSURLU plan var (eksik kenar durum testi, kapsam taşması, yanlış çıktı dosyası,
zayıf doğrulama); her çift iki kez sorulur (A/B yer değiştirir → sıra yanlılığı ölçülür). Gerçek `judge_messages`
ve plan() içindeki ayrıştırmanın aynısı kullanılır. Ölçü: doğru seçim x/8, geçersiz yanıt, süre.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evren_studio.agent import deep as dp  # noqa: E402
from evren_studio.api.client import EvrenClient  # noqa: E402
from evren_studio.config import DEFAULT_BASE_URL  # noqa: E402
from evren_studio.secrets import load_api_key  # noqa: E402


def _plan(model: str, gorevler: list[tuple[str, str]]) -> dict:
    return {"model": model, "render": "\n".join(f"{i}. {t} — ölçüt: {c}" for i, (t, c) in enumerate(gorevler, 1))}


CIFTLER = [
    ("calc.py'ye div(a, b) ekle: b sıfırsa ValueError fırlatsın; testini yaz.",
     [("calc.py'ye div ekle, b == 0 ise ValueError fırlat", "div(6,3)==2, div(1,0) ValueError"),
      ("test_calc.py'ye div testleri ekle (normal ve sıfır bölen)", "python -m unittest geçer, sıfır testi var")],
     [("calc.py'ye div ekle", "div(6,3)==2"),
      ("test_calc.py'ye div(6,3) testi ekle", "python -m unittest geçer")]),
    ("liste.py'ye son(lst, n) ekle: son n elemanı döndürsün, n 0 ise boş liste. Testini yaz.",
     [("liste.py'ye son ekle; n <= 0 için [] döndür", "son([1,2,3],2)==[2,3], son(x,0)==[]"),
      ("test_liste.py'ye son testleri (n=2 ve n=0)", "unittest geçer")],
     [("liste.py'ye son ekle", "son([1,2,3],2)==[2,3]"),
      ("Tüm modülü sınıf yapısına dönüştür ve README yaz", "README var, sınıflar çalışır"),
      ("test_liste.py'ye son testi", "unittest geçer")]),
    ("satislar.csv'den kategori başına toplamı hesaplayıp rapor.md'ye tablo olarak yaz.",
     [("satislar.csv'yi oku, kategori toplamlarını hesapla", "toplamlar CSV ile elle doğrulanır"),
      ("rapor.md'ye Markdown tablo yaz (kategori | toplam)", "rapor.md var, her kategori bir satır, toplamlar doğru")],
     [("satislar.csv'yi oku, kategori toplamlarını hesapla", "betik çalışır"),
      ("Sonucu rapor.txt'ye yaz", "dosya oluştu")]),
    ("kullanici.py'de kaydet(ad) kullanıcı adını doğrulasın: yalnız harf, rakam, alt çizgi; 3-16 karakter; "
     "geçersizse ValueError.",
     [("re.fullmatch(r'[A-Za-z0-9_]{3,16}') ile doğrula, geçersizse ValueError",
       "'ali_42' geçer; 'abc!!!', 'ab', 20 karakter ValueError"),
      ("Geçerli/geçersiz örneklerle test yaz", "unittest geçer")],
     [("Uzunluğu 3-16 arası değilse ValueError", "'ab' ValueError"),
      ("Bir test yaz", "unittest geçer")]),
]


def _secim(text: str) -> str | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
    except ValueError:
        return None
    s = str(data.get("secim", "")).strip().upper()
    return s[:1] if s[:1] in ("A", "B") else None


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    configs = sys.argv[1:]
    c = EvrenClient(DEFAULT_BASE_URL, load_api_key(), timeout=240.0, max_retries=1)
    rapor = []
    try:
        for cfg in configs:
            model, _, effort = cfg.partition(":")
            kw = {"extra_body": {"reasoning_effort": effort}} if effort else {}
            max_tokens = 600 if effort == "none" else 6000
            dogru, gecersiz, sure, a_secimi = 0, 0, 0.0, 0
            for goal, iyi, kusurlu in CIFTLER:
                for iyi_basta in (True, False):
                    plans = [_plan("x", iyi), _plan("y", kusurlu)] if iyi_basta else [_plan("y", kusurlu), _plan("x", iyi)]
                    t0 = time.monotonic()
                    try:
                        r = c.chat(model, dp.judge_messages(goal, plans), max_tokens=max_tokens, **kw)
                        text = r.content or ""
                    except Exception as e:
                        text = f"HATA {e}"
                    sure += time.monotonic() - t0
                    sec = _secim(text)
                    beklenen = "A" if iyi_basta else "B"
                    gecersiz += sec is None
                    a_secimi += sec == "A"
                    dogru += sec == beklenen
            rec = {"yapilandirma": cfg, "dogru": dogru, "toplam": 2 * len(CIFTLER), "gecersiz": gecersiz,
                   "A_secimi": a_secimi, "sure_sn": round(sure, 1)}
            rapor.append(rec)
            print(f"== {cfg}: doğru seçim {dogru}/{rec['toplam']} · geçersiz {gecersiz} · A seçimi {a_secimi} · "
                  f"{sure:.0f} sn", flush=True)
    finally:
        c.close()
    out = ROOT / "build" / "derin" / f"yargic_{int(time.time())}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
