"""Sesle yazma (Madde 20 C3, 2026-11-12; Qt'siz): konuşmayı yazıya çevirir (faster-whisper — MIT, çevrimdışı).

Neden ayrı ortam: faster-whisper + CTranslate2 + model yüzlerce MB; kurulum paketine konmaz. İlk kullanımda kullanıcı
onayıyla `<veri>/ses/venv` sanal ortamına kurulur, model `<veri>/ses/modeller`e iner (bir kez). Çeviri AYRI süreçte
çalışır: uygulama donmaz, bellek iş bitince geri verilir; ses hiçbir sunucuya gönderilmez (bilgisayarda kalır).
Model: "small" (Türkçede "base"den belirgin doğru, CPU'da int8 ile kısa cümle birkaç saniye) — ölçüm oturum günlüğünde.
KAYIT da bu ortamda, ayrı süreçte yapılır (sounddevice/PortAudio — MIT): kurulum paketi QtMultimedia'yı (~60 MB, FFmpeg)
dışarıda bırakıyor; mikrofon için uygulamaya hiçbir şey eklenmez. Kaydedici "HAZIR" yazınca dinlemeye başlamıştır;
durdurma dosyası oluşunca (ya da üst sınırda) WAV'ı yazıp çıkar.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

PACKAGE = "faster-whisper==1.2.1"
PACKAGES = [PACKAGE, "sounddevice>=0.5"]
KIT_VERSION = 2                      # kuruldu.json'daki sürüm; değişince eksik paketler yeniden kurulur
MODEL = "small"
SAMPLE_RATE = 16000
MAX_SECONDS = 120                    # tek kayıt üst sınırı (yanlışlıkla açık kalan mikrofon)

RECORDER = r'''
import os, sys, time, wave
try:
    import sounddevice as sd
except Exception as exc:
    print("HATA: ses kütüphanesi yok: %s" % exc, flush=True); sys.exit(2)
out, stop, maxs = sys.argv[1], sys.argv[2], float(sys.argv[3])
chunks = []
def cb(indata, frames, t, status):
    chunks.append(bytes(indata))
try:
    stream = sd.RawInputStream(samplerate=16000, channels=1, dtype="int16", callback=cb)
    stream.start()
except Exception as exc:
    print("HATA: mikrofon açılamadı: %s" % exc, flush=True); sys.exit(3)
print("HAZIR", flush=True)
t0 = time.monotonic()
while not os.path.exists(stop) and time.monotonic() - t0 < maxs:
    time.sleep(0.03)
stream.stop(); stream.close()
with wave.open(out, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b"".join(chunks))
print("BITTI %.2f" % (time.monotonic() - t0), flush=True)
'''

# WAV numpy ile okunur ve modele DİZİ olarak verilir: faster-whisper dosya verilince PyAV ile çözer; PyAV 19
# `metadata_errors` parametresini kaldırdığı için faster-whisper 1.2.1 ile çöküyordu (2026-11-12 gerçek kurulum).
WORKER = r'''
import json, sys, time, wave
import numpy as np
t0 = time.monotonic()
from faster_whisper import WhisperModel
wav, model, root, lang = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
with wave.open(wav) as w:
    ch, sw, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
    raw = w.readframes(w.getnframes())
a = np.frombuffer(raw, dtype={1: np.uint8, 2: np.int16, 4: np.int32}[sw]).astype(np.float32)
a = (a - 128.0) / 128.0 if sw == 1 else a / float(2 ** (8 * sw - 1))
if ch > 1:
    a = a.reshape(-1, ch).mean(axis=1)
if rate != 16000 and len(a):
    n = int(len(a) * 16000 / rate)
    a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)
m = WhisperModel(model, device="cpu", compute_type="int8", download_root=root)
segs, info = m.transcribe(a, language=lang or None, vad_filter=True, beam_size=5)
text = " ".join(s.text.strip() for s in segs).strip()
print(json.dumps({"text": text, "seconds": round(time.monotonic() - t0, 1), "lang": info.language}, ensure_ascii=False))
'''


class VoiceError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata."""


@dataclass
class Transcript:
    text: str
    seconds: float


def home(data_dir: Path) -> Path:
    return Path(data_dir) / "ses"


def _venv_python(data_dir: Path) -> Path:
    v = home(data_dir) / "venv"
    return v / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def installed(data_dir: Path) -> bool:
    """Ortam + model + paket takımının güncel sürümü kurulu mu (eski takımda kaydedici eksik olabilir)."""
    marker = home(data_dir) / "kuruldu.json"
    if not (_venv_python(data_dir).is_file() and marker.is_file()):
        return False
    try:
        return int(json.loads(marker.read_text(encoding="utf-8")).get("surum") or 0) >= KIT_VERSION
    except (ValueError, OSError, AttributeError):
        return False


def _flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def _run(argv: list[str], timeout: float, log: Callable[[str], None]) -> str:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, creationflags=_flags())
    except subprocess.TimeoutExpired as exc:
        raise VoiceError(f"İşlem zaman aşımına uğradı ({int(timeout)} sn): {' '.join(argv[:3])}") from exc
    except OSError as exc:
        raise VoiceError(f"Çalıştırılamadı: {exc}") from exc
    if p.returncode != 0:
        tail = (p.stderr or p.stdout or "").strip()[-600:]
        raise VoiceError(f"Komut başarısız ({p.returncode}): {' '.join(argv[:3])}…\n{tail}")
    return p.stdout


