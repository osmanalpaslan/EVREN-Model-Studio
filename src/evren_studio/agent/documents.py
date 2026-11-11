"""PDF, Word (.docx) ve PowerPoint (.pptx) belgelerini modelin okuyacağı düz metne çevirir (Qt'siz).

Madde 20 A3 (2026-11-11, docs/knowledge/REPO_TARAMASI_2026-11.md): uygulama bu belgeleri hiç okuyamıyordu — ajanın
read_file'ı "ikili dosya" diye reddediyor, sohbet eki "içerik eklenmedi" diye gidiyordu. Microsoft MarkItDown'ın
yaklaşımı; çekirdeği ağır `magika` (ML) getirdiği için onun kullandığı küçük kütüphaneler doğrudan: pdfminer.six (MIT),
python-docx (MIT), python-pptx (MIT).

Çıktı: başlıklar `#`, tablolar Markdown tablo, PDF'de `--- Sayfa N ---`, sunumda `## Slayt N` ve konuşmacı notları.
YALNIZ OKUMA: bu dosyalar düzenleme araçlarına açılmaz (metne çevrilmiş belgeyi geri yazmak dosyayı bozar).
Taranmış (yalnız görüntü) PDF'de metin katmanı yoktur → açık bir not döner, içerik uydurulmaz.
"""
from __future__ import annotations

from pathlib import Path

DOC_SUFFIXES = {".pdf", ".docx", ".pptx"}
MAX_DOC_BYTES = 50 * 1024 * 1024          # 50 MB üstü belge açılmaz (bellek/süre)
MAX_PDF_PAGES = 300
MAX_CHARS = 400_000                       # modele gidecek en çok metin (read_file ayrıca satır sınırı uygular)


class DocumentError(Exception):
    """Kullanıcıya/modele gösterilecek Türkçe hata."""


def is_document(path: str | Path) -> bool:
    return Path(path).suffix.lower() in DOC_SUFFIXES


def extract(path: str | Path) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in DOC_SUFFIXES:
        raise DocumentError(f"Desteklenmeyen belge türü: {ext}")
    try:
        size = p.stat().st_size
    except OSError as exc:
        raise DocumentError(f"Belge okunamadı: {exc}") from exc
    if size > MAX_DOC_BYTES:
        raise DocumentError(f"Belge çok büyük ({size // (1024 * 1024)} MB; sınır {MAX_DOC_BYTES // (1024 * 1024)} MB).")
    try:
        text = {".pdf": _pdf, ".docx": _docx, ".pptx": _pptx}[ext](p)
    except DocumentError:
        raise
    except Exception as exc:              # bozuk/şifreli/beklenmeyen biçim: modele anlaşılır hata
        raise DocumentError(f"{p.name} okunamadı ({type(exc).__name__}: {str(exc)[:200]}). Dosya bozuk, şifreli ya da "
                            "beklenmeyen biçimde olabilir.") from exc
    text = text.strip()
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + f"\n\n⚠ KISALTILDI: belge {MAX_CHARS:,} karakterden uzun; kalanı gösterilmedi."
    return text


# ---- PDF -----------------------------------------------------------------------------------------------------------

def _pdf(p: Path) -> str:
    from pdfminer.high_level import extract_text

    raw = extract_text(str(p), maxpages=MAX_PDF_PAGES)
    pages = raw.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    out = [f"--- Sayfa {i} ---\n{pg.strip()}" for i, pg in enumerate(pages, 1) if pg.strip()]
    if not out:
        return (f"(Bu PDF'te okunabilir metin yok: {len(pages)} sayfa. Büyük olasılıkla taranmış görüntü — metin "
                "katmanı olmadan içerik okunamaz. Görsel olarak eklerseniz görsel okuyabilen motor bakabilir.)")
    note = f"\n\n⚠ İlk {MAX_PDF_PAGES} sayfa okundu." if len(pages) >= MAX_PDF_PAGES else ""
    return "\n\n".join(out) + note


# ---- Word -----------------------------------------------------------------------------------------------------------

def _table_md(rows: list[list[str]]) -> str:
    rows = [[c.replace("\n", " ").replace("|", "\\|").strip() for c in r] for r in rows if any(c.strip() for c in r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    head = "| " + " | ".join(rows[0]) + " |"
    sep = "|" + "---|" * width
    body = ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join([head, sep, *body])


def _docx(p: Path) -> str:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = docx.Document(str(p))
    out: list[str] = []
    for child in d.element.body.iterchildren():           # paragraf ve tabloları BELGEDEKİ SIRAYLA
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = Paragraph(child, d)
            text = para.text.strip()
            if not text:
                continue
            style = (para.style.name if para.style is not None else "") or ""
            if style.lower().startswith(("heading", "başlık")) and style[-1:].isdigit():
                out.append("#" * min(6, int(style[-1])) + " " + text)
            elif style.lower() in ("title", "konu başlığı"):
                out.append("# " + text)
            elif "list" in style.lower() or "liste" in style.lower():
                out.append("- " + text)
            else:
                out.append(text)
        elif tag == "tbl":
            t = Table(child, d)
            md = _table_md([[cell.text for cell in row.cells] for row in t.rows])
            if md:
                out.append(md)
    return "\n\n".join(out) if out else "(Belgede metin yok.)"


# ---- PowerPoint -------------------------------------------------------------------------------------------------------

def _pptx(p: Path) -> str:
    from pptx import Presentation

    prs = Presentation(str(p))
    out: list[str] = []
    for i, slide in enumerate(prs.slides, 1):
        title = ""
        if slide.shapes.title is not None and slide.shapes.title.has_text_frame:
            title = slide.shapes.title.text_frame.text.strip()
        parts = [f"## Slayt {i}" + (f": {title}" if title else "")]
        for shape in slide.shapes:
            if shape == slide.shapes.title:
                continue
            if getattr(shape, "has_table", False) and shape.has_table:
                md = _table_md([[c.text for c in row.cells] for row in shape.table.rows])
                if md:
                    parts.append(md)
            elif getattr(shape, "has_text_frame", False) and shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    t = "".join(r.text for r in para.runs).strip()
                    if t:
                        parts.append(("  " * para.level) + "- " + t)
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip() if slide.notes_slide.notes_text_frame else ""
            if notes:
                parts.append(f"(Konuşmacı notu: {notes})")
        out.append("\n".join(parts))
    return "\n\n".join(out) if out else "(Sunumda slayt yok.)"
