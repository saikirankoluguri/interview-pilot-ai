"""Full local workflow with deterministic scores and no network or model calls."""

import asyncio

import pytest

from app.bootstrap import build_application
from app.schemas.interview import InterviewSettings, SessionStatus
from app.utils.errors import InvalidSessionState


def test_five_turn_interview(settings, candidate):
    async def run():
        app = build_application(settings)
        session = app.engine.create_session(
            candidate, InterviewSettings(target_role=candidate.target_role, panel_size=3)
        )
        start = await app.engine.start_interview(session.session_id)
        assert "Welcome" in start.question
        questions = [start.question]
        for index in range(5):
            response = await app.engine.process_candidate_answer(
                session.session_id,
                f"Synthetic response {index}: I tested alternatives and measured the results.",
            )
            assert response.question not in questions
            questions.append(response.question)
        current = app.engine.get_session(session.session_id)
        assert len(current.answers) == len(current.turns) == len(current.live_evaluations) == 5
        assert [t.next_difficulty for t in current.turns] == [3, 4, 4, 4, 3]
        report = await app.engine.end_interview(session.session_id)
        assert report.is_mock and len(report.questions) == 6
        assert app.engine.get_session(session.session_id).status == SessionStatus.COMPLETED
        assert (settings.report_dir / f"{session.session_id}.json").exists()
        assert await app.engine.end_interview(session.session_id) == report
        with pytest.raises(InvalidSessionState):
            await app.engine.process_candidate_answer(session.session_id, "late answer")

    asyncio.run(run())