def install(data_dir: Path, base_python: str, log: Callable[[str], None] = lambda s: None,
            model: str = MODEL) -> None:
    """Ortamı kurar + modeli indirir (internet gerekir; bir kez). Yarıda kalırsa yeniden çağrılabilir."""
    h = home(data_dir)
    h.mkdir(parents=True, exist_ok=True)
    py = _venv_python(data_dir)
    if not py.is_file():
        log("Ses ortamı oluşturuluyor…")
        _run([base_python, "-m", "venv", str(h / "venv")], 300, log)
    log("faster-whisper ve ses kaydı bileşeni kuruluyor (~100 MB, bir kez)…")
    _run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-q", *PACKAGES], 1800, log)
    log(f"Konuşma modeli indiriliyor ({model}, ~480 MB, bir kez)…")
    _run([str(py), "-c", "import sys; from faster_whisper import WhisperModel; "
          "WhisperModel(sys.argv[1], device='cpu', compute_type='int8', download_root=sys.argv[2])",
          model, str(h / "modeller")], 3600, log)
    (h / "kuruldu.json").write_text(json.dumps({"paketler": PACKAGES, "model": model, "surum": KIT_VERSION}),
                                    encoding="utf-8")
    log("Sesle yazma hazır.")


class Recording:
    """Ayrı süreçte mikrofon kaydı. start() "HAZIR" gelene kadar bekler (en çok 15 sn); stop() WAV yolunu döndürür."""

    def __init__(self, data_dir: Path, max_seconds: float = MAX_SECONDS, popen=subprocess.Popen):
        self.data_dir = Path(data_dir)
        self.dir = Path(tempfile.mkdtemp(prefix="evren-ses-"))
        self.wav = self.dir / "kayit.wav"
        self.stop_file = self.dir / "dur"
        self.max_seconds = max_seconds
        self._popen = popen
        self.proc = None
        self.started = 0.0
        self._lines: list[str] = []

    def start(self, timeout: float = 15.0) -> "Recording":
        if not installed(self.data_dir):
            raise VoiceError("Sesle yazma kurulu değil.")
        script = home(self.data_dir) / "kaydet.py"
        if not script.is_file() or script.read_text(encoding="utf-8") != RECORDER:
            script.write_text(RECORDER, encoding="utf-8")
        self.proc = self._popen([str(_venv_python(self.data_dir)), str(script), str(self.wav), str(self.stop_file),
                                 str(self.max_seconds)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", creationflags=_flags())
        ready = threading.Event()

        def pump() -> None:
            for line in self.proc.stdout:
                self._lines.append(line.strip())
                if line.startswith(("HAZIR", "HATA")):
                    ready.set()
            ready.set()
        threading.Thread(target=pump, name="ses-kaydi", daemon=True).start()
        if not ready.wait(timeout) or not any(x.startswith("HAZIR") for x in self._lines):
            err = next((x for x in self._lines if x.startswith("HATA")), "") or "kaydedici yanıt vermedi"
            self.cancel()
            raise VoiceError(err.replace("HATA: ", "")[:300])
        self.started = time.monotonic()
        return self

    def stop(self, timeout: float = 15.0) -> Path:
        self.stop_file.write_text("", encoding="utf-8")
        try:
            self.proc.wait(timeout)
        except subprocess.TimeoutExpired as exc:
            self.cancel()
            raise VoiceError("Kayıt kapanmadı.") from exc
        if not self.wav.is_file():
            raise VoiceError("Kayıt dosyası oluşmadı: " + " ".join(self._lines[-3:])[:300])
        return self.wav

    def cancel(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.kill()

    def cleanup(self) -> None:
        import shutil

        self.cancel()
        shutil.rmtree(self.dir, ignore_errors=True)


def duration(wav: Path) -> float:
    try:
        with wave.open(str(wav)) as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except (OSError, wave.Error, EOFError):
        return 0.0


def transcribe(data_dir: Path, wav: Path, language: str = "tr", model: str = MODEL,
               runner: Callable[[list[str], float], str] | None = None) -> Transcript:
    if not installed(data_dir):
        raise VoiceError("Sesle yazma kurulu değil.")
    h = home(data_dir)
    worker = h / "cevir.py"
    if not worker.is_file() or worker.read_text(encoding="utf-8") != WORKER:
        worker.write_text(WORKER, encoding="utf-8")
    argv = [str(_venv_python(data_dir)), str(worker), str(wav), model, str(h / "modeller"), language]
    out = (runner or (lambda a, t: _run(a, t, lambda s: None)))(argv, 600)
    line = next((ln for ln in reversed(out.strip().splitlines()) if ln.startswith("{")), "")
    try:
        data = json.loads(line)
    except ValueError as exc:
        raise VoiceError(f"Çeviri sonucu okunamadı: {out.strip()[-300:]}") from exc
    return Transcript(text=str(data.get("text") or "").strip(), seconds=float(data.get("seconds") or 0))


def write_wav(path: Path, pcm16: bytes, rate: int = SAMPLE_RATE) -> Path:
    """16 bit tek kanal PCM → WAV."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm16)
    return path


def base_python() -> str:
    from .mcp import McpError, _base_python

    try:
        return _base_python()
    except McpError as exc:
        raise VoiceError(str(exc)) from exc

