"""F7 Poly Haven (Qt'siz): CC0 model/doku/HDRI arama ve indirme — resmî ücretsiz API (api.polyhaven.com).

Üçüncü taraf "polyhaven-mcp" (yıldızsız, lisanssız) yerine doğrudan API (kullanıcı onayı 2026-10-24). API Kullanım
Şartları (Poly-Haven/Public-API ToS, 2026-10-24 okundu): ücretsiz, anahtarsız; istekler uygulamaya özgü User-Agent
taşımalı (2.4) ve arayüzde içeriğin Poly Haven'dan geldiği görünmeli (2.5) → araç kartı "Poly Haven: …" yazar ve
indirilen klasöre KAYNAK.txt bırakılır. Varlıklar CC0 (atıf gerekmez).
"""
from __future__ import annotations

from pathlib import Path

API = "https://api.polyhaven.com"
USER_AGENT = "EVREN-Studio/1.0 (polyhaven)"            # ToS 2.4: uygulamaya özgü
TYPES = {"models": "models", "model": "models", "textures": "textures", "texture": "textures", "hdris": "hdris",
         "hdri": "hdris"}
MAX_DOWNLOAD = 300 * 1024 * 1024
_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


class PolyHavenError(Exception):
    pass


def _client(client=None):
    import httpx

    return client or httpx.Client(timeout=60.0, follow_redirects=True, headers={"User-Agent": USER_AGENT})


def search(query: str, asset_type: str = "models", limit: int = 12, client=None) -> str:
    t = TYPES.get((asset_type or "models").lower(), "models")
    own = client is None
    c = _client(client)
    try:
        r = c.get(f"{API}/assets", params={"t": t})
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        raise PolyHavenError(f"Poly Haven'a ulaşılamadı: {type(exc).__name__}: {exc}"[:200]) from exc
    finally:
        if own:
            c.close()
    words = [w for w in (query or "").lower().translate(_TR).split() if w]
    hits = []
    for aid, a in data.items():
        hay = " ".join([aid, a.get("name", ""), " ".join(a.get("categories") or []), " ".join(a.get("tags") or [])])
        hay = hay.lower().translate(_TR)
        if all(w in hay for w in words):
            hits.append((a.get("download_count", 0), aid, a))
    hits.sort(key=lambda h: -h[0])
    if not hits:
        return f"Poly Haven'da \"{query}\" için {t} bulunamadı (İngilizce anahtar sözcük dene: chair, rock, sword…)."
    lines = [f"Poly Haven ({t}, CC0) — \"{query}\" için {len(hits)} sonuç, en popüler {min(limit, len(hits))}:"]
    for _n, aid, a in hits[:limit]:
        extra = f", {a['polycount']} üçgen" if a.get("polycount") else ""
        lines.append(f"- {aid}: {a.get('name', aid)} [{', '.join((a.get('categories') or [])[:3])}]{extra}")
    lines.append("İndirmek için polyhaven_download(asset_id, ...) kullan.")
    return "\n".join(lines)


def download(asset_id: str, dest: Path, resolution: str = "1k", fmt: str = "", client=None) -> list[Path]:
    """Varlığı `dest` klasörüne indirir (ana dosya + ekleri). Dönüş: yazılan dosyalar."""
    own = client is None
    c = _client(client)
    try:
        r = c.get(f"{API}/files/{asset_id}")
        if r.status_code == 404:
            raise PolyHavenError(f"Böyle bir varlık yok: {asset_id}")
        r.raise_for_status()
        files = r.json()
        kind = fmt or ("gltf" if "gltf" in files else "blend" if "blend" in files else "hdri" if "hdri" in files else "")
        if kind not in files:
            raise PolyHavenError(f"{asset_id} için biçim yok: {fmt or '?'} (var olanlar: {', '.join(files)})")
        by_res = files[kind]
        res = resolution if resolution in by_res else sorted(by_res, key=lambda x: int(x.rstrip("k") or 0))[0]
        node = by_res[res]
        entry = node.get(kind) or next(iter(node.values()))
        plan = [(Path(entry["url"].rsplit("/", 1)[-1]), entry["url"], entry.get("size", 0))]
        for rel, inc in (entry.get("include") or {}).items():
            plan.append((Path(rel), inc["url"], inc.get("size", 0)))
        total = sum(sz for _p, _u, sz in plan)
        if total > MAX_DOWNLOAD:
            raise PolyHavenError(f"Çok büyük ({total // (1024 * 1024)} MB); daha düşük çözünürlük seç (1k).")
        dest.mkdir(parents=True, exist_ok=True)
        root = dest.resolve()
        written = []
        for rel, url, _sz in plan:
            out = (dest / rel).resolve()
            if root not in out.parents and out != root:
                raise PolyHavenError(f"Geçersiz dosya yolu: {rel}")
            out.parent.mkdir(parents=True, exist_ok=True)
            with c.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(out, "wb") as f:
                    for chunk in resp.iter_bytes():
                        f.write(chunk)
            written.append(out)
        (dest / "KAYNAK.txt").write_text(f"{asset_id} — Poly Haven (CC0), https://polyhaven.com/a/{asset_id}\n"
                                         f"Biçim: {kind}, çözünürlük: {res}\n", encoding="utf-8")
        return written
    except PolyHavenError:
        raise
    except Exception as exc:
        raise PolyHavenError(f"İndirilemedi: {type(exc).__name__}: {exc}"[:200]) from exc
    finally:
        if own:
            c.close()
