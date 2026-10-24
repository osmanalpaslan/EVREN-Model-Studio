"""Uygulama içi çizgi simgeleri (SVG, 24×24, kendi çizimimiz).

`icon("folder")` temanın metin rengiyle; `icon("send", color)` istenen
renkle QIcon döndürür. Simgeler önbelleğe alınır.
"""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from . import theme

_P = {
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.3-4.3"/>',
    "folder": '<path d="M3.5 7.5a2 2 0 0 1 2-2h3.8l2 2h7.2a2 2 0 0 1 2 2v7.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
    "message": '<path d="M5 5h14a1.5 1.5 0 0 1 1.5 1.5v9A1.5 1.5 0 0 1 19 17H10l-5 3.5V6.5A1.5 1.5 0 0 1 5 5z"/>',
    "terminal": '<rect x="3" y="4.5" width="18" height="15" rx="2.5"/><path d="M7.5 9.5l3 2.5-3 2.5M13 15h3.5"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2.8v2.6M12 18.6v2.6M2.8 12h2.6M18.6 12h2.6M5.5 5.5l1.8 1.8M16.7 16.7l1.8 1.8M5.5 18.5l1.8-1.8M16.7 7.3l1.8-1.8"/>',
    "panel-right": '<rect x="3" y="4.5" width="18" height="15" rx="2.5"/><path d="M15 4.5v15"/>',
    "panel-left": '<rect x="3" y="4.5" width="18" height="15" rx="2.5"/><path d="M9 4.5v15"/>',
    "send": '<path d="M12 19V5.5M6.5 11L12 5.5l5.5 5.5"/>',
    "stop": '<rect x="7" y="7" width="10" height="10" rx="2" fill="{c}"/>',
    "chevron-down": '<path d="M6.5 9.5L12 15l5.5-5.5"/>',
    "chevron-right": '<path d="M9.5 6.5L15 12l-5.5 5.5"/>',
    "file": '<path d="M6.5 3.5h7l4 4v13h-11z"/><path d="M13.5 3.5v4h4"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "x": '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    "undo": '<path d="M9 14.5L4.5 10 9 5.5"/><path d="M4.5 10H14a5.5 5.5 0 0 1 0 11h-3"/>',
    "cpu": '<rect x="7" y="7" width="10" height="10" rx="2"/><path d="M10 3.5V7M14 3.5V7M10 17v3.5M14 17v3.5M3.5 10H7M3.5 14H7M17 10h3.5M17 14h3.5"/>',
    "activity": '<path d="M3 12h4l2.5-7 5 14 2.5-7h4"/>',
    "alert": '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17.2v.1"/>',
    "gauge": '<path d="M4.5 17a8 8 0 1 1 15 0"/><path d="M12 15l3.5-4.5"/>',
    "plug": '<path d="M9 3.5V8M15 3.5V8M7 8h10v3a5 5 0 0 1-10 0z"/><path d="M12 16v4.5"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.4a2.5 2.5 0 1 1 3.6 2.3c-.7.4-1.2.9-1.2 1.6v.4M12 17.2v.1"/>',
    "server": '<rect x="4" y="4" width="16" height="7" rx="2"/><rect x="4" y="13" width="16" height="7" rx="2"/><path d="M8 7.5h.01M8 16.5h.01"/>',
    "list": '<path d="M9.5 6.5h10M9.5 12h10M9.5 17.5h10M4.5 6.5h1M4.5 12h1M4.5 17.5h1"/>',
    "branch": '<circle cx="7" cy="5.5" r="2"/><circle cx="7" cy="18.5" r="2"/><circle cx="17" cy="7.5" r="2"/><path d="M7 7.5v9M17 9.5c0 4-3.5 4.5-8.5 7.5"/>',
    "paperclip": '<path d="M19.5 11.5l-7.8 7.8a5 5 0 0 1-7-7l8.3-8.3a3.4 3.4 0 0 1 4.8 4.8l-8.2 8.2a1.8 1.8 0 0 1-2.6-2.6l7.4-7.4"/>',
    "trash": '<path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l1 13h9l1-13"/>',
    "pencil": '<path d="M4.5 19.5h4l10-10-4-4-10 10z"/><path d="M13 7l4 4"/>',
    "pin": '<path d="M9 3.5h6l-1 6 3 3H7l3-3z"/><path d="M12 12.5v8"/>',
    "thumbs-down": '<path d="M7.5 13.5v-9"/><path d="M7.5 13.5l3.4 6a1.7 1.7 0 0 0 3.1-1.3l-.9-4.2h4.8a2 2 0 0 0 2-2.4l-1.2-5.6a2 2 0 0 0-2-1.5H7.5"/><path d="M3.5 4.5h4v9h-4z"/>',
    "copy": '<rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M15.5 8.5V6a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h2.5"/>',
    "spark": '<path d="M12 2.8l2.1 6.4 6.6 2.3-6.6 2.3L12 20.2l-2.1-6.4-6.6-2.3 6.6-2.3z" fill="{c}"/>',
    "bulb": '<path d="M9.5 18h5M10.5 21h3"/><path d="M12 3a6 6 0 0 0-3.6 10.8c.7.5 1.1 1.2 1.1 2V16h5v-.2c0-.8.4-1.5 1.1-2A6 6 0 0 0 12 3z"/>',
    "refresh": '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.5 4.5v5h-5"/>',
    "git": '<circle cx="6.5" cy="5.5" r="2"/><circle cx="6.5" cy="18.5" r="2"/><circle cx="17.5" cy="8.5" r="2"/><path d="M6.5 7.5v9"/><path d="M17.5 10.5c0 4-5 3.5-9.4 6.6"/>',
    "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    "shield": '<path d="M12 3.5l7.5 3v5.5c0 4.5-3.2 7.6-7.5 8.5-4.3-.9-7.5-4-7.5-8.5V6.5z"/>',
    "more": '<circle cx="5.5" cy="12" r="1.3" fill="{c}"/><circle cx="12" cy="12" r="1.3" fill="{c}"/><circle cx="18.5" cy="12" r="1.3" fill="{c}"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "map": '<path d="M9 4.5l-5.5 2v13l5.5-2 6 2 5.5-2v-13l-5.5 2z"/><path d="M9 4.5v13M15 6.5v13"/>',
    "download": '<path d="M12 4.5v11M7 11l5 5 5-5M5 19.5h14"/>',
    "external": '<path d="M13.5 4.5h6v6M19.5 4.5L11 13"/><path d="M18 14v4.5a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6H10"/>',
    "dot": '<circle cx="12" cy="12" r="4" fill="{c}"/>',
    "circle": '<circle cx="12" cy="12" r="7"/>',
    "circle-check": '<circle cx="12" cy="12" r="8" fill="{c}" stroke="none"/><path d="M8.3 12.3l2.5 2.5 5-5" stroke="{bg}"/>',
    "circle-half": '<circle cx="12" cy="12" r="7"/><path d="M12 5a7 7 0 0 1 0 14z" fill="{c}"/>',
}

_cache: dict[tuple, QIcon] = {}


def svg(name: str, color: str, bg: str | None = None) -> str:
    body = _P.get(name, _P["dot"]).replace("{c}", color).replace("{bg}", bg or theme.current().bg)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</svg>'
    )


def pixmap(name: str, color: str | None = None, size: int = 18, ratio: float = 2.0) -> QPixmap:
    color = color or theme.current().text_dim
    renderer = QSvgRenderer(QByteArray(svg(name, color).encode("utf-8")))
    px = QPixmap(int(size * ratio), int(size * ratio))
    px.fill(Qt.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size * ratio, size * ratio))
    painter.end()
    px.setDevicePixelRatio(ratio)
    return px


def icon(name: str, color: str | None = None, size: int = 18) -> QIcon:
    color = color or theme.current().text_dim
    key = (name, color, size, theme.current().name)
    if key not in _cache:
        _cache[key] = QIcon(pixmap(name, color, size))
    return _cache[key]


def clear_cache() -> None:
    _cache.clear()
