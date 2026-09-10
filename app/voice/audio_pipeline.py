"""Provider-independent realtime session controller for one interview connection."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from uuid import UUID

from app.config.settings import Settings
from app.interview.engine import InterviewEngine
from app.providers.stt.base import SpeechToTextProvider
from app.providers.tts.base import TextToSpeechProvider
from app.providers.vad.base import VoiceActivityDetectionProvider
from app.schemas.audio import AudioBuffer, Transcript
from app.schemas.evaluation import LiveEvaluation, TurnLatencyMetrics
from app.schemas.interview import InterviewMessage, SessionStatus
from app.utils.errors import AudioProcessingError, InterviewError, ProviderError
from app.utils.helpers import utc_now
from app.voice.turn_manager import ConnectionState, TurnManager, TurnState

logger = logging.getLogger(__name__)

_REPEAT_PROMPT = "Sorry, I didn't catch that. Could you say that again?"
_WAIT_PROMPT = "Take your time. Let me know when you're ready to answer."
_PAUSE_PROMPT = "I haven't heard a response, so the voice session is paused. Reconnect when ready."
_CLOSING_PROMPT = "Thanks for your time. That concludes the interview."


@dataclass(frozen=True)
class RealtimeTurnResult:
    """Private completed-turn result; the UI publishes only safe status and audio."""

    session_id: UUID
    message: InterviewMessage
    audio: AudioBuffer
    voice_state: TurnState
    turn_id: UUID | None = None
    transcript: Transcript | None = None
    evaluation: LiveEvaluation | None = None
    latency: TurnLatencyMetrics | None = None
    recovery_status: str | None = None
    error_code: str | None = None


# Compatibility name retained for Phase 1 callers.
VoiceResponse = RealtimeTurnResult


class RealtimeSessionController:
    """Owns bounded audio, turn state, provider calls, and per-session synchronization."""

    def __init__(
        self,
        engine: InterviewEngine,
        session_id: UUID,
        stt: SpeechToTextProvider,
        tts: TextToSpeechProvider,
        vad: VoiceActivityDetectionProvider,
        settings: Settings | None = None,
    ) -> None:
        self.engine = engine
        self.session_id = session_id
        self.stt = stt
        self.tts = tts
        self.vad = vad
        self.settings = settings or Settings()
        self.turns = TurnManager()
        self.connection_state = ConnectionState.DISCONNECTED
        self.buffer = b""
        self.sample_rate = 16000
        self._last_vad_duration = 0.0
        self._listening_audio_seconds = 0.0
        self._total_inactivity_seconds = 0.0
        self._speech_started = False
        self._no_speech_prompted = False
        self._busy = asyncio.Lock()
        self._ingest = asyncio.Lock()
        self._end_requested = False
        self._output_sinks: set[asyncio.Queue[AudioBuffer]] = set()
        self.last_response: RealtimeTurnResult | None = None

    @property
    def is_busy(self) -> bool:
        return self._busy.locked()

    def connect(self) -> None:
        reconnecting = self.connection_state == ConnectionState.DISCONNECTED and bool(
            self.last_response
        )
        self.connection_state = (
            ConnectionState.RECONNECTING if reconnecting else ConnectionState.CONNECTING
        )
        session = self.engine.get_session(self.session_id)
        if (
            reconnecting
            and session.status == SessionStatus.IN_PROGRESS
            and self.turns.state == TurnState.IDLE
        ):
            self.turns.begin_listening()
        self.connection_state = ConnectionState.CONNECTED
        logger.info("session=%s connection=%s", self.session_id, self.connection_state.value)

    def disconnect(self) -> None:
        self.connection_state = ConnectionState.DISCONNECTED
        self._clear_buffer()
        logger.info("session=%s connection=%s", self.session_id, self.connection_state.value)

    def add_output_sink(self, sink: asyncio.Queue[AudioBuffer]) -> None:
        self._output_sinks.add(sink)

    def remove_output_sink(self, sink: asyncio.Queue[AudioBuffer]) -> None:
        self._output_sinks.discard(sink)

    def _publish(self, audio: AudioBuffer) -> None:
        for sink in tuple(self._output_sinks):
            if sink.full():
                try:
                    sink.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            sink.put_nowait(audio)

    def _clear_buffer(self) -> None:
        self.buffer = b""
        self._last_vad_duration = 0
        self._speech_started = False

    def _reset_listening_window(self) -> None:
        self._clear_buffer()
        self._listening_audio_seconds = 0
        self._no_speech_prompted = False

    def _panel_voice(self) -> str | None:
        session = self.engine.get_session(self.session_id)
        if not session.questions or not session.panel:
            return None
        question = session.questions[-1]
        return session.panel[question.panel_index].voice_id

    async def _synthesize_with_retry(self, text: str) -> AudioBuffer:
        last_error: InterviewError | None = None
        for attempt in range(2):
            try:
                audio = await self.tts.synthesize(text, voice=self._panel_voice())
                if not audio.pcm:
                    raise AudioProcessingError("Interviewer audio is unavailable.")
                if attempt:
                    logger.info("session=%s provider=tts retry=1 success=true", self.session_id)
                return audio
            except InterviewError as exc:
                last_error = exc
                logger.warning(
                    "session=%s provider=tts attempt=%d error=%s",
                    self.session_id,
                    attempt + 1,
                    type(exc).__name__,
                )
        raise AudioProcessingError(
            "Interviewer audio is unavailable. Please reconnect and try again."
        ) from last_error

    async def _speak(
        self,
        message: InterviewMessage,
        *,
        transcript: Transcript | None = None,
        metrics: TurnLatencyMetrics | None = None,
        recovery_status: str | None = None,
        error_code: str | None = None,
    ) -> RealtimeTurnResult:
        audio = await self._synthesize_with_retry(message.question)
        self.turns.begin_speaking()
        session = self.engine.get_session(self.session_id)
        turn = session.turns[-1] if transcript is not None and session.turns else None
        self.last_response = RealtimeTurnResult(
            session_id=self.session_id,
            message=message,
            audio=audio,
            voice_state=self.turns.state,
            turn_id=turn.question.question_id if turn else None,
            transcript=transcript,
            evaluation=turn.evaluation if turn else None,
            latency=metrics,
            recovery_status=recovery_status,
            error_code=error_code,
        )
        self._publish(audio)
        logger.info(
            "session=%s voice_state=%s recovery=%s",
            self.session_id,
            self.turns.state.value,
            recovery_status or "none",
        )
        return self.last_response

    async def start(self) -> RealtimeTurnResult:
        async with self._busy:
            self.turns.begin_preparing()
            try:
                message = await self.engine.start_interview(self.session_id)
                return await self._speak(message)
            except InterviewError:
                self.turns.fail()
                raise

    def playback_finished(self) -> None:
        recovery = self.last_response.recovery_status if self.last_response else None
        if recovery == "inactivity_paused":
            self.turns.stop()
            self.disconnect()
        elif self.last_response and self.last_response.error_code:
            self.turns.fail()
        else:
            self.turns.playback_finished(
                ended=bool(self.last_response and self.last_response.message.ended)
            )
            session = self.engine.get_session(self.session_id)
            if self.turns.state == TurnState.ENDING and session.status == SessionStatus.COMPLETED:
                self.turns.complete()
        if recovery == "no_speech_prompt":
            self._clear_buffer()
            self._listening_audio_seconds = 0
            self._no_speech_prompted = False
        else:
            self._reset_listening_window()
            if recovery != "inactivity_paused":
                self._total_inactivity_seconds = 0

    def refresh(self) -> None:
        session = self.engine.get_session(self.session_id)
        if session.status == SessionStatus.COMPLETED and self.turns.state == TurnState.ENDING:
            self.turns.complete()

    def _useful_transcript(self, transcript: Transcript) -> bool:
        useful = "".join(character for character in transcript.text if character.isalnum())
        return len(useful) >= self.settings.realtime_min_transcript_characters

    async def _recovery(
        self,
        text: str,
        metrics: TurnLatencyMetrics,
        status: str,
    ) -> RealtimeTurnResult:
        self._clear_buffer()
        return await self._speak(
            InterviewMessage(question=text, panel_member="Interviewer"),
            metrics=metrics,
            recovery_status=status,
        )

    async def process_audio(
        self,
        audio: AudioBuffer,
        *,
        speech_end_at: datetime | None = None,
    ) -> RealtimeTurnResult:
        """Finalize one utterance. Empty STT never reaches the interview engine."""
        if self._busy.locked():
            raise AudioProcessingError("A candidate answer is already being processed.")
        async with self._busy:
            if self.turns.state not in {TurnState.PROCESSING, TurnState.ENDING}:
                self.turns.begin_processing()
            started = perf_counter()
            metrics = TurnLatencyMetrics(speech_end_at=speech_end_at or utc_now())
            try:
                part = perf_counter()
                metrics.stt_started_at = utc_now()
                try:
                    transcript = await self.stt.transcribe(audio)
                except (ProviderError, AudioProcessingError):
                    metrics.stt_seconds = perf_counter() - part
                    metrics.stt_ended_at = utc_now()
                    return await self._recovery(_REPEAT_PROMPT, metrics, "stt_error_repeat")
                metrics.stt_seconds = perf_counter() - part
                metrics.stt_ended_at = utc_now()
                if not self._useful_transcript(transcript):
                    return await self._recovery(_REPEAT_PROMPT, metrics, "empty_transcript_repeat")

                part = perf_counter()
                metrics.llm_started_at = utc_now()
                message = await self.engine.process_candidate_answer(
                    self.session_id, transcript.text
                )
                metrics.llm_seconds = perf_counter() - part
                metrics.llm_ended_at = utc_now()
                should_finalize = self._end_requested and not message.ended
                if should_finalize:
                    self.turns.begin_ending()
                    message = InterviewMessage(
                        question=_CLOSING_PROMPT,
                        panel_member=message.panel_member,
                        ended=True,
                    )

                part = perf_counter()
                metrics.tts_started_at = utc_now()
                result = await self._speak(message, transcript=transcript, metrics=metrics)
                metrics.tts_seconds = perf_counter() - part
                metrics.tts_ended_at = utc_now()
                metrics.audio_playback_ready_at = metrics.tts_ended_at
                metrics.total_seconds = perf_counter() - started
                if metrics.speech_end_at is not None:
                    metrics.speech_end_to_audio_ready_seconds = max(
                        0,
                        (metrics.audio_playback_ready_at - metrics.speech_end_at).total_seconds(),
                    )
                await self.engine.save_latency(self.session_id, metrics)
                if should_finalize:
                    await self.engine.end_interview(self.session_id)
                logger.info(
                    "session=%s turn=%s stt_ms=%.1f llm_ms=%.1f tts_ms=%.1f total_ms=%.1f",
                    self.session_id,
                    result.turn_id,
                    metrics.stt_ms,
                    metrics.llm_ms,
                    metrics.tts_ms,
                    metrics.total_processing_ms,
                )
                return result
            except InterviewError as exc:
                self._clear_buffer()
                if isinstance(exc, ProviderError):
                    try:
                        result = await self._speak(
                            InterviewMessage(
                                question=(
                                    "I'm having trouble processing the response. "
                                    "Please reconnect and try again."
                                ),
                                panel_member="Interviewer",
                            ),
                            metrics=metrics,
                            recovery_status="provider_error",
                            error_code="provider_error",
                        )
                        return result
                    except InterviewError:
                        pass
                self.turns.fail()
                raise

    async def _no_speech_recovery(self) -> RealtimeTurnResult:
        self.turns.begin_processing()
        self._no_speech_prompted = True
        return await self._recovery(
            _WAIT_PROMPT,
            TurnLatencyMetrics(speech_end_at=utc_now()),
            "no_speech_prompt",
        )

    async def _inactivity_pause(self) -> RealtimeTurnResult:
        self.turns.begin_processing()
        return await self._recovery(
            _PAUSE_PROMPT,
            TurnLatencyMetrics(speech_end_at=utc_now()),
            "inactivity_paused",
        )

    async def accept_chunk(self, chunk: AudioBuffer) -> RealtimeTurnResult | None:
        """Gate interviewer audio, detect speech start/end, and bound candidate audio."""
        async with self._ingest:
            if (
                self.turns.state
                not in {
                    TurnState.LISTENING,
                    TurnState.CANDIDATE_SPEAKING,
                }
                or self._busy.locked()
            ):
                return None
            if self.buffer and self.sample_rate != chunk.sample_rate:
                self._clear_buffer()
                raise AudioProcessingError("Microphone sample rate changed; reconnect audio.")
            self.sample_rate = chunk.sample_rate
            self._listening_audio_seconds += chunk.duration
            self._total_inactivity_seconds += chunk.duration
            max_bytes = int(self.settings.max_candidate_turn_seconds * chunk.sample_rate * 2)
            if len(self.buffer) + len(chunk.pcm) > max_bytes:
                if self._speech_started and self.buffer:
                    audio = AudioBuffer(self.buffer, self.sample_rate)
                    self._clear_buffer()
                    self.turns.begin_processing()
                    return await self.process_audio(audio, speech_end_at=utc_now())
                self._clear_buffer()
            self.buffer += chunk.pcm
            audio = AudioBuffer(self.buffer, self.sample_rate)
            interval = self.settings.realtime_vad_interval_ms / 1000
            if audio.duration - self._last_vad_duration < interval:
                return None
            self._last_vad_duration = audio.duration
            try:
                vad_result = await self.vad.detect_end_of_turn(audio)
            except InterviewError as exc:
                self._clear_buffer()
                self.turns.recover(active=True)
                raise AudioProcessingError(
                    "Voice detection was interrupted. Please try speaking again."
                ) from exc

            if vad_result.speech_detected and not self._speech_started:
                self._speech_started = True
                self._total_inactivity_seconds = 0
                self.turns.speech_started()
                logger.info(
                    "session=%s voice_state=%s",
                    self.session_id,
                    self.turns.state.value,
                )
            if self._speech_started and vad_result.end_of_turn:
                completed_audio = audio
                self._clear_buffer()
                self._listening_audio_seconds = 0
                self.turns.begin_processing()
                return await self.process_audio(completed_audio, speech_end_at=utc_now())
            if not self._speech_started:
                pre_roll_seconds = max(1.0, self.settings.vad_speech_pad_ms / 1000)
                pre_roll_bytes = int(pre_roll_seconds * self.sample_rate * 2)
                self.buffer = self.buffer[-pre_roll_bytes:]
                self._last_vad_duration = AudioBuffer(self.buffer, self.sample_rate).duration
                if self._total_inactivity_seconds >= self.settings.no_speech_end_seconds:
                    return await self._inactivity_pause()
                if (
                    self._listening_audio_seconds >= self.settings.no_speech_timeout_seconds
                    and not self._no_speech_prompted
                ):
                    return await self._no_speech_recovery()
            return None

    async def retry_audio(self) -> RealtimeTurnResult:
        """Replay the current question without submitting another answer."""
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
                    ),
                    recovery_status="playback_retry",
                )
            except InterviewError:
                self.turns.fail()
                raise

    def request_end(self) -> None:
        """Immediately gate new input; an in-flight turn observes the end request."""
        self._end_requested = True
        self._clear_buffer()
        if self.turns.state not in {TurnState.ENDING, TurnState.COMPLETED}:
            self.turns.begin_ending()
        logger.info("session=%s voice_end_requested=true", self.session_id)

    async def end(self, *, reason: str = "candidate") -> RealtimeTurnResult:
        """Stop input, speak a natural closing, finalize feedback, and clean buffers."""
        self.request_end()
        async with self._busy:
            session = self.engine.get_session(self.session_id)
            if self.last_response and self.last_response.message.ended:
                result = self.last_response
            else:
                if self.turns.state != TurnState.ENDING:
                    self.turns.begin_ending()
                panel_name = session.panel[0].name if session.panel else "Interviewer"
                result = await self._speak(
                    InterviewMessage(
                        question=_CLOSING_PROMPT,
                        panel_member=panel_name,
                        ended=True,
                    ),
                    recovery_status=f"end_{reason}",
                )
            if session.status != SessionStatus.COMPLETED:
                await self.engine.end_interview(self.session_id)
            self._clear_buffer()
            return result

    async def close(self) -> None:
        """Transport cleanup preserves completed turns and discards partial audio."""
        self.disconnect()
        self._output_sinks.clear()


# Phase 1 public name remains available while the implementation is now realtime-capable.
AudioPipeline = RealtimeSessionController
