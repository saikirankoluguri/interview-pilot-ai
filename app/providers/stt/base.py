"""Speech transcription contract using normalized audio."""

from typing import Protocol

from app.schemas.audio import AudioBuffer, Transcript


class SpeechToTextProvider(Protocol):
    async def transcribe(self, audio: AudioBuffer) -> Transcript: ...
