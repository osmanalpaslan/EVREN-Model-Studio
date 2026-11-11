"""Sesle yazma (Madde 20 C3, 2026-11-12): kurulum, ayrı süreçte yazıya çevirme, WAV/biçim dönüşümü, arayüz akışı.
Gerçek faster-whisper ile ölçüm: oturum günlüğü (Türkçe TTS örnekleri)."""
from __future__ import annotations

import array
import json
import os
import time
import wave
from pathlib import Path

import pytest

from evren_studio.agent import voice


def _fake_install(data: Path) -> None:
    py = data / "ses" / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    py.parent.mkdir(parents=True)
    py.write_text("", encoding="utf-8")
    (data / "ses" / "kuruldu.json").write_text("{}", encoding="utf-8")


def test_kurulu_degilken_cevirmez(tmp_path):
    assert not voice.installed(tmp_path)
    with pytest.raises(voice.VoiceError, match="kurulu değil"):
        voice.transcribe(tmp_path, tmp_path / "x.wav")


def test_yarim_kurulum_kurulu_sayilmaz_ve_eski_cevirici_yenilenir(tmp_path):
    _fake_install(tmp_path)
    (tmp_path / "ses" / "kuruldu.json").unlink()
    assert not voice.installed(tmp_path)                                   # ortam var, model inmemiş → kurulu değil
    _fake_install_marker = tmp_path / "ses" / "kuruldu.json"
    _fake_install_marker.write_text("{}", encoding="utf-8")
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
    assert "WhisperModel" in calls[2][2] and calls[2][3] == voice.MODEL
    assert voice.installed(tmp_path) and json.loads((tmp_path / "ses" / "kuruldu.json").read_text())["model"] == "small"
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


def test_wav_yazimi(tmp_path):
    pcm = array.array("h", [0, 1000, -1000] * 1000).tobytes()
    p = voice.write_wav(tmp_path / "a.wav", pcm)
    with wave.open(str(p)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 16000, 3000)


def test_mikrofon_bicimi_16k_tek_kanala_donusur():
    from PySide6.QtMultimedia import QAudioFormat

    from evren_studio.ui.voice_input import to_mono16k

    fmt = QAudioFormat()
    fmt.setSampleRate(48000)
    fmt.setChannelCount(2)
    fmt.setSampleFormat(QAudioFormat.Float)
    one_sec = array.array("f", [0.5, -0.5] * 48000).tobytes()          # 1 sn stereo 48 kHz
    out = array.array("h")
    out.frombytes(to_mono16k(one_sec, fmt))
    assert len(out) == 16000 and all(v == 0 for v in out[:10])           # (0.5 + -0.5)/2 = 0
    fmt16 = QAudioFormat()
    fmt16.setSampleRate(16000)
    fmt16.setChannelCount(1)
    fmt16.setSampleFormat(QAudioFormat.Int16)
    raw = array.array("h", [5, 6, 7]).tobytes()
    assert to_mono16k(raw, fmt16) == raw                                 # zaten uygun → dokunulmaz


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


def _notes(w, monkeypatch):
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
    notes = _notes(w, monkeypatch)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    monkeypatch.setattr(voice, "base_python", lambda: "C:/Py/python.exe")
    monkeypatch.setattr(voice, "install", lambda data, py, log=None: _fake_install(Path(data)))
    w.session.composer.mic_btn.click()
    assert _wait(app, lambda: any("kuruldu" in n for n in notes))
    assert voice.installed(w.ctx.data_dir()) and not w.session.voice.busy and w.session.composer.mic_btn.isEnabled()


def test_cevrilen_metin_kutuya_eklenir_gonderilmez(win, monkeypatch, tmp_path):
    app, w = win
    v, comp = w.session.voice, w.session.composer
    comp.set_text("Önce şunu yap:")
    monkeypatch.setattr(voice, "transcribe", lambda data, wav: voice.Transcript("testleri çalıştır", 1.0))
    sent = []
    comp.submitted.connect(sent.append)
    wav = tmp_path / "d" / "k.wav"
    wav.parent.mkdir()
    wav.write_bytes(b"x")
    v.transcribe(wav)
    assert _wait(app, lambda: comp.edit.toPlainText() == "Önce şunu yap: testleri çalıştır")
    assert sent == [] and not wav.parent.exists()                         # gönderilmedi; geçici ses silindi


def test_bos_ceviri_ve_hata_notu(win, monkeypatch, tmp_path):
    app, w = win
    notes = _notes(w, monkeypatch)
    v = w.session.voice
    monkeypatch.setattr(voice, "transcribe", lambda data, wav: voice.Transcript("", 1.0))
    v.transcribe(tmp_path / "a.wav")
    assert _wait(app, lambda: any("anlaşılamadı" in n for n in notes))

    def boom(data, wav):
        raise voice.VoiceError("model yok")
    monkeypatch.setattr(voice, "transcribe", boom)
    v.transcribe(tmp_path / "b.wav")
    assert _wait(app, lambda: any("çevrilemedi: model yok" in n for n in notes)) and not v.busy


def test_cok_kisa_kayit_cevrilmez(win, monkeypatch):
    app, w = win
    notes = _notes(w, monkeypatch)
    v = w.session.voice

    class Src:
        def stop(self):
            pass

        def deleteLater(self):
            pass
    calls = []
    monkeypatch.setattr(v, "transcribe", lambda wav: calls.append(wav))
    v.source, v.io, v._t0, v.buf = Src(), None, time.monotonic(), bytearray(b"\x00" * 100)
    v.stop()
    assert calls == [] and any("çok kısa" in n for n in notes) and not v.recording
