"""F4 #10 iş şablonları (Qt'siz): sık işler için hazır istem + önerilen profil/skill.

Şablon yalnız mesaj kutusunu doldurur (GÖNDERMEZ): kullanıcı köşeli parantezli yerleri kendi işine göre düzenler.
Kullanıcı şablonları veritabanında (templates tablosu); yerleşikler burada. Godot oyun şablonu F7'de eklenecek.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Template:
    name: str
    prompt: str
    description: str = ""
    profile: str = ""                 # önerilen profil adı (varsa uygulanır)
    needs_skill: str = ""             # önerilen skill adı (yoksa kullanıcıya söylenir)
    builtin: bool = True
    id: int = 0


BUILTIN: list[Template] = [
    Template(
        "Excel/CSV raporu",
        "Bu klasördeki [dosya adı] verisinden [ne istendiği: ör. bölge bazında aylık toplam satış] raporu hazırla. "
        "Önce read_table ile dosyanın yapısını incele; hesapları bir Python betiğiyle yap ve betiği kaydet. "
        "Sonucu [Rapor.xlsx / rapor.md] olarak bu klasöre kaydet; ham dosyalara dokunma.",
        "Tablo verisinden tekrarlanabilir rapor (betikle hesaplar)."),
    Template(
        "Hesap kapama raporu",
        "Hesap kapama raporunu skill kurallarına göre üret: bu klasördeki açık/kapalı işler, fırsat, sözleşme ve CRS "
        "dosyalarını kullan. Sonucu \"Hesap Kapama Raporu.xlsx\" adıyla BU klasörün köküne kaydet; ham dosyalara "
        "dokunma. Belirsiz bir kural varsa varsayım yapmadan sor.",
        "Skill'li gerçek iş süreci (önce skill'i ekleyin).", needs_skill="hesap-kapama"),
    Template(
        "Web sayfasını test et (QA)",
        "/qa [adres, ör. http://localhost:5173] — [neyin test edileceği: ör. kayıt formu, giriş, sepet]",
        "QA ajanı tarayıcıda test uzmanı gibi dener, bulguları raporlar."),
    Template(
        "Yeni Python projesi",
        "Bu klasörde Python ile [ne yapacak] yazacağız. Önce kısa bir plan sun; onayımdan sonra modüller, "
        "komut satırı arayüzü ve unittest testleriyle yaz, testleri çalıştırıp geçtiğini göster.",
        "Plan → onay → kod + test."),
    Template(
        "Hata ayıkla",
        "[Hata mesajı veya belirti]. Nedenini bul, en küçük düzeltmeyi yap ve ilgili testleri çalıştırıp geçtiğini "
        "göster. İlgisiz dosyalara dokunma.",
        "Belirtiden kök nedene, küçük düzeltme."),
]


def from_row(r: dict) -> Template:
    return Template(name=r["name"], prompt=r["prompt"], profile=r.get("profile") or "", builtin=False,
                    id=int(r["id"]), description="Kendi şablonunuz")
