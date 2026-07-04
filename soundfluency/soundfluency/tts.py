"""Engines de TTS.

O engine padrão é o Kokoro (open source, Apache 2.0), hoje o modelo aberto mais
bem avaliado para inglês — qualidade próxima do ElevenLabs rodando local, sem
custo por caractere. O modelo (~310 MB) é baixado automaticamente na primeira
execução.

Para qualidade máxima absoluta há o engine ElevenLabs (API paga): exporte
ELEVENLABS_API_KEY e use --engine elevenlabs.

O engine espeak existe apenas para testar o pipeline sem baixar modelo — a voz
é robótica de propósito, não use em vídeo final.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 24000

MODEL_DIR = Path(os.environ.get("SOUNDFLUENCY_MODEL_DIR", Path.home() / ".soundfluency" / "models"))
KOKORO_MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
KOKORO_VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"[tts] baixando {url} -> {dest} (só na primeira vez)")
    with urllib.request.urlopen(url) as resp, open(tmp, "wb") as out:
        shutil.copyfileobj(resp, out)
    tmp.rename(dest)


class KokoroEngine:
    """TTS de alta qualidade rodando local (CPU serve; GPU acelera)."""

    def __init__(self, voice: str = "af_heart"):
        try:
            from kokoro_onnx import Kokoro
        except ImportError:
            sys.exit("kokoro-onnx não instalado. Rode: pip install -r requirements.txt")

        model = MODEL_DIR / "kokoro-v1.0.onnx"
        voices = MODEL_DIR / "voices-v1.0.bin"
        for url, dest in ((KOKORO_MODEL_URL, model), (KOKORO_VOICES_URL, voices)):
            if not dest.exists():
                _download(url, dest)

        self.kokoro = Kokoro(str(model), str(voices))
        self.voice = voice

    def synth(self, text: str, out_wav: Path, speed: float = 1.0) -> float:
        samples, sr = self.kokoro.create(text, voice=self.voice, speed=speed, lang="en-us")
        sf.write(out_wav, samples, sr)
        return len(samples) / sr


class ElevenLabsEngine:
    """Qualidade máxima via API paga. Requer ELEVENLABS_API_KEY."""

    def __init__(self, voice_id: str, model: str = "eleven_multilingual_v2"):
        self.api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            sys.exit("Defina ELEVENLABS_API_KEY para usar o engine elevenlabs.")
        self.voice_id = voice_id
        self.model = model

    def synth(self, text: str, out_wav: Path, speed: float = 1.0) -> float:
        import json
        import urllib.request

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        payload = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": speed},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
        )
        mp3 = out_wav.with_suffix(".mp3")
        with urllib.request.urlopen(req) as resp, open(mp3, "wb") as out:
            shutil.copyfileobj(resp, out)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3),
             "-ar", str(SAMPLE_RATE), "-ac", "1", str(out_wav)],
            check=True,
        )
        mp3.unlink()
        data, sr = sf.read(out_wav)
        return len(data) / sr


class EspeakEngine:
    """Voz sintética básica — SOMENTE para testar o pipeline."""

    def __init__(self, voice: str = "en-us"):
        if not shutil.which("espeak-ng"):
            sys.exit("espeak-ng não instalado (apt install espeak-ng).")
        self.voice = voice

    def synth(self, text: str, out_wav: Path, speed: float = 1.0) -> float:
        wpm = str(int(160 * speed))
        subprocess.run(
            ["espeak-ng", "-v", self.voice, "-s", wpm, "-w", str(out_wav), text],
            check=True,
        )
        data, sr = sf.read(out_wav)
        if sr != SAMPLE_RATE:
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(out_wav),
                 "-ar", str(SAMPLE_RATE), "-ac", "1", str(out_wav.with_suffix(".r.wav"))],
                check=True,
            )
            out_wav.with_suffix(".r.wav").rename(out_wav)
            data, sr = sf.read(out_wav)
        return len(data) / sr


def make_engine(cfg: dict, name: str | None = None):
    tts_cfg = cfg["tts"]
    engine = name or tts_cfg["engine"]
    if engine == "kokoro":
        return KokoroEngine(voice=tts_cfg["voice"])
    if engine == "elevenlabs":
        return ElevenLabsEngine(tts_cfg["elevenlabs_voice_id"], tts_cfg["elevenlabs_model"])
    if engine == "espeak":
        return EspeakEngine()
    sys.exit(f"Engine desconhecido: {engine}")


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SAMPLE_RATE), dtype=np.float32)


def load_wav(path: Path) -> np.ndarray:
    data, sr = sf.read(path, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    assert sr == SAMPLE_RATE, f"sample rate inesperado em {path}: {sr}"
    return data
