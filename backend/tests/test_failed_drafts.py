"""A request whose drafting fails is closed as rejected, never left waiting on an approver.

A request is stored before the model drafts it, so the visitor's allowance is charged
once. When the model service fails, the request is rejected with a ``model_error`` entry
and the route answers 502. When anything else fails after the request is stored, as when
an SDK release stopped accepting an argument, it is closed the same way and the error is
re-raised unchanged, so the server log keeps the traceback. Either way no nameless
request reaches the approval queue. Nothing calls a model.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.interpreter import Interpretation, InterpreterError
from app.pipeline import IntakeModelError, interpret_intake


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


def _raises(exc):
    def interpret_fn(_raw, **_):
        raise exc

    return interpret_fn


def test_a_model_service_failure_rejects_the_request(storage):
    failure = InterpreterError("stub-model", "model request failed (APIConnectionError)")
    with pytest.raises(IntakeModelError):
        interpret_intake("track bookmarks", storage, interpret_fn=_raises(failure))

    request = _only_request(storage)
    assert request["status"] == "rejected"
    assert _steps(storage, request["id"]) == ["intake_received", "model_error", "routed"]
    [error] = [e for e in storage.get_audit_log(request["id"]) if e["step"] == "model_error"]
    assert error["detail"]["model"] == "stub-model"
    assert error["detail"]["reason"] == "model request failed (APIConnectionError)"


def test_an_unexpected_failure_rejects_the_request_and_is_re_raised(storage):
    failure = TypeError("Messages.create() got an unexpected keyword argument 'temperature'")
    with pytest.raises(TypeError) as raised:
        interpret_intake("track bookmarks", storage, interpret_fn=_raises(failure))
    assert raised.value is failure, "re-raised unchanged, so the log keeps the traceback"

    request = _only_request(storage)
    assert request["status"] == "rejected"
    assert _steps(storage, request["id"]) == ["intake_received", "model_error", "routed"]
    [error] = [e for e in storage.get_audit_log(request["id"]) if e["step"] == "model_error"]
    assert error["detail"]["reason"] == "drafting failed unexpectedly (TypeError)"
    assert error["detail"]["model"] == get_settings().anthropic_model


def test_a_failure_after_the_model_answers_rejects_the_request_too(storage, monkeypatch):
    def crashing_route(*_args, **_kwargs):
        raise RuntimeError("routing failed")

    monkeypatch.setattr("app.pipeline._route", crashing_route)
    with pytest.raises(RuntimeError):
        interpret_intake(
            "track bookmarks",
            storage,
            interpret_fn=lambda _raw, **_: Interpretation("stub", BOOKMARKED, "{}", None),
        )

    request = _only_request(storage)
    assert request["status"] == "rejected"
    assert _steps(storage, request["id"])[-2:] == ["model_error", "routed"]


def test_through_the_api_a_crashing_sdk_leaves_nothing_pending(storage, monkeypatch):
    class CrashingClient:
        def __init__(self, api_key=None):
            self.messages = self

        def create(self, **kwargs):
            raise TypeError("Messages.create() got an unexpected keyword argument 'temperature'")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    get_settings.cache_clear()
    monkeypatch.setattr("app.interpreter.anthropic.Anthropic", CrashingClient)
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/requests",
        json={
            "raw_intake_text": "track when someone subscribes to our newsletter",
            "business_value": "measures newsletter growth",
            "submitter_name": "Ada",
            "submitter_team": "Marketing",
        },
    )
    assert response.status_code == 500
    assert [request["status"] for request in client.get("/requests").json()] == ["rejected"]
