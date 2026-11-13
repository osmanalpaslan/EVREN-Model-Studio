"""İş sürerken gönderilen mesajlar (Madde 23 a, kullanıcı 2026-11-13: "bir prompt yazdığımda o işlem bitene kadar yeni
prompt yazamıyorum; Claude Code'daki gibi ara mesajla işine devam etsin; işlenmemiş promptu geri çekebilmeliyim").

Qt'siz, iş parçacığı güvenli kuyruk. Arayüz ekler ve geri çeker (ana iş parçacığı); ajan koşucusu her adım arasında
iletilebilir olanları alır (arka plan iş parçacığı). Bir mesaj ya ALINIR ya GERİ ÇEKİLİR — ikisi birden olamaz (kilit):
geri çekme yalnız henüz alınmamış mesajda başarılıdır.

İletilebilir (çalışan işe ara mesaj olarak gidebilir) = ek dosya/görsel yok ve komut ("/...") değil. Ekli mesajlar ve
komutlar sırada bekler, iş bitince yeni tur olarak gönderilir. Sıra korunur: yalnız BAŞTAKİ iletilebilir mesajlar alınır
(ekli bir mesajın arkasındaki düz mesaj onu sollamaz).
"""
from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Pending:
    id: int
    text: str                                   # kullanıcının yazdığı (gösterilen) metin
    content: str = ""                           # modele gidecek metin (@dosya açılımı vb.); boşsa text
    attachments: list[Any] = field(default_factory=list)

    @property
    def steerable(self) -> bool:
        return not self.attachments and not self.text.lstrip().startswith("/")

    @property
    def body(self) -> str:
        return self.content or self.text


class Inbox:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: list[Pending] = []
        self._ids = itertools.count(1)
        # Değişince çağrılır (herhangi bir iş parçacığından: arayüz bunu Qt sinyaline bağlar)
        self.on_change: Callable[[], None] | None = None

    def _changed(self) -> None:
        cb = self.on_change
        if cb is not None:
            try:
                cb()
            except Exception:
                pass                                # bildirim hatası kuyruğu bozmasın

    def add(self, text: str, attachments: list | None = None, content: str = "") -> Pending:
        with self._lock:
            item = Pending(next(self._ids), text, content, list(attachments or []))
            self._items.append(item)
        self._changed()
        return item

    def withdraw(self, item_id: int) -> Pending | None:
        """Henüz alınmamışsa çıkarıp döndürür; alınmışsa (ajana iletildi) None."""
        with self._lock:
            for i, it in enumerate(self._items):
                if it.id == item_id:
                    item = self._items.pop(i)
                    break
            else:
                return None
        self._changed()
        return item

    def take_steerable(self) -> list[Pending]:
        """Baştaki iletilebilir mesajlar (koşucu adım arasında çağırır)."""
        with self._lock:
            n = 0
            while n < len(self._items) and self._items[n].steerable:
                n += 1
            taken, self._items = self._items[:n], self._items[n:]
        if taken:
            self._changed()
        return taken

    def take_batch(self) -> list[Pending]:
        """İş bitince gönderilecek sıradaki parti: baştaki komut ("/...") TEK başına; değilse komuta kadar olan tüm
        mesajlar (tek yeni turda birleşir — Claude Code da sıradakileri birlikte gönderir)."""
        with self._lock:
            if not self._items:
                return []
            if self._items[0].text.lstrip().startswith("/"):
                n = 1
            else:
                n = 0
                while n < len(self._items) and not self._items[n].text.lstrip().startswith("/"):
                    n += 1
            taken, self._items = self._items[:n], self._items[n:]
        self._changed()
        return taken

    def take_all(self) -> list[Pending]:
        with self._lock:
            taken, self._items = self._items, []
        if taken:
            self._changed()
        return taken

    def items(self) -> list[Pending]:
        with self._lock:
            return list(self._items)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def __bool__(self) -> bool:
        return len(self) > 0


def merge(items: list[Pending]) -> tuple[str, list]:
    """Bir partiyi (take_batch) tek mesaja çevirir: metinler boş satırla birleşir, ekler toplanır."""
    text = "\n\n".join(p.text for p in items if p.text.strip())
    atts: list = []
    for p in items:
        atts += p.attachments
    return text, atts
