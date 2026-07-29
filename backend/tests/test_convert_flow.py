"""Converting a draft into a property-on-an-existing-event request.

The requester reads a ``property_extension`` or ``property_already_exists`` finding,
agrees with it, and converts. The original draft is never mutated: it is marked
``superseded`` and a NEW request re-enters model intake with the original's fields,
drafts, gets its own catalog review, and lands at ``draft`` for its own
confirmation. Interpreters and duplicate reviews are stubs throughout — nothing
here makes a live call.
"""

import json
from functools import partial

import pytest

from app.catalog import DuplicateReview, ReviewFinding
from app.interpreter import Interpretation
from app.pipeline import (
    DECIDABLE_STATUSES,
    InvalidTransition,
    NoMatchingFinding,
    RequestNotFound,
    convert_to_property_request,
    decide,
    interpret_intake,
    submit_request,
)
from app.publisher import get_publisher
from app.rate_limit import RateLimiter

MODEL = "claude-sonnet-4-6"
TARGET_EVENT = "Product Added to Wishlist"

BOOKMARKED = {
    "name": "Product Bookmarked",
    "category": "Wishlisting",
    "description": "User bookmarked a product to revisit later.",
    "properties": [{"name": "bookmark_source", "type": "string", "required": True}],
}

# What the model drafts on the second pass, once the request is a property addition.
WISHLIST_ADDITION = {
    "name": TARGET_EVENT,
    "category": "Wishlisting",
    "description": "Adds bookmark detail to the existing wishlist event.",
    "properties": [{"name": "bookmark_source", "type": "string", "required": True}],
}

EXTENSION_FINDING = ReviewFinding(
    kind="property_extension",
    existing_event=TARGET_EVENT,
    category="Wishlisting",
    property_names=["bookmark_source"],
    reason=(
        "Bookmarking detail could live on the existing wishlist event rather than "
        "a new one."
    ),
    confidence="medium",
)

DUPLICATE_FINDING = ReviewFinding(
    kind="duplicate_event",
    existing_event=TARGET_EVENT,
    category="Wishlisting",
    reason="Both fire when a shopper saves a product for later.",
    confidence="high",
)


def stub_interpret(_raw, **_):
    return Interpretation(MODEL, BOOKMARKED, json.dumps(BOOKMARKED), None)


def stub_interpret_addition(_raw, **_):
    return Interpretation(MODEL, WISHLIST_ADDITION, json.dumps(WISHLIST_ADDITION), None)


def stub_extension_finding(_definition, **_):
    return DuplicateReview(MODEL, [EXTENSION_FINDING], '{"findings": [...]}')


def stub_duplicate_finding(_definition, **_):
    return DuplicateReview(MODEL, [DUPLICATE_FINDING], '{"findings": [...]}')


def stub_no_findings(_definition, **_):
    return DuplicateReview(MODEL)


def _steps(storage, request_id):
    return [entry["step"] for entry in storage.get_audit_log(request_id)]


def _draft(storage, duplicate_fn=stub_extension_finding):
    return interpret_intake(
        "track when a shopper bookmarks a product",
        storage,
        interpret_fn=stub_interpret,
        duplicate_fn=duplicate_fn,
        submitter_name="Sam",
        submitter_team="Product",
        call_type="track",
        side="Client",
        business_value="find out where bookmarking happens",
        needed_by="2026-08-15",
        destinations=["Amplitude"],
    )


def _convert(storage, rid, existing_event=TARGET_EVENT):
    return convert_to_property_request(
        rid,
        existing_event,
        storage,
        interpret_fn=stub_interpret_addition,
        duplicate_fn=stub_no_findings,
    )


