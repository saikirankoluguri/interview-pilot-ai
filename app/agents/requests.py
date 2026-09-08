"""Load trusted prompts and serialize bounded private context for provider requests."""

from pathlib import Path

from app.documents.context_builder import build_context
from app.interview.session import InterviewSession
from app.providers.llm.base import LLMRequest, LLMTask

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


def make_request(
    task: LLMTask, prompt: str, session: InterviewSession, extra_instructions: str = ""
) -> LLMRequest:
    context = build_context(session.candidate, session.settings)
    snapshot = session.model_copy(update={"candidate": context.candidate})
    return LLMRequest(
        task=task,
        instructions=(PROMPTS / prompt).read_text(encoding="utf-8") + "\n" + extra_instructions,
        context_json=snapshot.model_dump_json(),
    )
