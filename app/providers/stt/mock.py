"""Deterministic workflow transcription, not speech recognition."""

from app.schemas.audio import AudioBuffer, Transcript
from app.utils.errors import AudioProcessingError


class MockSTTProvider:
    def __init__(self, transcript: str | None = None) -> None:
        self.transcript = transcript or (
            "Mock transcript: I designed a service, tested failure cases, "
            "compared alternatives, and measured the outcome."
        )

    async def transcribe(self, audio: AudioBuffer) -> Transcript:
        if not audio.pcm:
            raise AudioProcessingError("No microphone audio was received.")
        return Transcript(self.transcript, is_mock=True)
