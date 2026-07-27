"""Deterministic governance rules.

These run on a parsed :class:`EventDefinition` (see ``models.py``). They are pure,
non-LLM checks: event-name convention, property-name convention, PII blocklist,
category membership, and duplicate detection against the sample tracking plan.

The three name-level checks take keyword-only overrides so a governance profile
(see ``governance.py``) can reconfigure them; the defaults reproduce the built-in
convention, so existing callers are unaffected.
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from .models import Decision, Evaluation, EventDefinition, RuleCheck

if TYPE_CHECKING:
    from .governance import GovernanceProfile

_PLAN_PATH = Path(__file__).with_name("sample_tracking_plan.json")

# Lowercase connectors allowed inside an event name, e.g. "Product Added to Wishlist".
_CONNECTORS = {"to", "from"}

# Title Case particles that end a phrasal verb, e.g. "Newsletter Signed Up". Unlike
# connectors they are ordinary Title Case words; they only shift where the verb is.
_PARTICLES = {"Up", "In", "Out", "On", "Off", "Down"}

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

# A Title Case word: capitalized ("Cart") or an all-caps acronym ("SKU").
_TITLE_WORD = re.compile(r"^[A-Z](?:[a-z0-9]*|[A-Z0-9]+)$")
_SNAKE_CASE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")


@lru_cache
def load_plan() -> dict:
    return json.loads(_PLAN_PATH.read_text())


@lru_cache
def known_categories() -> frozenset:
    return frozenset(load_plan()["categories"].keys())


def effective_categories(profile: "GovernanceProfile") -> tuple[frozenset[str], str]:
    """The categories a definition is actually checked against, and where they
    came from: "profile" or "sample_plan". A profile that declares categories
    constrains to them; an empty list falls back to the sample tracking plan."""
    if profile.categories:
        return frozenset(profile.categories), "profile"
    return known_categories(), "sample_plan"


@lru_cache
def known_event_names() -> frozenset:
    plan = load_plan()
    return frozenset(
        event["name"]
        for events in plan["categories"].values()
        for event in events
    )


# --- naming convention -----------------------------------------------------------

def _is_past_tense(word: str, irregular_past: Collection[str]) -> bool:
    return word.endswith("ed") or word.lower() in irregular_past


def event_name_error(
    name: str,
    *,
    convention: str = "title_case_object_action",
    connectors: Collection[str] = _CONNECTORS,
    particles: Collection[str] = _PARTICLES,
    irregular_past: Collection[str] = _IRREGULAR_PAST,
) -> str | None:
    """Return an error message if ``name`` violates the event naming convention,
    else ``None``. The defaults reproduce the built-in Title Case convention; a
    governance profile can swap the convention and the word lists.

    title_case_object_action: two or more Title-Case words, single-spaced, with the
    action verb (the word before a ``to``/``from`` connector, or the final word
    otherwise) in past tense. A phrasal-verb particle ("Newsletter Signed Up")
    shifts the verb one word left. All-caps acronyms ("SKU Added") count as Title
    Case words. Connectors are lowercase. Underscores, camelCase, and all-lowercase
    are rejected.

    snake_case_object_action: lowercase snake_case with two or more tokens, same
    verb, connector, and particle logic applied to lowercase tokens.
    """
    if convention == "title_case_object_action":
        return _title_case_error(name, set(connectors), set(particles), set(irregular_past))
    if convention == "snake_case_object_action":
        return _snake_case_error(
            name, set(connectors), {p.lower() for p in particles}, set(irregular_past)
        )
    raise ValueError(f"unknown event naming convention '{convention}'")


def _title_case_error(
    name: str, connectors: set, particles: set, irregular_past: set
) -> str | None:
    if name != name.strip() or "  " in name:
        return "name must be single-spaced with no leading/trailing whitespace"
    if "_" in name:
        return "name must not contain underscores (use Object Action, Title Case)"

    words = name.split(" ")
    if len(words) < 2:
        return "name must be at least two words (Object Action)"

    for i, word in enumerate(words):
        if word in connectors:
            if i == 0 or i == len(words) - 1:
                return f"connector '{word}' cannot start or end the name"
            continue
        if word.lower() in connectors:
            return f"connector '{word}' must be lowercase"
        if not _TITLE_WORD.match(word):
            return f"word '{word}' must be Title Case (no camelCase or all-lowercase)"

    # The action verb sits just before the first connector, or is the final word.
    connector_positions = [i for i, w in enumerate(words) if w in connectors]
    verb_index = connector_positions[0] - 1 if connector_positions else len(words) - 1
    # A trailing particle shifts the verb one word left: "Newsletter Signed Up".
    if words[verb_index] in particles and verb_index > 0:
        verb_index -= 1
    verb = words[verb_index]
    if not _is_past_tense(verb, irregular_past):
        return f"action verb '{verb}' must be past tense"
    return None


def _snake_case_error(
    name: str, connectors: set, particles: set, irregular_past: set
) -> str | None:
    if not _SNAKE_CASE.match(name):
        return "name must be lowercase snake_case (object_action)"

    tokens = name.split("_")
    if len(tokens) < 2:
        return "name must be at least two tokens (object_action)"

    connector_positions = [i for i, t in enumerate(tokens) if t in connectors]
    for i in connector_positions:
        if i == 0 or i == len(tokens) - 1:
            return f"connector '{tokens[i]}' cannot start or end the name"

    # Same verb logic as Title Case, on lowercase tokens.
    verb_index = connector_positions[0] - 1 if connector_positions else len(tokens) - 1
    if tokens[verb_index] in particles and verb_index > 0:
        verb_index -= 1
    verb = tokens[verb_index]
    if not _is_past_tense(verb, irregular_past):
        return f"action verb '{verb}' must be past tense"
    return None


def property_name_error(name: str, *, convention: str = "snake_case") -> str | None:
    if convention != "snake_case":
        raise ValueError(f"unknown property naming convention '{convention}'")
    if not _SNAKE_CASE.match(name):
        return f"property '{name}' must be snake_case"
    return None


# --- PII -------------------------------------------------------------------------

def _contiguous(sub: list[str], tokens: list[str]) -> bool:
    n = len(sub)
    return any(tokens[i : i + n] == sub for i in range(len(tokens) - n + 1))


def pii_hit(
    property_name: str, *, blocklist: Collection[str] = _PII_BLOCKLIST
) -> str | None:
    """Return the blocklist entry that ``property_name`` matches, or ``None``."""
    tokens = property_name.split("_")
    for entry in blocklist:
        entry_tokens = entry.split("_")
        if len(entry_tokens) == 1:
            if entry_tokens[0] in tokens:
                return entry
        elif _contiguous(entry_tokens, tokens):
            return entry
    return None


# --- evaluation ------------------------------------------------------------------

def evaluate(
    event: EventDefinition, profile: "GovernanceProfile | None" = None
) -> Evaluation:
    """Run all deterministic rules over a parsed definition and return a decision.

    Returns a structured per-rule report. A failure on a hard rule (naming, category,
    property naming) rejects. PII is a non-blocking flag: a flagged definition still
    routes to approval, where a human must acknowledge the PII before approving. A clean
    definition whose name already exists in the plan is flagged as a duplicate and routed
    to approval. A clean, novel definition is routed to approval as ``pending_approval``.

    ``profile`` configures the rules; ``None`` resolves to ``DEFAULT_PROFILE``, which
    reproduces the constants above. (The default is ``None`` rather than the profile
    object itself because ``governance`` imports this module's constants — importing
    it back at module level would be circular.)
    """
    from .governance import DEFAULT_PROFILE

    if profile is None:
        profile = DEFAULT_PROFILE

    checks = []

    naming = profile.event_naming
    name_err = event_name_error(
        event.name,
        convention=naming.convention,
        connectors=naming.connectors,
        particles=naming.particles,
        irregular_past=naming.irregular_past,
    )
    checks.append(
        RuleCheck(
            rule="event_naming",
            passed=name_err is None,
            detail=name_err or f"valid name under {naming.convention}",
        )
    )

    allowed_categories, category_source_key = effective_categories(profile)
    category_source = (
        "the governance profile" if category_source_key == "profile"
        else "the tracking plan"
    )
    category_ok = event.category in allowed_categories
    checks.append(
        RuleCheck(
            rule="category",
            passed=category_ok,
            detail=(
                f"category is in {category_source}"
                if category_ok
                else f"category '{event.category}' is not in {category_source}"
            ),
        )
    )

    prop_convention = profile.property_naming.convention
    bad_props = [
        p.name
        for p in event.properties
        if property_name_error(p.name, convention=prop_convention)
    ]
    checks.append(
        RuleCheck(
            rule="property_naming",
            passed=not bad_props,
            detail=(
                f"all property names are {prop_convention}"
                if not bad_props
                else f"not {prop_convention}: {', '.join(bad_props)}"
            ),
        )
    )

    blocklist = profile.pii.blocklist
    pii_hits = [
        f"{p.name} -> {pii_hit(p.name, blocklist=blocklist)}"
        for p in event.properties
        if pii_hit(p.name, blocklist=blocklist)
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
