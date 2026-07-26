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

from .models import Decision, Evaluation, EventDefinition, RuleCheck

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
def known_categories() -> frozenset:
    return frozenset(load_plan()["categories"].keys())


@lru_cache
def known_event_names() -> frozenset:
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

    Returns a structured per-rule report. A failure on a hard rule (naming, category,
    property naming) rejects. PII is a non-blocking flag: a flagged definition still
    routes to approval, where a human must acknowledge the PII before approving. A clean
    definition whose name already exists in the plan is flagged as a duplicate and routed
    to approval. A clean, novel definition is routed to approval as ``pending_approval``.
    """
    checks = []

    name_err = event_name_error(event.name)
    checks.append(
        RuleCheck(
            rule="event_naming",
            passed=name_err is None,
            detail=name_err or "valid Object Action, Title Case name",
        )
    )

    category_ok = event.category in known_categories()
    checks.append(
        RuleCheck(
            rule="category",
            passed=category_ok,
            detail=(
                "category is in the tracking plan"
                if category_ok
                else f"category '{event.category}' is not in the tracking plan"
            ),
        )
    )

    bad_props = [p.name for p in event.properties if property_name_error(p.name)]
    checks.append(
        RuleCheck(
            rule="property_naming",
            passed=not bad_props,
            detail=(
                "all property names are snake_case"
                if not bad_props
                else f"not snake_case: {', '.join(bad_props)}"
            ),
        )
    )

    pii_hits = [
        f"{p.name} -> {pii_hit(p.name)}" for p in event.properties if pii_hit(p.name)
    ]
    pii_flagged = bool(pii_hits)
    pii_details = "; ".join(pii_hits)
    checks.append(
        RuleCheck(
            rule="pii",
            passed=not pii_flagged,
            detail=(
                "no PII tokens in property names"
                if not pii_flagged
                else f"flagged (acknowledgment required to approve): {pii_details}"
            ),
        )
    )

    # PII does not reject; only the naming, category, and property-naming rules do.
    hard_failed = any(not c.passed for c in checks if c.rule != "pii")
    flags = (
        [f"'{event.name}' already exists in the tracking plan"]
        if not hard_failed and event.name in known_event_names()
        else []
    )
    if hard_failed:
        decision, routed = Decision.rejected, False
    elif flags:
        decision, routed = Decision.flagged_duplicate, True
    else:
        decision, routed = Decision.pending_approval, True

    return Evaluation(
        decision=decision,
        routed_to_approval=routed,
        checks=checks,
        flags=flags,
        pii_flagged=pii_flagged,
        pii_details=pii_details,
    )
