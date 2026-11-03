"""Gözlem ajanı (src/evren_studio/gozlem.py + tools/ai_memory.py gozlem): kayıt, temizleme, tekilleştirme,
depoya gönderim (geçici "uzak" depo), geliştirici tarafında okuma/kapatma ve uygulama kaynakları. Ağ yok."""
from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import time
from pathlib import Path

import pytest

from evren_studio import gozlem

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def gz(tmp_path, monkeypatch):
    """Gözlem açık, kuyruk geçici klasörde."""
    monkeypatch.setenv("EVREN_GOZLEM", "1")
    monkeypatch.setattr(gozlem, "AYAR_ACIK", True)
    monkeypatch.setattr(gozlem, "gercek_veri_dizini", lambda: tmp_path / "veri")
    for k, v in {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.invalid", "GIT_COMMITTER_NAME": "t",
                 "GIT_COMMITTER_EMAIL": "t@t.invalid"}.items():
        monkeypatch.setenv(k, v)
    return tmp_path / "veri"


def _items(veri):
    return gozlem.Kuyruk(veri).oku()


def _git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout


def _bare(tmp_path) -> str:
    remote = tmp_path / "uzak.git"
    _git(tmp_path, "init", "-q", "--bare", str(remote))
    return str(remote)


# ---- temizleme (depo herkese açık) -----------------------------------------------------------------

def test_temizleme_gizli_ve_kisisel_veriyi_siler():
    home = str(Path.home())
    user = Path.home().name
    sahte = "sk" + "-" + "abcdefghijklmnop" + "qrstuvwxyz123456"     # parça parça: kanca gerçek anahtar sanmasın
    t = gozlem.temizle(f"{home}\\Desktop\\musteri listesi.xlsx açılamadı; anahtar {sahte} "
                       f"Bearer abc.def kisi@ornek.com.tr https://h.example/v1/x?key=1 10.0.0.5 {socket.gethostname()}",
                       limit=500)
    for bad in ("musteri", "listesi", "sk-abc", "abc.def", "kisi@", "key=1", "10.0.0.5", socket.gethostname()):
        assert bad not in t, (bad, t)
    for part in user.split():
        if len(part) >= 4:
            assert part.lower() not in t.lower()
    assert "<yol>" in t and "<eposta>" in t and "https://h.example/v1/x?<sorgu>" in t


def test_temizleme_baska_surucudeki_bosluklu_yolu_ve_tirnakli_yolu_siler():
    assert gozlem.temizle(r"D:\Gizli Proje\rapor 2026.docx bulunamadı") == "<yol>"
    assert gozlem.temizle(r"[Errno 2] No such file: 'E:\a b\c.txt' devam") == "[Errno 2] No such file: '<yol>' devam"


def test_temizleme_uygulamanin_kendi_kaynak_yolunu_goreli_tutar():
    p = gozlem.SOURCE_ROOT / "src" / "evren_studio" / "ui" / "session_view.py"
    assert gozlem.temizle(f'File "{p}", line 12') == 'File "src/evren_studio/ui/session_view.py", line 12'


def test_temizleme_kisaltir_ve_bos_metni_kaldirir():
    assert len(gozlem.temizle("a" * 10 + " " + "b " * 300)) <= gozlem.MAX_METIN + 1
    assert gozlem.temizle(None) == ""


def test_ayrinti_yalniz_izinli_anahtarlar():
    out = gozlem._ayrinti_temizle({"model": "glm-5.3", "icerik": "kullanıcının mesajı", "http": 503, "x": None})
    assert out == {"model": "glm-5.3", "http": 503}


# ---- imza ve kuyruk --------------------------------------------------------------------------------

def test_imza_satir_ve_sayi_degisince_ayni_istisna_turu_degisince_farkli():
    a = gozlem.imza_hesapla("cokme", "x", "ValueError", ["src/evren_studio/a.py:10 f"], "satır 12 hatalı")
    b = gozlem.imza_hesapla("cokme", "x", "ValueError", ["src/evren_studio/a.py:99 f"], "satır 13 hatalı")
    c = gozlem.imza_hesapla("cokme", "x", "KeyError", ["src/evren_studio/a.py:10 f"], "satır 12 hatalı")
    assert a == b != c


