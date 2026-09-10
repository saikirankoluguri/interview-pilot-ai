"""Speech synthesis contract returning normalized PCM audio."""

from typing import Protocol

from app.providers.health import ProviderHealth
from app.schemas.audio import AudioBuffer


class TextToSpeechProvider(Protocol):
    async def synthesize(self, text: str, *, voice: str | None = None) -> AudioBuffer: ...
    async def health_check(self) -> ProviderHealth: ...
