# Hesap kapama skill'i — düzeltme önerileri (2026-10-21)

> Kaynak: EVREN ile iki gerçek koşu + kurallardan hesaplanan beklenen sonuçla hücre hücre denetim
> (`tests/e2e_hesap_kapama_real_api.py`, CHALLENGE_RESULTS.md "Gerçek iş süreci: hesap kapama raporu").
> Skill dosyası (SKILL.md, references/) DEĞİŞTİRİLMEDİ; aşağıdakiler kullanıcının onayına sunulan önerilerdir.
> Her öneri, iki koşuda farklı yorumlanan ya da kendi içinde çelişen bir yeri kapatır.

## 1. `Manuel / Kullanıcı` ile " / " yasağı çelişiyor (§3.4 ↔ §5 madde 5)

§3.4 Kapama Türü değerlerinden biri `Manuel / Kullanıcı`; §5 madde 5 "hiçbir hücrede ` / ` ile birleştirilmiş
değer kalmamış" diyor. Ajan ya değeri değiştirir ya da doğrulamayı yanlış sayar.

**Öneri (§3.4):** değeri `Manuel` yap → `24153 → oto hesapkapama · 12055 → webservis · diğer → Manuel`.
(Eski adı korumak gerekiyorsa §5 madde 5'e "`Manuel / Kullanıcı` sabit değeri hariç" notu ekle.)

## 2. Dağılım toplamı hangi iş kümesinden? (§5 madde 1–3 ↔ §3.8)

Koşu 1 dağılımları 32 iş (tümü), koşu 2 ise kapsam dışını düşerek 30 iş üzerinden verdi. §5 "toplam = kaynak iş
sayısı" diyor ama §3.8 kapsam dışı işleri "süreçten çıkarılır" diye tanımlıyor.

**Öneri (§5 madde 1–2 ve Yönetim Özeti):** "Açılış kaynağı ve açılma türü dağılımları **kapsam dışı dahil tüm
kaynak işler** üzerinden verilir (toplam = açık + kapalı iş sayısı). Kapama türü dağılımı tüm kapalı işler
üzerinden verilir. Kapsam dışı iş sayısı ayrıca gösterilir."

## 3. Açık işte "Kapatan Kullanıcı" (§4)

Tanımsız. Koşulardan biri boş bıraktı, diğeri `(iş açık)` yazdı.

**Öneri (§3.4'ün altına):** "İş açıksa `Kapama Türü` = `(iş açık)`, **`Kapatan Kullanıcı` boş** bırakılır."

## 4. Sözlükte olmayan kullanıcı id'sinin biçimi (§3.3)

"id'yi yaz ve raporda bildir" diyor. Koşulardan biri `19999`, diğeri `19999 - (sözlükte yok)` yazdı.

**Öneri:** "Sözlükte olmayan id hücreye **yalnız id** olarak yazılır (`19999`); Yönetim Özeti'nde 'Sözlükte
olmayan kullanıcı id'leri' satırında listelenir."

## 5. "Soru 1–5" tanımsız (§4, Yönetim Özeti)

Her koşu kendi beş sorusunu uydurdu.

**Öneri:** soruları skill'e yaz. Örnek:
1. Toplam / açık / kapalı iş ve kapsam dışı iş sayısı
2. Açılış kaynağı dağılımı
3. Açılma türü dağılımı
4. Kapalı işlerde kapama türü dağılımı
5. Kapalı işlerde fırsat/sözleşme tutarlılığı (Analiz Önceliği dağılımı) ve CRS'te kapalı ama bizde açık iş sayısı

## 6. Tarih biçimi tanımsız

Koşular tarihi `2026-09-01` metni olarak yazdı (Excel'de tarih olarak sıralanmaz).

**Öneri (§4 Biçim):** "Tarih sütunları Excel tarih değeri olarak yazılır, biçimi `gg.aa.yyyy`."

## 7. ⚠️ Teknik tuzaklar #9 kullanıcının Excel'ini kapatabilir

`Get-Process EXCEL | Stop-Process -Force` kullanıcının açık, kaydedilmemiş Excel dosyalarını kapatır.

**Öneri (references/teknik_tuzaklar.md #9):** "**Asla** tüm Excel süreçlerini durdurma. Yalnız kendi oluşturduğun
COM nesnesini `$xl.Quit()` + `[Runtime.InteropServices.Marshal]::ReleaseComObject($xl)` ile kapat. Süreç kalırsa
yalnız başlamadan önce yoktan sonra var olan PID'i (kendi başlattığını) kapat." Ayrıca: Python + openpyxl varsa
Excel COM'a gerek yok (iki koşu da openpyxl ile 9 dakikanın altında bitti, Excel'e dokunmadı).

## 8. Geçici betikler skill klasörüne yazılmasın

Koşu 2 `_build.py`'yi `hesap-kapama-raporu/` içine yazıp orada bıraktı.

**Öneri (§8 Sınırlar):** "Skill klasörüne ve ham kaynak dosyalara yazma; geçici dosyaları `out/` altına yaz."

## 9. Tekrarlanabilirlik (genel)

Aynı veriden iki koşu farklı Yönetim Özeti üretti. Aylık iş için önerilen yol: ajana bir kez, bu denetçiden geçen
sabit bir betik (`rapor_uret.py`) yazdırmak ve her ay onu çalıştırmak. Sütun eşlemesi ilk çalıştırmada içerikten
çıkarılıp `sutun_esleme.json` olarak onaya sunulur; onaylı eşlemeyle sonraki çalıştırmalar aynı sonucu verir.
