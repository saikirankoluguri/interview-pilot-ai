"""Deterministic three-turn realtime simulation without hardware, network, or AI."""

import asyncio
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import build_application
from app.config.settings import Settings
from app.schemas.audio import AudioBuffer
from app.schemas.candidate import CandidateProfile
from app.schemas.interview import InterviewSettings
from app.voice.audio_pipeline import RealtimeSessionController


async def run() -> None:
    with TemporaryDirectory(prefix="interview-pilot-realtime-") as temp:
        settings = Settings(_env_file=None, data_dir=Path(temp))
        app = build_application(settings)
        candidate = CandidateProfile(
            name="Alex",
            target_role="Software Engineer",
            resume_text="Synthetic profile with Python services and API testing experience.",
            job_description=(
                "Build reliable software, test failure scenarios, explain trade-offs, "
                "and collaborate with engineering teams."
            ),
        )
        session = app.engine.create_session(
            candidate, InterviewSettings(target_role=candidate.target_role)
        )
        voice = RealtimeSessionController(
            app.engine,
            session.session_id,
            app.providers.stt,
            app.providers.tts,
            app.providers.vad,
            settings,
        )
        voice.connect()
        opening = await voice.start()
        print(f"state={voice.turns.state.value} opening_audio={opening.audio.duration:.3f}s")
        voice.playback_finished()
        for turn_number in range(1, 4):
            first = await voice.accept_chunk(AudioBuffer(b"\x01\x00" * 16000))
            assert first is None
            result = await voice.accept_chunk(AudioBuffer(b"\x01\x00" * 16000))
            assert result is not None and result.latency is not None
            print(
                f"turn={turn_number} state={voice.turns.state.value} "
                f"processing_ms={result.latency.total_processing_ms:.3f}"
            )
            voice.playback_finished()
        closing = await voice.end()
        print(f"state={voice.turns.state.value} closing_audio={closing.audio.duration:.3f}s")
        voice.playback_finished()
        report = app.engine.get_session(session.session_id).report
        assert report is not None
        print(
            f"state={voice.turns.state.value} completed_turns=3 "
            f"feedback_questions={len(report.questions)}"
        )
        await voice.close()


if __name__ == "__main__":
    asyncio.run(run())
