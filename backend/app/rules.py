"""Deterministic governance rules.

These run on a parsed :class:`EventDefinition` (see ``models.py``). They are pure,
non-LLM checks: event-name convention, property-name convention, PII blocklist,
category membership, and duplicate detection against the sample tracking plan.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .models import Decision, Evaluation, EventDefinition, RuleViolation

_PLAN_PATH = Path(__file__).with_name("sample_tracking_plan.json")

# Lowercase connectors allowed inside an event name, e.g. "Product Added to Wishlist".
_CONNECTORS = {"to", "from"}

# Past-tense verbs that don't end in "ed". Kept small and pragmatic; extend as the
# tracking plan grows rather than reaching for a stemmer.
_IRREGULAR_PAST = {
    "made", "sent", "paid", "bought", "sold", "found", "lost", "left", "kept",
    "built", "began", "chose", "won", "set", "put", "read", "cut", "hit",
    "split", "spent", "held", "told", "dealt", "shown", "drawn", "given",
}

# PII tokens to block in property names. Single-token entries match when present as a
# whole token; multi-token entries match as a contiguous token subsequence. Matching is
# on tokens, never substrings, so bare "name" (the product name) passes while
# "first_name" is blocked.
_PII_BLOCKLIST = [
    "email", "phone", "ssn", "social_security", "dob", "date_of_birth", "address",
    "full_name", "first_name", "last_name", "credit_card", "card_number", "password",
    "ip_address",
]

_TITLE_WORD = re.compile(r"^[A-Z][a-z0-9]*$")
_SNAKE_CASE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")


@lru_cache
def load_plan() -> dict:
    return json.loads(_PLAN_PATH.read_text())


@lru_cache
def _categories() -> frozenset[str]:
    return frozenset(load_plan()["categories"].keys())


@lru_cache
def _known_event_names() -> frozenset[str]:
    plan = load_plan()
    return frozenset(
        event["name"]
        for events in plan["categories"].values()
        for event in events
    )


# --- naming convention -----------------------------------------------------------

def _is_past_tense(word: str) -> bool:
    return word.endswith("ed") or word.lower() in _IRREGULAR_PAST


def event_name_error(name: str) -> str | None:
    """Return an error message if ``name`` is not a valid Object Action, Title Case
    event name, else ``None``.

    Valid: two or more Title-Case words, single-spaced, with the action verb (the word
    before a ``to``/``from`` connector, or the final word otherwise) in past tense.
    Connectors are lowercase. Underscores, camelCase, and all-lowercase are rejected.
    """
    if name != name.strip() or "  " in name:
        return "name must be single-spaced with no leading/trailing whitespace"
    if "_" in name:
        return "name must not contain underscores (use Object Action, Title Case)"

    words = name.split(" ")
    if len(words) < 2:
        return "name must be at least two words (Object Action)"

    for i, word in enumerate(words):
        if word in _CONNECTORS:
            if i == 0 or i == len(words) - 1:
                return f"connector '{word}' cannot start or end the name"
            continue
        if word.lower() in _CONNECTORS:
            return f"connector '{word}' must be lowercase"
        if not _TITLE_WORD.match(word):
            return f"word '{word}' must be Title Case (no camelCase or all-lowercase)"

    # The action verb sits just before the first connector, or is the final word.
    connector_positions = [i for i, w in enumerate(words) if w in _CONNECTORS]
    verb_index = connector_positions[0] - 1 if connector_positions else len(words) - 1
    verb = words[verb_index]
    if not _is_past_tense(verb):
        return f"action verb '{verb}' must be past tense"
    return None


def property_name_error(name: str) -> str | None:
    if not _SNAKE_CASE.match(name):
        return f"property '{name}' must be snake_case"
    return None


# --- PII -------------------------------------------------------------------------

def _contiguous(sub: list[str], tokens: list[str]) -> bool:
    n = len(sub)
    return any(tokens[i : i + n] == sub for i in range(len(tokens) - n + 1))


def pii_hit(property_name: str) -> str | None:
    """Return the blocklist entry that ``property_name`` matches, or ``None``."""
    tokens = property_name.split("_")
    for entry in _PII_BLOCKLIST:
        entry_tokens = entry.split("_")
        if len(entry_tokens) == 1:
            if entry_tokens[0] in tokens:
                return entry
        elif _contiguous(entry_tokens, tokens):
            return entry
    return None


# --- evaluation ------------------------------------------------------------------

def evaluate(event: EventDefinition) -> Evaluation:
    """Run all deterministic rules over a parsed definition and return a decision.

    Hard violations (naming, PII, unknown category) reject. A clean definition whose
    name already exists in the plan is flagged as a duplicate and routed to approval.
    A clean, novel definition is routed to approval as ``pending_approval``.
    """
    violations: list[RuleViolation] = []

    name_err = event_name_error(event.name)
    if name_err:
        violations.append(RuleViolation(rule="event_naming", message=name_err))

    if event.category not in _categories():
        violations.append(
            RuleViolation(
                rule="category",
                message=(
                    f"category '{event.category}' is not in the tracking plan "
                    f"({', '.join(sorted(_categories()))})"
                ),
            )
        )

    for prop in event.properties:
        prop_err = property_name_error(prop.name)
        if prop_err:
            violations.append(RuleViolation(rule="property_naming", message=prop_err))
        hit = pii_hit(prop.name)
        if hit:
            violations.append(
                RuleViolation(
                    rule="pii",
                    message=f"property '{prop.name}' matches PII token '{hit}'",
                )
            )

    if violations:
        return Evaluation(
            decision=Decision.rejected, routed_to_approval=False, violations=violations
        )

    if event.name in _known_event_names():
        return Evaluation(
            decision=Decision.flagged_duplicate,
            routed_to_approval=True,
            flags=[f"'{event.name}' already exists in the tracking plan"],
        )

    return Evaluation(decision=Decision.pending_approval, routed_to_approval=True)
