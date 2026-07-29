"""Catalog evidence on findings, derived at read time.

A finding names an existing event the requester has likely never seen, so the
request response joins each stored finding against the catalog and attaches that
event's own description and full property list. The join lives in the response
layer only: the stored finding stays the model's output, keeping the seam between
engine-derived fact and model inference, and the evidence follows the catalog if
the catalog changes. Interpreters and duplicate reviews are stubs throughout —
nothing here makes a live call.
"""

import json

from app.catalog import DuplicateReview, ReviewFinding, catalog_entries
from app.interpreter import Interpretation
from app.pipeline import interpret_intake

MODEL = "claude-sonnet-4-6"
TARGET_EVENT = "Product Added to Wishlist"

BOOKMARKED = {
    "name": "Product Bookmarked",
    "category": "Wishlisting",
    "description": "User bookmarked a product to revisit later.",
    "properties": [{"name": "product_id", "type": "string", "required": True}],
}

DUPLICATE_FINDING = ReviewFinding(
    kind="duplicate_event",
    existing_event=TARGET_EVENT,
    category="Wishlisting",
    reason="Both fire when a shopper saves a product for later.",
    confidence="high",
)

UNKNOWN_EVENT_FINDING = ReviewFinding(
    kind="duplicate_event",
    existing_event="Event Not In The Catalog",
    category="Wishlisting",
    reason="Names an event the catalog does not hold.",
    confidence="low",
)


def stub_interpret(_raw, **_):
    return Interpretation(MODEL, BOOKMARKED, json.dumps(BOOKMARKED), None)


def stub_findings(_definition, **_):
    return DuplicateReview(
        MODEL, [DUPLICATE_FINDING, UNKNOWN_EVENT_FINDING], '{"findings": [...]}'
    )


def _draft(storage):
    return interpret_intake(
        "track when a shopper bookmarks a product",
        storage,
        interpret_fn=stub_interpret,
        duplicate_fn=stub_findings,
    )


def test_the_response_carries_the_catalog_description_and_full_property_list(
    client, storage
):
    rid = _draft(storage)
    findings = client.get(f"/requests/{rid}").json()["duplicate_candidates"]

    entry = next(e for e in catalog_entries() if e.name == TARGET_EVENT)
    matched = next(f for f in findings if f["existing_event"] == TARGET_EVENT)
    assert matched["existing_event_description"] == entry.description
    assert matched["existing_event_properties"] == entry.property_names
    assert len(matched["existing_event_properties"]) > 1
    # The model's own fields ride along untouched; property_names keeps meaning
    # the properties at issue, not the catalog's list.
    assert matched["reason"] == DUPLICATE_FINDING.reason
    assert matched["property_names"] == []

    unknown = next(
        f for f in findings if f["existing_event"] == "Event Not In The Catalog"
    )
    assert unknown["existing_event_description"] is None
    assert unknown["existing_event_properties"] == []


def test_the_stored_finding_does_not_carry_the_catalog_evidence(storage):
    rid = _draft(storage)

    for finding in storage.get_request(rid)["duplicate_candidates"]:
        assert "existing_event_description" not in finding
        assert "existing_event_properties" not in finding
    assert "existing_event_description" not in ReviewFinding.model_fields
    assert "existing_event_properties" not in ReviewFinding.model_fields
