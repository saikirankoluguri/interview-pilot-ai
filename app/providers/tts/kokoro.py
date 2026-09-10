"""Lazy hexgrad Kokoro adapter with a narrow runtime-specific boundary."""

import asyncio
import logging
from threading import Lock
from time import perf_counter

import numpy as np

from app.config.settings import Settings
from app.providers.health import ProviderHealth
from app.providers.metrics import ProviderOperationMetrics
from app.schemas.audio import AudioBuffer
from app.utils.errors import (
    AudioProcessingError,
    ConfigurationError,
    ProviderInferenceError,
    ProviderInitializationError,
)
from app.voice.audio_utils import from_array

logger = logging.getLogger(__name__)


class KokoroProvider:
    """Adapter for hexgrad/kokoro 0.9.x; imports and assets stay runtime-local."""

    def __init__(self, settings: Settings) -> None:
        if settings.app_env != "lightning":
            raise ConfigurationError("Kokoro is available only in explicit Lightning mode.")
        self.settings = settings
        self._pipeline = None
        self._lock = Lock()
        self.last_metrics: ProviderOperationMetrics | None = None

    def _ensure_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        config = self.settings
        model_path = config.resolved_kokoro_model_path
        required = (model_path, config.kokoro_config_path, config.kokoro_voice_path)
        if not config.allow_model_downloads and not all(
            path is not None and path.is_file() for path in required
        ):
            raise ProviderInitializationError(
                "Configure cached Kokoro model, config, and voice paths."
            )
        try:
            from kokoro import KModel, KPipeline
        except ImportError as exc:
            raise ProviderInitializationError("Kokoro is not installed in this runtime.") from exc
        try:
            model = KModel(
                config=str(config.kokoro_config_path) if config.kokoro_config_path else None,
                model=str(model_path) if model_path else None,
            )
            model = model.to(config.tts_device).eval()
            self._pipeline = KPipeline(lang_code=config.kokoro_lang_code, model=model)
            return self._pipeline
        except Exception as exc:
            raise ProviderInitializationError(
                "Kokoro initialization failed. Verify cached assets and language dependencies."
            ) from exc

    @staticmethod
    def _numpy_audio(value: object) -> np.ndarray:
        if hasattr(value, "detach"):
            value = value.detach()
        if hasattr(value, "cpu"):
            value = value.cpu()
        if hasattr(value, "numpy"):
            value = value.numpy()
        return np.asarray(value, dtype=np.float32).reshape(-1)

    def _synthesize(self, text: str, voice: str | None) -> AudioBuffer:
        clean_text = text.strip()
        if not clean_text:
            raise AudioProcessingError("Interviewer text is empty.")
        if len(clean_text) > self.settings.tts_max_text_characters:
            raise AudioProcessingError("Interviewer text exceeds the speech synthesis limit.")
        with self._lock:
            pipeline = self._ensure_pipeline()
            voice_name = voice or (
                str(self.settings.kokoro_voice_path)
                if self.settings.kokoro_voice_path
                else self.settings.tts_voice
            )
            started = perf_counter()
            try:
                chunks = [
                    self._numpy_audio(audio)
                    for _, _, audio in pipeline(
                        clean_text, voice=voice_name, speed=self.settings.tts_speed
                    )
                    if audio is not None
                ]
                if not chunks or not any(chunk.size for chunk in chunks):
                    raise ProviderInferenceError("Kokoro returned no audio.")
                result = from_array(self.settings.tts_sample_rate, np.concatenate(chunks))
            except ProviderInferenceError:
                raise
            except Exception as exc:
                raise ProviderInferenceError("Kokoro synthesis failed.") from exc
            elapsed = perf_counter() - started
            self.last_metrics = ProviderOperationMetrics(
                "synthesize", elapsed, audio_duration_seconds=result.duration
            )
            logger.info(
                "provider=kokoro device=%s voice=%s duration_ms=%.1f audio_seconds=%.3f "
                "success=true",
                self.settings.tts_device,
                self.settings.tts_voice,
                elapsed * 1000,
                result.duration,
            )
            return result

    async def synthesize(self, text: str, *, voice: str | None = None) -> AudioBuffer:
        return await asyncio.to_thread(self._synthesize, text, voice)

    async def health_check(self) -> ProviderHealth:
        started = perf_counter()
        await asyncio.to_thread(self._health_initialize)
        return ProviderHealth(
            provider="kokoro",
            status="healthy",
            mode="real",
            latency_ms=(perf_counter() - started) * 1000,
            model=str(self.settings.resolved_kokoro_model_path or "configured-runtime"),
            device=self.settings.tts_device,
            detail=f"voice={self.settings.tts_voice}",
        )

    def _health_initialize(self) -> None:
        with self._lock:
            self._ensure_pipeline()
