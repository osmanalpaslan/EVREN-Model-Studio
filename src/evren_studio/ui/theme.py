"""Görsel tema: renk belirteçleri, yazı tipleri ve uygulama geneli QSS.

Tüm renkler burada tanımlanır; bileşenler sabit renk yazmaz, `current()`
paletini kullanır. Koyu ve açık tema aynı belirteç adlarını paylaşır.

TASARIM DİLİ (2026-11-12, kullanıcı isteği "güncel iOS tasarım dili"): iOS 27 / Liquid Glass'tan masaüstüne uyarlama —
• kontroller içeriğin üstünde "cam" katman: yazma kutusu, öneri kartları, düğmeler hafif dikey geçişli yüzey +
  ince TANIMLI kenar (iOS 27: gölge yerine belirgin kenar; daha az bulanık, daha okunur);
• hap/kapsül biçimler ve iç içe uyumlu (concentric) köşe yarıçapları: düğme 12, giriş 10, kart 16, yazma kutusu 22;
• iOS anahtarları (switch) onay kutusu yerine; seçim listelerinde daire içinde tik; açılır listede ⌃⌄ işareti;
• sağ panel sekmeleri iOS bölümlü denetim (segmented control); kenar çubuğunda yuvarlak seçim hapı;
• büyük başlıklar Segoe UI Variable Display; iOS sistem renkleri (erişilebilir/artırılmış kontrast varyantları).
Kullanıcı kararları KORUNUR: koyu temada tüm yazı/simge parlak, vurgu beyaz, seçili satır nötr gri (2026-10-19);
açık tema parlak beyaz DEĞİL, yumuşak gri (DepoWise'da seçilen dil, zemin #E6E8EC yakını). Tüm yazı renkleri
yedi zeminde WCAG ile ölçüldü (bkz. tests/test_ios_tasarim.py, R-33).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str             # ana içerik zemini
    sidebar: str        # sol menü
    panel: str          # sağ panel
    surface: str        # kart / giriş kutusu
    surface2: str       # yükseltilmiş yüzey, giriş alanı
    hover: str
    selected: str
    border: str
    border_strong: str
    text: str
    text_dim: str
    text_faint: str
    accent: str
    accent_hover: str
    accent_soft: str
    on_accent: str
    code_bg: str
    code_border: str
    success: str
    danger: str
    warning: str
    add_bg: str
    del_bg: str
    hunk: str
    scrollbar: str
    muted: str          # yalnız yer tutucu yazı ve devre dışı öğe (okunur ama etkin değil)
    # ---- iOS 27 cam dili (2026-11-12) ----
    glass_top: str      # cam yüzey dikey geçişinin üstü (ışık)
    glass_bottom: str   # cam yüzey geçişinin altı
    rim: str            # cam kenarı (tanımlı kenar)
    bubble: str         # kullanıcı mesajı baloncuğu
    thumb: str          # bölümlü denetimde seçili parça
    switch_on: str      # anahtar açık izi (iOS yeşili)
    switch_off: str     # anahtar kapalı izi
    switch_line: str    # kapalı anahtarın kenarı (açık zeminde görünsün)
    knob: str           # anahtar topuzu
    knob_line: str      # topuz kenarı


DARK = Palette(
    name="koyu",
    # iOS koyu sistem zeminleri (systemBackground → secondary/tertiary), masaüstü için siyah biraz yumuşatıldı
    bg="#0F0F11", sidebar="#17171A", panel="#141416",
    surface="#1C1C1E", surface2="#2C2C2E", hover="#262629", selected="#3A3A3C",
    border="#38383A", border_strong="#48484A",
    # Kullanıcı kararı (2026-10-19): koyu temada tüm yazı/düğme/simge "Görevler" başlığı kadar
    # parlak olsun; eski #a2a6af / #6d717a yer yer okunmuyordu. Hiyerarşi boyut ve kalınlıkla kalır.
    text="#F2F2F7", text_dim="#F2F2F7", text_faint="#F2F2F7",
    # Kullanıcı kararı (2026-10-19): koyu temada düğmeler/vurgu mavi değil, yazılarla aynı beyaz;
    # birincil düğme beyaz zemin + koyu yazı, seçili satır nötr gri.
    accent="#F2F2F7", accent_hover="#FFFFFF", accent_soft="#3A3A3C", on_accent="#0F0F11",
    code_bg="#0A0A0C", code_border="#2C2C2E",
    # iOS erişilebilir koyu sistem renkleri (seçili satırda da ≥ 4,5)
    success="#30D158", danger="#FF7B73", warning="#FFB340",
    add_bg="#0F2E1A", del_bg="#3A1517", hunk="#64A8FF",
    scrollbar="#48484A", muted="#ABABB0",
    glass_top="#333336", glass_bottom="#262629", rim="#4A4A4E", bubble="#2C2C2E", thumb="#4A4A4E",
    switch_on="#30D158", switch_off="#3A3A3C", switch_line="#5A5A5E", knob="#FFFFFF", knob_line="#FFFFFF",
)

LIGHT = Palette(
    name="açık",
    # Yumuşak gri (parlak beyaz değil): kartlar zeminden bir ton açık, kenar çubuğu bir ton koyu
    bg="#E9EBEF", sidebar="#DFE2E7", panel="#E4E7EB",
    surface="#F7F8FA", surface2="#EDEFF2", hover="#DADDE3", selected="#CDD3DC",
    border="#D0D5DC", border_strong="#B6BDC7",
    # Okunurluk (2026-11-01 ve 2026-11-07 ölçümleri): ikincil yazılar tüm açık zeminlerde ≥ 4,5 (seçili satır dahil)
    text="#1D2129", text_dim="#454C58", text_faint="#4A515D",
    accent="#0657BB", accent_hover="#054A9E", accent_soft="#D6E4FA", on_accent="#FFFFFF",
    code_bg="#EFF1F4", code_border="#D0D5DC",
    success="#0E6633", danger="#A3221B", warning="#7A4900",
    add_bg="#DDF3E4", del_bg="#FADBD9", hunk="#0657BB",
    scrollbar="#B6BDC7", muted="#535B68",
    glass_top="#FFFFFF", glass_bottom="#F0F2F5", rim="#C3C9D2", bubble="#D9E6FB", thumb="#FFFFFF",
    switch_on="#2E9E4F", switch_off="#C9CED6", switch_line="#8C94A0", knob="#FFFFFF", knob_line="#B6BDC7",
)

_current: Palette = DARK

UI_FONTS = ["Segoe UI Variable Text", "Segoe UI", "Inter", "Arial"]
TITLE_FONTS = ["Segoe UI Variable Display", "Segoe UI Variable Text", "Segoe UI", "Inter", "Arial"]
CODE_FONTS = ["Cascadia Mono", "Cascadia Code", "Consolas", "Courier New"]

# Köşe yarıçapları (iç içe uyum: iç öğe = dış öğe − boşluk)
R_BUTTON, R_FIELD, R_CARD, R_COMPOSER, R_MENU = 12, 10, 16, 22, 14


def current() -> Palette:
    return _current


# ---- tema değişince yenilenecek bileşenler ------------------------------------------------------------------------
# Kullanıcı 2026-11-07: uygulama açıkken koyu → açık geçişte simgeler ve satır içi renkler eski temada kalıyordu
# (sağ üst düğmeler, sol menü, öneri kartı başlıkları neredeyse görünmez). Rengi oluşturulurken sabitlenen her
# bileşen kendini buraya kaydeder; apply_theme her değişimde yeniden boyar. Sahip silinince kayıt kendiliğinden düşer.
_watchers: list[tuple] = []          # (weakref(sahip), fn(sahip, palet), anahtar)


def watch(owner, fn, key: str = "") -> None:
    """`fn(owner, palette)` şimdi ve her tema değişiminde çağrılır (owner yaşadıkça). fn owner'ı YAKALAMAMALI
    (yoksa sahip hiç silinmez); ilk parametreden kullanır. Aynı sahip + `key` ile yeniden kaydedilirse eskisinin
    YERİNE geçer (ör. durum değiştikçe yeniden çizilen simge — kayıtlar birikmesin)."""
    import weakref

    fn(owner, _current)
    if key:
        _watchers[:] = [w for w in _watchers if not (w[2] == key and w[0]() is owner)]
    _watchers.append((weakref.ref(owner), fn, key))
    if len(_watchers) % 256 == 0:
        _prune()


def rich(label, fn, key: str = "rich") -> None:
    """İçinde renk geçen zengin metin, geçerli paletten: `theme.rich(lbl, lambda p: f"<span style='color:{p.text_dim}'>…")`."""
    watch(label, lambda w, p, f=fn: w.setText(f(p)), key)


def style(widget, fn, key: str = "style") -> None:
    """Satır içi stil, geçerli paletten: `theme.style(lbl, lambda p: f"color: {p.warning};")` — tema değişince yenilenir."""
    watch(widget, lambda w, p, f=fn: w.setStyleSheet(f(p)), key)


def _alive(obj) -> bool:
    if obj is None:
        return False
    try:
        import shiboken6

        return shiboken6.isValid(obj)
    except ImportError:          # pragma: no cover
        return True


def _prune() -> None:
    _watchers[:] = [w for w in _watchers if _alive(w[0]())]


def notify_changed() -> int:
    """Kayıtlı bileşenleri geçerli temayla yeniden boyar; yenilenen sayısı."""
    done = 0
    keep = []
    for item in list(_watchers):
        obj = item[0]()
        if not _alive(obj):
            continue
        try:
            item[1](obj, _current)
            done += 1
        except RuntimeError:     # C++ nesnesi o an silinmiş
            continue
        keep.append(item)
    _watchers[:] = keep
    return done


def watcher_count() -> int:
    return len(_watchers)


def palette_for(theme: str) -> Palette:
    return LIGHT if theme in ("açık", "acik", "light") else DARK


def _first_available(candidates: list[str]) -> str:
    from PySide6.QtGui import QGuiApplication

    if QGuiApplication.instance() is None:
        # Yazı tipi veritabanı uygulama nesnesi olmadan sorgulanırsa Qt süreci ÇÖKER (yakalanamaz; 2026-11-12
        # build_qss başlık yazı tipini sorgulamaya başlayınca uygulamasız testte görüldü)
        return candidates[0]
    try:
        families = set(QFontDatabase.families())
    except Exception:
        families = set()
    for c in candidates:
        if c in families:
            return c
    return candidates[-1]


def ui_font_family() -> str:
    return _first_available(UI_FONTS)


def title_font_family() -> str:
    return _first_available(TITLE_FONTS)


def code_font_family() -> str:
    return _first_available(CODE_FONTS)


def code_font(size: int = 10) -> QFont:
    f = QFont(code_font_family())
    f.setStyleHint(QFont.Monospace)
    f.setPointSize(size)
    return f


# ---- QSS görsel varlıkları (SVG) ----------------------------------------------------------------------------------


def _asset(name: str, svg: str) -> str:
    """SVG'yi geçici klasöre bir kez yazar (içerik özeti dosya adında: renk değişince yenisi yazılır); QSS yolu."""
    import tempfile
    from pathlib import Path

    digest = hashlib.sha1(svg.encode("utf-8")).hexdigest()[:10]
    path = Path(tempfile.gettempdir()) / "evren_studio_tema" / f"{name}_{digest}.svg"
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(svg, encoding="utf-8")
        except OSError:
            return ""
    return path.as_posix()


