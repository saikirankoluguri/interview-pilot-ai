"""Lazy hexgrad Kokoro adapter with explicit cached asset paths."""

import asyncio
from threading import Lock

import numpy as np

from app.config.settings import Settings
from app.schemas.audio import AudioBuffer
from app.utils.errors import ConfigurationError, ProviderError
from app.voice.audio_utils import from_array


class KokoroProvider:
    def __init__(self, settings: Settings) -> None:
        if settings.app_env != "lightning":
            raise ConfigurationError("Kokoro is available only in explicit Lightning mode.")
        self.settings = settings
        self._pipeline = None
        self._lock = Lock()

    def _synthesize(self, text: str, voice: str | None) -> AudioBuffer:
        with self._lock:
            try:
                config = self.settings
                if self._pipeline is None:
                    if not config.allow_model_downloads and not all(
                        p is not None and p.is_file()
                        for p in (
                            config.kokoro_model_path,
                            config.kokoro_config_path,
                            config.kokoro_voice_path,
                        )
                    ):
                        raise ConfigurationError(
                            "Configure cached Kokoro model, config, and voice paths."
                        )
                    from kokoro import KModel, KPipeline
                    from loguru import logger

                    logger.disable("kokoro")

                    model = KModel(
                        config=str(config.kokoro_config_path)
                        if config.kokoro_config_path
                        else None,
                        model=str(config.kokoro_model_path) if config.kokoro_model_path else None,
                    )
                    model = model.to("cuda" if config.whisper_device == "cuda" else "cpu").eval()
                    self._pipeline = KPipeline(lang_code=config.kokoro_lang_code, model=model)
                # V0.1 uses one configured voice for every panelist; model output
                # cannot choose paths.
                voice_name = (
                    str(config.kokoro_voice_path) if config.kokoro_voice_path else config.tts_voice
                )
                chunks = [
                    audio.detach().cpu().numpy()
                    for _, _, audio in self._pipeline(
                        text, voice=voice_name, speed=config.tts_speed
                    )
                    if audio is not None
                ]
                if not chunks:
                    raise ProviderError("Kokoro returned no audio.")
                return from_array(config.tts_sample_rate, np.concatenate(chunks))
            except ConfigurationError:
                raise
            except Exception as exc:
                raise ProviderError(
                    "Kokoro synthesis failed. Verify cloud assets and language dependencies."
                ) from exc

    async def synthesize(self, text: str, *, voice: str | None = None) -> AudioBuffer:
        return await asyncio.to_thread(self._synthesize, text, voice)
