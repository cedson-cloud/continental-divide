"""Semantic review of a drafted request against the event catalog.

The seam matters here: ``rules.py`` reports mechanical duplicates — exact name
matches — as fact. This module asks a model what a draft *means* relative to the
existing plan: an event that already covers the same behavior, properties that
belong on an existing event rather than a new one, or a property the named event
already carries. It reports that as inference requiring human confirmation. Its
output is advisory only and can never reject a request; the worst it can do is
ask a human to look twice.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel, Field, ValidationError

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

FindingKind = Literal["duplicate_event", "property_extension", "property_already_exists"]


class CatalogEntry(BaseModel):
    name: str
    category: str
    description: str
    property_names: list[str]


class ReviewFinding(BaseModel):
    kind: FindingKind
    existing_event: str
    category: str
    # Empty for duplicate_event; the properties at issue for the other kinds.
    property_names: list[str] = Field(default_factory=list)
    # An argument a human can evaluate and disagree with, not a similarity score.
    reason: str
    confidence: Literal["high", "medium", "low"]


@dataclass
class DuplicateReview:
    model: str
    findings: list[ReviewFinding] = field(default_factory=list)
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


def build_review_system_prompt(
    entries: list[CatalogEntry],
    request_kind: Optional[str] = None,
    existing_event: Optional[str] = None,
) -> str:
    """Assemble the review prompt for the request kind. Constraints, in order: the
    question depends on what the requester asked for, the mechanical checks are
    already done, an empty answer is normal, reasons must be arguable, and the model
    is not the authority on the outcome."""
    catalog_lines = [
        f"- {e.name} / {e.category} / {e.description} / properties: "
        + (", ".join(e.property_names) if e.property_names else "(none)")
        for e in entries
    ]

    if request_kind == "new_property_on_existing":
        questions = (
            "The requester is adding properties to an existing event they have "
            f'already named: "{existing_event}". That event is not a duplicate '
            "candidate — the requester chose it deliberately, so never report it "
            'with kind "duplicate_event". Answer one question instead: does '
            f'"{existing_event}" already carry a property that means the same thing '
            "as one being added, under a different name? Report each such case with "
            'kind "property_already_exists", naming the existing event and listing '
            'the added property names at issue in "property_names".'
        )
    else:
        questions = (
            "You answer two questions about the draft. One: is there an existing "
            "event that may mean the same thing under a different name? Report it "
            'with kind "duplicate_event" and an empty "property_names". Two: does '
            "the draft look like properties that belong on an existing event rather "
            "than a new event — behavior the plan already tracks, extended with new "
            'detail? Report that with kind "property_extension", naming the existing '
            "event and listing the drafted property names that belong on it."
        )

    parts = [
        (
            "You review a drafted analytics event request against an existing "
            "tracking plan and report what the draft means relative to it."
        ),
        questions,
        (
            "Exact and near-lexical name matches are ALREADY handled by a deterministic "
            "engine before you run. Your job is meaning, not spelling: report only what "
            "that engine cannot see."
        ),
        (
            EMPTY_RESULT_SENTENCE
            + " Over-flagging is worse than under-flagging, because every finding costs "
            "a human a decision. A reviewer that flags everything is worse than none."
        ),
        (
            "For each finding, write the reason as an argument a human can evaluate "
            'and disagree with — "both fire when a shopper saves a product for later, '
            'the wishlist is just named differently" — never a bare similarity '
            'assertion like "the names are close".'
        ),
        (
            "You are not authoritative. A human decides what to do with each finding; "
            "your output is recorded as inference, not fact."
        ),
        (
            "The existing tracking plan, one event per line as "
            "name / category / description / property names:\n"
            + "\n".join(catalog_lines)
        ),
        (
            'Return ONLY a JSON object: {"findings": [...]}. No prose, no markdown '
            "code fences. Each finding is an object with:\n"
            '- "kind": one of "duplicate_event" | "property_extension" | '
            '"property_already_exists"\n'
            '- "existing_event": the existing event\'s exact name\n'
            '- "category": that event\'s category\n'
            '- "property_names": the property names at issue; an empty list for '
            '"duplicate_event"\n'
            '- "reason": the argument described above\n'
            '- "confidence": one of "high" | "medium" | "low".'
        ),
    ]
    return "\n\n".join(parts)


def build_review_user_message(definition: EventDefinition) -> str:
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


def _parse_findings(cleaned: str) -> tuple[list[ReviewFinding], Optional[str]]:
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return [], f"model output was not valid JSON: {exc.msg}"
    if not isinstance(payload, dict) or not isinstance(payload.get("findings"), list):
        return [], 'model output was not an object with a "findings" list'
    try:
        return (
            [ReviewFinding.model_validate(f) for f in payload["findings"]],
            None,
        )
    except ValidationError as exc:
        return [], f"finding did not match the expected shape: {exc.error_count()} error(s)"


def _apply_kind_rules(
    findings: list[ReviewFinding],
    request_kind: Optional[str],
    existing_event: Optional[str],
) -> list[ReviewFinding]:
    """A new_property_on_existing request has already named its event; the prompt
    forbids reporting that event as a duplicate, and this guard enforces it when the
    model does anyway."""
    if request_kind != "new_property_on_existing" or not existing_event:
        return findings
    return [
        f
        for f in findings
        if not (f.kind == "duplicate_event" and f.existing_event == existing_event)
    ]


def review_against_catalog(
    definition: EventDefinition,
    *,
    request_kind: Optional[str] = None,
    existing_event: Optional[str] = None,
    entries: Optional[list[CatalogEntry]] = None,
) -> DuplicateReview:
    """Ask the model what the draft means relative to the catalog. The question
    depends on ``request_kind``: a new event is reviewed for duplicates and for
    property extensions; a property addition is reviewed only for properties the
    named event already carries. Returns an empty findings list with ``parse_error``
    set when the output could not be read; raises :class:`DuplicateReviewError` when
    the service itself is unreachable. Either way the caller treats the review as
    advisory and routes the request normally."""
    settings = get_settings()
    model = settings.anthropic_model
    if entries is None:
        entries = catalog_entries()
    if request_kind == "new_property_on_existing" and not existing_event:
        # The requester said "existing event" but named none; the draft's own name
        # is the best available target.
        existing_event = definition.name

    api_key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise DuplicateReviewError(model, "no ANTHROPIC_API_KEY configured")

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            temperature=0,
            system=build_review_system_prompt(entries, request_kind, existing_event),
            messages=[
                {"role": "user", "content": build_review_user_message(definition)}
            ],
        )
    except anthropic.AnthropicError as exc:
        raise DuplicateReviewError(
            model, f"model request failed ({type(exc).__name__})"
        ) from exc

    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    findings, parse_error = _parse_findings(_strip_fences(text))
    findings = _apply_kind_rules(findings, request_kind, existing_event)
    return DuplicateReview(model, findings, text, parse_error)
