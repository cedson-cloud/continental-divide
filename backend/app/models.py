"""Typed event-definition schema (Pydantic v2).

This is the structured shape a raw intake request is parsed into. Parse failure is a
hard rejection with the validation errors recorded; the deterministic checks in
``rules.py`` run only on a successfully parsed definition.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PropertyType(str, Enum):
    string = "string"
    number = "number"
    integer = "integer"
    boolean = "boolean"
    array = "array"
    object = "object"


class EventProperty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    type: PropertyType
    required: bool = False
    # For array properties, the shared shape its items follow (e.g. "product_item").
    items: Optional[str] = None


class EventDefinition(BaseModel):
    """The structured definition produced from a raw request."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    description: Optional[str] = None
    properties: List[EventProperty] = Field(default_factory=list)


class Decision(str, Enum):
    pending_approval = "pending_approval"
    rejected = "rejected"
    # Clean but needs a human because it collides with an existing event.
    flagged_duplicate = "flagged_duplicate"


class RuleViolation(BaseModel):
    rule: str
    message: str


class Evaluation(BaseModel):
    """Outcome of running an event definition through the deterministic rules."""

    decision: Decision
    routed_to_approval: bool
    violations: List[RuleViolation] = Field(default_factory=list)
    flags: List[str] = Field(default_factory=list)
