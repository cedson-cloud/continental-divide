"""Withdrawing a draft that duplicates an existing event.

A requester who reads a ``duplicate_event`` finding and agrees with it needs a way
out that is neither fabricating a difference nor abandoning the tab. Withdrawing
ends the draft at ``withdrawn`` — no model call, no Notion push, never decidable,
never in the queue. A requester who cannot tell has a middle door instead:
submitting with ``duplicate_unsure`` passes the question to the approver without a
note. Interpreters and duplicate reviews are stubs throughout — nothing here makes
a live call.
"""

import json

import pytest

from app.catalog import DuplicateReview, ReviewFinding
from app.interpreter import Interpretation
from app.pipeline import (
    DECIDABLE_STATUSES,
    DuplicateNoteRequired,
    InvalidTransition,
    NoMatchingFinding,
    RequestNotFound,
    decide,
    interpret_intake,
    submit_request,
    withdraw_request,
)
from app.publisher import get_publisher

MODEL = "claude-sonnet-4-6"
ACTOR = {"email": "tester@example.com", "method": "local", "verified": False}
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

EXTENSION_FINDING = ReviewFinding(
    kind="property_extension",
    existing_event=TARGET_EVENT,
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


def stub_duplicate_finding(_definition, **_):
    return DuplicateReview(MODEL, [DUPLICATE_FINDING], '{"findings": [...]}')


def stub_extension_finding(_definition, **_):
    return DuplicateReview(MODEL, [EXTENSION_FINDING], '{"findings": [...]}')


def stub_no_findings(_definition, **_):
    return DuplicateReview(MODEL)


def _draft(storage, duplicate_fn=stub_duplicate_finding):
    return interpret_intake(
        "track when a shopper bookmarks a product",
        storage,
        interpret_fn=stub_interpret,
        duplicate_fn=duplicate_fn,
    )


def test_withdraw_from_draft_succeeds_and_lands_withdrawn(client, storage):
    rid = _draft(storage)
    withdraw_request(rid, TARGET_EVENT, "the wishlist event covers this", storage)

    assert storage.get_request(rid)["status"] == "withdrawn"
    withdrawn = next(
        e for e in storage.get_audit_log(rid) if e["step"] == "withdrawn"
    )
    assert withdrawn["detail"] == {
        "existing_event": TARGET_EVENT,
        "reason": "the wishlist event covers this",
        "actor": ACTOR,
    }

    # Over HTTP, and the reason is optional: agreeing needs no essay.
    rid = _draft(storage)
    response = client.post(
        f"/requests/{rid}/withdraw", json={"existing_event": TARGET_EVENT}
    )
    assert response.status_code == 200
    assert response.json() == {"id": rid, "status": "withdrawn"}


def test_withdraw_naming_an_event_no_duplicate_finding_points_at_is_refused(
    client, storage
):
    # No findings at all.
    rid = _draft(storage, duplicate_fn=stub_no_findings)
    with pytest.raises(NoMatchingFinding):
        withdraw_request(rid, TARGET_EVENT, None, storage)

    # A property finding names the event, but it is not a duplicate accusation.
    rid = _draft(storage, duplicate_fn=stub_extension_finding)
    with pytest.raises(NoMatchingFinding):
        withdraw_request(rid, TARGET_EVENT, None, storage)

    # A duplicate finding exists, but the caller names a different event.
    rid = _draft(storage)
    with pytest.raises(NoMatchingFinding):
        withdraw_request(rid, "Order Completed", None, storage)

    response = client.post(
        f"/requests/{rid}/withdraw", json={"existing_event": "Order Completed"}
    )
    assert response.status_code == 422
    assert storage.get_request(rid)["status"] == "draft"


def test_withdraw_from_a_non_draft_status_is_refused(client, storage):
    with pytest.raises(RequestNotFound):
        withdraw_request(9999, TARGET_EVENT, None, storage)
    assert (
        client.post("/requests/9999/withdraw", json={"existing_event": TARGET_EVENT})
        .status_code
        == 404
    )

    rid = _draft(storage)
    submit_request(rid, storage, duplicate_note="bookmarking is distinct")
    with pytest.raises(InvalidTransition):
        withdraw_request(rid, TARGET_EVENT, None, storage)
    response = client.post(
        f"/requests/{rid}/withdraw", json={"existing_event": TARGET_EVENT}
    )
    assert response.status_code == 409
    assert "cannot be withdrawn" in response.json()["detail"]

    # A withdrawn request cannot be withdrawn a second time, or submitted.
    rid = _draft(storage)
    withdraw_request(rid, TARGET_EVENT, None, storage)
    with pytest.raises(InvalidTransition):
        withdraw_request(rid, TARGET_EVENT, None, storage)
    with pytest.raises(InvalidTransition):
        submit_request(rid, storage)


def test_withdraw_makes_no_model_call_and_no_notion_push(storage, monkeypatch):
    rid = _draft(storage)

    def refuse_model_call(*_args, **_kwargs):
        raise AssertionError("withdraw must not call the model")

    pushed = []
    monkeypatch.setattr("app.pipeline.interpret", refuse_model_call)
    monkeypatch.setattr("app.pipeline.review_against_catalog", refuse_model_call)
    monkeypatch.setattr(
        "app.pipeline.push_request", lambda request: pushed.append(request["id"])
    )

    withdraw_request(rid, TARGET_EVENT, None, storage)
    assert storage.get_request(rid)["status"] == "withdrawn"
    assert pushed == []


def test_submit_with_duplicate_unsure_and_no_note_succeeds(client, storage):
    rid = _draft(storage)
    submit_request(rid, storage, duplicate_unsure=True)

    assert storage.get_request(rid)["status"] in DECIDABLE_STATUSES
    submitted = next(
        e for e in storage.get_audit_log(rid) if e["step"] == "submitted"
    )
    assert submitted["detail"]["duplicate_unsure"] is True
    assert "duplicate_note" not in submitted["detail"]

    # Over HTTP, through the submit body field.
    rid = _draft(storage)
    response = client.post(
        f"/requests/{rid}/submit", json={"duplicate_unsure": True}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending_approval"


def test_submit_with_neither_note_nor_unsure_is_still_refused(client, storage):
    rid = _draft(storage)
    with pytest.raises(DuplicateNoteRequired):
        submit_request(rid, storage)

    response = client.post(f"/requests/{rid}/submit", json={})
    assert response.status_code == 422
    assert storage.get_request(rid)["status"] == "draft"


def test_decide_refuses_a_withdrawn_request(client, storage):
    assert "withdrawn" not in DECIDABLE_STATUSES

    rid = _draft(storage)
    withdraw_request(rid, TARGET_EVENT, None, storage)
    with pytest.raises(InvalidTransition):
        decide(rid, "approve", storage, get_publisher())

    response = client.post(f"/requests/{rid}/decision", json={"decision": "approve"})
    assert response.status_code == 409
    assert storage.get_request(rid)["status"] == "withdrawn"


def test_a_withdrawn_request_is_absent_from_the_pending_queue(client, storage):
    rid = _draft(storage)
    withdraw_request(rid, TARGET_EVENT, None, storage)

    assert rid not in [row["id"] for row in client.get("/requests").json()]
    detail = client.get(f"/requests/{rid}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "withdrawn"
