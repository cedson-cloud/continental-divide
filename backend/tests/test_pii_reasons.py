"""Every PII hit needs a written reason from the requester (ADR 0003).

The requester argues and the approver acknowledges. On the model path the reasons arrive
when a draft is submitted; ``POST /requests/raw`` has no requester step, so they travel in
the request body, and a hit without one is refused with nothing written.
"""

import json

import pytest

from app.catalog import DuplicateReview
from app.governance import DEFAULT_PROFILE
from app.interpreter import Interpretation
from app.models import EventDefinition
from app.publisher import get_publisher
from app.pipeline import (
    PiiReasonRequired,
    decide,
    ingest,
    ingest_raw_definition,
    interpret_intake,
    submit_request,
)
from app.rules import pii_hits

MODEL = "claude-sonnet-4-6"

NEWSLETTER = {
    "name": "Newsletter Subscribed",
    "category": "Core Ordering",
    "description": "Fired when someone subscribes to the newsletter.",
    "properties": [
        {"name": "email", "type": "string", "required": True},
        {"name": "list_id", "type": "string"},
        {"name": "subscriber_first_name", "type": "string"},
    ],
}


def test_pii_hits_names_each_flagged_property_and_the_entry_it_matched():
    definition = EventDefinition.model_validate(NEWSLETTER)

    assert pii_hits(definition, DEFAULT_PROFILE) == {
        "email": "email",
        "subscriber_first_name": "first_name",
    }


def _stub_newsletter(_raw: str, **_) -> Interpretation:
    return Interpretation(MODEL, NEWSLETTER, json.dumps(NEWSLETTER), None)


def _stub_no_findings(_definition, **_) -> DuplicateReview:
    return DuplicateReview(MODEL)


def _pii_draft(storage) -> int:
    return interpret_intake(
        "track newsletter signups with the subscriber's email and first name",
        storage,
        interpret_fn=_stub_newsletter,
        duplicate_fn=_stub_no_findings,
    )


def _entry(storage, request_id, step):
    return next(e for e in storage.get_audit_log(request_id) if e["step"] == step)


def test_a_pii_draft_cannot_be_submitted_without_a_reason_for_every_hit(storage):
    rid = _pii_draft(storage)

    with pytest.raises(PiiReasonRequired, match="subscriber_first_name"):
        submit_request(rid, storage, pii_reasons={"email": "to send the newsletter"})

    assert storage.get_request(rid)["status"] == "draft"


def test_submitted_reasons_are_kept_on_the_request_and_in_the_trail(storage):
    rid = _pii_draft(storage)
    reasons = {
        "email": "to send the newsletter",
        "subscriber_first_name": "to greet the subscriber by name",
    }

    submit_request(rid, storage, pii_reasons=reasons)

    assert storage.get_request(rid)["status"] == "pending_approval"
    assert storage.get_request(rid)["pii_reasons"] == reasons
    assert _entry(storage, rid, "submitted")["detail"]["pii_reasons"] == reasons


def test_a_reason_for_a_field_no_rule_flagged_is_refused(storage):
    rid = _pii_draft(storage)
    reasons = {
        "email": "to send the newsletter",
        "subscriber_first_name": "to greet the subscriber by name",
        "list_id": "not personal data",
    }

    with pytest.raises(PiiReasonRequired, match="list_id"):
        submit_request(rid, storage, pii_reasons=reasons)

    assert storage.get_request(rid)["status"] == "draft"


def test_the_raw_path_refuses_a_pii_hit_without_a_reason_and_writes_nothing(storage):
    with pytest.raises(PiiReasonRequired, match="email"):
        ingest_raw_definition(
            "newsletter signup",
            NEWSLETTER,
            storage,
            business_value="measures newsletter growth",
            pii_reasons={"subscriber_first_name": "to greet the subscriber by name"},
        )

    assert storage.list_requests() == []


def test_the_raw_path_keeps_the_reasons_and_routes_to_approval(storage):
    reasons = {
        "email": "to send the newsletter",
        "subscriber_first_name": "to greet the subscriber by name",
    }

    rid = ingest_raw_definition(
        "newsletter signup",
        NEWSLETTER,
        storage,
        business_value="measures newsletter growth",
        pii_reasons=reasons,
    )

    assert storage.get_request(rid)["status"] == "pending_approval"
    assert storage.get_request(rid)["pii_reasons"] == reasons
    assert _entry(storage, rid, "intake_received")["detail"]["pii_reasons"] == reasons


def test_the_offline_ingest_path_refuses_a_pii_hit_without_a_reason(storage):
    with pytest.raises(PiiReasonRequired, match="email"):
        ingest("newsletter signup", NEWSLETTER, storage)

    assert storage.list_requests() == []


def test_the_approvers_acknowledgment_quotes_the_requesters_reasons(storage):
    reasons = {
        "email": "to send the newsletter",
        "subscriber_first_name": "to greet the subscriber by name",
    }
    rid = _pii_draft(storage)
    submit_request(rid, storage, pii_reasons=reasons)

    decide(rid, "approve", storage, get_publisher(), pii_acknowledged=True)

    assert _entry(storage, rid, "pii_acknowledged")["detail"]["pii_reasons"] == reasons


def test_post_raw_answers_422_for_a_missing_reason_and_stores_nothing(client):
    response = client.post(
        "/requests/raw",
        json={"definition": NEWSLETTER, "business_value": "measures newsletter growth"},
    )

    assert response.status_code == 422
    assert "email" in response.json()["detail"]
    assert client.get("/requests").json() == []


def test_post_submit_answers_422_for_a_missing_reason(client, storage):
    rid = _pii_draft(storage)

    response = client.post(f"/requests/{rid}/submit", json={})

    assert response.status_code == 422
    assert "subscriber_first_name" in response.json()["detail"]


def test_request_detail_shows_each_hit_beside_its_reason(client, storage):
    reasons = {
        "email": "to send the newsletter",
        "subscriber_first_name": "to greet the subscriber by name",
    }
    rid = _pii_draft(storage)
    assert client.post(
        f"/requests/{rid}/submit", json={"pii_reasons": reasons}
    ).status_code == 200

    detail = client.get(f"/requests/{rid}").json()

    assert detail["pii_hits"] == {
        "email": "email",
        "subscriber_first_name": "first_name",
    }
    assert detail["pii_reasons"] == reasons