def _check_icon(p: Palette) -> str:
    """Tik işareti (on_accent renginde). Koyu temada vurgu beyaz olunca işaretli kutu içi boş beyaz kare görünüyordu
    (2026-10-19); tik bunu ayırt eder."""
    return _asset("tik", '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3.5 8.5l3 3 6-7" '
                  f'fill="none" stroke="{p.on_accent}" stroke-width="2" stroke-linecap="round" '
                  'stroke-linejoin="round"/></svg>')


def _switch_icon(p: Palette, on: bool, disabled: bool = False) -> str:
    """iOS anahtarı (36×22): iz + topuz. Kapalı izin kenarı açık zeminde de görünür (iOS 27 tanımlı kenar)."""
    track, line = (p.switch_on, p.switch_on) if on else (p.switch_off, p.switch_line)
    cx = 25 if on else 11
    op = "0.45" if disabled else "1"
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="36" height="22" viewBox="0 0 36 22">'
           f'<g opacity="{op}"><rect x="0.75" y="0.75" width="34.5" height="20.5" rx="10.25" fill="{track}" '
           f'stroke="{line}" stroke-width="1.5"/><circle cx="{cx}" cy="11" r="8.25" fill="{p.knob}" '
           f'stroke="{p.knob_line}" stroke-width="0.75"/></g></svg>')
    return _asset(f"anahtar_{'acik' if on else 'kapali'}{'_pasif' if disabled else ''}", svg)


