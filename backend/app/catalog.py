"""Semantic duplicate review against the event catalog.

The seam matters here: ``rules.py`` reports mechanical duplicates — exact name
matches — as fact. This module asks a model whether a drafted event *means* the
same thing as an existing one under a different name, and reports that as
inference requiring human confirmation. Its output is advisory only and can
never reject a request; the worst it can do is ask an approver to look twice.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel, ValidationError

from .config import get_settings
from .interpreter import _strip_fences
from .models import EventDefinition
from .rules import load_plan

# Asserted on by tests and rendered verbatim into the system prompt: the model must
# know that finding nothing is the normal outcome, not a failure to perform.
EMPTY_RESULT_SENTENCE = (
    "Returning an empty list is a valid and common answer: most drafted events are "
    "genuinely new."
)


class CatalogEntry(BaseModel):
    name: str
    category: str
    description: str
    property_names: list[str]


class DuplicateCandidate(BaseModel):
    existing_event: str
    category: str
    # An argument a human can evaluate and disagree with, not a similarity score.
    reason: str
    confidence: Literal["high", "medium", "low"]


@dataclass
class DuplicateReview:
    model: str
    candidates: list[DuplicateCandidate] = field(default_factory=list)
    raw_response: str = ""
    parse_error: Optional[str] = None


class DuplicateReviewError(Exception):
    """Raised when the model service itself fails (API error, missing key)."""

    def __init__(self, model: str, message: str) -> None:
        self.model = model
        super().__init__(message)


@lru_cache
def catalog_entries() -> list[CatalogEntry]:
    plan = load_plan()
    return [
        CatalogEntry(
            name=event["name"],
            category=category,
            description=event.get("description", ""),
            property_names=[p["name"] for p in event.get("properties", [])],
        )
        for category, events in plan["categories"].items()
        for event in events
    ]


def build_duplicate_system_prompt(entries: list[CatalogEntry]) -> str:
    """Assemble the review prompt. Constraints, in order: the mechanical checks are
    already done, an empty answer is normal, reasons must be arguable, and the model
    is not the authority on the outcome."""
    catalog_lines = [
        f"- {e.name} / {e.category} / {e.description} / properties: "
        + (", ".join(e.property_names) if e.property_names else "(none)")
        for e in entries
    ]

    parts = [
        (
            "You review a drafted analytics event against an existing tracking plan "
            "and report events that may mean the same thing under a different name."
        ),
        (
            "Exact and near-lexical name matches are ALREADY handled by a deterministic "
            "engine before you run. Your only job is same-meaning-different-words: an "
            "existing event that describes the same user behavior the draft describes."
        ),
        (
            EMPTY_RESULT_SENTENCE
            + " Over-flagging is worse than under-flagging, because every flag costs a "
            "human a decision. A duplicate checker that flags everything is worse than "
            "none."
        ),
        (
            "For each candidate, write the reason as an argument a human can evaluate "
            'and disagree with — "both fire when a shopper saves a product for later, '
            'the wishlist is just named differently" — never a bare similarity '
            'assertion like "the names are close".'
        ),
        (
            "You are not authoritative. A human approver decides whether the draft is a "
            "duplicate; your output is recorded as inference, not fact."
        ),
        (
            "The existing tracking plan, one event per line as "
            "name / category / description / property names:\n"
            + "\n".join(catalog_lines)
        ),
        (
            'Return ONLY a JSON object: {"candidates": [...]}. No prose, no markdown '
            "code fences. Each candidate is an object with:\n"
            '- "existing_event": the existing event\'s exact name\n'
            '- "category": that event\'s category\n'
            '- "reason": the argument described above\n'
            '- "confidence": one of "high" | "medium" | "low".'
        ),
    ]
    return "\n\n".join(parts)


def build_duplicate_user_message(definition: EventDefinition) -> str:
    lines = [
        "Drafted event:",
        f"name: {definition.name}",
        f"category: {definition.category}",
        f"description: {definition.description or '(none)'}",
        "properties: "
        + (
            ", ".join(p.name for p in definition.properties)
            if definition.properties
            else "(none)"
        ),
    ]
    return "\n".join(lines)


def _parse_candidates(cleaned: str) -> tuple[list[DuplicateCandidate], Optional[str]]:
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return [], f"model output was not valid JSON: {exc.msg}"
    if not isinstance(payload, dict) or not isinstance(payload.get("candidates"), list):
        return [], 'model output was not an object with a "candidates" list'
    try:
        return (
            [DuplicateCandidate.model_validate(c) for c in payload["candidates"]],
            None,
        )
    except ValidationError as exc:
        return [], f"candidate did not match the expected shape: {exc.error_count()} error(s)"


def review_for_duplicates(
    definition: EventDefinition, *, entries: Optional[list[CatalogEntry]] = None
) -> DuplicateReview:
    """Ask the model for semantic duplicate candidates. Returns an empty candidate
    list with ``parse_error`` set when the output could not be read; raises
    :class:`DuplicateReviewError` when the service itself is unreachable. Either way
    the caller treats the review as advisory and routes the request normally."""
    settings = get_settings()
    model = settings.anthropic_model
    if entries is None:
        entries = catalog_entries()

    api_key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise DuplicateReviewError(model, "no ANTHROPIC_API_KEY configured")

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            temperature=0,
            system=build_duplicate_system_prompt(entries),
            messages=[
                {"role": "user", "content": build_duplicate_user_message(definition)}
            ],
        )
    except anthropic.AnthropicError as exc:
        raise DuplicateReviewError(
            model, f"model request failed ({type(exc).__name__})"
        ) from exc

    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    candidates, parse_error = _parse_candidates(_strip_fences(text))
    return DuplicateReview(model, candidates, text, parse_error)
