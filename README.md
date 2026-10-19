# EVREN Studio

EVREN LLM API'si (https://evren.ssyz.org.tr/) için Türkçe Windows masaüstü
uygulaması: **proje klasörünüzde çalışan bir kod ajanı** ve genel sohbet.
Claude Code masaüstü uygulamasına benzer bir çalışma ortamı sunar; tüm model
çağrıları yalnızca sizin EVREN anahtarınızla EVREN'e gider.

## Hızlı başlangıç

1. GitHub sayfasında **Code → Download ZIP** ile indirip bir klasöre çıkarın
   (veya `git clone`). **`kurulum.bat`** dosyasına çift tıklayın: Python'u bulur
   (yoksa sorup kurar), gerekli paketleri kurar ve masaüstüne **EVREN Studio**
   kısayolu ekler. Sonraki açılışlar bu kısayoldan (veya `run.bat`) yapılır.
2. Karşılama ekranındaki **Anahtar gir** düğmesiyle EVREN anahtarınızı
   kaydedin (Windows Credential Manager'da saklanır, ekranda maskelenir).
3. **Yeni oturum** → bir **proje klasörü** seçin (veya klasörsüz sohbet) →
   görevi yazın, Enter'a basın.

## Çalışma alanı

```
┌ Sol menü ───────┬ Oturum ─────────────────────────────┬ Sağ panel ─────┐
│ + Yeni oturum   │ Başlık · proje klasörü · git dalı   │ Görevler        │
│ Ara             │                                     │ Değişiklikler   │
│ Bugün / Dün …   │  Kullanıcı mesajı                   │ Dosyalar        │
│  oturumlar      │  EVREN: düşünce · yanıt (Markdown)  │ Terminal        │
│                 │   ✓ Okundu: src/app.py              │                 │
│ Modeller, Kota, │   ✎ Düzenlenecek (+3 −1) [diff]     │                 │
│ Durum İzleme,   │     [Onayla] [Hep izin ver] [Reddet]│                 │
│ Hata Merkezi …  │ ┌ Yazma kutusu: @dosya, /komut ───┐ │                 │
│ Ayarlar         │ │ 📎  Onaylı ▾  glm-5.3 ▾      ⬆ │ │                 │
└─────────────────┴─────────────────────────────────────┴─────────────────┘
```

## Özellikler

- **Kod ajanı**: dosya listeleme, okuma, regex arama, glob, dosya yazma,
  birebir metin değiştirerek düzenleme, PowerShell komutu çalıştırma ve
  görev listesi araçları. Her şey seçili proje klasörüyle sınırlıdır.
- **Çalışma modları (Claude Code gibi)**: *Manuel* (her değişiklik ve komut
  için onay), *Düzenlemeleri kabul et* (dosyalar onaysız, komutlar onaylı),
  *Plan* (salt okunur), *Otomatik* (hiçbir işlem için onay istenmez:
  tüm düzenlemeler, komutlar ve dosya okumaları onaysız; durdurmak için Esc).
- **Kapsam koruması**: ajan yalnız isteneni yapar; tur sonu özeti + "Turu geri al";
  istenmemiş değişiklikler otomatik işaretlenir ("Kapsam dışını geri al");
  isteğe bağlı "Önce plan" (Ayarlar).
- **Ortam denetimi**: proje klasörü bağlanınca gereken programlar (Node, pnpm,
  yarn, Python, uv, Git, Go, Rust, .NET, Java) denetlenir; eksikler Ayarlar'daki
  seçime göre *Otomatik* (sormadan) veya *Manuel* (Kur / Şimdi değil bildirimi)
  winget veya npm ile kurulur. Ajan da gerektiğinde `install_program` ile ister.
- **Otomatik özet (auto-compact)**: uzun konuşmalar, bağlam eşiğine (%75,
  en fazla 100k token) gelince mesajdan önce özetlenir; uzun görevlerde güvenli
  noktada özetleyip kendiliğinden devam eder. Elle: `/compact [odak]`.
- **Proje klasörü bağla**: klasörsüz başlatılan sohbete sonradan klasör bağlanabilir.
- **Onay kutuları**: değişiklik uygulanmadan önce renkli diff; komutlar
  çalışmadan önce gösterilir. "Bu oturumda hep izin ver" ve reddetme notu.
- **Geri alma**: ajanın her dosya değişikliği kaydedilir; sağ paneldeki
  *Değişiklikler* sekmesinden tek tek veya topluca geri alınır.
- **Sohbet deneyimi**: akışlı yanıt, Markdown + sözdizimi renklendirme,
  muhakeme modellerinin düşünce süreci (katlanabilir), mesajı düzenleyip
  yeniden gönderme, kopyalama, oturum arama/sabitleme/dışa aktarma.
- **Komutlar**: `/init` (EVREN.md proje hafızası), `/ozet` (uzun konuşmayı
  özetle), `/plan`, `/onayli`, `/otomatik`, `/model`, `/yeni`, `/yardim`;
  mesajda `@yol/dosya` ile dosya ekleme.
- **Araç protokolü**: OpenAI uyumlu yerel function calling; model
  reddederse (400/422) otomatik olarak metin protokolüne geçilir.
- **Ücretli sağlayıcılar (isteğe bağlı, doğrulanmadı)**: kendi OpenAI veya
  Anthropic API anahtarınızla GPT/Claude modelleri; gruplu model seçici,
  Ayarlar'da adım adım anahtar rehberi ve aylık bütçe (varsayılan $5, tahmini).
- **Auto Pro**: işe göre en uygun motoru seçen, görev ortasında motor
  değiştirmeyen, sorun olursa yedeğe geçen yönlendirici. Yalnız API anahtarını
  girdiğiniz sağlayıcıları kullanır (yalnız EVREN, yalnız OpenAI/Anthropic veya
  birlikte); uygulamanın kendi yapay zekâ işleri (oturum başlığı, hata açıklaması,
  commit mesajı, özet, inceleme) de bağlı API üzerinden çalışır.
- **Proje ajanı**: `/proje <hedef>` yazın; plan çıkarır, onayınızdan sonra
  görevleri siz başında olmadan sırayla yapar, her birini test eder, ayrı git
  dalında commit'ler, bitince bildirim ve rapor (EVREN_RAPOR.md) verir.
- **Ekler**: dosya ve görselleri sürükleyip bırakın veya Ctrl+V ile
  yapıştırın; kart olarak görünür, görseller görsel okuyan modellere gider.
- **Kullanım düğmesi**: model seçicinin yanında günlük kalan kota; tıklayınca
  grafikli ve açıklamalı kullanım paneli.
- **Modern arayüz**: koyu/açık tema, kendi simge seti, ortalanmış okuma
  sütunu, klavye kısayolları (Enter, Shift+Enter, Esc, Ctrl+N/B/J/K/L/,).
- **Aşama 1'den gelenler**: Modeller, Kullanım/Kota, Hata Merkezi (Türkçe
  kurtarma önerileri), EVREN Durum İzleme Ajanı, bağlantı testi, tanılama.