def _circle_check(p: Palette, on: bool) -> str:
    """Seçim listesi göstergesi (iOS çoklu seçim): boş daire / vurgu renginde dolu daire + tik."""
    if on:
        body = (f'<circle cx="9" cy="9" r="8.5" fill="{p.accent}"/><path d="M5.2 9.3l2.6 2.6 5-5.5" fill="none" '
                f'stroke="{p.on_accent}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>')
    else:
        body = f'<circle cx="9" cy="9" r="7.75" fill="none" stroke="{p.border_strong}" stroke-width="1.5"/>'
    return _asset(f"secim_{'acik' if on else 'kapali'}",
                  f'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18">{body}</svg>')


def _chevrons(p: Palette) -> str:
    """Açılır liste işareti (iOS açılır düğmesi ⌃⌄): kutunun seçenek sunduğu görülsün (2026-11-12 analiz: Ayarlar'daki
    açılır listelerde ok görünmüyordu, düz metin kutusu sanılıyordu)."""
    return _asset("acilir", '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="14" viewBox="0 0 10 14">'
                  f'<path d="M2 5.2l3-3 3 3M2 8.8l3 3 3-3" fill="none" stroke="{p.text_dim}" stroke-width="1.5" '
                  'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def _arrow(p: Palette, up: bool) -> str:
    d = "M1.5 5l3.5-3.5 3.5 3.5" if up else "M1.5 1.5l3.5 3.5 3.5-3.5"
    return _asset(f"ok_{'yukari' if up else 'asagi'}",
                  '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="7" viewBox="0 0 10 7">'
                  f'<path d="{d}" fill="none" stroke="{p.text_dim}" stroke-width="1.5" stroke-linecap="round" '
                  'stroke-linejoin="round"/></svg>')


COMPACT_QSS = """
QPushButton {{ padding: 3px 10px; }}
QToolButton[variant="chip"] {{ padding: 2px 8px; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ padding: 2px 8px; }}
QMenu::item {{ padding: 4px 22px 4px 10px; }}
QPushButton[nav="true"] {{ padding: 4px 10px; }}
QTabBar::tab {{ padding: 5px 10px; }}
QFrame#card {{ padding: 0; }}
"""


def build_qss(p: Palette, font_pt: int, compact: bool = False) -> str:
    return _build_qss(p, font_pt) + (COMPACT_QSS.replace("{{", "{").replace("}}", "}") if compact else "")


def _glass(p: Palette) -> str:
    """Cam yüzey: üstte ışık, altta bir ton koyu (iOS 27 Liquid Glass'ın masaüstü karşılığı)."""
    return f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {p.glass_top}, stop:1 {p.glass_bottom})"