def _raise_in_pkg():
    try:
        int("x")
    except ValueError as exc:
        return exc


def test_kaydet_tekillestirir_sayar_ve_kendi_cercevelerini_tutar(gz):
    exc = _raise_in_pkg()
    i1 = gozlem.kaydet("cokme", "Yakalanmamış hata: ValueError", onem="yuksek", alan="ui", exc=exc)
    i2 = gozlem.kaydet("cokme", "Yakalanmamış hata: ValueError", onem="yuksek", alan="ui", exc=exc)
    assert i1 == i2
    g = _items(gz)[i1]
    assert g.sayac == 2 and g.istisna == "ValueError" and g.surumler == [gozlem.surum()]
    assert all(not c.startswith("tests/") for c in g.cerceveler)       # test çerçevesi değil, yalnız src/


def test_kapaliyken_kayit_yok(gz, monkeypatch):
    monkeypatch.setenv("EVREN_GOZLEM", "0")
    assert gozlem.kaydet("cokme", "x") is None
    monkeypatch.setenv("EVREN_GOZLEM", "1")
    monkeypatch.setattr(gozlem, "AYAR_ACIK", False)
    assert gozlem.kaydet("cokme", "x") is None
    assert not (gz / "gozlem" / "kuyruk.json").exists()


def test_kaydet_hata_firlatmaz(gz, monkeypatch):
    monkeypatch.setattr(gozlem.Kuyruk, "yaz", lambda *a, **k: (_ for _ in ()).throw(OSError("disk dolu")))
    assert gozlem.kaydet("cokme", "x") is None


def test_kuyruk_budanir_once_dusuk_onemliler(gz, monkeypatch):
    monkeypatch.setattr(gozlem, "MAX_KAYIT", 3)
    gozlem.kaydet("cokme", "kritik bir", onem="kritik")
    for i in range(4):
        gozlem.kaydet("qt_uyari", f"uyari {chr(97 + i)}", onem="dusuk")
    items = _items(gz)
    assert len(items) == 3 and any(g.onem == "kritik" for g in items.values())


def test_dusuk_onemli_ortam_esige_kadar_gonderilmez():
    g = gozlem.Gozlem(imza="x", tur="api_hatasi", baslik="b", onem="dusuk", alan="ortam", sayac=2)
    assert not g.gonderilmeli()
    g.sayac = 3
    assert g.gonderilmeli()
    g.gonderilen = 3
    assert not g.gonderilmeli()
    assert gozlem.Gozlem(imza="y", tur="cokme", baslik="b", onem="yuksek", alan="ui", sayac=1).gonderilmeli()


# ---- kaynak sınıflandırması: tetiklenen VE tetiklenmeyen (R-22) -----------------------------------------

class _Err:
    def __init__(self, kind, status=None, message="m", model="glm-5.3", code=None):
        from evren_studio.api.errors import ErrorKind

        self.kind = ErrorKind(kind)
        self.status, self.message, self.model, self.code, self.operation = status, message, model, code, "chat"


def test_api_hatasi_siniflandirma(gz):
    assert gozlem.api_hatasi(_Err("kimlik_doğrulama", 401)) is None          # yanlış anahtar: kullanıcı durumu
    assert gozlem.api_hatasi(_Err("kota_sınırı", 429)) is None
    assert gozlem.api_hatasi(_Err("kredi_bitti", 402)) is None
    s = gozlem.api_hatasi(_Err("sunucu_kullanılamıyor", 503, "Model şu anda dolu"))
    v = gozlem.api_hatasi(_Err("geçersiz_istek", 400, "tools[0] geçersiz"))
    items = _items(gz)
    assert (items[s].onem, items[s].alan) == ("dusuk", "ortam")
    assert (items[v].onem, items[v].alan) == ("yuksek", "api") and items[v].ayrinti["http"] == 400


