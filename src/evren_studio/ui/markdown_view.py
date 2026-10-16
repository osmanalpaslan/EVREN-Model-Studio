"""Markdown → Qt zengin metin dönüştürücü ve içeriğe göre uzayan görüntüleyici."""
from __future__ import annotations

import html
import math
import re

import markdown as md
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QSizePolicy, QTextBrowser

from . import theme

_CODE_RE = re.compile(
    r'<pre><code(?: class="language-([\w+#.\-]+)")?>(.*?)</code></pre>', re.S
)
_INLINE_CODE_RE = re.compile(r"<code>")
_LANG_ALIASES = {"ps1": "powershell", "ps": "powershell", "sh": "bash", "shell": "bash",
                 "py": "python", "cs": "csharp", "c#": "csharp", "js": "javascript",
                 "ts": "typescript", "yml": "yaml", "cmd": "batch", "bat": "batch"}


def _pyg_style(p: theme.Palette) -> str:
    return "github-dark" if p.name == "koyu" else "friendly"


def _highlight(code: str, lang: str | None, p: theme.Palette) -> str:
    lexer = TextLexer()
    if lang:
        try:
            lexer = get_lexer_by_name(_LANG_ALIASES.get(lang.lower(), lang.lower()))
        except ClassNotFound:
            pass
    try:
        fmt = HtmlFormatter(nowrap=True, noclasses=True, style=_pyg_style(p))
    except ClassNotFound:
        fmt = HtmlFormatter(nowrap=True, noclasses=True)
    out = highlight(code, lexer, fmt)
    # Pygments arka plan renklerini kaldır (zemin tablo hücresinden gelir)
    return re.sub(r"background-color:\s*#[0-9a-fA-F]{3,8};?", "", out).rstrip("\n")


def render_markdown(text: str, p: theme.Palette | None = None) -> str:
    p = p or theme.current()
    body = md.markdown(text or "", extensions=["fenced_code", "tables", "sane_lists"],
                       output_format="html")
    code_family = theme.code_font_family()

    def repl(m: re.Match) -> str:
        lang = m.group(1)
        code = html.unescape(m.group(2))
        label = (
            f'<p style="margin:0 0 6px 0; color:{p.text_faint}; font-size:small;">{html.escape(lang)}</p>'
            if lang else ""
        )
        return (
            f'<table width="100%" cellspacing="0" cellpadding="10" '
            f'style="background-color:{p.code_bg}; margin-top:6px; margin-bottom:8px;">'
            f'<tr><td>{label}<pre style="font-family:\'{code_family}\'; margin:0; '
            f'white-space:pre-wrap;">{_highlight(code, lang, p)}</pre></td></tr></table>'
        )

    body = _CODE_RE.sub(repl, body)
    body = _INLINE_CODE_RE.sub(
        f'<code style="font-family:\'{code_family}\'; background-color:{p.surface2}; '
        f'color:{p.text};">&#8202;', body)
    body = body.replace("</code>", "&#8202;</code>")
    body = body.replace(
        "<table>",
        f'<table border="1" cellspacing="0" cellpadding="6" '
        f'style="border-color:{p.border}; border-style:solid; margin-top:6px; margin-bottom:8px;">')
    return body


def document_css(p: theme.Palette, font_pt: int) -> str:
    return f"""
body {{ color: {p.text}; }}
p {{ margin-top: 0px; margin-bottom: 8px; line-height: 145%; }}
a {{ color: {p.accent}; text-decoration: none; }}
h1 {{ font-size: {font_pt + 7}pt; font-weight: 600; margin-top: 10px; margin-bottom: 6px; }}
h2 {{ font-size: {font_pt + 4}pt; font-weight: 600; margin-top: 10px; margin-bottom: 6px; }}
h3 {{ font-size: {font_pt + 2}pt; font-weight: 600; margin-top: 8px; margin-bottom: 4px; }}
h4, h5, h6 {{ font-size: {font_pt + 1}pt; font-weight: 600; margin-top: 6px; margin-bottom: 4px; }}
ul, ol {{ margin-top: 0px; margin-bottom: 8px; }}
li {{ margin-bottom: 3px; }}
blockquote {{ color: {p.text_dim}; margin-left: 12px; }}
th {{ background-color: {p.surface2}; font-weight: 600; }}
hr {{ color: {p.border}; }}
"""


class MarkdownView(QTextBrowser):
    """Kaydırma çubuksuz, içeriği kadar uzayan Markdown görüntüleyici."""

    def __init__(self, parent=None, font_pt: int = 10):
        super().__init__(parent)
        self.setProperty("md", True)
        self.font_pt = font_pt
        self.setOpenExternalLinks(True)
        self.setReadOnly(True)
        self.setFrameShape(QTextBrowser.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.document().setDocumentMargin(0)
        self.viewport().setAutoFillBackground(False)
        self.document().contentsChanged.connect(self._fit)
        self._source = ""
        self.setFixedHeight(20)

    def source_text(self) -> str:
        return self._source

    def set_markdown(self, text: str) -> None:
        self._source = text or ""
        p = theme.current()
        self.document().setDefaultStyleSheet(document_css(p, self.font_pt))
        self.setHtml(render_markdown(self._source, p))
        self._fit()

    def set_plain(self, text: str) -> None:
        self._source = text or ""
        self.setPlainText(self._source)
        self._fit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Bağlam nesnesi verilir: widget silinirse zamanlayıcı da iptal olur
        QTimer.singleShot(0, self, self._fit)

    def wheelEvent(self, event) -> None:
        event.ignore()  # dış kaydırma alanı kaydırsın

    def _fit(self) -> None:
        width = self.viewport().width()
        if width <= 0:
            return
        doc = self.document()
        doc.setTextWidth(width)
        h = int(math.ceil(doc.size().height())) + 2
        if h != self.height():
            self.setFixedHeight(max(h, 18))
