"""Application composition root; domain classes never select model vendors."""

from dataclasses import dataclass

from app.agents.final_evaluator import FinalEvaluatorAgent
from app.agents.interviewer import InterviewerAgent
from app.agents.live_evaluator import LiveEvaluatorAgent
from app.config.settings import Settings
from app.evaluation.rubric import load_rubric
from app.interview.adaptive import AdaptivePolicy
from app.interview.engine import InterviewEngine
from app.interview.planner import InterviewPlannerAgent
from app.interview.question_router import QuestionRouter
from app.providers.factory import Providers, create_providers
from app.storage.file_store import FileStore
from app.storage.session_store import SessionStore


@dataclass
class Application:
    settings: Settings
    engine: InterviewEngine
    providers: Providers
    uploads: FileStore


def build_application(
    settings: Settings | None = None, providers: Providers | None = None
) -> Application:
    settings = settings or Settings()
    providers = providers or create_providers(settings)
    rubric = load_rubric()
    store = SessionStore(settings.transcript_dir, settings.report_dir)
    engine = InterviewEngine(
        planner=InterviewPlannerAgent(providers.llm),
        interviewer=InterviewerAgent(providers.llm),
        live_evaluator=LiveEvaluatorAgent(providers.llm, rubric),
        final_evaluator=FinalEvaluatorAgent(providers.llm),
        policy=AdaptivePolicy(rubric.adaptive),
        router=QuestionRouter(rubric.adaptive.max_consecutive_topic),
        store=store,
        rubric=rubric,
    )
    return Application(
        settings, engine, providers, FileStore(settings.upload_dir, settings.max_upload_bytes)
    )
