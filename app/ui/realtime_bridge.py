"""Lazy FastRTC 0.0.34 bridge around the transport-independent voice controller."""

import asyncio
from time import monotonic
from typing import Protocol

from app.schemas.audio import AudioBuffer
from app.utils.errors import ConfigurationError, InterviewError
from app.voice.audio_pipeline import RealtimeSessionController
from app.voice.audio_utils import for_transport, from_array
from app.voice.turn_manager import TurnState


class VoiceConnection(Protocol):
    voice: RealtimeSessionController


def create_realtime_transport() -> object:
    """Create one FastRTC handler template without importing provider runtimes."""
    try:
        from fastrtc import AsyncStreamHandler, WebRTCError
    except ImportError as exc:
        raise ConfigurationError(
            "Realtime voice is unavailable. Install the Lightning realtime dependencies."
        ) from exc

    class InterviewStream(AsyncStreamHandler):
        def __init__(self) -> None:
            super().__init__(
                expected_layout="mono",
                input_sample_rate=16000,
                output_sample_rate=24000,
            )
            self.connection: VoiceConnection | None = None
            self.output: asyncio.Queue[AudioBuffer] = asyncio.Queue(maxsize=4)
            self.speaking_until = 0.0

        def copy(self):
            return InterviewStream()

        async def start_up(self) -> None:
            await self.wait_for_args()
            if len(self.latest_args) < 2 or self.latest_args[1] is None:
                raise WebRTCError("Start the interview before connecting the microphone.")
            self.connection = self.latest_args[1]
            pipeline = self.connection.voice
            pipeline.connect()
            pipeline.add_output_sink(self.output)
            if (
                pipeline.last_response is not None
                and pipeline.turns.state == TurnState.INTERVIEWER_SPEAKING
            ):
                await self.output.put(pipeline.last_response.audio)

        def _finish_playback_if_due(self) -> None:
            if self.connection is None:
                return
            pipeline = self.connection.voice
            if (
                pipeline.turns.state == TurnState.INTERVIEWER_SPEAKING
                and monotonic() >= self.speaking_until > 0
            ):
                pipeline.playback_finished()
                pipeline.refresh()
                self.speaking_until = 0

        async def receive(self, frame) -> None:
            if self.connection is None:
                return
            self._finish_playback_if_due()
            try:
                await self.connection.voice.accept_chunk(from_array(*frame))
            except InterviewError as exc:
                raise WebRTCError(str(exc)) from None

        async def emit(self):
            self._finish_playback_if_due()
            try:
                audio = await asyncio.wait_for(self.output.get(), timeout=0.1)
            except TimeoutError:
                return None
            self.speaking_until = monotonic() + audio.duration + 0.2
            rate, samples = for_transport(audio)
            return rate, samples.reshape(1, -1)

        async def shutdown(self) -> None:
            if self.connection is not None:
                pipeline = self.connection.voice
                pipeline.remove_output_sink(self.output)
                await pipeline.close()
                self.connection = None

    return InterviewStream()
