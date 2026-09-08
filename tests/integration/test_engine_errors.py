"""Single-call live processing, early end, expiry, and failure persistence."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.bootstrap import build_application
from app.providers.factory import Providers, create_providers
from app.providers.llm.base import LLMTask
from app.providers.llm.mock import MockLLMProvider
from app.schemas.interview import InterviewSettings, SessionStatus
from app.utils.errors import ProviderError


class RecordingMock(MockLLMProvider):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.fail_live = False

    async def generate_structured(self, request, schema):
        self.calls.append(request.task)
        if request.task == LLMTask.LIVE_DECISION and self.fail_live:
            raise ProviderError("Simulated unavailable provider.")
        return await super().generate_structured(request, schema)


def test_single_live_call_and_early_end(settings, candidate):
    async def run():
        llm = RecordingMock()
        others = create_providers(settings)
        app = build_application(settings, Providers(llm, others.stt, others.tts, others.vad))
        session = app.engine.create_session(
            candidate, InterviewSettings(target_role=candidate.target_role)
        )
        await app.engine.start_interview(session.session_id)
        before = len(llm.calls)
        await app.engine.process_candidate_answer(
            session.session_id, "A synthetic example of a design decision."
        )
        assert llm.calls[before:] == [LLMTask.LIVE_DECISION]
        await app.engine.end_interview(session.session_id)
        fresh = app.engine.create_session(
            candidate, InterviewSettings(target_role=candidate.target_role)
        )
        await app.engine.start_interview(fresh.session_id)
        report = await app.engine.end_interview(fresh.session_id)
        assert report.overall_score == 0 and len(report.questions) == 1

    asyncio.run(run())


def test_timer_and_failure_preserve_data(settings, candidate):
    async def run():
        llm = RecordingMock()
        others = create_providers(settings)
        app = build_application(settings, Providers(llm, others.stt, others.tts, others.vad))
        now = datetime(2026, 1, 1, tzinfo=UTC)
        app.engine.clock = lambda: now
        session = app.engine.create_session(
            candidate, InterviewSettings(target_role=candidate.target_role)
        )
        await app.engine.start_interview(session.session_id)
        app.engine.clock = lambda: now + timedelta(minutes=31)
        response = await app.engine.process_candidate_answer(session.session_id, "late response")
        assert response.ended and not app.engine.get_session(session.session_id).answers
        app.engine.clock = lambda: now
        session = app.engine.create_session(
            candidate, InterviewSettings(target_role=candidate.target_role)
        )
        await app.engine.start_interview(session.session_id)
        llm.fail_live = True
        with pytest.raises(ProviderError):
            await app.engine.process_candidate_answer(
                session.session_id, "Preserve this synthetic response."
            )
        failed = app.engine.get_session(session.session_id)
        assert failed.status == SessionStatus.FAILED and len(failed.answers) == 1
        await app.engine.end_interview(session.session_id)
        assert app.engine.get_session(session.session_id).status == SessionStatus.COMPLETED

    asyncio.run(run())