def test_convert_creates_a_new_draft_carrying_the_original_intake(storage):
    rid = _draft(storage)
    nid = _convert(storage, rid)
    assert nid != rid

    new = storage.get_request(nid)
    assert new["status"] == "draft"
    assert new["raw_intake_text"] == "track when a shopper bookmarks a product"
    assert new["submitter_name"] == "Sam"
    assert new["submitter_team"] == "Product"
    assert new["call_type"] == "track"
    assert new["side"] == "Client"
    assert new["business_value"] == "find out where bookmarking happens"
    assert new["needed_by"] == "2026-08-15"
    assert new["destinations"] == ["Amplitude"]
    assert new["request_kind"] == "new_property_on_existing"
    assert new["existing_event"] == TARGET_EVENT

    # The new request went through full intake, including its own catalog review,
    # and the trail is navigable from both ends.
    new_steps = _steps(storage, nid)
    for step in ("intake_received", "model_interpreted", "duplicate_review"):
        assert step in new_steps
    supersedes = next(
        e for e in storage.get_audit_log(nid) if e["step"] == "supersedes"
    )
    assert supersedes["detail"] == {
        "original_request_id": rid,
        "existing_event": TARGET_EVENT,
    }
    superseded_by = next(
        e for e in storage.get_audit_log(rid) if e["step"] == "superseded_by"
    )
    assert superseded_by["detail"] == {
        "new_request_id": nid,
        "existing_event": TARGET_EVENT,
    }

    # The new draft is a normal draft: the requester still confirms it. Named after
    # an event already in the plan, the mechanical duplicate rule flags it — the
    # point here is that submission moves it into the approval queue.
    submit_request(nid, storage)
    assert storage.get_request(nid)["status"] in DECIDABLE_STATUSES


def test_original_ends_superseded_not_decidable_and_absent_from_queue(client, storage):
    assert "superseded" not in DECIDABLE_STATUSES

    rid = _draft(storage)
    nid = _convert(storage, rid)
    assert storage.get_request(rid)["status"] == "superseded"

    with pytest.raises(InvalidTransition):
        decide(rid, "approve", storage, get_publisher())
    assert client.post(f"/requests/{rid}/decision", json={"decision": "approve"}).status_code == 409
    with pytest.raises(InvalidTransition):
        submit_request(rid, storage)

    submit_request(nid, storage)
    listed = [row["id"] for row in client.get("/requests").json()]
    assert nid in listed
    assert rid not in listed

    detail = client.get(f"/requests/{rid}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "superseded"


def test_convert_refused_when_no_finding_names_the_event(client, storage):
    # No findings at all.
    rid = _draft(storage, duplicate_fn=stub_no_findings)
    with pytest.raises(NoMatchingFinding):
        _convert(storage, rid)

    # A duplicate_event finding names the event, but it is the wrong kind.
    rid = _draft(storage, duplicate_fn=stub_duplicate_finding)
    with pytest.raises(NoMatchingFinding):
        _convert(storage, rid)

    # A property finding exists, but the caller names a different event.
    rid = _draft(storage)
    with pytest.raises(NoMatchingFinding):
        _convert(storage, rid, existing_event="Order Completed")

    response = client.post(
        f"/requests/{rid}/convert", json={"existing_event": "Order Completed"}
    )
    assert response.status_code == 422
    assert storage.get_request(rid)["status"] == "draft"


def test_convert_refused_unless_draft(client, storage):
    with pytest.raises(RequestNotFound):
        convert_to_property_request(9999, TARGET_EVENT, storage)
    assert (
        client.post("/requests/9999/convert", json={"existing_event": TARGET_EVENT})
        .status_code
        == 404
    )

    rid = _draft(storage)
    submit_request(rid, storage)
    with pytest.raises(InvalidTransition):
        _convert(storage, rid)
    response = client.post(
        f"/requests/{rid}/convert", json={"existing_event": TARGET_EVENT}
    )
    assert response.status_code == 409
    assert "cannot be converted" in response.json()["detail"]

    # A superseded original cannot be converted a second time.
    rid = _draft(storage)
    _convert(storage, rid)
    with pytest.raises(InvalidTransition):
        _convert(storage, rid)


def test_convert_shares_the_intake_rate_limiter(client, storage, monkeypatch):
    rid = _draft(storage)
    monkeypatch.setattr(
        "app.routes.convert_to_property_request",
        partial(
            convert_to_property_request,
            interpret_fn=stub_interpret_addition,
            duplicate_fn=stub_no_findings,
        ),
    )
    monkeypatch.setattr("app.routes._limiter", RateLimiter(1, 60))

    response = client.post(
        f"/requests/{rid}/convert", json={"existing_event": TARGET_EVENT}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "draft"

    # The single allowed hit is spent, and it gates plain intake and convert alike.
    intake = client.post(
        "/requests",
        json={
            "raw_intake_text": "track something",
            "business_value": "curiosity",
            "submitter_name": "Ada",
            "submitter_team": "Product",
        },
    )
    assert intake.status_code == 429
    response = client.post(
        f"/requests/{rid}/convert", json={"existing_event": TARGET_EVENT}
    )
    assert response.status_code == 429
