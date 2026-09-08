"""Speech synthesis contract returning normalized PCM audio."""

from typing import Protocol

from app.schemas.audio import AudioBuffer


class TextToSpeechProvider(Protocol):
    async def synthesize(self, text: str, *, voice: str | None = None) -> AudioBuffer: ...
