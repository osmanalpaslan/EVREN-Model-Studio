# EVREN Studio — EVREN ajanı için kısa proje notu

Bu dosya EVREN Studio'nun kendi kod ajanına her adımda verilir; kısa tut.
(Diğer motorların ayrıntılı protokolü AGENTS.md'dedir; EVREN ajanı onu
uygulamak zorunda değildir.)

- Proje: EVREN LLM API için Türkçe Windows masaüstü uygulaması (Python 3.12, PySide6).
- Kod: `src/evren_studio/` — `agent/` (ajan çekirdeği, Qt'siz), `api/` (istemciler),
  `ui/` (arayüz), `db.py` (SQLite).
- Test: `.\.venv\Scripts\python.exe -m pytest -q` (tamamı ~1 dk). Tek dosya için
  `.\.venv\Scripts\python.exe -m pytest -q tests\<dosya>.py`.
- Dosyaları BOM'suz UTF-8 yaz; Türkçe metinler bozulmasın.
- Test dosyalarını, kullanıcı açıkça istemedikçe değiştirme.
- API anahtarını asla dosyaya, loga veya komut çıktısına yazma.
- İş bitince ne değiştirdiğini ve hangi testi çalıştırdığını kısaca yaz.
