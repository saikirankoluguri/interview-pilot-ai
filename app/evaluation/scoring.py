"""Content-only live scoring and configurable final aggregation."""

from app.evaluation.rubric import ScoringRubric
from app.schemas.evaluation import FinalReport, LiveEvaluation


def calculate_live_score(evaluation: LiveEvaluation, rubric: ScoringRubric) -> float:
    return round(
        sum(getattr(evaluation, key) * weight for key, weight in rubric.live_weights.items()), 2
    )


def calculate_final_score(report: FinalReport, rubric: ScoringRubric) -> float:
    return round(
        sum(getattr(report, key) * weight for key, weight in rubric.final_weights.items()), 2
    )
