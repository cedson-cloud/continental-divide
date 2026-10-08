"""Identify and group join track (ADR 0003), on the model-free path.

The plan holds one identify call, and an identify request adds traits to it: no event
name, no category. A group request names a group type and adds traits to it. Traits get
the same naming and PII checks as properties, and personal data is in the right place
only on identify.
"""

from pathlib import Path

import pytest

from app.governance import (
    DEFAULT_PROFILE,
    GovernanceError,
    load_profile,
    profile_from_dict,
)
from app.models import Decision, EventDefinition
from app.publisher import MockPublisher
from app.rules import evaluate

TEMPLATES = Path(__file__).resolve().parents[2] / "governance" / "templates"
SEGMENT = load_profile(TEMPLATES / "segment-ecommerce.yaml")

IDENTIFY = {
    "call_type": "identify",
    "description": "Facts about a person, sent when they register.",
    "traits": [
        {"name": "email", "type": "string"},
        {"name": "plan_tier", "type": "string"},
    ],
}


def _checks(evaluation):
    return {c.rule: c for c in evaluation.checks}


def test_identify_runs_trait_naming_and_pii_and_nothing_about_event_names():
    evaluation = evaluate(EventDefinition.model_validate(IDENTIFY), SEGMENT)

    assert set(_checks(evaluation)) == {"trait_naming", "pii"}
    assert evaluation.decision is Decision.pending_approval
    assert evaluation.pii_hits == {"email": "email"}
    assert "on identify" in _checks(evaluation)["pii"].detail


GROUP = {
    "call_type": "group",
    "name": "company",
    "description": "The organization a person belongs to.",
    "traits": [
        {"name": "company_name", "type": "string"},
        {"name": "contact_email", "type": "string"},
    ],
}


def test_group_checks_its_type_and_traits_and_says_personal_data_belongs_on_identify():
    evaluation = evaluate(EventDefinition.model_validate(GROUP), SEGMENT)

    assert set(_checks(evaluation)) == {"group_naming", "trait_naming", "pii"}
    assert evaluation.decision is Decision.pending_approval
    assert evaluation.pii_hits == {"contact_email": "email"}
    assert "belongs on identify, not on a group trait" in _checks(evaluation)["pii"].detail


def test_a_group_may_declare_its_type_with_no_traits():
    evaluation = evaluate(
        EventDefinition.model_validate({"call_type": "group", "name": "company"}), SEGMENT
    )

    assert evaluation.decision is Decision.pending_approval


def test_a_badly_named_trait_rejects_and_says_it_is_a_trait():
    definition = {**IDENTIFY, "traits": [{"name": "planTier", "type": "string"}]}

    evaluation = evaluate(EventDefinition.model_validate(definition), SEGMENT)

    assert evaluation.decision is Decision.rejected
    assert "trait 'planTier' must be snake_case" in _checks(evaluation)["trait_naming"].detail


def test_a_badly_named_group_type_rejects():
    evaluation = evaluate(
        EventDefinition.model_validate({**GROUP, "name": "Company"}), SEGMENT
    )

    assert evaluation.decision is Decision.rejected
    assert not _checks(evaluation)["group_naming"].passed


def test_personal_data_on_a_track_property_is_told_it_belongs_on_identify():
    track = {
        "name": "Newsletter Subscribed",
        "category": "Core Ordering",
        "properties": [{"name": "email", "type": "string"}],
    }

    evaluation = evaluate(EventDefinition.model_validate(track), SEGMENT)

    assert evaluation.decision is Decision.pending_approval
    assert (
        "belongs on identify, not on a track property" in _checks(evaluation)["pii"].detail
    )


def test_a_profile_allows_all_three_call_types_unless_it_says_otherwise():
    data = DEFAULT_PROFILE.model_dump()
    del data["call_types"]

    assert profile_from_dict(data).call_types == ["track", "identify", "group"]
    assert SEGMENT.call_types == ["track", "identify", "group"]


def test_a_profile_can_drop_group_but_cannot_name_an_unknown_call_type():
    data = DEFAULT_PROFILE.model_dump()

    assert profile_from_dict({**data, "call_types": ["track", "identify"]}).call_types == [
        "track",
        "identify",
    ]
    with pytest.raises(GovernanceError):
        profile_from_dict({**data, "call_types": ["track", "page"]})


def _raw(client, definition, **body):
    return client.post(
        "/requests/raw",
        json={"definition": definition, "business_value": "know who signs up", **body},
    )


def test_an_identify_request_with_a_reasoned_email_trait_reaches_approval(client):
    response = _raw(
        client,
        IDENTIFY,
        call_type="identify",
        pii_reasons={"email": "the canonical ID's contact address"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending_approval"
    detail = client.get(f"/requests/{response.json()['id']}").json()
    assert detail["call_type"] == "identify"
    assert detail["parsed_definition"]["call_type"] == "identify"


def test_a_call_type_the_profile_does_not_allow_is_refused(client, monkeypatch):
    no_group = SEGMENT.model_copy(update={"call_types": ["track", "identify"]})
    monkeypatch.setattr("app.routes.load_active_profile", lambda: no_group)

    response = _raw(client, GROUP, call_type="group", pii_reasons={"contact_email": "x"})

    assert response.status_code == 422
    assert "group" in response.json()["detail"]
    assert client.get("/requests").json() == []


def test_a_definition_that_states_a_different_call_type_is_refused(client):
    response = _raw(client, {**IDENTIFY, "call_type": "group"}, call_type="identify")

    assert response.status_code == 422
    assert "states call type 'group'" in response.json()["detail"]
    assert client.get("/requests").json() == []


def test_a_property_request_cannot_be_an_identify_or_group_call(client):
    response = _raw(
        client,
        IDENTIFY,
        call_type="identify",
        request_kind="new_property_on_existing",
        existing_event="Order Completed",
        pii_reasons={"email": "x"},
    )

    assert response.status_code == 422
    assert "a property request adds to a track event" in str(response.json()["detail"])


def test_an_identify_definition_with_a_name_is_recorded_as_a_schema_rejection(client):
    response = _raw(
        client, {**IDENTIFY, "name": "User Identified"}, call_type="identify"
    )

    assert response.json()["status"] == "rejected"
    steps = [e["step"] for e in client.get(f"/requests/{response.json()['id']}").json()["audit_log"]]
    assert "schema_rejected" in steps


def test_the_publisher_titles_identify_and_group_and_lists_their_traits():
    publisher = MockPublisher()

    identify = publisher.publish(EventDefinition.model_validate(IDENTIFY))
    group = publisher.publish(EventDefinition.model_validate(GROUP))

    assert identify.confluence_doc["title"] == "Identify traits"
    assert identify.jira_ticket["summary"] == "Implement identify traits"
    assert [t["name"] for t in identify.confluence_doc["traits"]] == ["email", "plan_tier"]
    assert group.confluence_doc["title"] == "Group: company"
    assert group.jira_ticket["summary"] == "Implement group call: company"


def test_the_data_dictionary_still_answers_with_an_approved_identify_request(client):
    rid = _raw(
        client, IDENTIFY, call_type="identify", pii_reasons={"email": "contact address"}
    ).json()["id"]
    assert client.post(
        f"/requests/{rid}/decision", json={"decision": "approve", "pii_acknowledged": True}
    ).json()["status"] == "published"

    response = client.get("/catalog")

    assert response.status_code == 200
    assert all(e["request_id"] != rid for e in response.json()["events"])
