"""End-of-turn contract over the currently buffered candidate utterance."""

from typing import Protocol

from app.schemas.audio import AudioBuffer, VADResult


class VoiceActivityDetectionProvider(Protocol):
    async def detect_end_of_turn(self, audio: AudioBuffer) -> VADResult: ...
