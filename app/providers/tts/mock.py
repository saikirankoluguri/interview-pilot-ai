"""Playable deterministic silence for plumbing tests; no speech is synthesized."""

from app.schemas.audio import AudioBuffer


class MockTTSProvider:
    async def synthesize(self, text: str, *, voice: str | None = None) -> AudioBuffer:
        return AudioBuffer(pcm=b"\x00\x00" * 6000, sample_rate=24000)
