"""Mesaj ekleri: sürükle-bırak, yapıştır (Ctrl+V) ve ataç düğmesi.

Claude Code sohbet paneli gibi: eklenen dosyalar yazma kutusunun üstünde
küçük resim (görsel) veya dosya kartı olarak görünür; dosya yolu metne
yazılmaz, arka planda `Attachment.path` içinde tutulur.

- Görseller gönderilmeden önce en fazla MAX_IMAGE_SIDE piksele küçültülüp
  veri klasöründeki `attachments/` altına kopyalanır (asıl dosya değişmez,
  silinse bile sohbet geçmişi bozulmaz). Panodan yapıştırılan görsel (ekran
  görüntüsü) de oraya PNG olarak kaydedilir.
- Görsel okuyabilen modeller gerçek API ile ölçüldü (2026-10-19,
  docs/knowledge/MODEL_CAPABILITIES.md); okuyamayanlar 400 döner.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QToolButton, QVBoxLayout, QWidget

from . import icons, theme

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
MAX_IMAGE_SIDE = 1568           # sağlayıcıların önerdiği üst sınır; daha büyüğü token israfı
MAX_ATTACHMENTS = 10
THUMB = 52


@dataclass
class Attachment:
    path: str                   # gönderilecek dosya (görselde: küçültülmüş kopya)
    kind: str                   # "image" | "file"
    name: str                   # gösterilen ad
    size: int = 0
    source: str = ""            # kullanıcının seçtiği asıl yol (bilgi amaçlı)

    def to_meta(self) -> dict:
        return {"path": self.path, "kind": self.kind, "name": self.name, "size": self.size,
                "source": self.source}

    @classmethod
    def from_meta(cls, d: dict) -> "Attachment":
        return cls(path=d.get("path", ""), kind=d.get("kind", "file"), name=d.get("name", "?"),
                   size=int(d.get("size") or 0), source=d.get("source", ""))


def is_image(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_SUFFIXES


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}".replace(".", ",")
        n /= 1024
    return f"{n} B"


def _store_dir(data_dir: Path) -> Path:
    d = Path(data_dir) / "attachments"
    d.mkdir(parents=True, exist_ok=True)
    return d


def store_image(img: QImage, data_dir: Path, name: str) -> Attachment | None:
    """Görseli küçültüp veri klasörüne kaydeder (PNG; büyük fotoğrafta JPEG)."""
    if img.isNull():
        return None
    if max(img.width(), img.height()) > MAX_IMAGE_SIDE:
        img = img.scaled(MAX_IMAGE_SIDE, MAX_IMAGE_SIDE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = f"{stamp}-{uuid.uuid4().hex[:6]}"
    photo = img.width() * img.height() > 600_000 and not img.hasAlphaChannel()
    target = _store_dir(data_dir) / (stem + (".jpg" if photo else ".png"))
    if not img.save(str(target), "JPEG" if photo else "PNG", 85 if photo else -1):
        return None
    return Attachment(str(target), "image", name, target.stat().st_size)


def attachment_from_path(path: str, data_dir: Path) -> Attachment | None:
    p = Path(path)
    if not p.is_file():
        return None
    if is_image(p):
        img = QImage(str(p))
        if not img.isNull():
            a = store_image(img, data_dir, p.name)
            if a:
                a.source = str(p)
                return a
    return Attachment(str(p), "file", p.name, p.stat().st_size, str(p))


def clipboard_image_attachment(img: QImage, data_dir: Path) -> Attachment | None:
    name = f"ekran-goruntusu-{datetime.now().strftime('%H%M%S')}.png"
    return store_image(img, data_dir, name)


def thumbnail(path: str, size: int = THUMB) -> QPixmap:
    px = QPixmap(path)
    if px.isNull():
        return icons.pixmap("file", theme.current().text_dim, size // 2)
    return px.scaled(size * 2, size * 2, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)


class AttachmentChip(QFrame):
    """Tek ek: görselde küçük resim, dosyada simge + ad + boyut; ✕ ile kaldırılır."""

    remove_requested = Signal(object)

    def __init__(self, att: Attachment, removable: bool = True, parent=None):
        super().__init__(parent)
        self.att = att
        self.setObjectName("AttachmentChip")
        self.setToolTip(att.source or att.name)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 6 if att.kind == "file" else 4, 4)
        lay.setSpacing(6)
        if att.kind == "image":
            pic = QLabel()
            pic.setFixedSize(THUMB, THUMB)
            px = thumbnail(att.path)
            pic.setPixmap(px.copy((px.width() - THUMB * 2) // 2, (px.height() - THUMB * 2) // 2,
                                  THUMB * 2, THUMB * 2) if px.width() >= THUMB * 2 else px)
            pic.setScaledContents(True)
            pic.setObjectName("AttachmentThumb")
            lay.addWidget(pic)
        else:
            ic = QLabel()
            ic.setPixmap(icons.pixmap("file", theme.current().accent, 20))
            lay.addWidget(ic)
            col = QVBoxLayout()
            col.setSpacing(0)
            name = QLabel(att.name if len(att.name) <= 28 else att.name[:25] + "…")
            name.setStyleSheet("font-weight: 600;")
            col.addWidget(name)
            meta = QLabel(f"{Path(att.name).suffix.lstrip('.').upper() or 'DOSYA'} · {human_size(att.size)}")
            meta.setProperty("role", "faint")
            col.addWidget(meta)
            lay.addLayout(col)
        if removable:
            x = QToolButton()
            x.setObjectName("AttachmentRemove")
            x.setIcon(icons.icon("x", size=12))
            x.setIconSize(QSize(12, 12))
            x.setToolTip("Eki kaldır")
            x.setCursor(Qt.PointingHandCursor)
            x.clicked.connect(lambda: self.remove_requested.emit(self.att))
            lay.addWidget(x, 0, Qt.AlignTop)


class AttachmentBar(QScrollArea):
    """Yazma kutusunun üstündeki ek şeridi (yatay kaydırılır)."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AttachmentBar")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedHeight(THUMB + 18)
        inner = QWidget()
        self._row = QHBoxLayout(inner)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(8)
        self._row.addStretch(1)
        self.setWidget(inner)
        self._items: list[Attachment] = []
        self.setVisible(False)

    def items(self) -> list[Attachment]:
        return list(self._items)

    def add(self, att: Attachment) -> bool:
        if len(self._items) >= MAX_ATTACHMENTS:
            return False
        if any(a.source and a.source == att.source for a in self._items):
            return False            # aynı dosya iki kez eklenmez
        self._items.append(att)
        chip = AttachmentChip(att)
        chip.remove_requested.connect(self.remove)
        self._row.insertWidget(self._row.count() - 1, chip)
        self.setVisible(True)
        self.changed.emit()
        return True

    def remove(self, att: Attachment) -> None:
        for i in range(self._row.count()):
            w = self._row.itemAt(i).widget()
            if isinstance(w, AttachmentChip) and w.att is att:
                w.setParent(None)
                w.deleteLater()
                break
        self._items = [a for a in self._items if a is not att]
        self.setVisible(bool(self._items))
        self.changed.emit()

    def take(self) -> list[Attachment]:
        items = self.items()
        for a in items:
            self.remove(a)
        return items


class AttachmentStrip(QWidget):
    """Gönderilmiş mesajın altında salt okunur ek gösterimi."""

    def __init__(self, items: list[Attachment], parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addStretch(1)
        for a in items:
            lay.addWidget(AttachmentChip(a, removable=False))
