"""Lazy faster-whisper adapter; model loading occurs only on an explicit cloud call."""

import asyncio
from threading import Lock

from app.config.settings import Settings
from app.schemas.audio import AudioBuffer, Transcript
from app.utils.errors import ConfigurationError, ProviderError
from app.voice.audio_utils import as_float32


class WhisperProvider:
    def __init__(self, settings: Settings) -> None:
        if settings.app_env != "lightning":
            raise ConfigurationError("Whisper is available only in explicit Lightning mode.")
        self.settings = settings
        self._model = None
        self._lock = Lock()

    def _transcribe(self, audio: AudioBuffer) -> Transcript:
        with self._lock:
            try:
                if self._model is None:
                    from faster_whisper import WhisperModel

                    self._model = WhisperModel(
                        self.settings.whisper_model_size,
                        device=self.settings.whisper_device,
                        compute_type=self.settings.whisper_compute_type,
                        download_root=str(self.settings.model_cache_dir),
                        local_files_only=not self.settings.allow_model_downloads,
                    )
                segments, _ = self._model.transcribe(
                    as_float32(audio), beam_size=1, vad_filter=False
                )
                text = " ".join(segment.text.strip() for segment in segments).strip()
                return Transcript(text)
            except Exception as exc:
                raise ProviderError(
                    "Whisper transcription failed. Verify cloud packages and model cache."
                ) from exc

    async def transcribe(self, audio: AudioBuffer) -> Transcript:
        return await asyncio.to_thread(self._transcribe, audio)
