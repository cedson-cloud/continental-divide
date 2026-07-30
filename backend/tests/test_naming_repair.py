"""Deterministic repair of a name the convention rejected.

The claim under test is narrow and total: every name this module hands a requester is
a name the real rule accepts. Nothing here calls a model, and the profiles are pinned
to templates rather than ``active.yaml`` so flipping the active profile cannot
silently rewrite these expectations.
"""

from pathlib import Path

import pytest

from app.governance import load_profile
from app.naming_repair import MAX_SUGGESTIONS, suggest_compliant_names
from app.rules import event_name_error

TEMPLATES = Path(__file__).parents[2] / "governance" / "templates"


@pytest.fixture(scope="module")
def title_case():
    return load_profile(TEMPLATES / "segment-ecommerce.yaml")


@pytest.fixture(scope="module")
def snake_case():
    return load_profile(TEMPLATES / "posthog-snake-case.yaml")


def _rule_error(name: str, profile) -> str | None:
    naming = profile.event_naming
    return event_name_error(
        name,
        convention=naming.convention,
        connectors=naming.connectors,
        particles=naming.particles,
        irregular_past=naming.irregular_past,
    )


# Names that fail the Title Case convention for structurally different reasons. The
# table exists so the universal gate below is asserted over a spread of inputs rather
# than one lucky case.
FAILING_TITLE_CASE_NAMES = [
    "Back in Stock Alert Requested",   # a preposition inside the noun phrase
    "Item Saved for Later",            # same, but the repair fails a second rule
    "product added",                   # every word lowercase
    "Product Added To Wishlist",       # a connector capitalized
    "sku added",                       # would-be acronym, lowercase
    "iPhone Viewed",                   # interior capital
    "checkout",                        # a single word
    "Cart  Cleared",                   # double-spaced
    "cart_cleared",                    # snake_case under a Title Case profile
]


def test_the_defect_from_request_11_gets_a_compliant_name(title_case):
    # The name the tool drafted itself, and the name its own rule accepts.
    assert _rule_error("Back in Stock Alert Requested", title_case) is not None
    assert suggest_compliant_names(
        "Back in Stock Alert Requested", profile=title_case
    ) == ["Back In Stock Alert Requested"]


@pytest.mark.parametrize("name", FAILING_TITLE_CASE_NAMES)
def test_every_returned_candidate_passes_the_real_rule(name, title_case):
    """The universal gate, asserted generically: whatever the repair produces for any
    of these inputs, the engine accepts it. A candidate is never merely 'closer'."""
    for candidate in suggest_compliant_names(name, profile=title_case):
        assert _rule_error(candidate, title_case) is None, candidate


@pytest.mark.parametrize("name", FAILING_TITLE_CASE_NAMES)
def test_suggestions_are_bounded_and_never_repeat_the_rejected_name(name, title_case):
    candidates = suggest_compliant_names(name, profile=title_case)
    assert len(candidates) <= MAX_SUGGESTIONS
    assert name not in candidates
    assert len(set(candidates)) == len(candidates)


def test_a_repair_that_would_fail_again_is_not_offered(title_case):
    """"Item Saved for Later" Title-cases to "Item Saved For Later", which then fails
    on TENSE. A naive fixer would hand the requester that name and a second
    rejection; the honest answer is nothing."""
    assert _rule_error("Item Saved For Later", title_case) == (
        "action verb 'Later' must be past tense"
    )
    assert suggest_compliant_names("Item Saved for Later", profile=title_case) == []


def test_a_connector_in_the_wrong_case_yields_its_lowercase_form(title_case):
    assert "to" in title_case.event_naming.connectors
    assert suggest_compliant_names(
        "Product Added To Wishlist", profile=title_case
    ) == ["Product Added to Wishlist"]


def test_a_compliant_word_beside_a_broken_one_is_left_alone(title_case):
    # Repair is per-word, so fixing "added" must not flatten the acronym next to it.
    assert suggest_compliant_names("SKU added", profile=title_case) == ["SKU Added"]


@pytest.mark.parametrize(
    "name",
    [
        "Back in Stock Alert Requested",
        "Item Saved for Later",
        "product added",
        "Product Added",
        "back_in_stock_alert_requested",
    ],
)
def test_under_snake_case_candidates_are_snake_case_or_empty(name, snake_case):
    candidates = suggest_compliant_names(name, profile=snake_case)
    for candidate in candidates:
        assert candidate == candidate.lower()
        assert " " not in candidate
        assert _rule_error(candidate, snake_case) is None


def test_the_convention_comes_from_the_profile_not_a_hardcoded_default(
    title_case, snake_case
):
    assert suggest_compliant_names("product added", profile=title_case) == [
        "Product Added"
    ]
    assert suggest_compliant_names("product added", profile=snake_case) == [
        "product_added"
    ]


@pytest.mark.parametrize("name", FAILING_TITLE_CASE_NAMES)
def test_ordering_is_deterministic_across_repeated_calls(name, title_case):
    first = suggest_compliant_names(name, profile=title_case)
    for _ in range(3):
        assert suggest_compliant_names(name, profile=title_case) == first


def test_an_empty_or_whitespace_name_returns_nothing(title_case):
    assert suggest_compliant_names("", profile=title_case) == []
    assert suggest_compliant_names("   ", profile=title_case) == []
