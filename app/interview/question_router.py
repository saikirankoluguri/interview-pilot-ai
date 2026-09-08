"""Lightweight duplicate/topic protection without embeddings or extra model calls."""

import re

from app.schemas.interview import DifficultyLevel, InterviewQuestion


def fingerprint(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))


class QuestionRouter:
    def __init__(self, max_consecutive_topic: int = 3) -> None:
        self.max_consecutive_topic = max_consecutive_topic

    def route(
        self,
        proposal: InterviewQuestion,
        history: list[InterviewQuestion],
        topics: list[str],
        level: DifficultyLevel,
        panel_size: int,
    ) -> InterviewQuestion:
        """Use safe contextual follow-ups if a proposal duplicates or overuses a topic."""
        seen = {fingerprint(q.text) for q in history}
        topic = proposal.topic
        text = proposal.text
        recent = history[-self.max_consecutive_topic :]
        overused = len(recent) == self.max_consecutive_topic and all(
            fingerprint(q.topic) == fingerprint(topic) for q in recent
        )
        if overused:
            topic = next((t for t in topics if fingerprint(t) != fingerprint(topic)), "experience")
            text = f"For {topic}, describe a concrete challenge and how you approached it?"
        if fingerprint(text) in seen:
            for angle in (
                "trade-offs",
                "failure modes",
                "verification",
                "alternatives",
                "outcomes",
            ):
                candidate = f"For {topic}, what {angle} did you consider in your example?"
                if fingerprint(candidate) not in seen:
                    text = candidate
                    break
            else:
                text = (
                    f"In a different {topic} example, what would you change "
                    f"under constraint number {len(history) + 1} and why?"
                )
        return InterviewQuestion(
            text=text, topic=topic, difficulty=level, panel_index=len(history) % panel_size
        )