def test_ajan_olayi_yalniz_anormallikleri_kaydeder(gz):
    assert gozlem.ajan_olayi({"model": "m", "ok": True, "duration_s": 3}) is None
    assert gozlem.ajan_olayi({"model": "m", "ok": False, "error_kind": "zaman_aşımı"}) is None
    i = gozlem.ajan_olayi({"model": "gemma-4-31b", "role": "kod", "ok": False, "event": "test_edit", "detail": "x"})
    assert _items(gz)[i].ayrinti == {"model": "gemma-4-31b", "rol": "kod", "olay": "test_edit"}


def test_tur_sonu_ve_qt_uyarisi(gz):
    assert gozlem.tur_sonu("done") is None and gozlem.tur_sonu("cancelled") is None
    assert gozlem.tur_sonu("max_steps", model="m", adim=80) is not None
    assert gozlem.qt_mesaji("warning", "QWindowsWindow::setGeometry: Unable to set geometry 100x100") is None
    assert gozlem.qt_mesaji("info", "bilgi") is None
    i = gozlem.qt_mesaji("warning", "QObject::setParent: Cannot set parent, new parent is in a different thread")
    assert _items(gz)[i].onem == "dusuk"


# ---- depoya gönderim ----------------------------------------------------------------------------------

def test_gonder_yetim_dal_acar_dosyalari_yazar_ve_temizdir(gz, tmp_path):
    remote = _bare(tmp_path)
    gozlem.kaydet("cokme", "Yakalanmamış hata: ValueError", onem="yuksek", alan="ui", exc=_raise_in_pkg(),
                  mesaj=f"{Path.home()}\\Belgeler\\gizli.txt")
    msg = gozlem.gonder(url=remote)
    assert "1 gözlem depoya gönderildi" in msg
    files = _git(tmp_path, "--git-dir", remote, "ls-tree", "-r", "--name-only", gozlem.BRANCH).split()
    assert "README.md" in files
    assert any(f.endswith("/kayit.md") for f in files)
    assert any(f.endswith(f"/olay-{gozlem.makine_kimligi()}.json") for f in files)
    # Gizlilik kapısı: dalda kullanıcı adı, ev klasörü, bilgisayar adı geçmez
    blob = "".join(_git(tmp_path, "--git-dir", remote, "show", f"{gozlem.BRANCH}:{f}") for f in files)
    for bad in (str(Path.home()), "gizli.txt", socket.gethostname(), *[p for p in Path.home().name.split()
                                                                       if len(p) >= 4]):
        assert bad.lower() not in blob.lower(), bad
    assert gozlem.gonder(url=remote) == "Gönderilecek yeni gözlem yok."
    assert gozlem.durum()["bekleyen"] == 0


def test_iki_makine_cakismadan_ve_eski_klonla_gonderir(gz, tmp_path, monkeypatch):
    remote = _bare(tmp_path)
    veri_b = tmp_path / "veri_b"
    gozlem.kaydet("cokme", "ortak hata", onem="yuksek")
    gozlem.kaydet("cokme", "ortak hata", onem="yuksek", veri_dizini=veri_b)
    assert "gönderildi" in gozlem.gonder(url=remote)                      # A: dalı açar
    monkeypatch.setattr(gozlem, "makine_kimligi", lambda: "bbbbbbbb")
    assert "gönderildi" in gozlem.gonder(veri_dizini=veri_b, url=remote)   # B: A'nın dalının üstüne
    monkeypatch.undo()
    monkeypatch.setenv("EVREN_GOZLEM", "1")
    monkeypatch.setattr(gozlem, "gercek_veri_dizini", lambda: gz)
    gozlem.kaydet("cokme", "ortak hata", onem="yuksek")                    # A'nın klonu artık eski
    assert "gönderildi" in gozlem.gonder(url=remote)
    files = _git(tmp_path, "--git-dir", remote, "ls-tree", "-r", "--name-only", gozlem.BRANCH).split()
    olay = [f for f in files if "/olay-" in f]
    assert len(olay) == 2 and len([f for f in files if f.endswith("kayit.md")]) == 1
    a = json.loads(_git(tmp_path, "--git-dir", remote, "show",
                        f"{gozlem.BRANCH}:{[f for f in olay if 'bbbbbbbb' not in f][0]}"))
    assert a["sayac"] == 2


