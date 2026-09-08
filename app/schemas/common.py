"""Shared validation conventions for domain contracts."""

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    """Reject unexpected input and normalize surrounding string whitespace."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)
