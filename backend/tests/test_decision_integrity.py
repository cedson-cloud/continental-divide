"""What a decision leaves behind when publishing fails, or when two decisions race.

A failing publisher is a real adapter at the ``Publisher`` seam, not a mock. The race is
reproduced deterministically by a storage adapter that hands ``decide()`` a stale
snapshot, the way a second approver's page would after the first approver acted.
"""

import json
from pathlib import Path

import pytest

from app.models import EventDefinition
from app.pipeline import (
    InvalidTransition,
    PublishFailed,
    decide,
    ingest_raw_definition,
    publish_approved,
)
from app.publisher import MockPublisher, Publisher, PublishResult

CLEAN_EXAMPLE = Path(__file__).parents[1] / "examples" / "clean_cart_cleared.json"


class FailingPublisher(Publisher):
    name = "failing"

    def publish(self, event_definition: EventDefinition) -> PublishResult:
        raise RuntimeError("publisher unreachable")


def _pending(storage) -> int:
    return ingest_raw_definition(
        "clear the whole cart",
        json.loads(CLEAN_EXAMPLE.read_text()),
        storage,
        business_value="measures cart abandonment",
    )


def test_a_publish_failure_is_recorded_and_leaves_the_request_approved(storage):
    request_id = _pending(storage)

    with pytest.raises(PublishFailed):
        decide(request_id, "approve", storage, FailingPublisher(), note="looks good")

    assert storage.get_request(request_id)["status"] == "approved"
    log = storage.get_audit_log(request_id)
    assert [entry["step"] for entry in log][-2:] == ["decision_received", "publish_failed"]
    assert log[-1]["detail"]["publisher"] == "failing"
    assert "publisher unreachable" in log[-1]["detail"]["error"]


def test_an_approved_request_whose_publish_failed_can_be_published_again(storage):
    request_id = _pending(storage)
    with pytest.raises(PublishFailed):
        decide(request_id, "approve", storage, FailingPublisher())

    result = publish_approved(request_id, storage, MockPublisher())

    assert result.publisher == "mock"
    assert storage.get_request(request_id)["status"] == "published"
    steps = [entry["step"] for entry in storage.get_audit_log(request_id)]
    assert steps[-3:] == ["decision_received", "publish_failed", "published"]


def test_only_an_approved_request_can_be_published_again(storage):
    request_id = _pending(storage)

    with pytest.raises(InvalidTransition):
        publish_approved(request_id, storage, MockPublisher())

    assert storage.get_request(request_id)["status"] == "pending_approval"


def test_over_http_a_failed_publish_is_a_502_and_the_retry_publishes(client, monkeypatch):
    created = client.post(
        "/requests/raw",
        json={
            "definition": json.loads(CLEAN_EXAMPLE.read_text()),
            "business_value": "measures cart abandonment",
        },
    ).json()
    request_id = created["id"]

    monkeypatch.setattr("app.routes.get_publisher", FailingPublisher)
    response = client.post(f"/requests/{request_id}/decision", json={"decision": "approve"})
    assert response.status_code == 502
    assert "approved but publishing failed" in response.json()["detail"]
    assert client.get(f"/requests/{request_id}").json()["status"] == "approved"

    monkeypatch.setattr("app.routes.get_publisher", MockPublisher)
    response = client.post(f"/requests/{request_id}/publish")
    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert response.json()["published_artifact"]["publisher"] == "mock"


def test_over_http_publishing_a_request_that_is_not_approved_is_a_409(client):
    created = client.post(
        "/requests/raw",
        json={
            "definition": json.loads(CLEAN_EXAMPLE.read_text()),
            "business_value": "measures cart abandonment",
        },
    ).json()

    response = client.post(f"/requests/{created['id']}/publish")

    assert response.status_code == 409


class CountingPublisher(MockPublisher):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def publish(self, event_definition: EventDefinition) -> PublishResult:
        self.calls += 1
        return super().publish(event_definition)


class StaleSnapshot:
    """Real storage, except ``get_request`` returns the request as a second approver's
    page saw it, before the first decision landed."""

    def __init__(self, inner, snapshot: dict) -> None:
        self._inner = inner
        self._snapshot = snapshot

    def get_request(self, request_id: int) -> dict:
        return dict(self._snapshot)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def test_when_two_approvals_race_only_one_publishes(storage):
    request_id = _pending(storage)
    seen_by_second_approver = storage.get_request(request_id)
    publisher = CountingPublisher()
    decide(request_id, "approve", storage, publisher, approver_name="first")
    steps_after_first = [e["step"] for e in storage.get_audit_log(request_id)]

    with pytest.raises(InvalidTransition):
        decide(
            request_id,
            "approve",
            StaleSnapshot(storage, seen_by_second_approver),
            publisher,
            approver_name="second",
        )

    assert publisher.calls == 1
    assert storage.get_request(request_id)["status"] == "published"
    assert [e["step"] for e in storage.get_audit_log(request_id)] == steps_after_first


def test_a_reject_racing_an_approval_cannot_overwrite_it(storage):
    request_id = _pending(storage)
    seen_by_second_approver = storage.get_request(request_id)
    decide(request_id, "approve", storage, MockPublisher(), approver_name="first")
    steps_after_first = [e["step"] for e in storage.get_audit_log(request_id)]

    with pytest.raises(InvalidTransition):
        decide(
            request_id,
            "reject",
            StaleSnapshot(storage, seen_by_second_approver),
            MockPublisher(),
            approver_name="second",
        )

    assert storage.get_request(request_id)["status"] == "published"
    assert [e["step"] for e in storage.get_audit_log(request_id)] == steps_after_first
