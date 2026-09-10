"""Mono signed 16-bit little-endian PCM at an explicit sample rate."""

import wave
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from app.utils.errors import AudioProcessingError


@dataclass(frozen=True)
class AudioBuffer:
    """Transport-independent PCM, never an arbitrary uploaded path or tuple."""

    pcm: bytes
    sample_rate: int = 16000
    channels: Literal[1] = 1
    encoding: Literal["pcm_s16le"] = "pcm_s16le"

    def __post_init__(self) -> None:
        if not 8000 <= self.sample_rate <= 96000 or len(self.pcm) % 2:
            raise AudioProcessingError("Invalid PCM audio format.")
        if self.duration > 300:
            raise AudioProcessingError("Audio exceeds the canonical five-minute limit.")

    @property
    def duration(self) -> float:
        return len(self.pcm) / (2 * self.sample_rate)

    def to_wav(self) -> bytes:
        """Encode a playable WAV using only the standard library."""
        output = BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(self.pcm)
        return output.getvalue()


@dataclass(frozen=True)
class Transcript:
    text: str
    is_mock: bool = False
    detected_language: str | None = None
    language_probability: float | None = None
    audio_duration_seconds: float | None = None
    latency_seconds: float | None = None
    realtime_factor: float | None = None


@dataclass(frozen=True)
class VADResult:
    speech_detected: bool
    end_of_turn: bool
    speech_probability: float | None = None
    segments: tuple[tuple[float, float], ...] = ()
    latency_seconds: float | None = None
