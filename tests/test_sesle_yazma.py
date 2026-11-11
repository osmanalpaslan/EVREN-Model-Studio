"""Sesle yazma (Madde 20 C3, 2026-11-12): kurulum, ayrı süreçte KAYIT ve yazıya çevirme, arayüz akışı.
Gerçek faster-whisper + gerçek mikrofon ölçümü: oturum günlüğü (Türkçe TTS örnekleri)."""
from __future__ import annotations

import array
import io
import json
import os
import time
import wave
from pathlib import Path

import pytest

from evren_studio.agent import voice


def _fake_install(data: Path, surum: int = voice.KIT_VERSION) -> None:
    py = data / "ses" / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("", encoding="utf-8")
    (data / "ses" / "kuruldu.json").write_text(json.dumps({"surum": surum}), encoding="utf-8")


def test_kurulu_degilken_cevirmez_ve_kaydetmez(tmp_path):
    assert not voice.installed(tmp_path)
    with pytest.raises(voice.VoiceError, match="kurulu değil"):
        voice.transcribe(tmp_path, tmp_path / "x.wav")
    with pytest.raises(voice.VoiceError, match="kurulu değil"):
        voice.Recording(tmp_path).start()


def test_yarim_veya_eski_kurulum_kurulu_sayilmaz_ve_eski_cevirici_yenilenir(tmp_path):
    _fake_install(tmp_path)
    (tmp_path / "ses" / "kuruldu.json").unlink()
    assert not voice.installed(tmp_path)                                   # ortam var, model inmemiş
    _fake_install(tmp_path, surum=1)
    assert not voice.installed(tmp_path)                                   # eski takım: kaydedici yok → yeniden kur
    _fake_install(tmp_path)
    (tmp_path / "ses" / "cevir.py").write_text("ESKİ SÜRÜM", encoding="utf-8")
    voice.transcribe(tmp_path, tmp_path / "k.wav", runner=lambda a, t: '{"text": "x", "seconds": 1}')
    assert (tmp_path / "ses" / "cevir.py").read_text(encoding="utf-8") == voice.WORKER


def test_kurulum_sirasi_ve_isaret(tmp_path, monkeypatch):
    calls = []

    def run(argv, timeout, log):
        calls.append(argv)
        if argv[1:3] == ["-m", "venv"]:
            _py = Path(argv[3]) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            _py.parent.mkdir(parents=True)
            _py.write_text("", encoding="utf-8")
        return ""
    monkeypatch.setattr(voice, "_run", run)
    logs = []
    voice.install(tmp_path, "C:/Py/python.exe", log=logs.append)
    assert calls[0][:3] == ["C:/Py/python.exe", "-m", "venv"]
    assert calls[1][1:4] == ["-m", "pip", "install"] and voice.PACKAGE in calls[1]
    assert any(x.startswith("sounddevice") for x in calls[1])             # kaydedici de aynı ortamda
    assert "WhisperModel" in calls[2][2] and calls[2][3] == voice.MODEL
    data = json.loads((tmp_path / "ses" / "kuruldu.json").read_text())
    assert voice.installed(tmp_path) and data["model"] == "small" and data["surum"] == voice.KIT_VERSION
    assert any("indiriliyor" in x for x in logs)


def test_ceviri_ayri_surecte_ve_sonuc_okunur(tmp_path):
    _fake_install(tmp_path)
    seen = {}

    def runner(argv, timeout):
        seen["argv"], seen["timeout"] = argv, timeout
        return 'uyarı satırı\n{"text": " Merhaba dünya. ", "seconds": 2.5, "lang": "tr"}\n'
    res = voice.transcribe(tmp_path, tmp_path / "k.wav", runner=runner)
    assert res.text == "Merhaba dünya." and res.seconds == 2.5
    worker = Path(seen["argv"][1])
    assert worker.read_text(encoding="utf-8") == voice.WORKER and seen["argv"][-1] == "tr"
    with pytest.raises(voice.VoiceError, match="okunamadı"):
        voice.transcribe(tmp_path, tmp_path / "k.wav", runner=lambda a, t: "Traceback: çöktü")


