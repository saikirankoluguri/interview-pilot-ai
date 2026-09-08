"""Lazy Silero endpoint detection over buffered audio; no torch.hub downloads."""

import asyncio
from threading import Lock

from app.config.settings import Settings
from app.schemas.audio import AudioBuffer, VADResult
from app.utils.errors import ConfigurationError, ProviderError
from app.voice.audio_utils import as_float32


class SileroProvider:
    def __init__(self, settings: Settings) -> None:
        if settings.app_env != "lightning":
            raise ConfigurationError("Silero is available only in explicit Lightning mode.")
        self.settings = settings
        self._model = None
        self._timestamps = None
        self._lock = Lock()

    def _detect(self, audio: AudioBuffer) -> VADResult:
        with self._lock:
            try:
                if self._model is None:
                    from silero_vad import get_speech_timestamps, load_silero_vad

                    # Package-bundled JIT asset; do not use torch.hub.load.
                    self._model = load_silero_vad()
                    self._timestamps = get_speech_timestamps
                import torch

                segments = self._timestamps(
                    torch.from_numpy(as_float32(audio)),
                    self._model,
                    sampling_rate=16000,
                    threshold=self.settings.vad_threshold,
                    min_silence_duration_ms=int(self.settings.vad_silence_seconds * 1000),
                    speech_pad_ms=0,
                )
                last_end = segments[-1]["end"] / 16000 if segments else audio.duration
                return VADResult(
                    bool(segments),
                    bool(segments)
                    and audio.duration - last_end >= self.settings.vad_silence_seconds,
                )
            except Exception as exc:
                raise ProviderError(
                    "Silero detection failed. Verify the cloud VAD runtime."
                ) from exc

    async def detect_end_of_turn(self, audio: AudioBuffer) -> VADResult:
        return await asyncio.to_thread(self._detect, audio)
