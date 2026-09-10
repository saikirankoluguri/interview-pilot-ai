"""The only provider selection boundary; importing it never loads GPU packages."""

from dataclasses import dataclass

from app.config.settings import Settings
from app.providers.health import ProviderHealth
from app.providers.llm.base import LLMProvider
from app.providers.stt.base import SpeechToTextProvider
from app.providers.tts.base import TextToSpeechProvider
from app.providers.vad.base import VoiceActivityDetectionProvider
from app.utils.errors import ConfigurationError


def create_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        from app.providers.llm.mock import MockLLMProvider

        return MockLLMProvider()
    if settings.llm_provider != "qwen":
        raise ConfigurationError(f"Unknown LLM provider: {settings.llm_provider}")
    from app.providers.llm.qwen import QwenProvider

    return QwenProvider(settings)


def create_stt_provider(settings: Settings) -> SpeechToTextProvider:
    if settings.stt_provider == "mock":
        from app.providers.stt.mock import MockSTTProvider

        return MockSTTProvider()
    if settings.stt_provider != "whisper":
        raise ConfigurationError(f"Unknown STT provider: {settings.stt_provider}")
    from app.providers.stt.whisper import WhisperProvider

    return WhisperProvider(settings)


def create_tts_provider(settings: Settings) -> TextToSpeechProvider:
    if settings.tts_provider == "mock":
        from app.providers.tts.mock import MockTTSProvider

        return MockTTSProvider()
    if settings.tts_provider != "kokoro":
        raise ConfigurationError(f"Unknown TTS provider: {settings.tts_provider}")
    from app.providers.tts.kokoro import KokoroProvider

    return KokoroProvider(settings)


def create_vad_provider(settings: Settings) -> VoiceActivityDetectionProvider:
    if settings.vad_provider == "mock":
        from app.providers.vad.mock import MockVADProvider

        return MockVADProvider()
    if settings.vad_provider != "silero":
        raise ConfigurationError(f"Unknown VAD provider: {settings.vad_provider}")
    from app.providers.vad.silero import SileroProvider

    return SileroProvider(settings)


@dataclass(frozen=True)
class Providers:
    llm: LLMProvider
    stt: SpeechToTextProvider
    tts: TextToSpeechProvider
    vad: VoiceActivityDetectionProvider

    async def health_check(self) -> dict[str, ProviderHealth]:
        """Run explicit checks only when called; application startup never invokes this."""
        return {
            "llm": await self.llm.health_check(),
            "stt": await self.stt.health_check(),
            "tts": await self.tts.health_check(),
            "vad": await self.vad.health_check(),
        }


def create_providers(settings: Settings) -> Providers:
    return Providers(
        create_llm_provider(settings),
        create_stt_provider(settings),
        create_tts_provider(settings),
        create_vad_provider(settings),
    )
