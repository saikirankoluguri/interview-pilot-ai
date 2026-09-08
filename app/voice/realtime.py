"""Optional FastRTC/WebRTC adapter over the same application voice pipeline."""

import asyncio
from time import monotonic
from typing import Protocol

from app.utils.errors import ConfigurationError, InterviewError
from app.voice.audio_pipeline import AudioPipeline
from app.voice.audio_utils import for_transport, from_array
from app.voice.turn_manager import TurnState


class VoiceConnection(Protocol):
    voice: AudioPipeline


def create_realtime_transport() -> object:
    """Import transport only when selected; never use FastRTC's built-in model loaders.

    The Gradio WebRTC event passes [webrtc, server_side_context]. Each connection
    gets its own handler. Silero endpointing stays behind the injected VAD interface.
    """
    try:
        from fastrtc import AsyncStreamHandler, WebRTCError
    except ImportError as exc:
        raise ConfigurationError(
            "FastRTC is optional. Install cloud requirements or use Gradio audio."
        ) from exc

    class InterviewStream(AsyncStreamHandler):
        def __init__(self) -> None:
            super().__init__(
                expected_layout="mono", input_sample_rate=16000, output_sample_rate=24000
            )
            self.connection: VoiceConnection | None = None
            self.output: asyncio.Queue = asyncio.Queue(maxsize=2)
            self.speaking_until = 0.0

        def copy(self):
            return InterviewStream()

        async def start_up(self):
            await self.wait_for_args()
            if len(self.latest_args) < 2 or self.latest_args[1] is None:
                raise WebRTCError("Start the interview before connecting the microphone.")
            self.connection = self.latest_args[1]
            response = self.connection.voice.last_response
            if response is not None:
                await self.output.put(response.audio)

        async def receive(self, frame):
            if self.connection is None:
                return
            pipeline = self.connection.voice
            if (
                pipeline.turns.state == TurnState.SPEAKING
                and monotonic() >= self.speaking_until > 0
            ):
                pipeline.playback_finished()
            try:
                result = await pipeline.accept_chunk(from_array(*frame))
                if result is not None:
                    await self.output.put(result.audio)
            except InterviewError as exc:
                raise WebRTCError(str(exc)) from None

        async def emit(self):
            audio = await self.output.get()
            self.speaking_until = monotonic() + audio.duration + 0.3
            rate, samples = for_transport(audio)
            return rate, samples.reshape(1, -1)

        async def shutdown(self):
            if self.connection is not None:
                self.connection.voice.turns.stop()

    return InterviewStream()
