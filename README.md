# Gözlem kayıtları (otomatik)

Bu dal EVREN Studio'nun **gözlem ajanı** tarafından yazılır; elle düzenleme. Uygulama çalışırken görülen
hata ve anormallikler temizlenmiş olarak buraya gelir (anahtar, kullanıcı adı, dosya yolu, sohbet içeriği
yoktur). Geliştirici motoru `tools/ai_memory.py baslangic` ile açık gözlemleri görür ve kullanıcıya bildirir;
`ai_memory.py gozlem kayda-donustur <imza>` → düzeltme → `ai_memory.py gozlem kapat <imza> --kayit <id>`.

- `gozlemler/<imza>/kayit.md`: gözlemin insan için kaydı (durum: acik | cozuldu | kabul-edildi)
- `gozlemler/<imza>/olay-<makine>.json`: o makinedeki sayaç, ilk/son görülme, uygulama sürümleri
