"""Provider-independent microphone -> transcript -> engine -> spoken response pipeline."""

import asyncio
import logging
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

from app.interview.engine import InterviewEngine
from app.providers.stt.base import SpeechToTextProvider
from app.providers.tts.base import TextToSpeechProvider
from app.providers.vad.base import VoiceActivityDetectionProvider
from app.schemas.audio import AudioBuffer, Transcript
from app.schemas.evaluation import TurnLatencyMetrics
from app.schemas.interview import InterviewMessage, SessionStatus
from app.utils.errors import AudioProcessingError, InterviewError
from app.voice.turn_manager import TurnManager, TurnState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VoiceResponse:
    """Internal result; the UI publishes audio and public state, never transcript."""

    message: InterviewMessage
    audio: AudioBuffer
    transcript: Transcript | None = None


class AudioPipeline:
    def __init__(
        self,
        engine: InterviewEngine,
        session_id: UUID,
        stt: SpeechToTextProvider,
        tts: TextToSpeechProvider,
        vad: VoiceActivityDetectionProvider,
    ) -> None:
        self.engine = engine
        self.session_id = session_id
        self.stt = stt
        self.tts = tts
        self.vad = vad
        self.turns = TurnManager()
        self.buffer = b""
        self.sample_rate = 16000
        self._last_vad_duration = 0.0
        self._busy = asyncio.Lock()
        self.last_response: VoiceResponse | None = None

    def _clear_buffer(self) -> None:
        self.buffer = b""
        self._last_vad_duration = 0

    async def _speak(
        self, message: InterviewMessage, transcript: Transcript | None = None
    ) -> VoiceResponse:
        audio = await self.tts.synthesize(message.question)
        if not audio.pcm:
            raise AudioProcessingError("Interviewer audio is unavailable.")
        self.turns.begin_speaking()
        self.last_response = VoiceResponse(message, audio, transcript)
        return self.last_response

    async def start(self) -> VoiceResponse:
        async with self._busy:
            self.turns.begin_processing()
            try:
                message = await self.engine.start_interview(self.session_id)
                return await self._speak(message)
            except InterviewError:
                self.turns.recover(active=False)
                raise

    def playback_finished(self) -> None:
        self.turns.playback_finished(
            ended=bool(self.last_response and self.last_response.message.ended)
        )
        self._clear_buffer()

    async def process_audio(self, audio: AudioBuffer) -> VoiceResponse:
        """Complete-utterance path, also exercised directly by deterministic tests."""
        async with self._busy:
            self.turns.begin_processing()
            started = perf_counter()
            metrics = TurnLatencyMetrics()
            answer_processed = False
            try:
                part = perf_counter()
                transcript = await self.stt.transcribe(audio)
                metrics.stt_seconds = perf_counter() - part
                if not transcript.text.strip():
                    raise AudioProcessingError(
                        "No speech was transcribed. Please try speaking again."
                    )
                message = await self.engine.process_candidate_answer(
                    self.session_id, transcript.text
                )
                answer_processed = True
                part = perf_counter()
                result = await self._speak(message, transcript)
                metrics.tts_seconds = perf_counter() - part
                metrics.total_seconds = perf_counter() - started
                await self.engine.save_latency(self.session_id, metrics)
                logger.info(
                    "session=%s stt_seconds=%.3f tts_seconds=%.3f total_seconds=%.3f",
                    self.session_id,
                    metrics.stt_seconds,
                    metrics.tts_seconds,
                    metrics.total_seconds,
                )
                return result
            except InterviewError:
                active = (
                    self.engine.get_session(self.session_id).status == SessionStatus.IN_PROGRESS
                )
                self.turns.recover(active=active and not answer_processed)
                raise

    async def retry_audio(self) -> VoiceResponse:
        """Retry a failed spoken response without submitting another answer or LLM turn."""
        async with self._busy:
            session = self.engine.get_session(self.session_id)
            if session.status != SessionStatus.IN_PROGRESS or not session.questions:
                raise AudioProcessingError("There is no active interviewer question to play.")
            self.turns.begin_processing()
            question = session.questions[-1]
            try:
                return await self._speak(
                    InterviewMessage(
                        question=question.text,
                        panel_member=session.panel[question.panel_index].name,
                    )
                )
            except InterviewError:
                self.turns.recover(active=False)
                raise

    async def accept_chunk(self, chunk: AudioBuffer) -> VoiceResponse | None:
        """Accumulate streaming PCM and automatically submit a VAD-completed turn."""
        if self.turns.state != TurnState.LISTENING or self._busy.locked():
            return None
        if self.buffer and self.sample_rate != chunk.sample_rate:
            self._clear_buffer()
            raise AudioProcessingError("Microphone sample rate changed; restart recording.")
        self.sample_rate = chunk.sample_rate
        if len(self.buffer) + len(chunk.pcm) > chunk.sample_rate * 2 * 120:
            self._clear_buffer()
            raise AudioProcessingError("Please keep each spoken answer under two minutes.")
        self.buffer += chunk.pcm
        audio = AudioBuffer(self.buffer, self.sample_rate)
        if audio.duration - self._last_vad_duration < 0.25:
            return None
        self._last_vad_duration = audio.duration
        result = await self.vad.detect_end_of_turn(audio)
        if not result.speech_detected and audio.duration > 3:
            # Do not retain minutes of silence before speech begins.
            self.buffer = self.buffer[-self.sample_rate * 2 :]
            self._last_vad_duration = 0
        if result.end_of_turn and result.speech_detected:
            self._clear_buffer()
            return await self.process_audio(audio)
        return None

    async def end(self) -> None:
        async with self._busy:
            self.turns.stop()
            self._clear_buffer()
            await self.engine.end_interview(self.session_id)
