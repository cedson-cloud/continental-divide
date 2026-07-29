"""The requester confirmation step.

Model-path intake holds a non-rejected request at ``draft``; submitting it recovers
the routed decision from the ``routed`` audit entry and moves it into the approval
queue. The model-free paths (/requests/raw and offline ingest) keep routing straight
to their decision. Interpreters and duplicate reviews are stubs throughout — nothing
here makes a live call.
"""

import json
from pathlib import Path

import pytest

from app.catalog import DuplicateReview, ReviewFinding
from app.interpreter import Interpretation
from app.pipeline import (
    DECIDABLE_STATUSES,
    DuplicateNoteRequired,
    InvalidTransition,
    decide,
    ingest,
    interpret_intake,
    submit_request,
)
from app.publisher import get_publisher

MODEL = "claude-sonnet-4-6"
CLEAN_EXAMPLE = Path(__file__).parents[1] / "examples" / "clean_cart_cleared.json"

BOOKMARKED = {
    "name": "Product Bookmarked",
    "category": "Wishlisting",
    "description": "User bookmarked a product to revisit later.",
    "properties": [{"name": "product_id", "type": "string", "required": True}],
}

# An exact name from the sample plan, so the deterministic duplicate rule routes it
# to flagged_duplicate rather than pending_approval.
WISHLISTED = {
    "name": "Product Added to Wishlist",
    "category": "Wishlisting",
    "description": "User added a product to their wishlist.",
    "properties": [{"name": "product_id", "type": "string", "required": True}],
}

DUPLICATE_FINDING = ReviewFinding(
    kind="duplicate_event",
    existing_event="Product Added to Wishlist",
    category="Wishlisting",
    reason="Both fire when a shopper saves a product for later.",
    confidence="high",
)

EXTENSION_FINDING = ReviewFinding(
    kind="property_extension",
    existing_event="Product Added to Wishlist",
    category="Wishlisting",
    property_names=["product_id"],
    reason=(
        "Bookmarking detail could live on the existing wishlist event rather than "
        "a new one."
    ),
    confidence="medium",
)


def stub_interpret(_raw, **_):
    return Interpretation(MODEL, BOOKMARKED, json.dumps(BOOKMARKED), None)


def stub_interpret_wishlisted(_raw, **_):
    return Interpretation(MODEL, WISHLISTED, json.dumps(WISHLISTED), None)


def stub_duplicate_finding(_definition, **_):
    return DuplicateReview(MODEL, [DUPLICATE_FINDING], '{"findings": [...]}')


def stub_extension_finding(_definition, **_):
    return DuplicateReview(MODEL, [EXTENSION_FINDING], '{"findings": [...]}')


def stub_no_findings(_definition, **_):
    return DuplicateReview(MODEL)


def _steps(storage, request_id):
    return [entry["step"] for entry in storage.get_audit_log(request_id)]


def _draft(storage, duplicate_fn=stub_no_findings):
    return interpret_intake(
        "track when a shopper bookmarks a product",
        storage,
        interpret_fn=stub_interpret,
        duplicate_fn=duplicate_fn,
    )


def test_model_free_raw_path_never_produces_a_draft(client, storage):
    candidate = json.loads(CLEAN_EXAMPLE.read_text())

    response = client.post(
        "/requests/raw",
        json={"definition": candidate, "business_value": "measures cart abandonment"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending_approval"
    assert "submitted" not in _steps(storage, response.json()["id"])

    # The offline ingest path (run_examples.py) routes straight to its decision too.
    rid = ingest("cart cleared", candidate, storage)
    assert storage.get_request(rid)["status"] == "pending_approval"
    assert "submitted" not in _steps(storage, rid)


def test_submit_with_a_duplicate_finding_and_no_note_is_refused(client, storage):
    rid = _draft(storage, duplicate_fn=stub_duplicate_finding)
    assert storage.get_request(rid)["duplicate_candidates"] == [
        DUPLICATE_FINDING.model_dump()
    ]

    with pytest.raises(DuplicateNoteRequired):
        submit_request(rid, storage)

    response = client.post(f"/requests/{rid}/submit", json={})
    assert response.status_code == 422
    assert storage.get_request(rid)["status"] == "draft"

    response = client.post(
        f"/requests/{rid}/submit",
        json={"duplicate_note": "bookmarking is a distinct behavior"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending_approval"

    submitted = next(
        e for e in storage.get_audit_log(rid) if e["step"] == "submitted"
    )
    assert submitted["detail"]["duplicate_note"] == "bookmarking is a distinct behavior"


def test_property_extension_finding_alone_needs_no_duplicate_note(client, storage):
    # A property-extension finding is information, not an accusation: the requester
    # is not asked to argue their draft is not a duplicate, because nothing said it was.
    rid = _draft(storage, duplicate_fn=stub_extension_finding)
    assert storage.get_request(rid)["duplicate_candidates"] == [
        EXTENSION_FINDING.model_dump()
    ]

    response = client.post(f"/requests/{rid}/submit", json={})
    assert response.status_code == 200
    assert response.json()["status"] == "pending_approval"


def test_draft_is_never_decidable(client, storage):
    assert "draft" not in DECIDABLE_STATUSES

    rid = _draft(storage)
    with pytest.raises(InvalidTransition):
        decide(rid, "approve", storage, get_publisher())

    response = client.post(f"/requests/{rid}/decision", json={"decision": "approve"})
    assert response.status_code == 409
    assert storage.get_request(rid)["status"] == "draft"


def test_submitting_a_non_draft_is_refused(client, storage):
    candidate = json.loads(CLEAN_EXAMPLE.read_text())
    rid = client.post(
        "/requests/raw",
        json={"definition": candidate, "business_value": "measures cart abandonment"},
    ).json()["id"]

    response = client.post(f"/requests/{rid}/submit", json={})
    assert response.status_code == 409
    assert "cannot be submitted" in response.json()["detail"]
    assert client.post("/requests/9999/submit", json={}).status_code == 404


def test_queue_listing_excludes_drafts_until_submitted(client, storage):
    rid = _draft(storage)

    assert rid not in [row["id"] for row in client.get("/requests").json()]
    detail = client.get(f"/requests/{rid}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "draft"

    submit_request(rid, storage)
    assert rid in [row["id"] for row in client.get("/requests").json()]


def test_submit_recovers_the_routed_decision(storage):
    rid = interpret_intake(
        "track when a shopper wishlists a product",
        storage,
        interpret_fn=stub_interpret_wishlisted,
        duplicate_fn=stub_no_findings,
    )
    assert storage.get_request(rid)["status"] == "draft"
    routed = next(e for e in storage.get_audit_log(rid) if e["step"] == "routed")
    assert routed["detail"]["decision"] == "flagged_duplicate"

    submit_request(rid, storage)
    request = storage.get_request(rid)
    assert request["status"] == "flagged_duplicate"
    submitted = next(e for e in storage.get_audit_log(rid) if e["step"] == "submitted")
    assert submitted["detail"]["decision"] == "flagged_duplicate"


def test_notion_push_happens_at_submission_not_routing(storage, monkeypatch):
    pushed = []
    monkeypatch.setattr(
        "app.pipeline.push_request", lambda request: pushed.append(request["id"]) or None
    )

    rid = _draft(storage)
    assert pushed == []

    submit_request(rid, storage)
    assert pushed == [rid]
