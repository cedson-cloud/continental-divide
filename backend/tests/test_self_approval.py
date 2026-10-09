"""Every approval says whether the approver also requested it (docs/adr/0004, 0010).

The marker is derived from the audit log, never typed: the approver's identity is compared
with the actors who made and submitted the request. In the public demo the visitor holds
every role, so every approval there is marked. Nothing here makes a live model call.
"""

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.catalog import DuplicateReview
from app.identity import Identity
from app.interpreter import Interpretation
from app.pipeline import decide, ingest, interpret_intake, submit_request
from app.publisher import get_publisher

CLEAN_EXAMPLE = Path(__file__).parents[1] / "examples" / "clean_cart_cleared.json"
BOOKMARKED = {
    "name": "Product Bookmarked",
    "category": "Wishlisting",
    "description": "User bookmarked a product to revisit later.",
    "properties": [{"name": "product_id", "type": "string", "required": True}],
}

REQUESTER = Identity(email="requester@example.com", method="local", verified=False)
APPROVER = Identity(email="approver@example.com", method="local", verified=False)


def _decision(storage, request_id: int) -> dict:
    log = storage.get_audit_log(request_id)
    return next(e for e in log if e["step"] == "decision_received")["detail"]


def _raw(storage) -> int:
    return ingest("clear the whole cart", json.loads(CLEAN_EXAMPLE.read_text()), storage)


def _approve(storage, request_id: int) -> None:
    decide(request_id, "approve", storage, get_publisher())


def _draft(storage) -> int:
    return interpret_intake(
        "track when a shopper bookmarks a product",
        storage,
        interpret_fn=lambda _raw, **_: Interpretation(
            "stub", BOOKMARKED, json.dumps(BOOKMARKED), None
        ),
        duplicate_fn=lambda _definition, **_: DuplicateReview("stub", [], "{}"),
    )


def test_approving_your_own_request_is_marked_a_self_approval(storage):
    request_id = _raw(storage)
    _approve(storage, request_id)

    assert _decision(storage, request_id)["self_approval"] is True


def test_approving_someone_elses_request_is_not(storage):
    request_id = _raw(storage.acting_as(REQUESTER))
    _approve(storage.acting_as(APPROVER), request_id)

    assert _decision(storage, request_id)["self_approval"] is False


def test_the_same_email_in_another_case_is_the_same_person(storage):
    request_id = _raw(storage.acting_as(REQUESTER))
    shouted = Identity(email="Requester@Example.com", method="local", verified=False)
    _approve(storage.acting_as(shouted), request_id)

    assert _decision(storage, request_id)["self_approval"] is True


def test_whoever_submitted_the_draft_is_a_requester_too(storage):
    request_id = _draft(storage.acting_as(REQUESTER))
    submit_request(request_id, storage.acting_as(APPROVER))
    _approve(storage.acting_as(APPROVER), request_id)

    assert _decision(storage, request_id)["self_approval"] is True


def test_whoever_drafted_it_is_a_requester_even_when_someone_else_submitted(storage):
    request_id = _draft(storage.acting_as(REQUESTER))
    submit_request(request_id, storage.acting_as(APPROVER))
    _approve(storage.acting_as(REQUESTER), request_id)

    assert _decision(storage, request_id)["self_approval"] is True


def test_with_no_recorded_requester_the_marker_says_unknown_not_false(storage):
    request_id = storage.create_request(
        "clear the whole cart", parsed_definition=json.loads(CLEAN_EXAMPLE.read_text())
    )
    # An entry written before actors were recorded, as older local databases hold.
    with sqlite3.connect(storage.db_path) as conn:
        conn.execute(
            "INSERT INTO audit_log (request_id, step, detail) VALUES (?, ?, ?)",
            (request_id, "intake_received", json.dumps({"raw_intake_text": "clear it"})),
        )
    _approve(storage, request_id)

    assert _decision(storage, request_id)["self_approval"] is None


def test_a_rejection_carries_no_self_approval_marker(storage):
    request_id = _raw(storage)
    decide(request_id, "reject", storage, get_publisher(), note="not needed")

    assert "self_approval" not in _decision(storage, request_id)


def test_every_approval_in_the_demo_is_a_self_approval(demo_env):
    from app.main import app

    visitor = TestClient(app)
    assert visitor.post("/session").status_code == 200
    created = visitor.post(
        "/requests/raw",
        json={
            "definition": json.loads(CLEAN_EXAMPLE.read_text()),
            "business_value": "measures cart abandonment",
        },
    )
    request_id = created.json()["id"]

    decided = visitor.post(f"/requests/{request_id}/decision", json={"decision": "approve"})
    assert decided.status_code == 200, decided.text

    log = visitor.get(f"/requests/{request_id}").json()["audit_log"]
    decision = next(e for e in log if e["step"] == "decision_received")["detail"]
    assert decision["self_approval"] is True
    assert decision["actor"] == {
        "email": "anonymous visitor",
        "method": "demo",
        "verified": False,
    }
