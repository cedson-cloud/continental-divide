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
from .platforms import SystemEvent, plan_named_events, render_plan_name

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
# Names use plain ASCII characters only; case is judged separately, by the convention.
_TITLE_CASE_CHARS = re.compile(r"[A-Za-z0-9 _]")
_SNAKE_CASE_CHARS = re.compile(r"[A-Za-z0-9_]")


def _disallowed_characters(name: str, allowed: re.Pattern) -> str | None:
    """The characters ``name`` may not use, in order of first appearance, ready to
    quote back to the requester; ``None`` when every character is allowed."""
    found = dict.fromkeys(c for c in name if not allowed.fullmatch(c))
    if not found:
        return None
    return ", ".join("a space" if c == " " else f"'{c}'" for c in found)


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

# One-sentence descriptions of the name shape only, for prompt assembly. Connector
# words, particles, and irregular verbs come from the governance profile and are
# injected separately — never bake specific words in here.
_CONVENTION_DESCRIPTIONS: dict[str, str] = {
    "title_case_object_action": (
        "Object Action in Title Case — two or more words, single-spaced, each word "
        "capitalized (all-caps acronyms allowed), ending in a past-tense action verb."
    ),
    "snake_case_object_action": (
        "object_action in lowercase snake_case — two or more underscore-separated "
        "tokens, all lowercase, ending in a past-tense action verb."
    ),
}


