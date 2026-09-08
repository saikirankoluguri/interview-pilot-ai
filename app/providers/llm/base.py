"""Typed, vendor-neutral asynchronous language model contract."""

from enum import StrEnum
from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.schemas.common import DomainModel


class LLMTask(StrEnum):
    PLAN = "plan"
    OPENING = "opening"
    LIVE_DECISION = "live_decision"
    FINAL_EVALUATION = "final_evaluation"
    FEEDBACK = "feedback"


class LLMRequest(DomainModel):
    """Context is serialized domain data, distinct from trusted prompt instructions."""

    task: LLMTask
    instructions: str
    context_json: str


ResponseT = TypeVar("ResponseT", bound=BaseModel)


class LLMProvider(Protocol):
    async def generate(self, request: LLMRequest) -> str: ...
    async def generate_structured(
        self, request: LLMRequest, schema: type[ResponseT]
    ) -> ResponseT: ...