- **Güvenlik**: anahtar yalnızca Credential Manager'da; HTTPS zorunlu;
  telemetri yok; veriler `%LOCALAPPDATA%\EVREN-Model-Studio` altında.

## Yapay zekâ motorlarıyla geliştirme

Bu depoyu hangi motorla geliştirirseniz geliştirin (Claude Code, Kilo Code,
Cursor, Copilot, Codex, Gemini, EVREN Studio ajanı…) motor önce **AGENTS.md**
protokolünü okur. Ortak geliştirici hafızası `docs/ai-memory/` altındadır:
önceki motorların hataları, eksikler, nedenleri, çözümleri, kurallar ve
oturum günlükleri. Her motor işe `tools/ai_memory.py baslangic` ile başlar ve
bitirirken hafızayı besler; git kancası ve testler bunu denetler.

## Belgeler

- Kurulum: docs/INSTALLATION.md · Güvenlik: docs/SECURITY.md
- Proje durumu: docs/PROJECT_STATE.md · Görevler: docs/TASK_CHECKLIST.md
- Kararlar: docs/DECISIONS.md · Değişiklikler: docs/CHANGELOG.md
- İleride yapılacaklar (ör. kurulum paketi): docs/ILERIDE_YAPILACAKLAR.md
- Bilgi tabanı: docs/knowledge/ (API uyumluluğu, model yetenekleri, hata
  kataloğu, kurtarma rehberi, sınırlamalar, dersler, durum geçmişi)

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q              # birim + arayüz akış testleri
.\.venv\Scripts\python.exe tests\smoke_ui.py         # arayüz duman testi
.\.venv\Scripts\python.exe -u tests\e2e_real_api.py        # gerçek API (anahtar gerekir)
.\.venv\Scripts\python.exe -u tests\e2e_agent_real_api.py  # gerçek modellerle ajan araç turu
.\.venv\Scripts\python.exe -u tests\e2e_ui_real_api.py     # gerçek arayüz + gerçek API senaryosu
```

## Lisans

MIT — bkz. [LICENSE](LICENSE). Bağımlılıklar: PySide6 (LGPLv3), httpx
(BSD), keyring (MIT), Markdown (BSD), Pygments (BSD).
