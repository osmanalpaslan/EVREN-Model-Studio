"""PDF, Word ve PowerPoint okuma (Madde 20 A3, 2026-11-11). Önce: ajanın read_file'ı "ikili dosya" diye reddediyor, sohbet
eki "içerik eklenmedi" diye gidiyordu. Test belgeleri kodla üretilir (Türkçe, tablo, liste, konuşmacı notu; PDF Qt'nin
PDF yazıcısıyla gerçek yazı tipi gömülü). Salt okunur: belge adına düz metin yazılamaz (bozuk dosya üretirdi)."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from evren_studio.agent import documents  # noqa: E402
from evren_studio.agent.tools import ToolBox, ToolError, Workspace  # noqa: E402
from tests.test_attachments_usage import Client, _wait, win  # noqa: E402,F401 — ortak düzenek


def make_docx(path: Path) -> Path:
    import docx

    d = docx.Document()
    d.add_heading("Aylık Satış Raporu", level=1)
    d.add_paragraph("Şubeler ğüşıöç ÇĞİÖŞÜ toplamı aşağıdadır.")
    d.add_paragraph("Kadıköy şubesi hedefi aştı", style="List Bullet")
    t = d.add_table(rows=3, cols=2)
    for r, (a, b) in enumerate([("Şube", "Ciro"), ("Kadıköy", "125.000"), ("Üsküdar", "98.500")]):
        t.cell(r, 0).text, t.cell(r, 1).text = a, b
    d.add_heading("Sonuç", level=2)
    d.add_paragraph("Toplam 223.500 TL.")
    d.save(str(path))
    return path


def make_pptx(path: Path) -> Path:
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    s1 = prs.slides.add_slide(prs.slide_layouts[1])
    s1.shapes.title.text = "Çeyrek Hedefleri"
    s1.placeholders[1].text_frame.text = "Müşteri sayısı %20 artacak"
    s1.notes_slide.notes_text_frame.text = "Bu slaytta öğle arası verilecek"
    s2 = prs.slides.add_slide(prs.slide_layouts[5])
    s2.shapes.title.text = "Bütçe"
    tbl = s2.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(4), Inches(1)).table
    tbl.cell(0, 0).text, tbl.cell(0, 1).text, tbl.cell(1, 0).text, tbl.cell(1, 1).text = "Kalem", "Tutar", "Reklam", "40.000"
    prs.save(str(path))
    return path


def make_pdf(path: Path, pages: list[str]) -> Path:
    """Elle yazılmış en küçük PDF: standart Helvetica, WinAnsi (ü ö ç Ç Ö Ü var; ğ ş ı YOK — onlar gömülü yazı tipi
    ister, ayrıca gerçek çizimle denendi). Boş sayfa = yalnız dikdörtgen (taranmış belge gibi, metin katmanı yok)."""
    def esc(s: str) -> bytes:
        return s.encode("cp1252").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")

    nl = b"\n"
    objs: list[bytes] = []
    n = len(pages)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    font_id = 3 + 2 * n
    for i, text in enumerate(pages):
        stream = (b"BT /F1 14 Tf 72 720 Td (" + esc(text) + b") Tj ET") if text else b"0.2 0.4 0.6 rg 72 300 400 400 re f"
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {4 + 2 * i} 0 R "
                    f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode())
        objs.append(f"<< /Length {len(stream)} >>".encode() + nl + b"stream" + nl + stream + nl + b"endstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    out = bytearray(b"%PDF-1.4" + nl)
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj".encode() + nl + o + nl + b"endobj" + nl
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path


def test_word_basliklar_tablo_liste_turkce(tmp_path):
    out = documents.extract(make_docx(tmp_path / "rapor.docx"))
    assert "# Aylık Satış Raporu" in out and "## Sonuç" in out
    assert "ğüşıöç ÇĞİÖŞÜ" in out and "- Kadıköy şubesi hedefi aştı" in out
    assert "| Şube | Ciro |" in out and "| Kadıköy | 125.000 |" in out
    assert out.index("Aylık Satış") < out.index("| Şube") < out.index("## Sonuç")      # belge sırası korunur


def test_sunum_slayt_tablo_not(tmp_path):
    out = documents.extract(make_pptx(tmp_path / "sunum.pptx"))
    assert "## Slayt 1: Çeyrek Hedefleri" in out and "- Müşteri sayısı %20 artacak" in out
    assert "(Konuşmacı notu: Bu slaytta öğle arası verilecek)" in out
    assert "## Slayt 2: Bütçe" in out and "| Reklam | 40.000 |" in out


def test_pdf_sayfa_numarali_turkce(tmp_path):
    out = documents.extract(make_pdf(tmp_path / "fatura.pdf", ["Fatura No 2026-118 Müdür Çiçek Ödeme", "Toplam (KDV dahil) 1.180 TL"]))
    assert "--- Sayfa 1 ---" in out and "--- Sayfa 2 ---" in out
    assert "2026-118" in out and "Müdür Çiçek Ödeme" in out and "Toplam (KDV dahil) 1.180 TL" in out


def test_taranmis_pdf_icerik_uydurulmaz(tmp_path):
    out = documents.extract(make_pdf(tmp_path / "tarama.pdf", [""]))
    assert "okunabilir metin yok" in out and "taranmış" in out


def test_bozuk_ve_desteklenmeyen_belge_anlasilir_hata(tmp_path):
    bad = tmp_path / "bozuk.docx"
    bad.write_bytes(b"bu bir zip degil")
    with pytest.raises(documents.DocumentError, match="okunamadı"):
        documents.extract(bad)
    with pytest.raises(documents.DocumentError, match="Desteklenmeyen"):
        documents.extract(tmp_path / "x.odt")
    assert documents.is_document("A.PDF") and not documents.is_document("a.txt")


def test_ajan_read_file_belgeyi_okur_yazamaz(tmp_path):
    make_docx(tmp_path / "rapor.docx")
    tb = ToolBox(Workspace(tmp_path))
    out = tb.read_file("rapor.docx")
    assert "belge metne çevrildi — salt okunur" in out and "Aylık Satış Raporu" in out
    with pytest.raises(ToolError, match="metin olarak yazılamaz"):
        tb.prepare_write("cikti.docx", "düz metin")
    with pytest.raises(ToolError):
        tb.prepare_edit("rapor.docx", "Aylık", "Yıllık", False)            # belge düzenlenemez (ikili)
    tb.prepare_write("cikti.md", "# rapor")                               # tetiklenmeyen: düz metin serbest (R-22)


def test_sohbet_eki_belge_icerigi_modele_gider(win, tmp_path):
    app, w = win
    s = w.session
    client = Client()
    w.ctx.make_client = lambda log_sink=None: client
    s.new_session()
    s.welcome._choose(None)
    pdf = make_pdf(tmp_path / "teklif.pdf", ["Teklif tutari 45.000 TL Ödeme 30 gün"])
    s.add_files([str(make_docx(tmp_path / "rapor.docx")), str(pdf)])
    s.composer._submit()
    assert _wait(app, lambda: not s.running and client.calls)
    content = [m for m in client.calls[0]["messages"] if m["role"] == "user"][-1]["content"]
    assert "### rapor.docx" in content and "| Kadıköy | 125.000 |" in content and "ikili dosya" not in content
    assert "### teklif.pdf" in content and "45.000 TL" in content and "--- Sayfa 1 ---" in content