def test_kayit_md_gelistiricinin_durumunu_ezmez(gz, tmp_path):
    remote = _bare(tmp_path)
    imza = gozlem.kaydet("cokme", "x hata", onem="yuksek")
    gozlem.gonder(url=remote)
    clone = gz / "gozlem" / "depo"
    p = clone / "gozlemler" / imza / "kayit.md"
    p.write_text(p.read_text(encoding="utf-8").replace("durum: acik", "durum: cozuldu"), encoding="utf-8")
    _git(clone, "commit", "-qam", "kapat")
    _git(clone, "push", "-q", "origin", f"HEAD:{gozlem.BRANCH}")
    gozlem.kaydet("cokme", "x hata", onem="yuksek")
    gozlem.gonder(url=remote)
    assert "durum: cozuldu" in _git(tmp_path, "--git-dir", remote, "show", f"{gozlem.BRANCH}:gozlemler/{imza}/kayit.md")


def test_depo_yoksa_yalniz_yerel(gz, monkeypatch):
    monkeypatch.setattr(gozlem, "depo_url", lambda ayar=None: None)
    gozlem.kaydet("cokme", "x")
    assert "yalnız bu bilgisayarda" in gozlem.gonder()


def test_gonderim_hatasi_kaydedilir_ve_temizlenir(gz, tmp_path):
    gozlem.kaydet("cokme", "x", onem="yuksek")
    msg = gozlem.gonder(url=str(tmp_path / "olmayan" / "depo.git"))
    assert msg.startswith("Gönderilemedi") and gozlem.durum()["son_hata"]
    assert str(Path.home()).lower() not in msg.lower()


# ---- geliştirici tarafı (tools/ai_memory.py) -------------------------------------------------------------

