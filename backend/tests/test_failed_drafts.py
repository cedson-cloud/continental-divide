"""A request whose drafting fails ends at "Couldn't draft", never rejected and never left
waiting on an approver.

Only the deterministic engine rejects (CONTEXT.md), and a failed drafting is not its
verdict, so the request gets its own status, ``draft_failed``. A request is stored before
the model drafts it, so the visitor's allowance is charged once and is not refunded. When
the model service fails, or answers with nothing that reads as a definition, the request
ends with a ``model_error`` entry and the route answers 502. When anything else fails after
the request is stored, as when an SDK release stopped accepting an argument, it ends the
same way and the error is re-raised unchanged, so the server log keeps the traceback.
Nothing calls a model.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.interpreter import Interpretation, InterpreterError
from app.models import Decision
from app.pipeline import IntakeModelError, interpret_intake
from app.storage import RequestQuotaReached, workspace_storage
from app.workspace import new_workspace_id

from .conftest import TESTER


BOOKMARKED = {
    "name": "Product Bookmarked",
    "category": "Wishlisting",
    "description": "User bookmarked a product to revisit later.",
    "properties": [{"name": "product_id", "type": "string", "required": True}],
}


def _steps(storage, request_id):
    return [entry["step"] for entry in storage.get_audit_log(request_id)]


def _only_request(storage):
    [request] = storage.list_requests()
    return request


def _entry(storage, request_id, step):
    [entry] = [e for e in storage.get_audit_log(request_id) if e["step"] == step]
    return entry


def _raises(exc):
    def interpret_fn(_raw, **_):
        raise exc

    return interpret_fn


def _answers(proposed_definition, parse_error=None):
    return lambda _raw, **_: Interpretation("stub-model", proposed_definition, "{}", parse_error)


def test_couldnt_draft_is_a_status_and_never_a_decision():
    assert "draft_failed" not in {d.value for d in Decision}


def test_a_model_service_failure_ends_at_couldnt_draft(storage):
    failure = InterpreterError("stub-model", "model request failed (APIConnectionError)")
    with pytest.raises(IntakeModelError):
        interpret_intake("track bookmarks", storage, interpret_fn=_raises(failure))

    request = _only_request(storage)
    assert request["status"] == "draft_failed"
    assert _steps(storage, request["id"]) == ["intake_received", "model_error", "routed"]
    error = _entry(storage, request["id"], "model_error")
    assert error["detail"]["model"] == "stub-model"
    assert error["detail"]["reason"] == "model request failed (APIConnectionError)"


def test_the_routed_entry_carries_no_decision(storage):
    failure = InterpreterError("stub-model", "model request failed (APIConnectionError)")
    with pytest.raises(IntakeModelError):
        interpret_intake("track bookmarks", storage, interpret_fn=_raises(failure))

    routed = _entry(storage, _only_request(storage)["id"], "routed")
    assert routed["detail"]["routed_to_approval"] is False
    assert "decision" not in routed["detail"]


def test_an_unexpected_failure_ends_at_couldnt_draft_and_is_re_raised(storage):
    failure = TypeError("Messages.create() got an unexpected keyword argument 'temperature'")
    with pytest.raises(TypeError) as raised:
        interpret_intake("track bookmarks", storage, interpret_fn=_raises(failure))
    assert raised.value is failure, "re-raised unchanged, so the log keeps the traceback"

    request = _only_request(storage)
    assert request["status"] == "draft_failed"
    assert _steps(storage, request["id"]) == ["intake_received", "model_error", "routed"]
    error = _entry(storage, request["id"], "model_error")
    assert error["detail"]["reason"] == "drafting failed unexpectedly (TypeError)"
    assert error["detail"]["model"] == get_settings().anthropic_model


def test_a_failure_after_the_model_answers_ends_at_couldnt_draft_too(storage, monkeypatch):
    def crashing_route(*_args, **_kwargs):
        raise RuntimeError("routing failed")

    monkeypatch.setattr("app.pipeline._route", crashing_route)
    with pytest.raises(RuntimeError):
        interpret_intake("track bookmarks", storage, interpret_fn=_answers(BOOKMARKED))

    request = _only_request(storage)
    assert request["status"] == "draft_failed"
    assert _steps(storage, request["id"])[-2:] == ["model_error", "routed"]


def test_an_answer_with_no_readable_definition_ends_at_couldnt_draft(storage):
    unreadable = _answers(None, "model output was not valid JSON: Expecting value")
    with pytest.raises(IntakeModelError):
        interpret_intake("track bookmarks", storage, interpret_fn=unreadable)

    request = _only_request(storage)
    assert request["status"] == "draft_failed"
    assert _steps(storage, request["id"]) == [
        "intake_received",
        "model_interpreted",
        "model_error",
        "routed",
    ]
    error = _entry(storage, request["id"], "model_error")
    assert error["detail"]["reason"] == "model output was not valid JSON: Expecting value"


def test_a_definition_that_breaks_the_schema_is_still_the_engines_rejection(storage):
    nameless = {key: value for key, value in BOOKMARKED.items() if key != "name"}
    interpret_intake("track bookmarks", storage, interpret_fn=_answers(nameless))

    request = _only_request(storage)
    assert request["status"] == "rejected"
    assert "schema_rejected" in _steps(storage, request["id"])
    assert "model_error" not in _steps(storage, request["id"])


def test_a_failed_drafting_still_counts_against_the_allowance(demo_env):
    storage = workspace_storage(new_workspace_id()).acting_as(TESTER)
    failure = InterpreterError("stub-model", "model request failed (APIConnectionError)")
    for _ in range(5):
        with pytest.raises(IntakeModelError):
            interpret_intake("track bookmarks", storage, interpret_fn=_raises(failure))

    with pytest.raises(RequestQuotaReached):
        storage.create_request(raw_intake_text="x")
    assert {r["status"] for r in storage.list_requests()} == {"draft_failed"}


def _client_with_sdk(monkeypatch, create):
    """An API client whose Anthropic SDK answers every call with ``create``."""

    class StubClient:
        def __init__(self, api_key=None):
            self.messages = self

        def create(self, **kwargs):
            return create()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    get_settings.cache_clear()
    monkeypatch.setattr("app.interpreter.anthropic.Anthropic", StubClient)
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


def _post_request(client):
    return client.post(
        "/requests",
        json={
            "raw_intake_text": "track when someone subscribes to our newsletter",
            "business_value": "measures newsletter growth",
            "submitter_name": "Ada",
            "submitter_team": "Marketing",
        },
    )


def test_through_the_api_a_crashing_sdk_leaves_nothing_pending(storage, monkeypatch):
    def crash():
        raise TypeError("Messages.create() got an unexpected keyword argument 'temperature'")

    client = _client_with_sdk(monkeypatch, crash)
    assert _post_request(client).status_code == 500
    assert [request["status"] for request in client.get("/requests").json()] == ["draft_failed"]


def test_through_the_api_an_unreadable_answer_is_a_502(storage, monkeypatch):
    def prose():
        text = SimpleNamespace(type="text", text="Sure! Here is the event you asked for.")
        return SimpleNamespace(content=[text])

    client = _client_with_sdk(monkeypatch, prose)
    response = _post_request(client)
    assert response.status_code == 502
    assert "could not draft a definition" in response.json()["detail"]
    assert [request["status"] for request in client.get("/requests").json()] == ["draft_failed"]