def test_wav_yazimi_ve_sure(tmp_path):
    pcm = array.array("h", [0, 1000, -1000] * 8000).tobytes()
    p = voice.write_wav(tmp_path / "a.wav", pcm)
    with wave.open(str(p)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 16000, 24000)
    assert voice.duration(p) == 1.5 and voice.duration(tmp_path / "yok.wav") == 0.0


class FakeProc:
    """Kaydedici sürecinin yerine: HAZIR (ya da HATA) yazar; durdurma dosyası gelince WAV yazıp çıkar."""

    def __init__(self, argv, lines=("HAZIR\n",), seconds=1.0, **kw):
        self.argv = argv
        self.stdout = io.StringIO("".join(lines))
        self.wav, self.stop_file = Path(argv[2]), Path(argv[3])
        self.seconds = seconds
        self.killed = False
        self.code = None

    def wait(self, timeout=None):
        if self.stop_file.exists() and self.seconds:
            voice.write_wav(self.wav, b"\x00\x00" * int(16000 * self.seconds))
        self.code = 0
        return 0

    def poll(self):
        return self.code

    def kill(self):
        self.killed = True
        self.code = -9


def test_kayit_alt_surecte_hazir_bekler_durdurunca_wav(tmp_path):
    _fake_install(tmp_path)
    procs = []
    rec = voice.Recording(tmp_path, max_seconds=30, popen=lambda argv, **kw: procs.append(FakeProc(argv)) or procs[-1])
    rec.start(timeout=5)
    assert procs[0].argv[1].endswith("kaydet.py") and procs[0].argv[-1] == "30"
    assert (tmp_path / "ses" / "kaydet.py").read_text(encoding="utf-8") == voice.RECORDER
    wav = rec.stop()
    assert wav.is_file() and voice.duration(wav) == 1.0 and rec.stop_file.exists()
    rec.cleanup()
    assert not rec.dir.exists()


def test_mikrofon_acilamazsa_anlasilir_hata(tmp_path):
    _fake_install(tmp_path)
    pr = {}

    def popen(argv, **kw):
        pr["p"] = FakeProc(argv, lines=("HATA: mikrofon açılamadı: Invalid device\n",))
        return pr["p"]
    with pytest.raises(voice.VoiceError, match="mikrofon açılamadı"):
        voice.Recording(tmp_path, popen=popen).start(timeout=5)
    assert pr["p"].killed or pr["p"].code is not None


# ---- arayüz ----

@pytest.fixture()
def win(tmp_path, monkeypatch, fake_keyring):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setenv("EVREN_STUDIO_DATA_DIR", str(tmp_path / "data"))
    app = QApplication.instance() or QApplication([])
    from evren_studio.ui.main_window import MainWindow

    w = MainWindow()
    yield app, w
    w.close()


def _wait(app, cond, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def _notes(w):
    got = []
    w.session.voice.note.connect(lambda text, icon: got.append(text))
    return got


def test_karsilama_ekraninda_not_kilitleyen_pencere_acmaz(win, monkeypatch):
    """Oturum yokken _note MODAL pencere açar; sesle yazma notları orada mikrofon baloncuğuna gider."""
    from PySide6.QtWidgets import QMessageBox

    app, w = win
    assert not w.session.session_id
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: (_ for _ in ()).throw(AssertionError("modal")))
    w.session.voice.note.emit("Sesle yazma kuruluyor…", "download")
    app.processEvents()
    assert w.session.composer.mic_btn.toolTip() == "Sesle yazma kuruluyor…"