def _build_qss(p: Palette, font_pt: int) -> str:
    small = max(font_pt - 1, 8)
    title_family = title_font_family()
    check = _check_icon(p)
    sw_on, sw_off = _switch_icon(p, True), _switch_icon(p, False)
    sw_on_d, sw_off_d = _switch_icon(p, True, True), _switch_icon(p, False, True)
    sel_on, sel_off = _circle_check(p, True), _circle_check(p, False)
    chev, up, down = _chevrons(p), _arrow(p, True), _arrow(p, False)
    glass = _glass(p)
    return f"""
* {{ outline: none; }}
QWidget {{ color: {p.text}; font-size: {font_pt}pt; }}
QMainWindow, QWidget#Root, QWidget#CenterHost, QStackedWidget#CenterStack {{ background: {p.bg}; }}
QToolTip {{ background: {p.surface2}; color: {p.text}; border: 1px solid {p.rim};
           padding: 6px 9px; border-radius: 8px; }}
QLabel {{ background: transparent; }}
QLabel#dim, QLabel[role="dim"] {{ color: {p.text_dim}; }}
QLabel[role="faint"] {{ color: {p.text_faint}; font-size: {small}pt; }}
QLabel[role="warning"] {{ color: {p.warning}; }}
/* iOS büyük başlık */
QLabel#pageTitle, QLabel[role="title"] {{ font-family: "{title_family}"; font-size: {font_pt + 8}pt; font-weight: 700; }}
QLabel[role="h1"] {{ font-family: "{title_family}"; font-size: {font_pt + 5}pt; font-weight: 700; }}
QLabel[role="h2"] {{ font-size: {font_pt + 2}pt; font-weight: 600; }}
QLabel[role="section"] {{ color: {p.text_faint}; font-size: {small}pt; font-weight: 600;
                          padding: 12px 12px 4px 12px; }}

/* ---- düğmeler: cam yüzey + tanımlı kenar ---- */
QPushButton, QToolButton {{
    background: {glass}; color: {p.text}; border: 1px solid {p.border_strong};
    border-radius: {R_BUTTON}px; padding: 6px 14px;
}}
QPushButton:hover, QToolButton:hover {{ background: {p.hover}; border-color: {p.border_strong}; }}
QPushButton:pressed, QToolButton:pressed {{ background: {p.selected}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {p.muted}; background: {p.surface}; border-color: {p.border}; }}
QPushButton[variant="primary"] {{ background: {p.accent}; color: {p.on_accent}; border: 1px solid {p.accent};
                                  font-weight: 600; }}
QPushButton[variant="primary"]:hover {{ background: {p.accent_hover}; border-color: {p.accent_hover}; }}
QPushButton[variant="primary"]:disabled {{ background: {p.selected}; color: {p.muted}; border-color: {p.selected}; }}
QToolButton[variant="ghost"] {{ background: transparent; border: 1px solid transparent; }}
/* Yazılı ikincil düğme: çerçevesiz hâli düz yazı gibi görünüyordu, tıklanabilir olduğu anlaşılmıyordu
   (kullanıcı bildirimi 2026-11-01). Simgeli araç düğmeleri (QToolButton) çerçevesiz kalır. */
QPushButton[variant="ghost"] {{ background: transparent; border: 1px solid {p.border_strong}; }}
QPushButton[variant="ghost"]:hover, QToolButton[variant="ghost"]:hover {{ background: {p.hover}; }}
QPushButton[variant="danger"] {{ background: transparent; color: {p.danger}; border: 1px solid {p.border_strong}; }}
QPushButton[variant="danger"]:hover {{ background: {p.del_bg}; }}
/* Hap (chip): yazma kutusundaki ek/ses/mod/model/derin seçicileri. İnce kenarlı kapsül: 2026-11-12 analizinde düz
   yazı gibi göründükleri, tıklanabilir oldukları anlaşılmadığı görüldü (iOS 27 cam düğmeleri de tanımlı kenarlı). */
QToolButton[variant="chip"] {{ background: transparent; border: 1px solid {p.border}; border-radius: {R_BUTTON}px;
                               padding: 4px 10px; color: {p.text_dim}; }}
QToolButton[variant="chip"]:hover {{ background: {p.hover}; color: {p.text}; border-color: {p.border_strong}; }}
QToolButton[variant="chip"]:checked {{ background: {p.accent_soft}; color: {p.text}; border-color: {p.border_strong}; }}
QPushButton[variant="chip"] {{ background: transparent; border: 1px solid {p.border}; border-radius: {R_BUTTON}px;
                               padding: 4px 12px; color: {p.text_dim}; }}
QPushButton[variant="chip"]:hover {{ background: {p.hover}; color: {p.text}; }}
QPushButton[variant="chip"]:checked {{ background: {p.accent_soft}; color: {p.text}; border-color: {p.accent}; }}
QToolButton[variant="icon"], QPushButton[variant="icon"] {{ background: transparent; border: none;
                                                           border-radius: 9px; padding: 5px; }}
QToolButton[variant="icon"]:hover, QPushButton[variant="icon"]:hover {{ background: {p.hover}; }}
QToolButton[variant="icon"]:checked {{ background: {p.selected}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}
QPushButton#SendButton {{ background: {p.accent}; border: none; border-radius: 15px; padding: 0; }}
QPushButton#SendButton:hover {{ background: {p.accent_hover}; }}
QPushButton#SendButton:disabled {{ background: {p.selected}; }}
QPushButton#SendButton[running="true"] {{ background: {p.text}; }}

/* ---- girişler: dolgulu iOS alanı ---- */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTimeEdit, QDateTimeEdit {{
    background: {p.surface2}; color: {p.text}; border: 1px solid {p.border};
    border-radius: {R_FIELD}px; padding: 5px 9px; selection-background-color: {p.accent_soft};
    selection-color: {p.text};
    placeholder-text-color: {p.muted};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QTimeEdit:focus, QDateTimeEdit:focus {{
    border-color: {p.accent};
}}
QComboBox {{ padding-right: 26px; }}
QComboBox::drop-down {{ border: none; width: 26px; subcontrol-origin: padding; subcontrol-position: center right; }}
QComboBox::down-arrow {{ image: url("{chev}"); width: 10px; height: 14px; }}
QComboBox QAbstractItemView {{ background: {p.surface}; border: 1px solid {p.rim}; border-radius: 10px; padding: 4px;
                               selection-background-color: {p.accent_soft}; selection-color: {p.text}; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QTimeEdit::up-button, QTimeEdit::down-button, QDateTimeEdit::up-button, QDateTimeEdit::down-button {{
    width: 18px; border: none; background: transparent; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow, QTimeEdit::up-arrow, QDateTimeEdit::up-arrow {{
    image: url("{up}"); width: 10px; height: 7px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QTimeEdit::down-arrow, QDateTimeEdit::down-arrow {{
    image: url("{down}"); width: 10px; height: 7px; }}
/* iOS anahtarı (switch) */
QCheckBox {{ spacing: 10px; background: transparent; }}
QCheckBox::indicator {{ width: 36px; height: 22px; border: none; background: transparent; }}
QCheckBox::indicator:unchecked {{ image: url("{sw_off}"); }}
QCheckBox::indicator:checked {{ image: url("{sw_on}"); }}
QCheckBox::indicator:unchecked:disabled {{ image: url("{sw_off_d}"); }}
QCheckBox::indicator:checked:disabled {{ image: url("{sw_on_d}"); }}
/* Seçim listesi: daire içinde tik */
QListView::indicator {{ width: 18px; height: 18px; border: none; background: transparent; }}
QListView::indicator:unchecked {{ image: url("{sel_off}"); }}
QListView::indicator:checked {{ image: url("{sel_on}"); }}

/* ---- menü (iOS bağlam menüsü) ---- */
QMenu {{ background: {p.surface}; border: 1px solid {p.rim}; border-radius: {R_MENU}px; padding: 6px; }}
QMenu::item {{ padding: 7px 28px 7px 12px; border-radius: 8px; }}
QMenu::item:selected {{ background: {p.hover}; }}
QMenu::item:disabled {{ color: {p.muted}; }}
QMenu::separator {{ height: 1px; background: {p.border}; margin: 5px 8px; }}
QMenu::indicator {{ width: 14px; height: 14px; left: 6px; }}
QMenu::indicator:checked {{ image: url("{check}"); background: {p.accent}; border-radius: 4px; }}

/* ---- kaydırma çubukları: ince, yuvarlak ---- */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 3px 1px; }}
QScrollBar::handle:vertical {{ background: {p.scrollbar}; border-radius: 3px; min-height: 36px; margin: 0 2px; }}
QScrollBar::handle:vertical:hover {{ background: {p.text_faint}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 1px 3px; }}
QScrollBar::handle:horizontal {{ background: {p.scrollbar}; border-radius: 3px; min-width: 36px; margin: 2px 0; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---- sol menü (iPadOS kenar çubuğu: yuvarlak seçim hapı) ---- */
QWidget#Sidebar {{ background: {p.sidebar}; border-right: 1px solid {p.border}; }}
QWidget#Sidebar QLineEdit {{ background: {p.surface}; border-radius: {R_FIELD}px; }}
QListWidget#SessionList {{ background: transparent; border: none; padding: 0 6px; }}
QListWidget#SessionList::item {{ border-radius: 10px; padding: 0; margin: 1px 0; }}
QListWidget#SessionList::item:hover {{ background: {p.hover}; }}
QListWidget#SessionList::item:selected {{ background: {p.accent_soft}; }}
QPushButton[nav="true"] {{ background: transparent; border: none; text-align: left; padding: 7px 10px;
                           border-radius: 10px; color: {p.text_dim}; }}
QPushButton[nav="true"]:hover {{ background: {p.hover}; color: {p.text}; }}
QPushButton[nav="true"]:checked {{ background: {p.accent_soft}; color: {p.text}; }}
QPushButton#NewSession {{ text-align: left; padding: 8px 12px; font-weight: 600; background: {glass};
                          border: 1px solid {p.rim}; border-radius: {R_BUTTON}px; }}
QPushButton#NewSession:hover {{ background: {p.hover}; }}

/* ---- Ayarlar menüsü (sade liste, seçili satır yuvarlak hap) ---- */
QListWidget#SettingsNav {{ background: transparent; border: none; outline: none; }}
QListWidget#SettingsNav::item {{ padding: 7px 10px; border-radius: 10px; margin: 1px 0; color: {p.text_dim}; }}
QListWidget#SettingsNav::item:hover {{ background: {p.hover}; color: {p.text}; }}
QListWidget#SettingsNav::item:selected {{ background: {p.accent_soft}; color: {p.text}; }}

/* ---- sağ panel ---- */
QWidget#SidePanel {{ background: {p.panel}; border-left: 1px solid {p.border}; }}
/* iOS bölümlü denetim (segmented control): iz + seçili parça */
QFrame#Segmented {{ background: {p.surface2}; border: 1px solid {p.border}; border-radius: 11px; }}
QFrame#Segmented QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 4px; }}
QFrame#Segmented QToolButton:hover {{ background: {p.hover}; }}
QFrame#Segmented QToolButton:checked {{ background: {p.thumb}; border: 1px solid {p.rim}; }}
QTabWidget#PanelTabs::pane {{ border: none; border-top: 1px solid {p.border}; }}
QTabWidget#PanelTabs > QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: transparent; color: {p.text_dim}; padding: 7px 14px; border: 1px solid transparent;
                border-radius: 9px; margin: 3px 2px; }}
QTabBar::tab:selected {{ color: {p.text}; background: {p.thumb}; border-color: {p.rim}; }}
QTabBar::tab:hover {{ color: {p.text}; }}

/* ---- ağaç / liste / tablo ---- */
QTreeView, QListWidget, QListView, QTableWidget, QTableView {{
    background: transparent; border: none; alternate-background-color: {p.surface};
}}
QTreeView::item, QListView::item {{ padding: 3px 4px; border-radius: 6px; }}
QTreeView::item:hover, QListWidget::item:hover {{ background: {p.hover}; }}
QTreeView::item:selected, QListWidget::item:selected {{ background: {p.selected}; color: {p.text}; }}
QTableWidget {{ gridline-color: {p.border}; border: 1px solid {p.border}; border-radius: 12px; background: {p.surface}; }}
QHeaderView::section {{ background: {p.surface2}; color: {p.text_dim}; border: none;
                        border-bottom: 1px solid {p.border}; padding: 6px 8px; font-weight: 600; }}
QTableCornerButton::section {{ background: {p.surface2}; border: none; }}

/* ---- kartlar (iOS gruplu kutular) ---- */
QFrame#card {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: {R_CARD}px; }}
QFrame#card QLabel {{ background: transparent; }}
QProgressBar {{ background: {p.surface2}; border: none; border-radius: 4px; text-align: center; color: {p.text};
                max-height: 8px; }}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 4px; }}
QSplitter::handle {{ background: {p.border}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

/* ---- sohbet alanı ---- */
QListWidget#CommandPopup {{ background: {p.surface}; border: 1px solid {p.rim};
                            border-radius: {R_MENU}px; padding: 5px; }}
QDialog#CommandPalette {{ background: {p.surface}; border: 1px solid {p.rim}; border-radius: {R_MENU}px; }}
QListWidget#CommandPopup::item {{ padding: 5px 9px; border-radius: 8px; min-height: 20px; }}
QListWidget#CommandPopup::item:hover {{ background: {p.hover}; }}
QListWidget#CommandPopup::item:selected {{ background: {p.accent_soft}; color: {p.text}; }}
QFrame#RunBar {{ background: {p.accent_soft}; border: 1px solid {p.rim}; border-radius: 14px; }}
/* Yazma kutusu: içeriğin üstünde yüzen cam kapsül */
QFrame#Composer {{ background: {glass}; border: 1px solid {p.rim}; border-radius: {R_COMPOSER}px; }}
QFrame#Composer[focus="true"] {{ border-color: {p.accent}; }}
QScrollArea#AttachmentBar, QScrollArea#AttachmentBar > QWidget > QWidget {{ background: transparent; }}
QFrame#AttachmentChip {{ background: {p.surface2}; border: 1px solid {p.rim}; border-radius: 12px; }}
QLabel#AttachmentThumb {{ border-radius: 6px; }}
QToolButton#AttachmentRemove {{ background: transparent; border: none; padding: 1px; border-radius: 8px; }}
QToolButton#AttachmentRemove:hover {{ background: {p.hover}; }}
QFrame#UsagePanel {{ background: {p.surface}; border: 1px solid {p.rim}; border-radius: {R_CARD}px; }}
QPlainTextEdit#ComposerEdit {{ background: transparent; border: none; padding: 4px 2px; }}
QFrame#UserBubble {{ background: {p.bubble}; border: 1px solid {p.bubble}; border-radius: 18px; }}
QFrame#ToolCard {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 12px; }}
QFrame#ToolCard[state="pending"] {{ border-color: {p.accent}; background: {p.accent_soft}; }}
QFrame#ToolCard[state="error"] {{ border-color: {p.border_strong}; }}
QFrame#ApprovalBox {{ background: {p.surface}; border: 1px solid {p.accent}; border-radius: 14px; }}
QFrame#ErrorCard {{ background: {p.del_bg}; border: 1px solid {p.danger}; border-radius: {R_CARD}px; }}
QFrame#InfoCard {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: {R_CARD}px; }}
QFrame#HeaderBar {{ background: {p.bg}; border-bottom: 1px solid {p.border}; }}
QFrame#ThinkingBox {{ background: transparent; border-left: 2px solid {p.border_strong}; }}
QPushButton#SuggestionCard {{ background: {glass}; border: 1px solid {p.rim}; border-radius: {R_CARD}px;
                              text-align: left; padding: 12px 14px; color: {p.text_dim}; }}
QPushButton#SuggestionCard:hover {{ border-color: {p.accent}; color: {p.text}; background: {p.surface}; }}
QTextBrowser[md="true"] {{ background: transparent; border: none; padding: 0; }}
QPlainTextEdit#CodeView, QPlainTextEdit#DiffView, QPlainTextEdit#TerminalView {{
    background: {p.code_bg}; border: 1px solid {p.code_border}; border-radius: 10px; padding: 6px;
}}
"""