def _ai_memory(root: Path):
    spec = importlib.util.spec_from_file_location("ai_memory_gz", ROOT / "tools" / "ai_memory.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT = root
    mod.INCIDENTS = root / "docs" / "ai-memory" / "incidents"
    mod.INCIDENTS.mkdir(parents=True, exist_ok=True)
    return mod


def _dev_repo(tmp_path, remote) -> Path:
    dev = tmp_path / "gelistirici"
    _git(tmp_path, "clone", "-q", remote, str(dev))
    return dev


def test_gelistirici_okur_bildirir_kayda_donusturur_kapatir_ve_yeniden_gorur(gz, tmp_path, monkeypatch, capsys):
    remote = _bare(tmp_path)
    _git(tmp_path, "--git-dir", remote, "symbolic-ref", "HEAD", "refs/heads/master")
    imza = gozlem.kaydet("gorev_hatasi", "Arka plan görevi hata verdi: KeyError", onem="yuksek", alan="genel",
                         exc=KeyError("k"))
    gozlem.kaydet("api_hatasi", "API hatası: sunucu_kullanılamıyor (HTTP 503)", onem="dusuk", alan="ortam")
    gozlem.gonder(url=remote)
    dev = _dev_repo(tmp_path, remote)
    am = _ai_memory(dev)
    lines = am.baslangic_gozlem(dev)
    assert lines[0].startswith("! KULLANICIYA BİLDİR: uygulamadan 1 açık gözlem")   # düşük ortam eşik altında
    assert imza in lines[2]

    class A:
        pass

    a = A()
    a.imza, a.motor, a.model = imza[:6], "test", "test"
    assert am._gozlem_kayda(a) == 0
    inc = list(am.INCIDENTS.glob("*.md"))
    text = inc[0].read_text(encoding="utf-8")
    assert "kaynak_motor: EVREN Studio gözlem ajanı" in text and f"Gözlem `{imza}`" in text
    assert "KeyError" in text

    monkeypatch.setattr(am, "ROOT", dev)
    k = A()
    k.imza, k.kayit, k.durum, k.not_ = imza, inc[0].stem, "cozuldu", "düzeltildi"
    assert am._gozlem_kapat(k) == 0
    assert am.baslangic_gozlem(dev) == []                     # kapandı → bildirim yok
    # Geliştiricinin çalışma kopyası: izlenen dosyalar ve dal değişmedi; yalnız kayda-donustur'un açtığı kayıt var
    assert _git(dev, "status", "--porcelain", "--untracked-files=no") == ""
    assert _git(dev, "ls-files", "--others", "--exclude-standard").split() == [
        inc[0].relative_to(dev).as_posix()]
    assert _git(dev, "worktree", "list").count("\n") == 1
    time.sleep(1.1)
    gozlem.kaydet("gorev_hatasi", "Arka plan görevi hata verdi: KeyError", onem="yuksek", alan="genel",
                  exc=KeyError("k"))
    gozlem.gonder(url=remote)
    lines = am.baslangic_gozlem(dev)
    assert "YENİDEN görüldü" in lines[0] and "YENİDEN GÖRÜLDÜ" in lines[2]


def test_gelistirici_dal_yoksa_sessiz(tmp_path):
    remote = _bare(tmp_path)
    dev = tmp_path / "bos"
    _git(tmp_path, "init", "-q", str(dev))
    _git(dev, "remote", "add", "origin", remote)
    assert _ai_memory(dev).baslangic_gozlem(dev) == []


# ---- uygulama kaynakları (gerçek yollar) --------------------------------------------------------------------

def test_arka_plan_gorev_hatasi_kaydedilir_apierror_kaydedilmez(gz, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from evren_studio.api.errors import ApiError, ErrorKind
    from evren_studio.ui import workers

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(workers, "_ACCEPTING", True)
    got = []

    def bozuk():
        raise KeyError("eksik")

    def api():
        raise ApiError(ErrorKind.TIMEOUT, "zaman aşımı")

    for fn in (bozuk, api):
        workers.Task(fn, on_done=got.append, on_error=got.append).start()
    end = time.monotonic() + 5
    while len(got) < 2 and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)
    items = list(_items(gz).values())
    assert [g.tur for g in items] == ["gorev_hatasi"] and items[0].ayrinti["gorev"].endswith("bozuk")


def test_tur_akisindan_adim_sinirinda_gozlem(gz, tmp_path, monkeypatch, fake_keyring):
    """R-31: send → koşucu → _on_done yolundan."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from evren_studio.api.client import ChatResult

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    try:
        w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
        w.ctx.settings.agent_max_steps = 2
        n = [0]

        class C:
            def chat(self, model, messages, **kw):
                n[0] += 1
                return ChatResult(content="", finish_reason="tool_calls", tool_calls=[{
                    "id": f"c{n[0]}", "name": "list_files", "arguments": json.dumps({"path": f"d{n[0]}"})}])

            def close(self):
                pass

        w.ctx.make_client = lambda log_sink=None: C()
        w.ctx.make_client_for = lambda provider, log_sink=None: C()
        s = w.session
        proj = tmp_path / "proje"
        proj.mkdir()
        s.new_session()
        s.welcome._choose(str(proj))
        s.composer.set_model("deepseek-v4.1-flash", emit=True)
        s.set_mode("auto")
        s.send("klasörleri listele")
        end = time.monotonic() + 15
        while s.running and time.monotonic() < end:
            app.processEvents()
            time.sleep(0.02)
        assert not s.running
        turs = [g for g in _items(gz).values() if g.tur == "tur_sonu"]
        assert turs and turs[0].ayrinti["durma"] == "max_steps" and turs[0].ayrinti["model"]
    finally:
        w.close()
