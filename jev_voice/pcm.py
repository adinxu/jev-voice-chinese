"""Tiny PCM helpers over stdlib `array` (replaces numpy).

Audio is mono 16 kHz float32. Frames are `array('f')`; the helpers here cover the
few operations the project needs: concatenation, RMS for the VAD, conversion to
signed 16-bit bytes for WAV/Whisper, and a sine tone for the Metal warm-up.
"""
from __future__ import annotations

import array
import math


def concat(parts: list[array.array]) -> array.array:
    out = array.array("f")
    for part in parts:
        out.extend(part)
    return out


def rms(frame: array.array) -> float:
    if not frame:
        return 0.0
    return math.sqrt(sum(x * x for x in frame) / len(frame))


def to_int16_bytes(pcm: array.array) -> bytes:
    ints = array.array("h", (max(-32768, min(32767, int(x * 32767))) for x in pcm))
    return ints.tobytes()


def sine(amplitude: float, freq: float, seconds: float, rate: int) -> array.array:
    n = int(rate * seconds)
    step = 2.0 * math.pi * freq / rate
    return array.array("f", (amplitude * math.sin(step * i) for i in range(n)))
