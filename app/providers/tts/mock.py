"""Playable deterministic silence for plumbing tests; no speech is synthesized."""

from app.providers.health import ProviderHealth
from app.schemas.audio import AudioBuffer
from app.utils.errors import AudioProcessingError


class MockTTSProvider:
    async def synthesize(self, text: str, *, voice: str | None = None) -> AudioBuffer:
        if not text.strip():
            raise AudioProcessingError("Interviewer text is empty.")
        return AudioBuffer(pcm=b"\x00\x00" * 6000, sample_rate=24000)

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth("mock", "healthy", "mock", detail="Deterministic TTS fixture")
