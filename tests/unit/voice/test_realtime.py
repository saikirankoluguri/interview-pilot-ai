"""Realtime state, buffering, recovery, concurrency, and FastRTC boundary tests."""

import asyncio
import sys
from datetime import timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from app.bootstrap import build_application
from app.config.settings import Settings
from app.providers.factory import Providers, create_providers
from app.providers.llm.base import LLMTask
from app.providers.llm.mock import MockLLMProvider
from app.schemas.audio import AudioBuffer, Transcript, VADResult
from app.schemas.interview import InterviewSettings, SessionStatus
from app.ui.service import UIContext, UIService
from app.utils.errors import AudioProcessingError, InvalidSessionState, ProviderError
from app.voice.audio_pipeline import RealtimeSessionController
from app.voice.turn_manager import ConnectionState, TurnManager, TurnState


class ScriptedVAD:
    def __init__(self, results):
        self.results = list(results)

    async def detect_end_of_turn(self, audio):
        return self.results.pop(0)


class FixedSTT:
    def __init__(self, text="synthetic candidate response", error=None):
        self.text = text
        self.error = error
        self.calls = 0

    async def transcribe(self, audio):
        self.calls += 1
        if self.error:
            raise self.error
        return Transcript(self.text)


class CountingTTS:
    def __init__(self, failures=0):
        self.failures = failures
        self.calls = 0

    async def synthesize(self, text, *, voice=None):
        self.calls += 1
        if self.calls <= self.failures:
            raise ProviderError("synthetic TTS failure")
        return AudioBuffer(b"\x00\x00" * 2400, 24000)


def controller(settings, candidate, *, stt=None, tts=None, vad=None, llm=None):
    defaults = create_providers(settings)
    providers = Providers(
        llm or defaults.llm,
        stt or defaults.stt,
        tts or defaults.tts,
        vad or defaults.vad,
    )
    app = build_application(settings, providers)
    session = app.engine.create_session(
        candidate, InterviewSettings(target_role=candidate.target_role)
    )
    voice = RealtimeSessionController(
        app.engine,
        session.session_id,
        providers.stt,
        providers.tts,
        providers.vad,
        settings,
    )
    voice.connect()
    return app, session, voice


def test_realtime_state_machine_and_invalid_transitions():
    turns = TurnManager()
    turns.begin_preparing()
    turns.begin_speaking()
    turns.playback_finished()
    turns.speech_started()
    turns.begin_processing()
    turns.begin_speaking()
    turns.playback_finished()
    turns.begin_ending()
    turns.begin_speaking()
    turns.playback_finished(ended=True)
    turns.complete()
    assert turns.history == [
        TurnState.IDLE,
        TurnState.PREPARING,
        TurnState.INTERVIEWER_SPEAKING,
        TurnState.LISTENING,
        TurnState.CANDIDATE_SPEAKING,
        TurnState.PROCESSING,
        TurnState.INTERVIEWER_SPEAKING,
        TurnState.LISTENING,
        TurnState.ENDING,
        TurnState.INTERVIEWER_SPEAKING,
        TurnState.ENDING,
        TurnState.COMPLETED,
    ]
    with pytest.raises(InvalidSessionState):
        turns.begin_listening()


def test_gating_speech_start_end_and_latency(settings, candidate):
    async def run():
        app, session, voice = controller(settings, candidate)
        opening = await voice.start()
        assert opening.audio.pcm and voice.turns.state == TurnState.INTERVIEWER_SPEAKING
        gated = await voice.accept_chunk(AudioBuffer(b"\x01\x00" * 16000))
        assert gated is None and not voice.buffer
        voice.playback_finished()
        assert voice.turns.state == TurnState.LISTENING
        assert await voice.accept_chunk(AudioBuffer(b"\x01\x00" * 16000)) is None
        assert voice.turns.state == TurnState.CANDIDATE_SPEAKING
        result = await voice.accept_chunk(AudioBuffer(b"\x01\x00" * 16000))
        assert result is not None and result.turn_id is not None
        assert result.latency.stt_started_at and result.latency.audio_playback_ready_at
        assert result.latency.speech_end_to_audio_ready_ms >= 0
        assert len(app.engine.get_session(session.session_id).answers) == 1

    asyncio.run(run())


def test_silence_before_speech_never_finalizes(settings, candidate):
    async def run():
        vad = ScriptedVAD(
            [
                VADResult(False, False),
                VADResult(False, True),
                VADResult(True, False),
                VADResult(True, True),
            ]
        )
        _, _, voice = controller(settings, candidate, vad=vad)
        await voice.start()
        voice.playback_finished()
        chunk = AudioBuffer(b"\x00\x00" * 8000)
        assert await voice.accept_chunk(chunk) is None
        assert await voice.accept_chunk(chunk) is None
        assert voice.turns.state == TurnState.LISTENING
        assert await voice.accept_chunk(chunk) is None
        assert voice.turns.state == TurnState.CANDIDATE_SPEAKING
        assert await voice.accept_chunk(chunk) is not None

    asyncio.run(run())


