"""Deterministic request fixtures for workflow verification, never answer-quality AI."""

from statistics import mean

from app.interview.session import InterviewSession
from app.providers.health import ProviderHealth
from app.providers.llm.base import LLMRequest, LLMTask, ResponseT
from app.schemas.evaluation import (
    AdaptiveAction,
    FinalReport,
    LiveEvaluation,
    LiveTurnDecision,
    QuestionFeedback,
)
from app.schemas.interview import InterviewMessage, InterviewPlan, InterviewQuestion, PanelMember
from app.utils.errors import ProviderError

QUESTION_BANK = (
    (
        "project experience",
        "Describe a project where your own decisions materially affected the result?",
    ),
    (
        "software design",
        "How would you separate responsibilities in a service that is growing quickly?",
    ),
    (
        "testing and automation",
        "How would you design a test strategy for a critical user workflow?",
    ),
    ("API reliability", "How would you diagnose intermittent failures in an API integration?"),
    (
        "Python and Java",
        "How do you choose data structures when correctness and performance both matter?",
    ),
    (
        "production scenarios",
        "How would you investigate a release that increased response latency?",
    ),
    ("collaboration", "Describe a technical disagreement and how you reached a decision?"),
)
ROUND_TOPICS = {
    "screening": ["introduction", "project experience", "role motivation"],
    "round_1": ["project experience", "software fundamentals", "testing and automation"],
    "round_2": ["design trade-offs", "API reliability", "production scenarios"],
    "technical": [
        "software design",
        "testing and automation",
        "API reliability",
        "Python and Java",
    ],
    "managerial": ["team priorities", "delivery trade-offs", "collaboration"],
    "behavioral": ["collaboration", "conflict resolution", "learning from failure"],
    "system_design": ["requirements", "scalability", "reliability", "design trade-offs"],
    "custom": ["custom round experience", "practical scenarios", "trade-offs"],
}


class MockLLMProvider:
    """Scores follow a documented cycle and are independent of candidate quality."""

    def __init__(self, scores: tuple[float, ...] = (85, 88, 65, 35, 30)) -> None:
        if not scores or any(not 0 <= s <= 100 for s in scores):
            raise ValueError("Mock scores must be within 0-100.")
        self.scores = scores

    async def generate(self, request: LLMRequest) -> str:
        if request.task == LLMTask.FEEDBACK:
            return "Mock feedback illustrates the report workflow; it is not an ability assessment."
        return "Mock generation: no language model was called."

    async def generate_structured(self, request: LLMRequest, schema: type[ResponseT]) -> ResponseT:
        session = InterviewSession.model_validate_json(request.context_json)
        if request.task == LLMTask.PLAN:
            result = self._plan(session)
        elif request.task == LLMTask.OPENING:
            company = f" at {session.candidate.company}" if session.candidate.company else ""
            result = InterviewMessage(
                question=f"Welcome, {session.candidate.name}. "
                f"For this {session.settings.round.value} "
                f"interview for {session.settings.target_role}{company}, "
                "which recent project best represents your contribution?",
                panel_member=session.panel[0].name,
            )
        elif request.task == LLMTask.LIVE_DECISION:
            result = self._live(session)
        elif request.task == LLMTask.FINAL_EVALUATION:
            result = self._final(session)
        else:
            raise ProviderError("Unsupported structured mock request.")
        return schema.model_validate(result.model_dump(mode="json"))

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth("mock", "healthy", "mock", detail="Deterministic LLM fixture")

    def _plan(self, session: InterviewSession) -> InterviewPlan:
        topics = ROUND_TOPICS[session.settings.round.value]
        panel = [
            PanelMember(name=name, title=title, focus_area=focus)
            for name, title, focus in (
                ("Morgan", "Technical Lead", "technical depth"),
                ("Jordan", "Hiring Manager", "delivery and collaboration"),
                ("Taylor", "Senior Engineer", "practical engineering"),
            )
        ][: session.settings.panel_size]
        skills = ("python", "java", "api", "testing", "automation", "design", "sql", "cloud")
        resume_areas = [
            skill for skill in skills if skill in session.candidate.resume_text.casefold()
        ]
        jd_areas = [
            skill for skill in skills if skill in session.candidate.job_description.casefold()
        ]
        return InterviewPlan(
            topics=topics,
            question_allocation=[2] * len(topics),
            starting_difficulty=session.current_difficulty,
            panel=panel,
            resume_priorities=resume_areas or ["project experience"],
            jd_priorities=jd_areas or [session.settings.target_role],
        )

    def _live(self, session: InterviewSession) -> LiveTurnDecision:
        index = len(session.answers) - 1
        score = self.scores[index % len(self.scores)]
        current = session.questions[-1]
        topics = session.plan.topics if session.plan else [topic for topic, _ in QUESTION_BANK]
        topic = current.topic if index % 3 < 2 else topics[(index // 3 + 1) % len(topics)]
        followups = ("trade-offs", "verification steps", "failure modes")
        text = f"For {topic}, what {followups[index % 3]} did you consider in your example?"
        if index % 3 == 2:
            text = next(
                (q for t, q in QUESTION_BANK if t == topic),
                f"For a {session.settings.target_role}, how would you approach {topic}?",
            )
        evaluation = LiveEvaluation(
            overall_score=score,
            correctness=score,
            relevance=score,
            depth=score,
            evidence=score,
            missing_concepts=["A measurable outcome"] if score < 80 else [],
            rationale="Deterministic mock score; not an ability assessment.",
            suggested_next_difficulty=session.current_difficulty,
        )
        return LiveTurnDecision(
            evaluation=evaluation,
            action=AdaptiveAction.FOLLOW_UP if index % 3 < 2 else AdaptiveAction.CHANGE_TOPIC,
            next_difficulty=session.current_difficulty,
            next_question=InterviewQuestion(
                text=text, topic=topic, difficulty=session.current_difficulty
            ),
        )

    def _final(self, session: InterviewSession) -> FinalReport:
        answers = {a.question_id: a.text for a in session.answers}
        scores = {t.question.question_id: t.evaluation.overall_score for t in session.turns}
        average = round(mean(scores.values()), 2) if scores else 0
        questions = [
            QuestionFeedback(
                question_id=q.question_id,
                question=q.text,
                answer_transcript=answers.get(q.question_id, "No answer recorded."),
                score=scores.get(q.question_id, 0),
                done_well=["Example feedback: described an approach."]
                if q.question_id in answers
                else [],
                missing=["Example feedback: add measurable evidence."]
                if q.question_id in answers
                else ["Not assessed: no answer recorded."],
                interviewer_expected="A clear approach, relevant trade-offs, "
                "and concrete evidence.",
                ideal_answer="State the context, explain your decision and alternatives, "
                "then describe "
                "how you verified the result. This is mock coaching, not a model answer.",
                recommended_topics=[q.topic],
            )
            for q in session.questions
        ]
        return FinalReport(
            session_id=session.session_id,
            overall_score=average,
            technical_score=average,
            relevance_score=average,
            communication_score=average,
            depth_score=average,
            practical_experience_score=average,
            questions=questions,
            strengths=["Mock example: structured engineering approach"],
            weaknesses=["Mock example: evidence needs more detail"],
            weak_topics=list(dict.fromkeys(q.topic for q in session.questions))[:3],
            preparation_recommendations=["Practice explaining a decision and its outcome."],
            next_mock_focus="Project decisions, trade-offs, and measurable outcomes",
            is_mock=True,
        )
