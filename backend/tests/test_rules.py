"""Unit tests for the deterministic governance rules: event naming (including
acronyms), property naming, PII token matching, category membership, duplicate
detection, and the combined evaluate() decision."""

import pytest

from app.models import Decision, EventDefinition
from app.rules import evaluate, event_name_error, pii_hit, property_name_error


def _event(name="Cart Cleared", category="Core Ordering", properties=("cart_id",)):
    return EventDefinition(
        name=name,
        category=category,
        description="d",
        properties=[{"name": p, "type": "string"} for p in properties],
    )


# --- event naming ----------------------------------------------------------------

@pytest.mark.parametrize(
    "name",
    [
        "Cart Cleared",
        "Order Completed",
        "Product Added to Wishlist",
        "Wishlist Product Added to Cart",
        "Payment Made",           # irregular past tense
        "SKU Added",              # all-caps acronym as the object
        "URL Clicked",
        "Coupon QR Scanned",      # acronym mid-name
        "Newsletter Signed Up",   # phrasal verb: particle shifts the verb left
        "User Opted In",
        "Cart Checked Out",
        "Wishlist Product Checked Out to Cart",  # particle before a connector
    ],
)
def test_valid_event_names(name):
    assert event_name_error(name) is None


@pytest.mark.parametrize(
    "name, fragment",
    [
        ("add_to_cart", "underscores"),
        ("Added", "at least two words"),
        ("addToCart", "at least two words"),
        ("Cart cleared", "Title Case"),
        ("cart Cleared", "Title Case"),
        ("SkU Added", "Title Case"),               # mixed-case junk is not an acronym
        ("Cart  Cleared", "single-spaced"),
        (" Cart Cleared", "single-spaced"),
        ("Cart Cleared ", "single-spaced"),
        ("to Cart Added", "cannot start or end"),
        ("Product Added to", "cannot start or end"),
        ("Product Added To Wishlist", "must be lowercase"),
        ("Cart Clear", "past tense"),
        ("Product Add to Wishlist", "past tense"),  # verb sits before the connector
        ("Product SKU", "past tense"),              # acronym can't stand in for the verb
        ("Newsletter Up", "past tense"),            # particle with no verb before it
        ("Newsletter Sign Up", "past tense"),
        ("Newsletter Signed up", "Title Case"),     # particles must be Title Case
    ],
)
def test_invalid_event_names(name, fragment):
    error = event_name_error(name)
    assert error is not None and fragment in error


# --- property naming -------------------------------------------------------------

@pytest.mark.parametrize("name", ["cart_id", "total", "image_url", "line_item_count"])
def test_valid_property_names(name):
    assert property_name_error(name) is None


@pytest.mark.parametrize("name", ["cartId", "Cart", "cart id", "cart__id", "_cart"])
def test_invalid_property_names(name):
    assert property_name_error(name) is not None


# --- PII token matching ----------------------------------------------------------

@pytest.mark.parametrize(
    "name, expected",
    [
        ("email", "email"),
        ("user_email", "email"),               # single token matches anywhere
        ("shipping_address", "address"),
        ("first_name", "first_name"),
        ("credit_card", "credit_card"),
        ("credit_card_last4", "credit_card"),  # contiguous subsequence
        ("name", None),                        # bare product name is fine
        ("username", None),                    # tokens, never substrings
        ("card_credit", None),                 # order matters for multi-token entries
        ("credit_limit_card", None),           # must be contiguous
    ],
)
def test_pii_hit(name, expected):
    assert pii_hit(name) == expected


# --- evaluate --------------------------------------------------------------------

def _check(evaluation, rule):
    return next(c for c in evaluation.checks if c.rule == rule)


def test_clean_novel_event_routes_to_approval():
    evaluation = evaluate(_event())
    assert evaluation.decision == Decision.pending_approval
    assert evaluation.routed_to_approval is True
    assert all(c.passed for c in evaluation.checks)
    assert evaluation.flags == []
    assert evaluation.pii_flagged is False


def test_bad_event_name_rejects():
    evaluation = evaluate(_event(name="add_to_cart"))
    assert evaluation.decision == Decision.rejected
    assert evaluation.routed_to_approval is False
    assert not _check(evaluation, "event_naming").passed


def test_unknown_category_rejects():
    evaluation = evaluate(_event(category="Made Up"))
    assert evaluation.decision == Decision.rejected
    assert not _check(evaluation, "category").passed


def test_bad_property_name_rejects():
    evaluation = evaluate(_event(properties=("cartId",)))
    assert evaluation.decision == Decision.rejected
    assert "cartId" in _check(evaluation, "property_naming").detail


def test_pii_flags_but_still_routes():
    evaluation = evaluate(_event(name="Newsletter Subscribed", properties=("email",)))
    assert evaluation.decision == Decision.pending_approval
    assert evaluation.routed_to_approval is True
    assert evaluation.pii_flagged is True
    assert evaluation.pii_details == "email -> email"
    assert not _check(evaluation, "pii").passed


def test_hard_failure_beats_pii_flag():
    evaluation = evaluate(_event(name="add_to_cart", properties=("email",)))
    assert evaluation.decision == Decision.rejected
    assert evaluation.routed_to_approval is False


def test_duplicate_name_is_flagged_and_routed():
    evaluation = evaluate(_event(name="Product Added", properties=("product_id",)))
    assert evaluation.decision == Decision.flagged_duplicate
    assert evaluation.routed_to_approval is True
    assert evaluation.flags == ["'Product Added' already exists in the tracking plan"]
