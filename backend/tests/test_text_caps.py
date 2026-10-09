"""Every free-text field that reaches a prompt or the audit log is capped at the
request-body layer (TASKS D5). An oversized field is rejected with 422 before the
handler runs, so nothing below it (the rate limiter, the model budget, storage)
sees the request.

Everything runs offline. The cases that post to POST /requests assert only the
validation layer, which rejects before any model call could happen, and the
per-request routes use an id that does not exist: body validation runs first, so
the 422 arrives before any 404 would.
"""

import json
from pathlib import Path

import pytest

from app.routes import (
    MAX_DESTINATIONS,
    MAX_NAME_CHARS,
    MAX_NOTE_CHARS,
    MAX_PERSON_NAME_CHARS,
)

CLEAN_EXAMPLE = Path(__file__).parents[1] / "examples" / "clean_cart_cleared.json"
MISSING_ID = 999_999

NOTE_OVER = "x" * (MAX_NOTE_CHARS + 1)
NAME_OVER = "x" * (MAX_NAME_CHARS + 1)
PERSON_OVER = "x" * (MAX_PERSON_NAME_CHARS + 1)


def _raw_body(**overrides):
    return {
        "definition": json.loads(CLEAN_EXAMPLE.read_text()),
        "business_value": "measures cart abandonment",
        **overrides,
    }


def _intake_body(**overrides):
    return {
        "raw_intake_text": "track when a shopper clears the cart",
        "business_value": "measures cart abandonment",
        "submitter_name": "Sam",
        "submitter_team": "Product",
        **overrides,
    }


CASES = [
    # (route, base body, field, oversized value, cap named in the error)
    ("/requests", _intake_body, "business_value", NOTE_OVER, MAX_NOTE_CHARS),
    ("/requests", _intake_body, "urgency_reason", NOTE_OVER, MAX_NOTE_CHARS),
    ("/requests", _intake_body, "submitter_name", PERSON_OVER, MAX_PERSON_NAME_CHARS),
    ("/requests", _intake_body, "existing_event", NAME_OVER, MAX_NAME_CHARS),
    ("/requests", _intake_body, "destinations", ["d"] * (MAX_DESTINATIONS + 1), MAX_DESTINATIONS),
    ("/requests/raw", _raw_body, "business_value", NOTE_OVER, MAX_NOTE_CHARS),
    ("/requests/raw", _raw_body, "urgency_reason", NOTE_OVER, MAX_NOTE_CHARS),
    ("/requests/raw", _raw_body, "submitter_name", PERSON_OVER, MAX_PERSON_NAME_CHARS),
    ("/requests/raw", _raw_body, "existing_event", NAME_OVER, MAX_NAME_CHARS),
    ("/requests/raw", _raw_body, "destinations", ["d"] * (MAX_DESTINATIONS + 1), MAX_DESTINATIONS),
    ("/requests/raw", _raw_body, "pii_reasons", {"email": NOTE_OVER}, MAX_NOTE_CHARS),
    ("/requests/raw", _raw_body, "pii_reasons", {NAME_OVER: "needed"}, MAX_NAME_CHARS),
    (f"/requests/{MISSING_ID}/submit", dict, "duplicate_note", NOTE_OVER, MAX_NOTE_CHARS),
    (f"/requests/{MISSING_ID}/submit", dict, "pii_reasons", {"email": NOTE_OVER}, MAX_NOTE_CHARS),
    (f"/requests/{MISSING_ID}/decision", lambda: {"decision": "approve"}, "note", NOTE_OVER, MAX_NOTE_CHARS),
    (f"/requests/{MISSING_ID}/decision", lambda: {"decision": "approve"}, "approver_name", PERSON_OVER, MAX_PERSON_NAME_CHARS),
    (f"/requests/{MISSING_ID}/dispute-rule", lambda: {"rule": "naming"}, "note", NOTE_OVER, MAX_NOTE_CHARS),
    (f"/requests/{MISSING_ID}/dispute-rule", lambda: {"note": "because"}, "rule", NAME_OVER, MAX_NAME_CHARS),
    (f"/requests/{MISSING_ID}/withdraw", lambda: {"existing_event": "Cart Cleared"}, "reason", NOTE_OVER, MAX_NOTE_CHARS),
    (f"/requests/{MISSING_ID}/withdraw", dict, "existing_event", NAME_OVER, MAX_NAME_CHARS),
    (f"/requests/{MISSING_ID}/rename", dict, "new_name", NAME_OVER, MAX_NAME_CHARS),
    (f"/requests/{MISSING_ID}/convert", dict, "existing_event", NAME_OVER, MAX_NAME_CHARS),
]


@pytest.mark.parametrize(
    "route, base, field, value, cap",
    CASES,
    ids=[f"{route.replace(str(MISSING_ID), 'id')}:{field}" for route, _, field, _, _ in CASES],
)
def test_oversized_field_is_rejected_before_the_handler(client, route, base, field, value, cap):
    response = client.post(route, json={**base(), field: value})
    assert response.status_code == 422
    assert str(cap) in json.dumps(response.json())


def test_fields_at_the_cap_are_accepted(client):
    response = client.post(
        "/requests/raw",
        json=_raw_body(
            business_value="x" * MAX_NOTE_CHARS,
            submitter_name="x" * MAX_PERSON_NAME_CHARS,
            urgency_reason="x" * MAX_NOTE_CHARS,
            urgent=True,
        ),
    )
    assert response.status_code == 200, response.json()
