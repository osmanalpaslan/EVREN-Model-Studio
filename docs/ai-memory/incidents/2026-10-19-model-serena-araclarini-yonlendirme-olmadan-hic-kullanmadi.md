---
id: 2026-10-19-model-serena-araclarini-yonlendirme-olmadan-hic-kullanmadi
tarih: 2026-10-19
tur: risk            # hata | eksik | risk | yanlis-iddia | surec | ortam
onem: orta          # kritik | yuksek | orta | dusuk
durum: cozuldu                # acik | izleniyor | cozuldu | kabul-edildi
alan: agent
kaynak_motor: Claude Code (masaüstü)
kaynak_model: claude-opus-5-5
cozen_motor: Claude Code (masaüstü)
cozen_model: claude-opus-5-5
ortam: Windows 11, Python 3.12.10
etiketler: [mcp, serena, istem]
kurallar: [R-25]
---

# Model Serena araçlarını yönlendirme olmadan hiç kullanmadı

## Belirti
tests/e2e_mcp_real_api.py (Auto Pro → deepseek-v4-flash): Serena açıkken 4 koşunun hiçbirinde
`mcp__serena__*` çağrılmadı (MCP 0); model search_files + read_file ile çözdü.

## Kök neden
Doğrulandı (gerçek API): araçlar modele sunuluyordu (Serena başlatıldı, günlükte görüldü) ama
ilk sistem istemi notu ("önce bunları kullan") genel kaldı; model alışık olduğu metin aramasını seçti.

## Çözüm
mcp.prompt_section somutlaştırıldı: tanım/kullanım bulma, yeniden adlandırma, imza değişikliği
işlerinde search_files'tan ÖNCE find_referencing_symbols/find_symbol; metin araması benzer
adları ve yorumları da bulur; sembol olmayan metinde doğrudan search_files.

## Kanıt
Yeniden ölçüm: Serena açık koşularda MCP 2 çağrı, 4/4 doğru; büyük projede (uygulamanın kendi
kaynağı, ~17 bin satır) 7/7, araç çıktısı 11,2k → 5,7k karakter. Zorluk paketi Serena açık:
CHALLENGE_RESULTS.md "MCP / Serena".

## Önleme
R-25: yeni araç eklerken modelin onu gerçekten SEÇTİĞİNİ gerçek API ile ölç.

## İlgili dosyalar
src/evren_studio/agent/mcp.py, tests/e2e_mcp_real_api.py
