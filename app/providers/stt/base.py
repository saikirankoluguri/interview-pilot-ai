"""Speech transcription contract using normalized audio."""

from typing import Protocol

from app.providers.health import ProviderHealth
from app.schemas.audio import AudioBuffer, Transcript


class SpeechToTextProvider(Protocol):
    async def transcribe(self, audio: AudioBuffer) -> Transcript: ...
    async def health_check(self) -> ProviderHealth: ...
