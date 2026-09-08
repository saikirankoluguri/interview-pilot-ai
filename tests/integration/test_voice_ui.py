"""Audio orchestration and UI privacy without microphones or external services."""

import asyncio
import wave
from io import BytesIO

import numpy as np
import pytest

from app.bootstrap import build_application
from app.schemas.audio import AudioBuffer
from app.schemas.interview import InterviewSettings
from app.ui.service import UIContext, UIService
from app.utils.errors import AudioProcessingError, InvalidSessionState
from app.voice.audio_pipeline import AudioPipeline
from app.voice.audio_utils import from_array
from app.voice.turn_manager import TurnState


def test_automatic_voice_pipeline(settings, candidate):
    async def run():
        app = build_application(settings)
        session = app.engine.create_session(
            candidate, InterviewSettings(target_role=candidate.target_role)
        )
        voice = AudioPipeline(
            app.engine, session.session_id, app.providers.stt, app.providers.tts, app.providers.vad
        )
        response = await voice.start()
        with wave.open(BytesIO(response.audio.to_wav())) as wav:
            assert wav.getnchannels() == 1 and wav.getnframes() > 0
        chunk = AudioBuffer(b"\x00\x00" * 16000)
        assert await voice.accept_chunk(chunk) is None
        voice.playback_finished()
        assert await voice.accept_chunk(chunk) is None
        response = await voice.accept_chunk(chunk)
        assert response.transcript.is_mock and voice.turns.state == TurnState.SPEAKING
        state = app.engine.get_session(session.session_id)
        assert len(state.turns) == 1 and state.turns[0].latency.total_seconds > 0
        context = UIContext(session.session_id, voice)
        service = UIService(app)
        assert "after the interview" in service.feedback(context)
        status = service.public_status(context)
        assert not any("85" in value or "Mock transcript" in value for value in status)
        await voice.end()
        assert "MOCK REPORT" in service.feedback(context)

    asyncio.run(run())


def test_turn_overlap_and_audio_validation():
    from app.voice.turn_manager import TurnManager

    turns = TurnManager()
    turns.begin_processing()
    with pytest.raises(InvalidSessionState):
        turns.begin_processing()
    turns.begin_speaking()
    turns.playback_finished()
    assert turns.state == TurnState.LISTENING
    with pytest.raises(AudioProcessingError):
        AudioBuffer(b"odd")
    with pytest.raises(AudioProcessingError):
        from_array(16000, np.array([np.nan]))
    audio = from_array(16000, np.zeros((1600, 2), dtype=np.int16))
    assert audio.duration == 0.1


def test_ui_has_no_live_transcript_or_answer_box(settings):
    from app.ui.gradio_app import create_app

    demo = create_app(build_application(settings))
    config = demo.get_config_file()
    assert not any(c["type"] == "chatbot" for c in config["components"])
    textboxes = [c["props"]["label"] for c in config["components"] if c["type"] == "textbox"]
    assert set(textboxes) == {
        "Candidate name",
        "Target role",
        "Company (optional)",
        "Job description",
        "Time remaining",
        "Voice state",
    }
    # Gradio 5 (the FastRTC-compatible range) serializes private callbacks as false.
    assert all(d.get("api_name") is False for d in config["dependencies"])
    assert any(
        d.get("connection") == "stream" or d.get("stream_every") == 0.5
        for d in config["dependencies"]
    )
