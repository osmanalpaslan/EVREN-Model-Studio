"""Model çıktısındaki JSON'u esnek okuma (Madde 20 A1, 2026-11-11; R-26).

Modeller yapılandırılmış blokları (plan, QA sonucu, Derin bulgu/denetim/yargıç, inceleme ve kapsam kararı) zaman zaman
bozuk yazar: kaçışsız tırnak, karışık tek/çift tırnak, erken kapanan `]},`, yarıda kesilmiş nesne (2026-11-07 gerçek
Derin Mod koşusu: qwen'in `<bulgu>`'su okunamadı, "anla" 0/3). Önce katı `json.loads`; olmazsa `json_repair`
(MIT, bağımlılıksız; docs/knowledge/REPO_TARAMASI_2026-11.md).

BİLEREK KULLANILMAYAN YER: araç çağrısı argümanları (runner, textproto). Yarıda kesilmiş bir `write_file` argümanı
"onarılırsa" dosya eksik içerikle sessizce yazılır; orada hatayı modele bildirip yeniden istemek daha güvenli.
"""
from __future__ import annotations

import json
from typing import Any


def loads(text: str | None) -> Any | None:
    """JSON değeri; okunamazsa ya da onarım boş/anlamsız bir şey verirse None (blok uydurulmaz)."""
    if not text or not text.strip():
        return None
    try:
        return json.loads(text)
    except ValueError:
        pass
    try:
        import json_repair
    except ImportError:              # pragma: no cover — paket kurulu değilse eski davranış (çağıran kendi yedeğine geçer)
        return None
    try:
        value = json_repair.loads(text)
    except Exception:                # onarım da yapamadıysa: yok say
        return None
    return value if isinstance(value, (dict, list)) and value else None


def obj(text: str | None) -> dict | None:
    """Yalnız JSON NESNESİ (dict) kabul edilir. Katı okuma olmazsa EN ÇOK BİLGİYİ kurtaran onarım seçilir (best)."""
    if not text or not text.strip():
        return None
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except ValueError:
        pass
    return best(text)


def _score(d: dict) -> int:
    """Kurtarılan bilgi: alan sayısı + dolu değerlerin toplam uzunluğu (boş/eksik alan cezalı)."""
    return sum(1 + len(json.dumps(v, ensure_ascii=False)) for v in d.values() if v not in ("", None, [], {}))


def best(text: str, extra: list[dict | None] | None = None) -> dict | None:
    """json_repair ile kendi anahtar-sınırı okuyucumuz (qa.loose_object) yarışır; en çok bilgiyi kurtaran kazanır.
    Neden ikisi: gerçek koşularda biri ötekinin bozduğu durumu doğru okudu — json_repair tek tırnaklı / yarıda kesilmiş
    JSON'da; anahtar-sınırı okuyucu değer içinde kaçışsız `'""'` olan QA sonucunda (2026-10-19) json_repair metni kesip
    bir alanı boş bıraktı."""
    from .qa import loose_object

    repaired = loads(text)
    cands = [c for c in [repaired if isinstance(repaired, dict) else None, loose_object(text), *(extra or [])]
             if isinstance(c, dict) and c]
    return max(cands, key=_score) if cands else None
