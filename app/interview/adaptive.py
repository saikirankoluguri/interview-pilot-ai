"""Deterministic rolling difficulty policy independent of LLM suggestions."""

from collections.abc import Sequence

from app.evaluation.rubric import AdaptiveConfig
from app.schemas.interview import Difficulty, DifficultyLevel


class AdaptivePolicy:
    def __init__(self, config: AdaptiveConfig) -> None:
        self.config = config

    def initial_level(self, mode: Difficulty) -> DifficultyLevel:
        return DifficultyLevel(self.config.initial_levels[mode.value])

    def rolling_score(self, scores: Sequence[float]) -> float:
        recent = list(reversed(scores[-3:]))
        weights = self.config.rolling_weights[: len(recent)]
        return (
            sum(s * w for s, w in zip(recent, weights, strict=True)) / sum(weights) if recent else 0
        )

    def next_level(
        self,
        current: DifficultyLevel,
        scores: Sequence[float],
        mode: Difficulty = Difficulty.ADAPTIVE,
    ) -> DifficultyLevel:
        if mode != Difficulty.ADAPTIVE:
            return current
        count = self.config.min_consistent_answers
        if len(scores) < count:
            return current
        recent = scores[-count:]
        rolling = self.rolling_score(scores)
        delta = 0
        if rolling >= self.config.increase_at_or_above and all(
            s >= self.config.increase_at_or_above for s in recent
        ):
            delta = self.config.max_level_step
        elif rolling < self.config.decrease_below and all(
            s < self.config.decrease_below for s in recent
        ):
            delta = -self.config.max_level_step
        return DifficultyLevel(min(5, max(1, int(current) + delta)))