def test_ilk_kullanimda_onay_hayir_ise_hicbir_sey(win, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    app, w = win
    v = w.session.voice
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    installs = []
    monkeypatch.setattr(voice, "install", lambda *a, **k: installs.append(a))
    w.session.composer.mic_btn.click()
    app.processEvents()
    assert not v.recording and not v.busy and installs == [] and not w.session.composer.mic_btn.isChecked()


def test_ilk_kullanimda_onay_evet_ise_arka_planda_kurar(win, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    app, w = win
    notes = _notes(w)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    monkeypatch.setattr(voice, "base_python", lambda: "C:/Py/python.exe")
    monkeypatch.setattr(voice, "install", lambda data, py, log=None: _fake_install(Path(data)))
    w.session.composer.mic_btn.click()
    assert _wait(app, lambda: any("kuruldu" in n for n in notes))
    assert voice.installed(w.ctx.data_dir()) and not w.session.voice.busy and w.session.composer.mic_btn.isEnabled()


class FakeRec:
    def __init__(self, data_dir, seconds=1.5, fail_start=None):
        self.data_dir = data_dir
        self.dir = Path(data_dir) / "kayit_tmp"
        self.seconds, self.fail_start = seconds, fail_start
        self.cleaned = False

    def start(self, timeout=15.0):
        if self.fail_start:
            raise voice.VoiceError(self.fail_start)
        self.dir.mkdir(parents=True, exist_ok=True)
        return self

    def stop(self, timeout=15.0):
        return voice.write_wav(self.dir / "kayit.wav", b"\x00\x00" * int(16000 * self.seconds))

    def cleanup(self):
        self.cleaned = True


def test_kaydet_durdur_cevir_metin_kutuya_eklenir_gonderilmez(win, monkeypatch):
    app, w = win
    v, comp = w.session.voice, w.session.composer
    _fake_install(w.ctx.data_dir())
    recs = []
    monkeypatch.setattr(voice, "Recording", lambda data: recs.append(FakeRec(data)) or recs[-1])
    seen = []
    monkeypatch.setattr(voice, "transcribe", lambda data, wav: (seen.append(voice.duration(wav)),
                                                                voice.Transcript("testleri çalıştır", 1.0))[1])
    comp.set_text("Önce şunu yap:")
    sent = []
    comp.submitted.connect(sent.append)
    comp.mic_btn.click()
    assert _wait(app, lambda: v.recording) and comp.mic_btn.isChecked()
    comp.mic_btn.click()
    assert _wait(app, lambda: comp.edit.toPlainText() == "Önce şunu yap: testleri çalıştır")
    assert seen == [1.5] and sent == [] and recs[0].cleaned and not v.busy and not comp.mic_btn.isChecked()


def test_cok_kisa_kayit_cevrilmez(win, monkeypatch):
    app, w = win
    notes = _notes(w)
    v = w.session.voice
    _fake_install(w.ctx.data_dir())
    monkeypatch.setattr(voice, "Recording", lambda data: FakeRec(data, seconds=0.2))
    calls = []
    monkeypatch.setattr(voice, "transcribe", lambda data, wav: calls.append(wav))
    v.start()
    assert _wait(app, lambda: v.recording)
    v.stop()
    assert _wait(app, lambda: any("çok kısa" in n for n in notes)) and calls == [] and not v.busy


def test_mikrofon_acilamazsa_not(win, monkeypatch):
    app, w = win
    notes = _notes(w)
    v = w.session.voice
    _fake_install(w.ctx.data_dir())
    monkeypatch.setattr(voice, "Recording", lambda data: FakeRec(data, fail_start="mikrofon açılamadı: izin yok"))
    v.start()
    assert _wait(app, lambda: any("Mikrofon açılamadı" in n and "izin" in n for n in notes))
    assert not v.recording and not v.busy


def test_bos_ceviri_ve_hata_notu(win, monkeypatch, tmp_path):
    app, w = win
    notes = _notes(w)
    v = w.session.voice
    monkeypatch.setattr(voice, "transcribe", lambda data, wav: voice.Transcript("", 1.0))
    v.transcribe(tmp_path / "a" / "a.wav")
    assert _wait(app, lambda: any("anlaşılamadı" in n for n in notes))

    def boom(data, wav):
        raise voice.VoiceError("model yok")
    monkeypatch.setattr(voice, "transcribe", boom)
    v.transcribe(tmp_path / "b" / "b.wav")
    assert _wait(app, lambda: any("çevrilemedi: model yok" in n for n in notes)) and not v.busy


def test_kapanista_acik_kayit_kapanir(win, monkeypatch):
    app, w = win
    v = w.session.voice
    rec = FakeRec(w.ctx.data_dir())
    v.rec = rec
    v.shutdown()
    assert rec.cleaned and v.rec is None
