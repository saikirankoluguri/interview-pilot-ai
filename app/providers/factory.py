"""The only provider selection boundary; importing it never loads GPU packages."""

from dataclasses import dataclass

from app.config.settings import Settings
from app.providers.llm.base import LLMProvider
from app.providers.stt.base import SpeechToTextProvider
from app.providers.tts.base import TextToSpeechProvider
from app.providers.vad.base import VoiceActivityDetectionProvider


def create_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        from app.providers.llm.mock import MockLLMProvider

        return MockLLMProvider()
    from app.providers.llm.qwen import QwenProvider

    return QwenProvider(settings)


def create_stt_provider(settings: Settings) -> SpeechToTextProvider:
    if settings.stt_provider == "mock":
        from app.providers.stt.mock import MockSTTProvider

        return MockSTTProvider()
    from app.providers.stt.whisper import WhisperProvider

    return WhisperProvider(settings)


def create_tts_provider(settings: Settings) -> TextToSpeechProvider:
    if settings.tts_provider == "mock":
        from app.providers.tts.mock import MockTTSProvider

        return MockTTSProvider()
    from app.providers.tts.kokoro import KokoroProvider

    return KokoroProvider(settings)


def create_vad_provider(settings: Settings) -> VoiceActivityDetectionProvider:
    if settings.vad_provider == "mock":
        from app.providers.vad.mock import MockVADProvider

        return MockVADProvider()
    from app.providers.vad.silero import SileroProvider

    return SileroProvider(settings)


@dataclass(frozen=True)
class Providers:
    llm: LLMProvider
    stt: SpeechToTextProvider
    tts: TextToSpeechProvider
    vad: VoiceActivityDetectionProvider


def create_providers(settings: Settings) -> Providers:
    return Providers(
        create_llm_provider(settings),
        create_stt_provider(settings),
        create_tts_provider(settings),
        create_vad_provider(settings),
    )
