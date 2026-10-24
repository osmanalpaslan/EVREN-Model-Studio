"""F3 #1 tablo inceleme aracı (`read_table`): Excel (.xlsx/.xlsm) ve CSV/TSV dosyalarının yapısını gösterir (Qt'siz).

Neden: `read_file` Excel açamıyordu (ikili dosya); hesap kapama oturumunda ajan her görevde önce betik yazıp
sayfa/başlık bulmak için birkaç adım harcadı. Bu araç tek adımda sayfalar, boyut, başlık satırı ve ilk satırları
verir. Yalnız standart kütüphane (zipfile + XML akışı): uygulamanın ortamında openpyxl yok, büyük dosyada da bellek
şişmez. Eski .xls (BIFF) okunmaz — kullanıcıya/ajana pandas/xlrd ile betik önerilir.
Hesaplama için DEĞİL: toplam/sayım gibi işler yine betikle yapılmalı (bkz. router.ROLE_HINTS["veri"]).
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MAX_ROWS = 15                   # gösterilecek ilk satır sayısı (başlık dahil)
MAX_ROWS_LIMIT = 60
MAX_COLS = 30
MAX_CELL = 60
MAX_FILE_BYTES = 80 * 1024 * 1024
TABLE_SUFFIXES = {".xlsx", ".xlsm", ".csv", ".tsv", ".txt"}

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
       "pr": "http://schemas.openxmlformats.org/package/2006/relationships"}
_M = "{%s}" % _NS["m"]


class TableError(Exception):
    pass


def _cell(v) -> str:
    s = "" if v is None else str(v)
    s = s.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return s if len(s) <= MAX_CELL else s[:MAX_CELL - 1] + "…"


def _col_index(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def _col_name(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _render(rows: list[list[str]], total_rows: int, total_cols: int, shown_from: int = 1) -> list[str]:
    width = min(total_cols, MAX_COLS)
    out = ["| satır | " + " | ".join(_col_name(i) for i in range(width)) + " |"]
    for k, r in enumerate(rows):
        cells = [_cell(r[i]) if i < len(r) else "" for i in range(width)]
        out.append(f"| {shown_from + k} | " + " | ".join(cells) + " |")
    if total_cols > MAX_COLS:
        out.append(f"(… {total_cols - MAX_COLS} sütun daha gösterilmedi)")
    if total_rows > len(rows):
        out.append(f"(… {total_rows - len(rows)} satır daha; toplam {total_rows} dolu satır)")
    return out


# ---- xlsx ------------------------------------------------------------------------------------

def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    try:
        data = z.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    out = []
    for si in ET.fromstring(data).iter(_M + "si"):
        out.append("".join(t.text or "" for t in si.iter(_M + "t")))
    return out


def _sheets(z: zipfile.ZipFile) -> list[tuple[str, str]]:
    """[(sayfa adı, zip içi yol)]"""
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = {r.get("Id"): r.get("Target") for r in rels.iter("{%s}Relationship" % _NS["pr"])}
    out = []
    for s in wb.iter(_M + "sheet"):
        rid = s.get("{%s}id" % _NS["r"])
        t = (target.get(rid) or "").lstrip("/")
        path = t if t.startswith("xl/") else "xl/" + t
        out.append((s.get("name") or "?", path))
    return out


def _date_styles(z: zipfile.ZipFile) -> set[int]:
    """Tarih biçimli hücre stil numaraları (Excel tarihleri sayı olarak saklar)."""
    try:
        st = ET.fromstring(z.read("xl/styles.xml"))
    except KeyError:
        return set()
    custom = {int(n.get("numFmtId")): (n.get("formatCode") or "").lower() for n in st.iter(_M + "numFmt")}
    builtin_dates = set(range(14, 23)) | {45, 46, 47}
    out = set()
    xfs = st.find(_M + "cellXfs")
    for i, xf in enumerate(xfs.iter(_M + "xf") if xfs is not None else []):
        fid = int(xf.get("numFmtId") or 0)
        code = custom.get(fid, "")
        if fid in builtin_dates or (code and re.search(r"[dmy]", re.sub(r"\[[^\]]*\]|\"[^\"]*\"", "", code))):
            out.add(i)
    return out


def _excel_date(v: str) -> str:
    from datetime import datetime, timedelta

    try:
        f = float(v)
    except ValueError:
        return v
    d = datetime(1899, 12, 30) + timedelta(days=f)
    return d.strftime("%Y-%m-%d") if f == int(f) else d.strftime("%Y-%m-%d %H:%M")


def _read_sheet(z: zipfile.ZipFile, path: str, sst: list[str], dates: set[int], keep: int):
    """(ilk `keep` dolu satır, dolu satır sayısı, sütun sayısı)."""
    rows: list[list[str]] = []
    count = 0
    max_col = 0
    with z.open(path) as f:
        for _ev, el in ET.iterparse(f):
            if el.tag != _M + "row":
                continue
            vals: dict[int, str] = {}
            for c in el.iter(_M + "c"):
                ref = c.get("r") or ""
                idx = _col_index(ref) if ref else len(vals)
                t = c.get("t")
                v = c.find(_M + "v")
                if t == "s" and v is not None:
                    text = sst[int(v.text)] if v.text and int(v.text) < len(sst) else ""
                elif t == "inlineStr":
                    text = "".join(x.text or "" for x in c.iter(_M + "t"))
                elif t == "b" and v is not None:
                    text = "DOĞRU" if v.text == "1" else "YANLIŞ"
                elif v is not None and v.text is not None:
                    text = v.text
                    if t not in ("str", "e") and int(c.get("s") or 0) in dates:
                        text = _excel_date(text)
                else:
                    text = ""
                if text != "":
                    vals[idx] = text
            if vals:
                count += 1
                max_col = max(max_col, max(vals) + 1)
                if len(rows) < keep:
                    rows.append([vals.get(i, "") for i in range(max(vals) + 1)])
            el.clear()
    return rows, count, max_col


def describe_xlsx(p: Path, sheet: str | None = None, max_rows: int = MAX_ROWS) -> str:
    try:
        z = zipfile.ZipFile(p)
    except zipfile.BadZipFile as exc:
        raise TableError(f"Excel dosyası açılamadı (bozuk veya şifreli olabilir): {exc}") from exc
    with z:
        sheets = _sheets(z)
        if not sheets:
            raise TableError("Dosyada sayfa bulunamadı.")
        sst = _shared_strings(z)
        dates = _date_styles(z)
        names = [n for n, _ in sheets]
        if sheet and sheet not in names:
            raise TableError(f"Sayfa bulunamadı: {sheet}. Sayfalar: {', '.join(names)}")
        lines = [f"{p.name} — Excel, {len(sheets)} sayfa: " + ", ".join(names)]
        chosen = [s for s in sheets if s[0] == sheet] if sheet else sheets[:3]
        for name, path in chosen:
            try:
                rows, count, cols = _read_sheet(z, path, sst, dates, max_rows)
            except KeyError:
                lines.append(f"\n## {name}: okunamadı (sayfa dosyası yok)")
                continue
            lines.append(f"\n## Sayfa: {name} — {count} dolu satır, {cols} sütun")
            if rows:
                lines.extend(_render(rows, count, cols))
            else:
                lines.append("(boş sayfa)")
        if not sheet and len(sheets) > 3:
            lines.append(f"\n(Diğer {len(sheets) - 3} sayfa için sheet parametresiyle tekrar çağır.)")
    return "\n".join(lines)


# ---- csv -------------------------------------------------------------------------------------

def _decode(data: bytes) -> tuple[str, str]:
    for enc in ("utf-8-sig", "cp1254", "latin-1"):
        try:
            return data.decode(enc), ("utf-8" + (" (BOM)" if data.startswith(b"\xef\xbb\xbf") else "")
                                      if enc == "utf-8-sig" else enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "bilinmiyor"


def describe_csv(p: Path, max_rows: int = MAX_ROWS) -> str:
    data = p.read_bytes()
    text, enc = _decode(data)
    sample = text[:20_000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        delim = dialect.delimiter
    except csv.Error:
        delim = "\t" if p.suffix.lower() == ".tsv" else ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows, count, cols = [], 0, 0
    for r in reader:
        if not any(c.strip() for c in r):
            continue
        count += 1
        cols = max(cols, len(r))
        if len(rows) < max_rows:
            rows.append(r)
    name = {";": "noktalı virgül", ",": "virgül", "\t": "sekme", "|": "dik çizgi"}.get(delim, repr(delim))
    lines = [f"{p.name} — CSV, ayırıcı: {name}, kodlama: {enc}, {count} dolu satır, {cols} sütun"]
    lines.extend(_render(rows, count, cols) if rows else ["(boş dosya)"])
    if any("," in c and re.fullmatch(r"-?\d{1,3}(\.\d{3})*,\d+", c.strip()) for r in rows[1:] for c in r):
        lines.append("Not: ondalık ayırıcı virgül görünüyor (Türkçe biçim); sayıya çevirirken ',' → '.' gerekir.")
    return "\n".join(lines)


def preview(p: Path, sheet: str | None = None, max_rows: int = 200) -> dict:
    """F5 #9 arayüz önizlemesi: {"sheets": [...], "sheet": ad, "rows": [[...]], "total": n, "cols": n}.
    Hata → TableError (desteklenmeyen tür, bozuk dosya)."""
    suffix = p.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        try:
            z = zipfile.ZipFile(p)
        except zipfile.BadZipFile as exc:
            raise TableError(f"Excel dosyası açılamadı: {exc}") from exc
        with z:
            sheets = _sheets(z)
            if not sheets:
                raise TableError("Dosyada sayfa bulunamadı.")
            name, path = next(((n, q) for n, q in sheets if n == sheet), sheets[0])
            rows, total, cols = _read_sheet(z, path, _shared_strings(z), _date_styles(z), max_rows)
        return {"sheets": [n for n, _ in sheets], "sheet": name, "rows": rows, "total": total, "cols": cols}
    if suffix in (".csv", ".tsv", ".txt"):
        text, _enc = _decode(p.read_bytes())
        try:
            delim = csv.Sniffer().sniff(text[:20_000], delimiters=";,\t|").delimiter
        except csv.Error:
            delim = "\t" if suffix == ".tsv" else ","
        rows, total, cols = [], 0, 0
        for r in csv.reader(io.StringIO(text), delimiter=delim):
            if not any(c.strip() for c in r):
                continue
            total += 1
            cols = max(cols, len(r))
            if len(rows) < max_rows:
                rows.append(r)
        return {"sheets": [], "sheet": "", "rows": rows, "total": total, "cols": cols}
    raise TableError(f"Desteklenmeyen tablo türü: {suffix}")


def describe(p: Path, sheet: str | None = None, max_rows: int | None = None) -> str:
    """Dosya türüne göre tablo özeti. Hata → TableError."""
    n = max(2, min(int(max_rows or MAX_ROWS), MAX_ROWS_LIMIT))
    suffix = p.suffix.lower()
    try:
        size = p.stat().st_size
    except OSError as exc:
        raise TableError(f"Dosya okunamadı: {exc}") from exc
    if size > MAX_FILE_BYTES:
        raise TableError(f"Dosya çok büyük ({size // (1024 * 1024)} MB); betikle oku.")
    if suffix in (".xlsx", ".xlsm"):
        return describe_xlsx(p, sheet, n)
    if suffix == ".xls":
        raise TableError("Eski .xls biçimi bu araçla okunmaz; pandas/xlrd kuruluysa betikle oku ya da kullanıcıdan "
                         ".xlsx olarak kaydetmesini iste.")
    if suffix in (".csv", ".tsv", ".txt"):
        return describe_csv(p, n)
    raise TableError(f"Desteklenmeyen tablo türü: {suffix or '(uzantısız)'} (xlsx, xlsm, csv, tsv okunur).")