def test_max_buffer_gracefully_finalizes(tmp_path, candidate):
    async def run():
        settings = Settings(
            _env_file=None,
            data_dir=tmp_path,
            max_candidate_turn_seconds=1,
        )
        vad = ScriptedVAD([VADResult(True, False)])
        _, _, voice = controller(settings, candidate, vad=vad)
        await voice.start()
        voice.playback_finished()
        chunk = AudioBuffer(b"\x01\x00" * 9600)
        assert await voice.accept_chunk(chunk) is None
        assert await voice.accept_chunk(chunk) is not None
        assert not voice.buffer

    asyncio.run(run())


@pytest.mark.parametrize(
    "stt,status",
    [
        (FixedSTT(" "), "empty_transcript_repeat"),
        (FixedSTT(error=ProviderError("synthetic STT failure")), "stt_error_repeat"),
    ],
)
def test_stt_recovery_does_not_count_answer(settings, candidate, stt, status):
    async def run():
        app, session, voice = controller(settings, candidate, stt=stt)
        await voice.start()
        voice.playback_finished()
        result = await voice.process_audio(AudioBuffer(b"\x01\x00" * 1600))
        assert result.recovery_status == status
        assert not app.engine.get_session(session.session_id).answers

    asyncio.run(run())


def test_tts_retries_once_and_fails_cleanly(settings, candidate):
    async def run():
        retrying = CountingTTS(failures=1)
        _, _, voice = controller(settings, candidate, tts=retrying)
        await voice.start()
        assert retrying.calls == 2
        failing = CountingTTS(failures=2)
        _, _, broken = controller(settings, candidate, tts=failing)
        with pytest.raises(AudioProcessingError):
            await broken.start()
        assert broken.turns.state == TurnState.ERROR

    asyncio.run(run())


def test_llm_retries_once_without_duplicate_answer(settings, candidate):
    class FlakyLLM(MockLLMProvider):
        def __init__(self):
            super().__init__()
            self.live_calls = 0

        async def generate_structured(self, request, schema):
            if request.task == LLMTask.LIVE_DECISION:
                self.live_calls += 1
                if self.live_calls == 1:
                    raise ProviderError("synthetic transient failure")
            return await super().generate_structured(request, schema)

    async def run():
        llm = FlakyLLM()
        app, session, voice = controller(settings, candidate, llm=llm)
        await voice.start()
        voice.playback_finished()
        await voice.process_audio(AudioBuffer(b"\x01\x00" * 1600))
        saved = app.engine.get_session(session.session_id)
        assert llm.live_calls == 2 and len(saved.answers) == 1 and len(saved.turns) == 1

    asyncio.run(run())


def test_duplicate_processing_and_end_during_processing(settings, candidate):
    class SlowSTT(FixedSTT):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def transcribe(self, audio):
            self.started.set()
            await self.release.wait()
            return await super().transcribe(audio)

    async def run():
        stt = SlowSTT()
        app, session, voice = controller(settings, candidate, stt=stt)
        await voice.start()
        voice.playback_finished()
        task = asyncio.create_task(voice.process_audio(AudioBuffer(b"\x01\x00" * 1600)))
        await stt.started.wait()
        with pytest.raises(AudioProcessingError):
            await voice.process_audio(AudioBuffer(b"\x01\x00" * 1600))
        voice.request_end()
        assert voice.turns.state == TurnState.ENDING
        stt.release.set()
        result = await task
        assert result.message.ended
        assert app.engine.get_session(session.session_id).status == SessionStatus.COMPLETED

    asyncio.run(run())


def test_no_speech_prompt_and_inactivity_pause(tmp_path, candidate):
    async def run():
        settings = Settings(
            _env_file=None,
            data_dir=tmp_path,
            no_speech_timeout_seconds=5,
            no_speech_end_seconds=10,
        )
        vad = ScriptedVAD([VADResult(False, False)] * 20)
        _, _, voice = controller(settings, candidate, vad=vad)
        await voice.start()
        voice.playback_finished()
        chunk = AudioBuffer(b"\x00\x00" * 8000)
        result = None
        for _ in range(10):
            result = await voice.accept_chunk(chunk)
            if result:
                break
        assert result.recovery_status == "no_speech_prompt"
        voice.playback_finished()
        result = None
        for _ in range(10):
            result = await voice.accept_chunk(chunk)
            if result:
                break
        assert result.recovery_status == "inactivity_paused"
        voice.playback_finished()
        assert voice.connection_state == ConnectionState.DISCONNECTED
        assert voice.turns.state == TurnState.IDLE

    asyncio.run(run())


def test_reconnect_preserves_current_question(settings, candidate):
    async def run():
        app, session, voice = controller(settings, candidate)
        await voice.start()
        voice.playback_finished()
        count = len(app.engine.get_session(session.session_id).questions)
        voice.disconnect()
        voice.turns.stop()
        voice.connect()
        assert voice.connection_state == ConnectionState.CONNECTED
        assert voice.turns.state == TurnState.LISTENING
        assert len(app.engine.get_session(session.session_id).questions) == count

    asyncio.run(run())