def convention_description(convention: str) -> str:
    try:
        return _CONVENTION_DESCRIPTIONS[convention]
    except KeyError:
        raise ValueError(f"unknown event naming convention '{convention}'") from None


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
    action verb (the word before the first connector, or the final word
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
    found = _disallowed_characters(name, _TITLE_CASE_CHARS)
    if found:
        return (
            "Title Case names may only use letters A–Z, numbers and spaces "
            f"(found {found})"
        )

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
    found = _disallowed_characters(name, _SNAKE_CASE_CHARS)
    if found:
        return (
            "snake_case names may only use lowercase letters a–z, numbers and "
            f"underscores (found {found})"
        )
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


def property_name_error(
    name: str, *, convention: str = "snake_case", kind: str = "property"
) -> str | None:
    """``kind`` names what is being judged in the message: a property, a trait, or a
    group type all follow the property naming convention."""
    if convention != "snake_case":
        raise ValueError(f"unknown property naming convention '{convention}'")
    found = _disallowed_characters(name, _SNAKE_CASE_CHARS)
    if found:
        return (
            f"{kind} '{name}' must be snake_case: lowercase letters a–z, numbers "
            f"and underscores only (found {found})"
        )
    if not _SNAKE_CASE.match(name):
        return f"{kind} '{name}' must be snake_case"
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


def pii_hits(
    event: EventDefinition, profile: "GovernanceProfile"
) -> dict[str, str]:
    """Each property or trait that matches the profile's PII blocklist, mapped to the
    entry it matched. Every one needs a written reason from the requester (ADR 0003)."""
    blocklist = profile.pii.blocklist
    return {
        p.name: entry
        for p in [*event.properties, *event.traits]
        if (entry := pii_hit(p.name, blocklist=blocklist))
    }


def _pii_check(event: EventDefinition, hits: dict[str, str]) -> RuleCheck:
    """The PII finding. The demand is the same on every call type — a written reason
    per hit, then an acknowledgment — but only on identify is personal data in the
    right place; anywhere else the reason has to argue otherwise (ADR 0003)."""
    if not hits:
        fields = "traits" if event.call_type != "track" else "property names"
        return RuleCheck(rule="pii", passed=True, detail=f"no PII tokens in {fields}")
    details = "; ".join(f"{name} -> {entry}" for name, entry in hits.items())
    if event.call_type == "identify":
        detail = (
            "personal data on identify: the requester says why each is needed, and "
            f"the approver acknowledges: {details}"
        )
    else:
        where = "a group trait" if event.call_type == "group" else "a track property"
        detail = (
            f"personal data belongs on identify, not on {where}: the requester's "
            f"reason has to argue otherwise, and the approver acknowledges: {details}"
        )
    return RuleCheck(rule="pii", passed=False, detail=detail)


# --- duplicates --------------------------------------------------------------------

# Rules that report a condition without rejecting. A human decides what to do about
# each; only naming, category, and property naming end a request. Mirrored by
# ADVISORY_RULES in frontend/components/RuleChecks.tsx, which paints these with a flag
# rather than the ✕ reserved for a real rejection.
_ADVISORY_RULES = {"pii", "duplicate", "near_duplicate"}

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_SEPARATORS = re.compile(r"[^a-z0-9]+")


def name_tokens(name: str) -> list[str]:
    """Split a name into comparable lowercase tokens, treating separators and camelCase
    boundaries alike, so "Order Completed", "order_completed" and "orderCompleted" all
    give ``["order", "completed"]``. Convention-agnostic on purpose: a profile can set
    either convention, and the comparison has to hold across both."""
    return [t for t in _SEPARATORS.split(_CAMEL_BOUNDARY.sub(" ", name).lower()) if t]


def _singular(token: str) -> str:
    return token[:-1] if token.endswith("s") and not token.endswith("ss") else token


def near_duplicate_of(name: str, known: Collection[str]) -> str | None:
    """Return the known name ``name`` is a near duplicate of, or ``None``.

    Near means the same name written differently: identical tokens once case and
    separators are normalized, or identical once simple plurals are removed. The final
    token — the action verb — must match exactly, because a differing verb is a
    differing event. That condition is what keeps the check usable: character similarity
    rates "Product Reviewed" and "Product Viewed" at 0.93, and they are not the same
    event. Candidates are scanned in sorted order so the reported match is stable.
    """
    tokens = name_tokens(name)
    if not tokens:
        return None
    stemmed = [_singular(t) for t in tokens]
    for candidate in sorted(known):
        if candidate == name:
            continue
        other = name_tokens(candidate)
        if len(other) != len(tokens) or other[-1] != tokens[-1]:
            continue
        if other == tokens or [_singular(t) for t in other] == stemmed:
            return candidate
    return None


# --- evaluation ------------------------------------------------------------------

def _evaluate_traits(
    event: EventDefinition, profile: "GovernanceProfile"
) -> Evaluation:
    """Identify and group definitions. Traits follow the property naming convention,
    and so does a group's type; a failure there rejects, as it does for properties.
    No event-name, category, or duplicate rule applies: the plan has one identify
    call and one call per group type, so a second request adds traits to it rather
    than duplicating it."""
    convention = profile.property_naming.convention
    checks = []
    if event.call_type == "group":
        group_error = property_name_error(
            event.name, convention=convention, kind="group type"
        )
        checks.append(
            RuleCheck(
                rule="group_naming",
                passed=group_error is None,
                detail=group_error or f"group type is {convention}",
            )
        )
    trait_errors = [
        error
        for t in event.traits
        if (error := property_name_error(t.name, convention=convention, kind="trait"))
    ]
    checks.append(
        RuleCheck(
            rule="trait_naming",
            passed=not trait_errors,
            detail="; ".join(trait_errors) or f"all trait names are {convention}",
        )
    )
    hits = pii_hits(event, profile)
    checks.append(_pii_check(event, hits))
    rejected = any(not c.passed for c in checks if c.rule not in _ADVISORY_RULES)
    return Evaluation(
        decision=Decision.rejected if rejected else Decision.pending_approval,
        routed_to_approval=not rejected,
        checks=checks,
        pii_flagged=bool(hits),
        pii_details="; ".join(f"{name} -> {entry}" for name, entry in hits.items()),
        pii_hits=hits,
    )


def _system_events(
    profile: "GovernanceProfile",
) -> tuple[dict[str, SystemEvent], dict[str, str]]:
    """The profile's system events keyed by plan name, and each listed equivalent name
    mapped to the plan name it means, all written in the profile's convention. Empty
    when the profile names no platform (ADR 0009)."""
    convention = profile.event_naming.convention
    by_plan_name = plan_named_events(profile.platform, convention)
    equivalents = {
        render_plan_name(name, convention): plan_name
        for plan_name, event in by_plan_name.items()
        for name in event.equivalents
    }
    return by_plan_name, equivalents


def _sent(event: SystemEvent) -> str:
    return f"sent as {event.sent_as} by {event.sent_by}"


def evaluate(
    event: EventDefinition,
    profile: "GovernanceProfile | None" = None,
    *,
    request_kind: str | None = None,
    existing_event: str | None = None,
) -> Evaluation:
    """Run all deterministic rules over a parsed definition and return a decision.

    Returns a structured per-rule report. A failure on a hard rule (naming, category,
    property naming) rejects. The rest are advisory: they report a condition and route
    to a human rather than ending the request.

    PII is advisory — a flagged definition still routes to approval, where a human must
    acknowledge it. So are both duplicate rules. ``duplicate`` fails when the name is
    already in the plan character for character; ``near_duplicate`` fails when the name
    is one a plan event already uses, written differently (see
    :func:`near_duplicate_of`). Either flags and routes as ``flagged_duplicate``; an
    exact match suppresses the near flag, being the stronger claim about the same
    collision. Both checks are always emitted, whatever they found — silence would look
    the same as the check not running. A clean, novel definition routes as
    ``pending_approval``.

    ``request_kind`` and ``existing_event`` qualify the duplicate checks: a
    ``new_property_on_existing`` request drafts against the event it names, so its
    name matching ``existing_event`` is expected, recorded as a passing ``duplicate``
    check rather than flagged. A match against any other plan event still flags.

    ``profile`` configures the rules; ``None`` resolves to ``DEFAULT_PROFILE``, which
    reproduces the constants above. (The default is ``None`` rather than the profile
    object itself because ``governance`` imports this module's constants — importing
    it back at module level would be circular.)
    """
    from .governance import DEFAULT_PROFILE

    if profile is None:
        profile = DEFAULT_PROFILE

    if event.call_type != "track":
        return _evaluate_traits(event, profile)

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
    prop_errors = [
        error
        for p in event.properties
        if (error := property_name_error(p.name, convention=prop_convention))
    ]
    checks.append(
        RuleCheck(
            rule="property_naming",
            passed=not prop_errors,
            detail=(
                "; ".join(prop_errors)
                if prop_errors
                else f"all property names are {prop_convention}"
            ),
        )
    )

    hits = pii_hits(event, profile)
    pii_flagged = bool(hits)
    pii_details = "; ".join(f"{name} -> {entry}" for name, entry in hits.items())
    checks.append(_pii_check(event, hits))

    # PII does not reject; only the naming, category, and property-naming rules do.
    # The duplicate rules are appended below and are advisory for the same reason, so
    # the exclusion is a set rather than a single name.
    hard_failed = any(not c.passed for c in checks if c.rule not in _ADVISORY_RULES)

    # A property request drafts against the event it names, so its name matching
    # that event is expected, not a duplicate.
    expected_match = (
        request_kind == "new_property_on_existing"
        and existing_event is not None
        and event.name.strip() == existing_event.strip()
    )
    system_events, system_equivalents = _system_events(profile)
    corpus = known_event_names() | system_events.keys()
    exact_match = not hard_failed and not expected_match and event.name in corpus
    # Both duplicate checks are always recorded, whatever they found: silence would
    # look the same as the check not running.
    if hard_failed:
        duplicate_detail = "not checked: the definition was rejected before this rule"
    elif expected_match:
        duplicate_detail = (
            f"'{event.name}' matches the event this property is being "
            "added to; expected, not a duplicate"
        )
    elif exact_match and event.name in system_events:
        duplicate_detail = (
            f"'{event.name}' is a system event, "
            f"{_sent(system_events[event.name])}"
        )
    elif exact_match:
        duplicate_detail = f"'{event.name}' already exists in the tracking plan"
    else:
        duplicate_detail = f"'{event.name}' is not already in the tracking plan"
    checks.append(
        RuleCheck(rule="duplicate", passed=not exact_match, detail=duplicate_detail)
    )

    near_match = (
        near_duplicate_of(event.name, corpus)
        if not hard_failed and not expected_match and not exact_match
        else None
    )
    # A listed equivalent differs in words, not spelling, so normalization cannot
    # find it; the platform file names it instead.
    checked = not hard_failed and not expected_match and not exact_match
    if near_match is None and checked:
        equivalent = (
            event.name
            if event.name in system_equivalents
            else near_duplicate_of(event.name, system_equivalents.keys())
        )
        if equivalent is not None:
            near_match = system_equivalents[equivalent]
    if hard_failed:
        near_detail = "not checked: the definition was rejected before this rule"
    elif expected_match or exact_match:
        near_detail = "not checked: an exact match already answers the question"
    elif near_match in system_events:
        near_detail = (
            f"'{event.name}' means the same as the system event '{near_match}', "
            f"{_sent(system_events[near_match])}"
        )
    elif near_match:
        near_detail = (
            f"'{event.name}' is the same name as '{near_match}' written differently"
        )
    else:
        near_detail = "no near duplicate in the tracking plan"
    checks.append(
        RuleCheck(rule="near_duplicate", passed=near_match is None, detail=near_detail)
    )

    # An exact match suppresses the near flag: it is the stronger claim about the
    # same collision, and two flags would describe one problem.
    if exact_match:
        flags = [f"'{event.name}' already exists in the tracking plan"]
    elif near_match:
        flags = [
            f"'{event.name}' is the same name as '{near_match}', which already "
            "exists in the tracking plan"
        ]
    else:
        flags = []
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
        pii_hits=hits,
    )
