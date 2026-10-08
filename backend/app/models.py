"""Typed event-definition schema (Pydantic v2).

This is the structured shape a raw intake request is parsed into. Parse failure is a
hard rejection with the validation errors recorded; the deterministic checks in
``rules.py`` run only on a successfully parsed definition.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# What kind of thing a definition records (ADR 0003). Part of the definition, never a
# routing outcome, so it is not a Decision.
CallType = Literal["track", "identify", "group"]


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
    """The structured definition produced from a raw request.

    Its shape follows the call type (ADR 0003). ``track`` is an event: a name, a
    category, and properties. ``identify`` adds traits to the plan's one identify call,
    so it has traits and no name or category. ``group`` names a group type
    (``company``) and the traits it carries, with no category.
    """

    model_config = ConfigDict(extra="forbid")

    call_type: CallType = "track"
    name: Optional[str] = Field(default=None, min_length=1)
    category: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    properties: List[EventProperty] = Field(default_factory=list)
    traits: List[EventProperty] = Field(default_factory=list)

    @model_validator(mode="after")
    def _shape_follows_call_type(self) -> "EventDefinition":
        problems = []
        if self.call_type == "track":
            if self.name is None:
                problems.append("a track definition needs a name")
            if self.category is None:
                problems.append("a track definition needs a category")
            if self.traits:
                problems.append("a track definition carries properties, not traits")
        else:
            if self.category is not None:
                problems.append(f"a {self.call_type} definition has no category")
            if self.properties:
                problems.append(
                    f"a {self.call_type} definition carries traits, not properties"
                )
        if self.call_type == "identify":
            if self.name is not None:
                problems.append(
                    "an identify definition has no name: the plan has one identify call"
                )
            if not self.traits:
                problems.append("an identify definition needs at least one trait")
        if self.call_type == "group" and self.name is None:
            problems.append("a group definition needs a name: its group type")
        if problems:
            raise ValueError("; ".join(problems))
        return self


class Decision(str, Enum):
    pending_approval = "pending_approval"
    rejected = "rejected"
    # Clean but needs a human because it collides with an existing event.
    flagged_duplicate = "flagged_duplicate"


class RuleCheck(BaseModel):
    rule: str
    passed: bool
    detail: str


class Evaluation(BaseModel):
    """Outcome of running an event definition through the deterministic rules."""

    decision: Decision
    routed_to_approval: bool
    checks: List[RuleCheck] = Field(default_factory=list)
    flags: List[str] = Field(default_factory=list)
    # PII is a non-blocking flag: a flagged event still submits and routes to approval,
    # but a human must acknowledge the PII before it can be approved.
    pii_flagged: bool = False
    pii_details: str = ""
    # Each flagged property and the blocklist entry it matched; every one needs a
    # written reason from the requester before the request reaches an approver.
    pii_hits: dict[str, str] = Field(default_factory=dict)