def test_vad_error_recovers_listening(settings, candidate):
    class BrokenVAD:
        async def detect_end_of_turn(self, audio):
            raise ProviderError("synthetic VAD failure")

    async def run():
        _, _, voice = controller(settings, candidate, vad=BrokenVAD())
        await voice.start()
        voice.playback_finished()
        with pytest.raises(AudioProcessingError, match="Voice detection"):
            await voice.accept_chunk(AudioBuffer(b"\x00\x00" * 8000))
        assert voice.turns.state == TurnState.LISTENING and not voice.buffer

    asyncio.run(run())


def test_llm_failure_retries_then_speaks_clean_error(settings, candidate):
    class BrokenLLM(MockLLMProvider):
        def __init__(self):
            super().__init__()
            self.live_calls = 0

        async def generate_structured(self, request, schema):
            if request.task == LLMTask.LIVE_DECISION:
                self.live_calls += 1
                raise ProviderError("synthetic private LLM failure")
            return await super().generate_structured(request, schema)

    async def run():
        llm = BrokenLLM()
        app, session, voice = controller(settings, candidate, llm=llm)
        await voice.start()
        voice.playback_finished()
        result = await voice.process_audio(AudioBuffer(b"\x01\x00" * 1600))
        assert llm.live_calls == 2 and result.error_code == "provider_error"
        assert "synthetic private" not in result.message.question
        assert app.engine.get_session(session.session_id).status == SessionStatus.FAILED
        voice.playback_finished()
        assert voice.turns.state == TurnState.ERROR

    asyncio.run(run())


def test_end_during_listening_speaks_closing_and_cleans(settings, candidate):
    async def run():
        app, session, voice = controller(settings, candidate)
        await voice.start()
        voice.playback_finished()
        voice.buffer = b"\x00\x00" * 100
        result = await voice.end()
        assert result.message.ended and not voice.buffer
        assert app.engine.get_session(session.session_id).status == SessionStatus.COMPLETED
        voice.playback_finished()
        assert voice.turns.state == TurnState.COMPLETED

    asyncio.run(run())


def test_timer_expiration_wraps_up_after_candidate_turn(settings, candidate):
    async def run():
        app, session, voice = controller(settings, candidate)
        await voice.start()
        voice.playback_finished()
        started_at = app.engine.get_session(session.session_id).started_at
        app.engine.clock = lambda: started_at + timedelta(minutes=31)

        result = await voice.process_audio(AudioBuffer(b"\x01\x00" * 1600))

        persisted = app.engine.get_session(session.session_id)
        assert result.message.ended
        assert persisted.status == SessionStatus.COMPLETED
        assert persisted.answers == []
        voice.playback_finished()
        assert voice.turns.state == TurnState.COMPLETED

    asyncio.run(run())


def test_mock_realtime_three_turn_flow(settings, candidate):
    async def run():
        app, session, voice = controller(settings, candidate)
        await voice.start()
        voice.playback_finished()

        for _ in range(3):
            result = await voice.process_audio(AudioBuffer(b"\x01\x00" * 1600))
            assert result.audio.pcm
            assert result.latency is not None
            assert voice.turns.state == TurnState.INTERVIEWER_SPEAKING
            voice.playback_finished()

        closing = await voice.end()
        assert closing.message.ended
        voice.playback_finished()
        persisted = app.engine.get_session(session.session_id)
        assert len(persisted.turns) == 3
        assert persisted.report is not None
        assert voice.turns.state == TurnState.COMPLETED

    asyncio.run(run())


def test_fastrtc_bridge_with_fake_runtime(monkeypatch, settings, candidate):
    class AsyncStreamHandler:
        def __init__(self, **kwargs):
            self.latest_args = []
            self.options = kwargs

        async def wait_for_args(self):
            return None

    class WebRTCError(Exception):
        pass

    monkeypatch.setitem(
        sys.modules,
        "fastrtc",
        SimpleNamespace(AsyncStreamHandler=AsyncStreamHandler, WebRTCError=WebRTCError),
    )

    async def run():
        from app.ui.realtime_bridge import create_realtime_transport

        _, _, voice = controller(settings, candidate)
        opening = await voice.start()
        context = UIContext(voice.session_id, voice)
        handler = create_realtime_transport()
        handler.latest_args = ["webrtc", context]
        await handler.start_up()
        assert handler.options["input_sample_rate"] == 16000
        rate, samples = await handler.emit()
        assert rate == opening.audio.sample_rate and samples.ndim == 2
        await handler.receive((16000, np.zeros((1, 1600), dtype=np.int16)))
        await handler.shutdown()
        assert voice.connection_state == ConnectionState.DISCONNECTED

    asyncio.run(run())


def test_candidate_ui_status_hides_private_realtime_data(settings, candidate):
    async def run():
        app, _, voice = controller(settings, candidate)
        await voice.start()
        status = UIService(app).public_status(UIContext(voice.session_id, voice))
        combined = " ".join(status)
        assert "correctness" not in combined.casefold()
        assert "Mock transcript" not in combined
        assert "85" not in combined
        assert "Gated" in status and "Playing" in status
        assert settings.debug_ui is False

    asyncio.run(run())