def apply_theme(app: QApplication, theme: str, font_pt: int = 10, compact: bool = False) -> Palette:
    global _current
    p = palette_for(theme)
    _current = p
    font = QFont(ui_font_family())
    font.setPointSize(font_pt)
    font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)
    qp = QPalette()
    qp.setColor(QPalette.Window, QColor(p.bg))
    qp.setColor(QPalette.WindowText, QColor(p.text))
    qp.setColor(QPalette.Base, QColor(p.surface))
    qp.setColor(QPalette.AlternateBase, QColor(p.surface2))
    qp.setColor(QPalette.Text, QColor(p.text))
    qp.setColor(QPalette.Button, QColor(p.surface2))
    qp.setColor(QPalette.ButtonText, QColor(p.text))
    qp.setColor(QPalette.Highlight, QColor(p.accent))
    qp.setColor(QPalette.HighlightedText, QColor(p.on_accent))
    qp.setColor(QPalette.ToolTipBase, QColor(p.surface2))
    qp.setColor(QPalette.ToolTipText, QColor(p.text))
    qp.setColor(QPalette.PlaceholderText, QColor(p.muted))
    qp.setColor(QPalette.Link, QColor(p.accent))
    app.setPalette(qp)
    app.setStyleSheet(build_qss(p, font_pt, compact))
    notify_changed()
    from PySide6.QtWidgets import QLabel

    for w in app.allWidgets():   # simgeler (icons._ThemedEngine) her çizimde temayı okur: yeniden çizdir
        if isinstance(w, QLabel) and "<a " in (w.text() or ""):
            # bağlantı rengi paletten (Link) ama QLabel metni ilk kurulumda dizer, tema değişince yenilemez
            t = w.text()
            w.setText("")
            w.setText(t)
        w.update()
    return p
