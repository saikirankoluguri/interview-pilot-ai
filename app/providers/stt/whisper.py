"""Lazy faster-whisper adapter; loading occurs only after explicit selection."""

import asyncio
import logging
from threading import Lock
from time import perf_counter

from app.config.settings import Settings
from app.providers.health import ProviderHealth
from app.providers.metrics import ProviderOperationMetrics, safe_ratio
from app.schemas.audio import AudioBuffer, Transcript
from app.utils.errors import (
    AudioProcessingError,
    ConfigurationError,
    ProviderInferenceError,
    ProviderInitializationError,
)
from app.voice.audio_utils import as_float32

logger = logging.getLogger(__name__)


class WhisperProvider:
    def __init__(self, settings: Settings) -> None:
        if settings.app_env != "lightning":
            raise ConfigurationError("Whisper is available only in explicit Lightning mode.")
        self.settings = settings
        self._model = None
        self._lock = Lock()
        self.last_metrics: ProviderOperationMetrics | None = None

    @property
    def model_name(self) -> str:
        path = self.settings.whisper_model_path
        return str(path) if path is not None else self.settings.whisper_model_size

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        if (
            self.settings.whisper_model_path is not None
            and not self.settings.whisper_model_path.exists()
        ):
            raise ProviderInitializationError("Configured Whisper model path does not exist.")
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ProviderInitializationError(
                "faster-whisper is not installed in this runtime."
            ) from exc
        try:
            kwargs = {
                "device": self.settings.whisper_device,
                "compute_type": self.settings.whisper_compute_type,
                "local_files_only": not self.settings.allow_model_downloads,
            }
            if self.settings.whisper_model_path is None:
                kwargs["download_root"] = str(self.settings.model_cache_dir)
            self._model = WhisperModel(self.model_name, **kwargs)
            return self._model
        except ProviderInitializationError:
            raise
        except Exception as exc:
            raise ProviderInitializationError(
                "Whisper initialization failed. Verify the CPU package and cached model."
            ) from exc

    def _transcribe(self, audio: AudioBuffer) -> Transcript:
        if not audio.pcm:
            raise AudioProcessingError("No microphone audio was received.")
        with self._lock:
            model = self._ensure_model()
            started = perf_counter()
            try:
                segments, info = model.transcribe(
                    as_float32(audio),
                    beam_size=1,
                    vad_filter=False,
                    language=self.settings.whisper_language,
                )
                text = " ".join(segment.text.strip() for segment in segments).strip()
            except Exception as exc:
                raise ProviderInferenceError("Whisper transcription failed.") from exc
            elapsed = perf_counter() - started
            self.last_metrics = ProviderOperationMetrics(
                "transcribe", elapsed, audio_duration_seconds=audio.duration
            )
            logger.info(
                "provider=whisper model=%s device=%s duration_ms=%.1f audio_seconds=%.3f "
                "success=true",
                self.model_name,
                self.settings.whisper_device,
                elapsed * 1000,
                audio.duration,
            )
            return Transcript(
                text=text,
                detected_language=getattr(info, "language", None),
                language_probability=getattr(info, "language_probability", None),
                audio_duration_seconds=audio.duration,
                latency_seconds=elapsed,
                realtime_factor=safe_ratio(elapsed, audio.duration),
            )

    async def transcribe(self, audio: AudioBuffer) -> Transcript:
        return await asyncio.to_thread(self._transcribe, audio)

    async def health_check(self) -> ProviderHealth:
        started = perf_counter()
        await asyncio.to_thread(self._health_initialize)
        return ProviderHealth(
            provider="whisper",
            status="healthy",
            mode="real",
            latency_ms=(perf_counter() - started) * 1000,
            model=self.model_name,
            device=self.settings.whisper_device,
        )

    def _health_initialize(self) -> None:
        with self._lock:
            self._ensure_model()
