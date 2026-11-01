"""Arayüz okunurluk denetimi (kontrast) — her ekran, iki tema.

Kullanım:
    .venv\\Scripts\\python.exe tools\\ui_denetim.py <cikti_klasoru> [koyu|açık|ikisi] [--goruntu]

Her ekranı (oturum, karşılama, tüm sayfalar, Ayarlar'ın tamamı kaydırılarak, sağ panelin
tüm sekmeleri, örnek mesaj/araç/onay/eylem kartları) açar; görünür her düğme, etiket,
onay kutusu ve giriş alanı için PENCERE görüntüsünden yazı/simge rengi ile arka plan
rengi arasındaki WCAG kontrast oranını ölçer.

  < 3.0  → HATA  (yazı neredeyse görünmüyor; düğme/simge için de alt sınır)
  < 4.5  → UYARI (normal metin için WCAG AA altı)
Devre dışı (disabled) bileşenler WCAG gereği ölçüm dışıdır, yalnız "pasif" diye sayılır.

Çıktı: <klasör>/denetim_<tema>.json ve --goruntu ile hatalı bileşenleri kırmızı çerçeveli
ekran görüntüleri. Gerçek API çağrısı YAPMAZ. QT_QPA_PLATFORM verilmezse offscreen kullanılır
(yazılar kutucuk çizilir ama renkleri gerçektir, ölçüm geçerlidir).
Kullanıcı bildirimi 2026-11-01: açık modda bazı düğmeler neredeyse görünmüyor; Ayarlar'daki
bazı sabit yazılar tema değişince okunmuyor.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HATA_ESIK = 3.0
UYARI_ESIK = 4.5


# ---- renk ölçümü -----------------------------------------------------------------------------


def _lum(rgb: tuple[int, int, int]) -> float:
    def ch(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def measure(img, x: int, y: int, w: int, h: int, short: bool = False) -> tuple[float, tuple, tuple] | None:
    """Bölgedeki baskın arka plan ile en zıt belirgin ön plan rengi arasındaki oran."""
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(img.width(), x + w), min(img.height(), y + h)
    if x1 - x0 < 6 or y1 - y0 < 6:
        return None
    counts: Counter = Counter()
    step = 1 if (x1 - x0) * (y1 - y0) < 60_000 else 2
    for yy in range(y0, y1, step):
        for xx in range(x0, x1, step):
            c = img.pixelColor(xx, yy)
            counts[(c.red(), c.green(), c.blue())] += 1
    total = sum(counts.values())
    bg, _ = counts.most_common(1)[0]
    # Windows yazıyı ClearType ile çizer: harf pikselleri yüzlerce ara renge bölünür, tek bir
    # renk eşiği geçemez. Bu yüzden "en az N pikselin ulaştığı kontrast" ölçülür (göze görünen
    # yazı rengi; birkaç kenar/gölge pikseli sonucu şişirmez).
    need = max(6, min(int(total * 0.0015), 30))
    if short:
        need = 3                       # tek karakterlik içerik (ör. "3"): birkaç çekirdek piksel yeter
    scored = sorted(((contrast(col, bg), n, col) for col, n in counts.items() if col != bg), reverse=True)
    acc = 0
    for r, n, col in scored:
        acc += n
        if acc >= need:
            if r < 1.05:
                return None            # boş alan (yazısız)
            return round(r, 2), bg, col
    return None


# ---- gezinme ve ölçüm -------------------------------------------------------------------------


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    tema_arg = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "ikisi"
    goruntu = "--goruntu" in sys.argv
    temalar = ["açık", "koyu"] if tema_arg == "ikisi" else [tema_arg]
    toplam_hata = 0
    for tema in temalar:
        bulgular = denetle(tema, out, goruntu)
        hatalar = [b for b in bulgular if b["duzey"] in ("HATA", "KESIK")]
        toplam_hata += len(hatalar)
        (out / f"denetim_{tema}.json").write_text(json.dumps(bulgular, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
        print(f"[{tema}] HATA {sum(b['duzey'] == 'HATA' for b in bulgular)} · KESIK "
              f"{sum(b['duzey'] == 'KESIK' for b in bulgular)} · UYARI {sum(b['duzey'] == 'UYARI' for b in bulgular)}")
        for b in hatalar[:60]:
            print(f"   {b['ekran']:<22} {b['tur']:<12} {b['oran']:>5}  {b['metin'][:50]!r}  ({b['ad']})")
    return 1 if toplam_hata else 0


def denetle(tema: str, out: Path, goruntu: bool) -> list[dict]:
    data = Path(tempfile.mkdtemp(prefix="evren-denetim-"))
    (data / "config.json").write_text(json.dumps({"theme": tema}), encoding="utf-8")
    os.environ["EVREN_STUDIO_DATA_DIR"] = str(data)

    from PySide6.QtCore import QPoint, QRect, Qt
    from PySide6.QtGui import QColor, QPainter, QPen
    from PySide6.QtWidgets import (
        QAbstractButton, QAbstractScrollArea, QAbstractSpinBox, QApplication, QCheckBox,
        QComboBox, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QRadioButton, QTabBar,
        QTextEdit,
    )

    app = QApplication.instance() or QApplication([])
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.resize(1400, 900)
    w.show()

    def pump(t: float = 0.3) -> None:
        end = time.monotonic() + t
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.01)

    bulgular: list[dict] = []
    gorulen: set[tuple] = set()
    gercek_cizim = os.environ.get("QT_QPA_PLATFORM", "") == "windows"

    def tur_adi(wd) -> str | None:
        if isinstance(wd, QCheckBox):
            return "onay_kutusu"
        if isinstance(wd, QRadioButton):
            return "secenek"
        if isinstance(wd, QAbstractButton):
            return "dugme"
        if isinstance(wd, QLabel):
            return "etiket" if (wd.text() or "").strip() else ("simge" if wd.pixmap() and not wd.pixmap().isNull() else None)
        if isinstance(wd, QLineEdit):
            return "giris"
        if isinstance(wd, (QComboBox, QAbstractSpinBox)):
            return "secim"
        if isinstance(wd, QTabBar):
            return "sekme"
        return None

    def olc(ekran: str) -> None:
        pump(0.25)
        img = w.grab().toImage()
        hata_kutulari = []
        for wd in w.findChildren(object):
            tur = tur_adi(wd) if hasattr(wd, "isVisible") else None
            if tur is None or not wd.isVisible() or wd.window() is not w:
                continue
            if wd.width() < 8 or wd.height() < 8:
                continue
            p = wd.mapTo(w, QPoint(0, 0))
            r = QRect(p.x(), p.y(), wd.width(), wd.height()).intersected(QRect(0, 0, img.width(), img.height()))
            if r.width() < 8 or r.height() < 8:
                continue
            # kaydırma alanının dışında kalan (görünmeyen) kısmı ölçme
            par = wd.parentWidget()
            while par is not None and par is not w:
                if isinstance(par, QAbstractScrollArea):
                    vp = par.viewport()
                    vpr = QRect(vp.mapTo(w, QPoint(0, 0)), vp.size())
                    r = r.intersected(vpr)
                par = par.parentWidget()
            if r.width() < 8 or r.height() < 8:
                continue
            metin = ""
            for attr in ("text", "placeholderText", "currentText"):
                f = getattr(wd, attr, None)
                if callable(f):
                    try:
                        metin = str(f() or "")
                    except TypeError:
                        metin = ""
                    if metin:
                        break
            if not metin:
                metin = wd.toolTip() or ""
            if isinstance(wd, QAbstractSpinBox):
                continue                       # içindeki giriş alanı (qt_spinbox_lineedit) ölçülür
            # KESİK: yazı bileşene sığmıyor (yarıda kalıyor). Düğme/onay kutusu: en küçük boyut
            # ipucundan dar; tek satırlık etiket: en uzun satır içerik genişliğinden uzun.
            kesik = False
            # offscreen'de yazı kutucuklarla çizilir, genişlikler gerçek değildir → yalnız gerçek çizimde
            if gercek_cizim and wd.isEnabled() and metin.strip() and not metin.endswith("…"):
                if isinstance(wd, QAbstractButton) and not isinstance(wd, QTabBar):
                    kesik = wd.width() + 2 < wd.minimumSizeHint().width()
                elif isinstance(wd, QLabel) and not wd.wordWrap() and wd.textFormat() != Qt.RichText \
                        and "<" not in metin:
                    satir = max(metin.splitlines() or [""], key=len)
                    kesik = wd.fontMetrics().horizontalAdvance(satir) > wd.contentsRect().width() + 2
            if kesik:
                kanahtar = ("KESIK", ekran.split("/")[0], type(wd).__name__, metin[:40])
                if kanahtar not in gorulen:
                    gorulen.add(kanahtar)
                    bulgular.append({
                        "tema": tema, "ekran": ekran, "tur": tur, "duzey": "KESIK", "oran": 0,
                        "metin": metin.replace("\n", " ")[:120], "ad": wd.objectName() or type(wd).__name__,
                        "rol": "", "arka": "", "on": "", "konum": [r.x(), r.y(), r.width(), r.height()],
                    })
                    hata_kutulari.append(r)
            sonuc = measure(img, r.x(), r.y(), r.width(), r.height(), short=len(metin.strip()) <= 2)
            if sonuc is None:
                continue
            oran, bg, fg = sonuc
            anahtar = (ekran.split("/")[0], type(wd).__name__, metin[:40], wd.objectName())
            if anahtar in gorulen:
                continue
            gorulen.add(anahtar)
            pasif = not wd.isEnabled()
            simge_esik = HATA_ESIK
            if pasif:
                duzey = "PASIF"
            elif oran < HATA_ESIK:
                duzey = "HATA"
            elif oran < UYARI_ESIK and tur in ("etiket", "giris", "secim", "onay_kutusu", "secenek"):
                duzey = "UYARI"
            else:
                duzey = "TAMAM"
            if duzey in ("HATA", "UYARI", "PASIF"):
                bulgular.append({
                    "tema": tema, "ekran": ekran, "tur": tur, "duzey": duzey, "oran": oran,
                    "metin": metin.replace("\n", " ")[:120], "ad": wd.objectName() or type(wd).__name__,
                    "rol": str(wd.property("role") or wd.property("variant") or ""),
                    "arka": "#%02x%02x%02x" % bg, "on": "#%02x%02x%02x" % fg,
                    "konum": [r.x(), r.y(), r.width(), r.height()],
                })
                if duzey == "HATA":
                    hata_kutulari.append(r)
            _ = simge_esik
        if goruntu:
            pix = w.grab()
            if hata_kutulari:
                pt = QPainter(pix)
                pt.setPen(QPen(QColor("#ff0000"), 2))
                for r in hata_kutulari:
                    pt.drawRect(r.adjusted(-1, -1, 1, 1))
                pt.end()
            pix.save(str(out / f"{tema}_{ekran.replace('/', '_')}.png"))

    def kaydir_ve_olc(ekran: str, sayfa) -> None:
        alanlar = [a for a in sayfa.findChildren(QAbstractScrollArea)
                   if a.isVisible() and a.verticalScrollBar().maximum() > 0
                   and not isinstance(a, (QTextEdit, QPlainTextEdit))]
        olc(ekran)
        for a in alanlar[:2]:
            sb = a.verticalScrollBar()
            adim = max(1, int(a.viewport().height() * 0.8))
            v, i = 0, 1
            while v < sb.maximum() and i < 25:
                v = min(sb.maximum(), v + adim)
                sb.setValue(v)
                olc(f"{ekran}/kaydir{i}")
                i += 1
            sb.setValue(0)

    # 1) karşılama
    w.show_sessions()
    olc("karsilama")
    # 2) proje oturumu + örnek içerik (mesaj, araç kartı, onay, eylem kartı, not)
    proj = data / "proje"
    proj.mkdir()
    (proj / "a.py").write_text("x = 1\n", encoding="utf-8")
    sv = w.session
    sv.welcome._choose(str(proj))
    sid = sv._ensure_session("Denetim oturumu")
    db = sv.ctx.db
    db.add_session_message(sid, "user", "a.py dosyasında x'i 2 yap ve testleri çalıştır.")
    db.add_session_message(sid, "assistant", "Dosyayı okuyup düzenliyorum. **Kalın** ve `kod` örneği.",
                           tool_calls=[{"id": "c1", "name": "read_file", "arguments": json.dumps({"path": "a.py"})},
                                       {"id": "c2", "name": "run_command",
                                        "arguments": json.dumps({"command": "python -m pytest -q"})}])
    db.add_session_message(sid, "tool", "x = 1", tool_call_id="c1", name="read_file",
                           meta={"summary": "Okundu: a.py"})
    db.add_session_message(sid, "tool", "1 failed", tool_call_id="c2", name="run_command",
                           meta={"summary": "Çalıştırıldı: python -m pytest -q (çıkış 1)", "error": True})
    db.add_session_message(sid, "assistant", "## Özet\n\n- madde\n\n```python\nx = 2\n```\n\nTamamlandı.")
    sv.open_session(sid)
    from evren_studio.agent.runner import ApprovalRequest, ToolCall
    from evren_studio.ui.transcript import ActionCard, ApprovalWidget, ErrorCard, NoteWidget

    req = ApprovalRequest(ToolCall("c9", "run_command", "{}"), "exec", "Komut çalıştırılsın mı?",
                          "pip install requests", prefix="pip", reason="Paket kurma")
    sv.transcript.add(ApprovalWidget(req))
    sv.transcript.add(ActionCard("Bu tur 1 dosyayı değiştirdi", ["• a.py"],
                                 [("Turu geri al", lambda: None, "ghost")], icon_name="file"))
    sv.transcript.add(ActionCard("İstenmemiş olabilecek değişiklik: 1 dosya", ["• tema.py — istenmedi"],
                                 [("Kapsam dışını geri al", lambda: None, "danger"), ("Sorun yok", lambda: None, "ghost")],
                                 icon_name="alert", warn=True))
    sv.transcript.add(ErrorCard("İstek başarısız", ["Örnek hata satırı"], [("Yeniden dene", lambda: None)]))
    sv.transcript.add(NoteWidget("Örnek bilgi notu", "spark"))
    sv.transcript.scroll_to_bottom()
    kaydir_ve_olc("oturum", sv)
    # komut listesi açık
    sv.composer.set_text("/")
    olc("oturum_komut_listesi")
    sv.composer.hide_popup()
    sv.composer.edit.clear()
    # çalışma çubuğu
    sv.composer.set_running(True)
    sv.composer.set_run_status("auto-pro  yanıt üretiyor  ·  3,4 sn")
    olc("oturum_calisiyor")
    sv.composer.set_running(False)
    sv.composer.set_run_status(None)
    # 3) sağ panel sekmeleri
    w.panel.setVisible(True)
    for ad in ("todos", "changes", "files", "terminal", "work", "git"):
        w.panel.show_tab(ad)
        olc(f"panel_{ad}")
    # 4) tüm sayfalar (Ayarlar dahil, kaydırılarak)
    for key, sayfa in w.pages.items():
        w.show_page(key)
        pump(0.6)
        kaydir_ve_olc(f"sayfa_{key}", sayfa)
    w.close()
    return sorted(bulgular, key=lambda b: (b["duzey"] != "HATA", b["oran"]))


if __name__ == "__main__":
    raise SystemExit(main())
