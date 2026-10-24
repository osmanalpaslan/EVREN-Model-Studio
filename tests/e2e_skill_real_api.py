"""F4 skill ölçümü (R-25): model skill'i gerçekten açıp kuralını uyguluyor mu; konu dışı işte açmıyor mu?
Gerçek API, anahtar gerekir; pytest toplamaz. Zorluk paketinin sürücüsünü kullanır.

    .\\.venv\\Scripts\\python.exe -u tests\\e2e_skill_real_api.py <model> [görev ...]

Görevler:
- skill_acik: "fatura-kurallari" skill'i etkin. Kurallar YALNIZ skill'de (biri references/kdv.md'de): fatura numarası
  biçimi ve KDV oranı. Model okumazsa tahmin edemez.
- skill_kapali: aynı istem, skill YOK (taban: model kuralı bilemez → kalmalı; ölçüm amacıyla beklenen sonuç).
- skill_konusuz: skill etkin ama iş ilgisiz (README yazım hatası) → read_skill çağrılmamalı (R-22).
Sonuç: build/skill/<model>/rapor.json · özet CHALLENGE_RESULTS.md "F4".
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e2e_zorluk_real_api as z  # noqa: E402

SKILL_MD = """---
name: fatura-kurallari
description: Şirketimizin fatura numarası biçimi, KDV hesabı ve fatura alanları kuralları. Fatura numarası veya KDV
  içeren her kod/rapor işinde kullan.
---
# Fatura kuralları

1. Fatura numarası biçimi: `FTR-<yıl>-<sıra>`; sıra 5 haneli, soldan sıfırla doldurulur. Örnek: 2026 yılının 7.
   faturası `FTR-2026-00007`.
2. KDV oranı ve yuvarlama kuralı `references/kdv.md` dosyasındadır; KDV hesaplayan kod yazmadan önce oku.
"""
KDV_MD = """# KDV

- KDV oranı %20'dir.
- KDV dahil tutar = tutar × 1,20; sonuç 2 ondalık basamağa YUKARI yuvarlanır (ör. 10,001 → 10,01).
"""
ISTEM = ("fatura.py dosyasında iki fonksiyon yaz: yeni_fatura_no(yil, sira) şirketimizin fatura numarasını üretsin, "
         "kdv_dahil(tutar) KDV dahil tutarı float olarak döndürsün; ikisi de şirket kurallarına uysun. tests/ altında "
         "unittest testleri yaz ve `python -m unittest discover -s tests` ile çalıştırıp geçtiğini göster.")

KABUL = """
import sys, json
sys.path.insert(0, ".")
from fatura import yeni_fatura_no, kdv_dahil
print(json.dumps([yeni_fatura_no(2026, 7) == "FTR-2026-00007", yeni_fatura_no(2025, 12345) == "FTR-2025-12345",
                  abs(kdv_dahil(100) - 120.0) < 1e-9, abs(kdv_dahil(8.3342) - 10.01) < 1e-9]))
"""


def skill_ekle(w, proj: Path, base: Path) -> None:
    src = base / "_skill_kaynak" / "fatura-kurallari"
    if not (src / "SKILL.md").is_file():
        (src / "references").mkdir(parents=True, exist_ok=True)
        (src / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
        (src / "references" / "kdv.md").write_text(KDV_MD, encoding="utf-8")
    if not any(s.name == "fatura-kurallari" for s in w.ctx.skills()):
        w.ctx.add_skill(src)


def skill_kaldir(w, proj: Path, base: Path) -> None:
    for s in w.ctx.skills():
        w.ctx.remove_skill(s.slug)


def kur_bos(p: Path) -> dict:
    return {}


def kontrol_fatura(p: Path, s: dict, yanit: str) -> list:
    import json

    if not (p / "fatura.py").is_file():
        return [("fatura.py var", False, "")]
    k = p / "_kabul_fatura.py"
    k.write_text(KABUL, encoding="utf-8")
    c, o = z.run([z.PY, str(k)], p)
    k.unlink(missing_ok=True)
    try:
        r = json.loads(o.strip().splitlines()[-1])
    except Exception:
        r = [False] * 4
    ok, info = z.unittest_ok(p)
    return [("fatura no biçimi (SKILL.md)", r[0] and r[1], o.strip()[-120:]),
            ("KDV %20 (references/kdv.md)", r[2], ""),
            ("yukarı yuvarlama (references/kdv.md)", r[3], ""),
            ("kendi testleri geçiyor", ok, info)]


def kur_readme(p: Path) -> dict:
    (p / "README.md").write_text("# Proje\n\nKurlum için `pip install -r requirements.txt` çalıştırın.\n", encoding="utf-8")
    return {}


def kontrol_readme(p: Path, s: dict, yanit: str) -> list:
    t = (p / "README.md").read_text(encoding="utf-8")
    return [("yazım düzeldi", "Kurulum" in t and "Kurlum" not in t, "")]


GOREVLER = {
    "skill_acik": {"kur": kur_bos, "kontrol": kontrol_fatura, "mesaj": ISTEM, "hazirla": skill_ekle},
    "skill_kapali": {"kur": kur_bos, "kontrol": kontrol_fatura, "mesaj": ISTEM, "hazirla": skill_kaldir},
    "skill_konusuz": {"kur": kur_readme, "kontrol": kontrol_readme, "mesaj": "README.md'deki yazım hatasını düzelt.",
                      "hazirla": skill_ekle},
}


if __name__ == "__main__":
    raise SystemExit(z.main(GOREVLER, baslik="Skill ölçümü (R-25)", alt="skill"))
