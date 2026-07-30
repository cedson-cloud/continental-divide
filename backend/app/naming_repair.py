"""Deterministic repair suggestions for an event name the convention rejected.

A naming rejection is the one outcome the requester cannot act on: the tool drafted
the name, the rule refused it, and nothing in the trail offered a way forward. This
module closes that gap without loosening the rule — it proposes names that the *same*
rule accepts.

Two constraints shape everything here.

**No model call, ever.** ``interpreter.py`` is explicitly instructed to capture the
requester's intent faithfully and never to rename an event so it passes a rule; a
model-generated suggestion would contradict that instruction and add spend to a path
that needs none. This is pure string work over the active governance profile.

**The real rule is the only judge.** Candidates are derived structurally from the
convention's own shape — not by parsing the error message — and every one of them is
then re-run through :func:`rules.event_name_error` under the caller's profile.
Anything that still fails is dropped. That gate is the point of the function: the
Title-Case repair of ``"Item Saved for Later"`` is ``"Item Saved For Later"``, which
fails a *second* rule on tense, and a fixer without the gate would hand the requester
that name and a fresh rejection. In that case the honest answer is an empty list.
"""

from __future__ import annotations

import itertools
import re
from typing import TYPE_CHECKING

from .rules import event_name_error

if TYPE_CHECKING:
    from .governance import GovernanceProfile

# The most candidates worth putting in front of a requester. More than a few reads as
# a machine guessing rather than a convention with an answer.
MAX_SUGGESTIONS = 3

# Bound on the pre-gate combination space. Repairs are per-word and most names have
# one offending word, so this is a runaway guard, not a real limit.
_MAX_COMBINATIONS = 64

# A name arrives as whitespace- or underscore-separated words regardless of which
# convention it was drafted under: the convention decides how the words are re-joined.
_WORD_SPLIT = re.compile(r"[\s_]+")

_TITLE_WORD = re.compile(r"^[A-Z](?:[a-z0-9]*|[A-Z0-9]+)$")
_SNAKE_TOKEN = re.compile(r"^[a-z0-9]+$")


def _title_word_forms(word: str) -> list[str]:
    """Title-Cased forms of a word that is not in Title Case. ``capitalize()`` and an
    upper-first splice differ on words with interior capitals — ``"iPhone"`` becomes
    ``"Iphone"`` under one and ``"IPhone"`` under the other — so both are offered and
    the rule decides."""
    forms = [word.capitalize(), word[0].upper() + word[1:]]
    return list(dict.fromkeys(f for f in forms if f))


def _word_candidates(word: str, connectors: set[str], convention: str) -> list[str]:
    """The forms of one word worth trying, most-likely first. A word already in the
    shape the convention wants is returned unchanged — repair is per-word, so a
    compliant acronym is never flattened on the way to fixing its neighbour."""
    if convention == "snake_case_object_action":
        if _SNAKE_TOKEN.match(word):
            return [word]
        return [word.lower()]

    # title_case_object_action
    if word in connectors:
        return [word]
    if word.lower() in connectors:
        # A connector in the wrong case: the convention wants it lowercase.
        return [word.lower()]
    if _TITLE_WORD.match(word):
        return [word]
    return _title_word_forms(word)


def suggest_compliant_names(
    name: str, *, profile: "GovernanceProfile"
) -> list[str]:
    """Names that satisfy ``profile``'s event-naming convention and stay as close to
    ``name`` as the convention allows.

    Deterministic, model-free, and gated: every returned candidate has been run back
    through :func:`rules.event_name_error` under ``profile`` and returned ``None``.
    An empty list is a valid and expected answer — it means no purely structural
    repair of this name passes, and the requester needs a different name or a
    different rule, not a second rejection.

    At most :data:`MAX_SUGGESTIONS` names, in a stable order.
    """
    naming = profile.event_naming
    connectors = set(naming.connectors)
    words = [w for w in _WORD_SPLIT.split(name.strip()) if w]
    if not words:
        return []

    joiner = "_" if naming.convention == "snake_case_object_action" else " "
    per_word = [_word_candidates(w, connectors, naming.convention) for w in words]

    if _combinations(per_word) > _MAX_COMBINATIONS:
        # Fall back to the single most-likely repair of every word rather than
        # enumerating; still gated below like any other candidate.
        combinations = [tuple(forms[0] for forms in per_word)]
    else:
        combinations = list(itertools.product(*per_word))

    accepted: list[str] = []
    for combination in combinations:
        candidate = joiner.join(combination)
        if candidate == name or candidate in accepted:
            continue
        if (
            event_name_error(
                candidate,
                convention=naming.convention,
                connectors=naming.connectors,
                particles=naming.particles,
                irregular_past=naming.irregular_past,
            )
            is not None
        ):
            continue
        accepted.append(candidate)
        if len(accepted) == MAX_SUGGESTIONS:
            break
    return accepted


def _combinations(per_word: list[list[str]]) -> int:
    total = 1
    for forms in per_word:
        total *= len(forms)
    return total
