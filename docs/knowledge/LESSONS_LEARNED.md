# Öğrenilen Dersler

> Tarih sırasıyla; her madde kanıtıyla birlikte. Aynı hatayı tekrar
> işlememek için yazılır.

## 2026-10-15 — Geliştirme günü 1

1. **URL birleştirme tuzağı**: Kullanıcı verilen temel adres `/v1` ile
   biterken istemci yollarına da `/v1` eklerseniz `/v1/v1/models` olur.
   Çözüm: temel adreste sondaki `/v1` soyulur, yollar resmî OpenAPI
   şemasındaki gibidir. Kanıt: test_model_listesi ilk çalışmada
   `https://test.example/v1/v1/models` isteğiyle düştü; normalizasyon
   sonrası geçti.

2. **SPA duyuru sayfası okunamaz**: evren.ssyz.org.tr istemci tarafında
   render edilir; HTTP GET yalnızca boş kabuk döndürür. Duyuru verisi
   `api.ssyz.org.tr/api/v1/announcements/active`'ta ve 401 gerektirir.
   Ders: izleme için sayfa İÇERİĞİ yerine erişilebilirlik + görünür metin
   + başlık/meta değişimi izlenir; URL kullanıcı tarafından değiştirilebilir.

3. **Muhakeme modeli bütçesi**: glm-5.3 düşük max_tokens'ta tüm bütçeyi
   reasoning'e harcayıp `content: null` döndürür (`finish_reason: length`,
   `reasoning_budget_exhausted: true`). Bu hata DEĞİLDİR. Ders: e2e
   testlerinde makul max_tokens kullan; boş içeriği hata sanma.

4. **PowerShell 5.1 tuzakları**: (a) `System.Net.Http` derlemesi açıkça
   yüklenmeden HttpClient bulunamaz; (b) bayt dizgesinde Türkçe karakter
   SyntaxError verir; (c) borulu çıktı tamponlanır → `python -u` kullan.
   Kanıt: ilk e2e denemesi 180 sn timeout'a düştü (tampon + yavaş muhakeme
   üretimi).

5. **SQLite iş parçacığı kuralı**: izleme ajanı ayrı iş parçacığında
   çalışır; `check_same_thread=False` + RLock olmadan kayıtlar
   ProgrammingError ile düşer. Kanıt: test_tek_tur_kayitlari ilk denemede
   düştü.

6. **İzleme iş parçacığı kapanış yarışı**: `stop()` yalnızca bayrak
   setlerse, iş parçacığı kayıt yazarken DB kapanabilir → 'Cannot operate
   on a closed database'. Çözüm: stop() içinde `join(timeout=10)`.
   Kanıt: test_dongu_30_dakika_planina_uyar uyarısı.

7. **dataclass alan sırası**: varsayılan değerli alandan sonra varsayılansız
   alan TypeError verir. monitor.py'de iki kez düzeltildi.

8. **keyring testi**: monkeypatch ile `_set_backend` değiştirilirse
   enjeksiyon ÇALIŞMAZ (lambda hiçbir şey yapmaz). Düz çağrı + teardown
   doğru yöntemdir. Sahte keyring, olmayan kayıtta gerçek keyring gibi
   PasswordDeleteError VERMELİDİR.

9. **MockTransport stream**: `httpx.Response(200, content=iter(...))` SSE
   benzetimi için yeterlidir; akış kopması `ReadTimeout` fırlatarak
   doğal biçimde simüle edilir.
