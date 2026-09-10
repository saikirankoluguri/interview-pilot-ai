"""Lazy Silero segment detection over canonical PCM; no torch.hub downloads."""

import asyncio
import logging
from threading import Lock
from time import perf_counter

from app.config.settings import Settings
from app.providers.health import ProviderHealth
from app.providers.metrics import ProviderOperationMetrics
from app.schemas.audio import AudioBuffer, VADResult
from app.utils.errors import (
    ConfigurationError,
    ProviderInferenceError,
    ProviderInitializationError,
)
from app.voice.audio_utils import as_float32

logger = logging.getLogger(__name__)
_SILERO_SAMPLE_RATE = 16000


class SileroProvider:
    def __init__(self, settings: Settings) -> None:
        if settings.app_env != "lightning":
            raise ConfigurationError("Silero is available only in explicit Lightning mode.")
        self.settings = settings
        self._model = None
        self._timestamps = None
        self._lock = Lock()
        self.last_metrics: ProviderOperationMetrics | None = None

    def _ensure_runtime(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from silero_vad import get_speech_timestamps, load_silero_vad
        except ImportError as exc:
            raise ProviderInitializationError(
                "Silero VAD and its CPU torch runtime are not installed."
            ) from exc
        try:
            if self.settings.vad_model_path is not None:
                if not self.settings.vad_model_path.is_file():
                    raise ProviderInitializationError(
                        "Configured Silero model path does not exist."
                    )
                self._model = torch.jit.load(
                    str(self.settings.vad_model_path), map_location=self.settings.vad_device
                )
            else:
                # silero-vad ships this asset in its wheel; never use torch.hub.load.
                self._model = load_silero_vad()
            if hasattr(self._model, "to"):
                self._model = self._model.to(self.settings.vad_device)
            if hasattr(self._model, "eval"):
                self._model = self._model.eval()
            self._timestamps = get_speech_timestamps
        except ProviderInitializationError:
            raise
        except Exception as exc:
            raise ProviderInitializationError(
                "Silero initialization failed. Verify the CPU runtime and model asset."
            ) from exc

    def _detect(self, audio: AudioBuffer) -> VADResult:
        if not audio.pcm:
            return VADResult(False, False, speech_probability=0)
        with self._lock:
            self._ensure_runtime()
            started = perf_counter()
            try:
                import torch

                values = as_float32(audio, _SILERO_SAMPLE_RATE)
                segments = self._timestamps(
                    torch.from_numpy(values),
                    self._model,
                    sampling_rate=_SILERO_SAMPLE_RATE,
                    threshold=self.settings.vad_threshold,
                    min_speech_duration_ms=self.settings.vad_min_speech_ms,
                    min_silence_duration_ms=self.settings.vad_min_silence_ms,
                    speech_pad_ms=self.settings.vad_speech_pad_ms,
                )
                normalized = tuple(
                    (
                        max(0, int(segment["start"])) / _SILERO_SAMPLE_RATE,
                        max(0, int(segment["end"])) / _SILERO_SAMPLE_RATE,
                    )
                    for segment in segments
                )
                speech_seconds = sum(max(0, end - start) for start, end in normalized)
                speech_probability = min(1.0, speech_seconds / audio.duration)
                trailing_silence = audio.duration - normalized[-1][1] if normalized else 0
                end_of_turn = bool(normalized) and trailing_silence >= (
                    self.settings.vad_min_silence_ms / 1000
                )
            except Exception as exc:
                raise ProviderInferenceError("Silero voice activity detection failed.") from exc
            elapsed = perf_counter() - started
            self.last_metrics = ProviderOperationMetrics(
                "detect", elapsed, audio_duration_seconds=audio.duration
            )
            logger.info(
                "provider=silero device=%s duration_ms=%.1f audio_seconds=%.3f success=true",
                self.settings.vad_device,
                elapsed * 1000,
                audio.duration,
            )
            return VADResult(
                speech_detected=bool(normalized),
                end_of_turn=end_of_turn,
                speech_probability=speech_probability,
                segments=normalized,
                latency_seconds=elapsed,
            )

    async def detect_end_of_turn(self, audio: AudioBuffer) -> VADResult:
        return await asyncio.to_thread(self._detect, audio)

    async def health_check(self) -> ProviderHealth:
        started = perf_counter()
        await asyncio.to_thread(self._health_initialize)
        return ProviderHealth(
            provider="silero",
            status="healthy",
            mode="real",
            latency_ms=(perf_counter() - started) * 1000,
            model=str(self.settings.vad_model_path or "package-bundled"),
            device=self.settings.vad_device,
        )

    def _health_initialize(self) -> None:
        with self._lock:
            self._ensure_runtime()
