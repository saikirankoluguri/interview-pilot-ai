"""Validated YAML policy; numerical thresholds are not duplicated in agents."""

from pathlib import Path

import yaml
from pydantic import Field, model_validator

from app.schemas.common import DomainModel
from app.utils.errors import ConfigurationError


class AdaptiveConfig(DomainModel):
    rolling_weights: list[float] = Field(min_length=3, max_length=3)
    increase_at_or_above: float
    decrease_below: float
    min_consistent_answers: int = Field(ge=2, le=3)
    max_level_step: int = Field(ge=1, le=1)
    max_consecutive_topic: int = Field(ge=2, le=6)
    initial_levels: dict[str, int]


class ScoringRubric(DomainModel):
    live_weights: dict[str, float]
    final_weights: dict[str, float]
    adaptive: AdaptiveConfig

    @model_validator(mode="after")
    def validate_weights(self) -> "ScoringRubric":
        for weights in (
            self.live_weights.values(),
            self.final_weights.values(),
            self.adaptive.rolling_weights,
        ):
            if any(w < 0 for w in weights) or abs(sum(weights) - 1) > 0.00001:
                raise ValueError("Scoring weights must be nonnegative and sum to one.")
        if set(self.live_weights) != {"correctness", "relevance", "depth", "evidence"}:
            raise ValueError("Live weights must use job-relevant evidence dimensions only.")
        if set(self.final_weights) != {
            "technical_score",
            "relevance_score",
            "depth_score",
            "practical_experience_score",
            "communication_score",
        }:
            raise ValueError("Unsupported final scoring dimensions.")
        if set(self.adaptive.initial_levels) != {"easy", "medium", "hard", "adaptive"}:
            raise ValueError("All difficulty modes need a starting level.")
        if any(not 1 <= n <= 5 for n in self.adaptive.initial_levels.values()):
            raise ValueError("Starting levels must be within 1-5.")
        return self


def load_rubric(path: Path | None = None) -> ScoringRubric:
    path = path or Path(__file__).resolve().parents[2] / "configs/scoring.yaml"
    try:
        return ScoringRubric.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ConfigurationError("Cannot load the scoring policy.") from exc
