"""Görsel tema: renk belirteçleri, yazı tipleri ve uygulama geneli QSS.

Tüm renkler burada tanımlanır; bileşenler sabit renk yazmaz, `current()`
paletini kullanır. Koyu ve açık tema aynı belirteç adlarını paylaşır.
"""
from __future__ import annotations

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
    surface2: str       # yükseltilmiş yüzey, kullanıcı mesajı
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


DARK = Palette(
    name="koyu",
    bg="#16171b", sidebar="#111215", panel="#131418",
    surface="#1d1f24", surface2="#24272e", hover="#262930", selected="#2c3039",
    border="#2a2d34", border_strong="#3a3e47",
    # Kullanıcı kararı (2026-10-19): koyu temada tüm yazı/düğme/simge "Görevler" başlığı kadar
    # parlak olsun; eski #a2a6af / #6d717a yer yer okunmuyordu. Hiyerarşi boyut ve kalınlıkla kalır.
    text="#e8e9ec", text_dim="#e8e9ec", text_faint="#e8e9ec",
    # Kullanıcı kararı (2026-10-19): koyu temada düğmeler/vurgu mavi değil, yazılarla aynı beyaz;
    # birincil düğme beyaz zemin + koyu yazı, seçili satır nötr gri.
    accent="#e8e9ec", accent_hover="#ffffff", accent_soft="#30343c", on_accent="#16171b",
    code_bg="#0f1013", code_border="#24262c",
    success="#4fd08a", danger="#ff7a7a", warning="#f2c25c",
    add_bg="#15301f", del_bg="#3a1a1d", hunk="#7c9cff",
    scrollbar="#3a3e47", muted="#9ca1ab",
)

LIGHT = Palette(
    name="açık",
    bg="#fbfbfa", sidebar="#f2f2ef", panel="#f6f6f4",
    surface="#ffffff", surface2="#f0f0ec", hover="#e9e9e5", selected="#e2e3ea",
    border="#e3e3de", border_strong="#cfcfc8",
    text="#1d1f23", text_dim="#5b606a", text_faint="#9095a0",
    accent="#3d63dd", accent_hover="#2f53c7", accent_soft="#e6ecfd", on_accent="#ffffff",
    code_bg="#f5f5f2", code_border="#e3e3de",
    success="#1f9d55", danger="#d64545", warning="#b7791f",
    add_bg="#e3f6e9", del_bg="#fbe5e5", hunk="#3d63dd",
    scrollbar="#c9c9c2", muted="#9095a0",
)

_current: Palette = DARK

UI_FONTS = ["Segoe UI Variable Text", "Segoe UI", "Inter", "Arial"]
CODE_FONTS = ["Cascadia Mono", "Cascadia Code", "Consolas", "Courier New"]


def current() -> Palette:
    return _current


def palette_for(theme: str) -> Palette:
    return LIGHT if theme in ("açık", "acik", "light") else DARK


def _first_available(candidates: list[str]) -> str:
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


def code_font_family() -> str:
    return _first_available(CODE_FONTS)


def code_font(size: int = 10) -> QFont:
    f = QFont(code_font_family())
    f.setStyleHint(QFont.Monospace)
    f.setPointSize(size)
    return f


