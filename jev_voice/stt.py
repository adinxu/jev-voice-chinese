"""Speech to text via whisper.cpp's `whisper-server` (Metal accelerated, model stays loaded)."""
from __future__ import annotations

import array
import io
import shutil
import subprocess
import time
import wave

from . import config, net
from .pcm import sine, to_int16_bytes

_BLANK = {"", "[BLANK_AUDIO]", "(silence)", "[silence]", "[inaudible]", "[Music]", "[MUSIC]", "(music)"}
# Whisper hallucinates these on near-silent audio.
_HALLUCINATIONS = {"thank you.", "thanks for watching.", "thank you for watching.", "you", "bye.", "thank you"}


def _wav_bytes(pcm: array.array, rate: int = config.SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(to_int16_bytes(pcm))
    return buf.getvalue()


class WhisperServer:
    def __init__(self, port: int = config.WHISPER_PORT) -> None:
        self.port = port
        self.url = f"http://127.0.0.1:{port}"
        self.proc: subprocess.Popen | None = None

    def _alive(self) -> bool:
        try:
            r = net.get(self.url + "/", timeout=1.0)
            return r.status < 500
        except Exception:
            return False

    def start(self) -> None:
        if self._alive():
            return
        exe = shutil.which("whisper-server")
        if not exe:
            raise SystemExit("whisper-server not found: brew install whisper-cpp")
        if not config.WHISPER_MODEL.exists():
            raise SystemExit(f"Whisper model missing: {config.WHISPER_MODEL}\n"
                             "  curl -L -o models/ggml-base.en.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin")
        self.proc = subprocess.Popen(
            [exe, "-m", str(config.WHISPER_MODEL), "--host", "127.0.0.1", "--port", str(self.port),
             "-t", str(config.WHISPER_THREADS), "-l", config.WHISPER_LANG, "-nt"]
            + (["-tr"] if config.WHISPER_TRANSLATE else []),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(200):
            if self._alive():
                self._warm_up()
                return
            time.sleep(0.05)
        raise SystemExit("whisper-server failed to start")

    def _warm_up(self) -> None:
        """First inference compiles Metal shaders (~2 s); pay that before the user speaks."""
        try:
            self.transcribe(sine(0.05, 220.0, 0.6, config.SAMPLE_RATE))
        except Exception:
            pass

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def transcribe(self, pcm: array.array) -> str:
        fields = {"response_format": "json", "temperature": "0.0",
                  "no_timestamps": "true", "language": config.WHISPER_LANG}
        if config.WHISPER_TRANSLATE:
            fields["translate"] = "true"
        r = net.post_multipart(
            self.url + "/inference",
            fields,
            {"file": ("audio.wav", _wav_bytes(pcm), "audio/wav")},
        )
        r.raise_for_status()
        text = (r.json().get("text") or "").strip()
        if text in _BLANK or text.lower() in _HALLUCINATIONS or len(text) < 2:
            return ""
        return text
