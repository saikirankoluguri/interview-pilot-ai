"""End-of-turn contract over the currently buffered candidate utterance."""

from typing import Protocol

from app.providers.health import ProviderHealth
from app.schemas.audio import AudioBuffer, VADResult


class VoiceActivityDetectionProvider(Protocol):
    async def detect_end_of_turn(self, audio: AudioBuffer) -> VADResult: ...
    async def health_check(self) -> ProviderHealth: ...
