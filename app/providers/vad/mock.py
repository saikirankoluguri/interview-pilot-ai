"""Deterministic chunk endpointing for mock workflow verification only."""

from app.providers.health import ProviderHealth
from app.schemas.audio import AudioBuffer, VADResult


class MockVADProvider:
    def __init__(self, complete_after_seconds: float = 2) -> None:
        self.complete_after_seconds = complete_after_seconds

    async def detect_end_of_turn(self, audio: AudioBuffer) -> VADResult:
        return VADResult(bool(audio.pcm), audio.duration >= self.complete_after_seconds)

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth("mock", "healthy", "mock", detail="Deterministic VAD fixture")
