"""Oyun araçları kurulumu: sağlama toplamı, zip slip, şablon klasörü, önceki indirmeyi yeniden kullanma (ağsız)."""
import hashlib
import io
import zipfile
from dataclasses import replace

import httpx
import pytest

from evren_studio.agent import gameinstall
from evren_studio.agent.gameinstall import InstallError, Item


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, b in files.items():
            z.writestr(n, b)
    return buf.getvalue()


def _client(payloads: dict[str, bytes], hits: list | None = None) -> httpx.Client:
    def handler(req):
        if hits is not None:
            hits.append(str(req.url))
        name = str(req.url).rsplit("/", 1)[-1]
        if name not in payloads:
            return httpx.Response(404)
        return httpx.Response(200, content=payloads[name])

    return httpx.Client(transport=httpx.MockTransport(handler))


def _item(key: str, data: bytes, algo: str = "sha256") -> Item:
    return replace(gameinstall.ITEMS[key], digest=hashlib.new(algo, data).hexdigest(), algo=algo, size=len(data))


def test_sağlama_uyuşmazsa_dosya_silinir(tmp_path):
    item = replace(gameinstall.ITEMS["blender"], digest="0" * 64)
    with pytest.raises(InstallError, match="SAĞLAMA"):
        gameinstall.download(item, tmp_path, lambda _m: None, client=_client({"blender-5.2.3-windows-x64.zip": b"sahte"}))
    assert list(tmp_path.iterdir()) == []


def test_http_hatası_anlaşılır(tmp_path):
    with pytest.raises(InstallError, match="HTTP 404"):
        gameinstall.download(gameinstall.ITEMS["blender"], tmp_path, lambda _m: None, client=_client({}))


def test_doğru_dosya_kaydedilir_ve_yeniden_indirilmez(tmp_path):
    data = b"x" * 3000
    item = _item("blender", data)
    hits: list = []
    c = _client({"blender-5.2.3-windows-x64.zip": data}, hits)
    p = gameinstall.download(item, tmp_path, lambda _m: None, client=c)
    assert p.read_bytes() == data
    logs: list[str] = []
    gameinstall.download(item, tmp_path, logs.append, client=c)
    assert len(hits) == 1 and "daha önce indirilmiş" in logs[0]


def test_zip_slip_reddedilir(tmp_path):
    z = zipfile.ZipFile(io.BytesIO(_zip({"../kotu.txt": b"x"})))
    with pytest.raises(InstallError, match="güvensiz"):
        gameinstall._safe_extract(z, tmp_path / "hedef")
    assert not (tmp_path / "kotu.txt").exists()


def test_kurulum_godot_şablon_blender_yerleşimi(tmp_path, monkeypatch):
    g = _zip({"Godot_v4.7.2-stable_win64.exe": b"exe", "Godot_v4.7.2-stable_win64_console.exe": b"c"})
    t = _zip({"templates/version.txt": b"4.7.2.stable", "templates/web_release.zip": b"w", "baska/x": b"y"})
    b = _zip({"blender-5.2.3-windows-x64/blender.exe": b"b"})
    items = {"godot": _item("godot", g, "sha512"), "sablonlar": _item("sablonlar", t, "sha512"),
             "blender": _item("blender", b)}
    monkeypatch.setattr(gameinstall, "ITEMS", items)
    c = _client({"Godot_v4.7.2-stable_win64.exe.zip": g, "Godot_v4.7.2-stable_export_templates.tpz": t,
                 "blender-5.2.3-windows-x64.zip": b})
    gameinstall.install(["godot", "sablonlar", "blender"], tmp_path, client=c)
    assert (tmp_path / "godot" / "._sc_").is_file()
    assert (tmp_path / "godot" / "Godot_v4.7.2-stable_win64.exe").is_file()
    tdir = tmp_path / "godot" / "editor_data" / "export_templates" / "4.7.2.stable"
    assert (tdir / "web_release.zip").is_file() and not (tdir / "baska").exists()
    assert (tmp_path / "blender" / "blender-5.2.3-windows-x64" / "blender.exe").is_file()


def test_gruplar_ve_boyut():
    assert gameinstall.GROUPS["godot"] == ["godot", "sablonlar"]
    assert 1_300_000_000 < gameinstall.total_size(["godot", "sablonlar"]) < 1_400_000_000
    assert all(len(i.digest) == (128 if i.algo == "sha512" else 64) for i in gameinstall.ITEMS.values())


def test_ayarlar_kartı_durumu_gösterir(monkeypatch):
    from PySide6.QtWidgets import QApplication

    from evren_studio.ui.gametools_card import GameToolsCard

    QApplication.instance() or QApplication([])

    monkeypatch.setattr(gameinstall, "status", lambda setting="": {"godot": True, "sablonlar": False, "blender": False})
    monkeypatch.setattr("evren_studio.agent.gametools.find_godot", lambda s="": "C:/g/godot.exe")
    monkeypatch.setattr("evren_studio.agent.gametools.find_blender", lambda s="": "")
    card = GameToolsCard(None)
    assert "1.281 MB" in card.godot_btn.text() and card.godot_btn.isEnabled()
    assert "406 MB" in card.blender_btn.text()
    assert "kurulu — C:/g/godot.exe" in card.state.text()
    card.deleteLater()