def build_qss(p: Palette, font_pt: int) -> str:
    small = max(font_pt - 1, 8)
    return f"""
* {{ outline: none; }}
QWidget {{ color: {p.text}; font-size: {font_pt}pt; }}
QMainWindow, QWidget#Root, QWidget#CenterHost, QStackedWidget#CenterStack {{ background: {p.bg}; }}
QToolTip {{ background: {p.surface2}; color: {p.text}; border: 1px solid {p.border_strong};
           padding: 5px 8px; border-radius: 6px; }}
QLabel {{ background: transparent; }}
QLabel#dim, QLabel[role="dim"] {{ color: {p.text_dim}; }}
QLabel[role="faint"] {{ color: {p.text_faint}; font-size: {small}pt; }}
QLabel#pageTitle, QLabel[role="title"] {{ font-size: {font_pt + 6}pt; font-weight: 600; }}
QLabel[role="h2"] {{ font-size: {font_pt + 2}pt; font-weight: 600; }}
QLabel[role="section"] {{ color: {p.text_faint}; font-size: {small}pt; font-weight: 600;
                          letter-spacing: 0.5px; padding: 10px 10px 4px 10px; }}

/* ---- düğmeler ---- */
QPushButton, QToolButton {{
    background: {p.surface2}; color: {p.text}; border: 1px solid {p.border};
    border-radius: 8px; padding: 6px 12px;
}}
QPushButton:hover, QToolButton:hover {{ background: {p.hover}; border-color: {p.border_strong}; }}
QPushButton:pressed, QToolButton:pressed {{ background: {p.selected}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {p.muted}; background: {p.surface}; }}
QPushButton[variant="primary"] {{ background: {p.accent}; color: {p.on_accent}; border: none; font-weight: 600; }}
QPushButton[variant="primary"]:hover {{ background: {p.accent_hover}; }}
QPushButton[variant="primary"]:disabled {{ background: {p.selected}; color: {p.muted}; }}
QPushButton[variant="ghost"], QToolButton[variant="ghost"] {{ background: transparent; border: 1px solid transparent; }}
QPushButton[variant="ghost"]:hover, QToolButton[variant="ghost"]:hover {{ background: {p.hover}; }}
QPushButton[variant="danger"] {{ background: transparent; color: {p.danger}; border: 1px solid {p.border}; }}
QPushButton[variant="danger"]:hover {{ background: {p.del_bg}; }}
QToolButton[variant="chip"] {{ background: transparent; border: 1px solid transparent; border-radius: 7px;
                               padding: 3px 8px; color: {p.text_dim}; }}
QToolButton[variant="chip"]:hover {{ background: {p.hover}; color: {p.text}; }}
QToolButton[variant="icon"], QPushButton[variant="icon"] {{ background: transparent; border: none; border-radius: 7px; padding: 5px; }}
QToolButton[variant="icon"]:hover, QPushButton[variant="icon"]:hover {{ background: {p.hover}; }}
QToolButton[variant="icon"]:checked {{ background: {p.selected}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}
QPushButton#SendButton {{ background: {p.accent}; border: none; border-radius: 15px; padding: 0; }}
QPushButton#SendButton:hover {{ background: {p.accent_hover}; }}
QPushButton#SendButton:disabled {{ background: {p.selected}; }}
QPushButton#SendButton[running="true"] {{ background: {p.text}; }}

/* ---- girişler ---- */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {p.surface}; color: {p.text}; border: 1px solid {p.border};
    border-radius: 8px; padding: 5px 8px; selection-background-color: {p.accent_soft};
    selection-color: {p.text};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {p.accent};
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{ background: {p.surface}; border: 1px solid {p.border_strong};
                               selection-background-color: {p.selected}; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 16px; border: none; }}
QCheckBox {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {p.border_strong}; background: {p.surface}; }}
QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; }}

/* ---- menü ---- */
QMenu {{ background: {p.surface}; border: 1px solid {p.border_strong}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 26px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {p.hover}; }}
QMenu::item:disabled {{ color: {p.muted}; }}
QMenu::separator {{ height: 1px; background: {p.border}; margin: 5px 6px; }}
QMenu::indicator {{ width: 14px; height: 14px; left: 6px; }}

/* ---- kaydırma çubukları ---- */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.scrollbar}; border-radius: 3px; min-height: 30px; margin: 0 2px; }}
QScrollBar::handle:vertical:hover {{ background: {p.text_faint}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p.scrollbar}; border-radius: 3px; min-width: 30px; margin: 2px 0; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---- sol menü ---- */
QWidget#Sidebar {{ background: {p.sidebar}; border-right: 1px solid {p.border}; }}
QWidget#Sidebar QLineEdit {{ background: {p.surface}; }}
QListWidget#SessionList {{ background: transparent; border: none; padding: 0 6px; }}
QListWidget#SessionList::item {{ border-radius: 8px; padding: 0; margin: 1px 0; }}
QListWidget#SessionList::item:hover {{ background: {p.hover}; }}
QListWidget#SessionList::item:selected {{ background: {p.selected}; }}
QPushButton[nav="true"] {{ background: transparent; border: none; text-align: left; padding: 7px 10px;
                           border-radius: 8px; color: {p.text_dim}; }}
QPushButton[nav="true"]:hover {{ background: {p.hover}; color: {p.text}; }}
QPushButton[nav="true"]:checked {{ background: {p.selected}; color: {p.text}; }}
QPushButton#NewSession {{ text-align: left; padding: 8px 12px; font-weight: 600; }}

/* ---- sağ panel ---- */
QWidget#SidePanel {{ background: {p.panel}; border-left: 1px solid {p.border}; }}
QTabWidget#PanelTabs::pane {{ border: none; border-top: 1px solid {p.border}; }}
QTabWidget#PanelTabs > QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: transparent; color: {p.text_dim}; padding: 10px 12px; border: none;
                border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {p.text}; border-bottom: 2px solid {p.accent}; }}
QTabBar::tab:hover {{ color: {p.text}; }}

/* ---- ağaç / liste / tablo ---- */
QTreeView, QListWidget, QListView, QTableWidget, QTableView {{
    background: transparent; border: none; alternate-background-color: {p.surface};
}}
QTreeView::item, QListView::item {{ padding: 3px 4px; border-radius: 5px; }}
QTreeView::item:hover, QListWidget::item:hover {{ background: {p.hover}; }}
QTreeView::item:selected, QListWidget::item:selected {{ background: {p.selected}; color: {p.text}; }}
QTableWidget {{ gridline-color: {p.border}; border: 1px solid {p.border}; border-radius: 8px; background: {p.surface}; }}
QHeaderView::section {{ background: {p.surface2}; color: {p.text_dim}; border: none;
                        border-bottom: 1px solid {p.border}; padding: 6px 8px; font-weight: 600; }}
QTableCornerButton::section {{ background: {p.surface2}; border: none; }}

/* ---- kartlar ve eski sayfalar ---- */
QFrame#card {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 12px; }}
QFrame#card QLabel {{ background: transparent; }}
QProgressBar {{ background: {p.surface2}; border: none; border-radius: 6px; text-align: center; color: {p.text}; height: 12px; }}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 6px; }}
QSplitter::handle {{ background: {p.border}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

/* ---- sohbet alanı ---- */
QListWidget#CommandPopup {{ background: {p.surface}; border: 1px solid {p.border_strong};
                            border-radius: 12px; padding: 4px; }}
QListWidget#CommandPopup::item {{ padding: 5px 8px; border-radius: 7px; min-height: 20px; }}
QListWidget#CommandPopup::item:hover {{ background: {p.hover}; }}
QListWidget#CommandPopup::item:selected {{ background: {p.accent_soft}; color: {p.text}; }}
QFrame#RunBar {{ background: {p.accent_soft}; border: 1px solid {p.border}; border-radius: 10px; }}
QFrame#Composer {{ background: {p.surface}; border: 1px solid {p.border_strong}; border-radius: 16px; }}
QFrame#Composer[focus="true"] {{ border-color: {p.accent}; }}
QScrollArea#AttachmentBar, QScrollArea#AttachmentBar > QWidget > QWidget {{ background: transparent; }}
QFrame#AttachmentChip {{ background: {p.bg}; border: 1px solid {p.border_strong}; border-radius: 10px; }}
QLabel#AttachmentThumb {{ border-radius: 6px; }}
QToolButton#AttachmentRemove {{ background: transparent; border: none; padding: 1px; border-radius: 8px; }}
QToolButton#AttachmentRemove:hover {{ background: {p.hover}; }}
QFrame#UsagePanel {{ background: {p.surface}; border: 1px solid {p.border_strong}; }}
QPlainTextEdit#ComposerEdit {{ background: transparent; border: none; padding: 4px 2px; }}
QFrame#UserBubble {{ background: {p.surface2}; border: 1px solid {p.border}; border-radius: 14px; }}
QFrame#ToolCard {{ background: transparent; border: 1px solid {p.border}; border-radius: 10px; }}
QFrame#ToolCard[state="pending"] {{ border-color: {p.accent}; background: {p.accent_soft}; }}
QFrame#ToolCard[state="error"] {{ border-color: {p.border}; }}
QFrame#ApprovalBox {{ background: {p.surface}; border: 1px solid {p.accent}; border-radius: 10px; }}
QFrame#ErrorCard {{ background: {p.del_bg}; border: 1px solid {p.danger}; border-radius: 12px; }}
QFrame#InfoCard {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 12px; }}
QFrame#HeaderBar {{ background: {p.bg}; border-bottom: 1px solid {p.border}; }}
QFrame#ThinkingBox {{ background: transparent; border-left: 2px solid {p.border_strong}; }}
QPushButton#SuggestionCard {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 12px;
                              text-align: left; padding: 12px 14px; color: {p.text_dim}; }}
QPushButton#SuggestionCard:hover {{ border-color: {p.border_strong}; color: {p.text}; background: {p.surface2}; }}
QTextBrowser[md="true"] {{ background: transparent; border: none; padding: 0; }}
QPlainTextEdit#CodeView, QPlainTextEdit#DiffView, QPlainTextEdit#TerminalView {{
    background: {p.code_bg}; border: 1px solid {p.code_border}; border-radius: 8px; padding: 6px;
}}
"""


def apply_theme(app: QApplication, theme: str, font_pt: int = 10) -> Palette:
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
    app.setStyleSheet(build_qss(p, font_pt))
    return p
