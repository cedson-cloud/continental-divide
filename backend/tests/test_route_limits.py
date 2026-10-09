"""One dispute per rule per request, and one rate limit over every authenticated route
(docs/adr/0010, TASKS D5).

The dispute cap lives in ``record_rule_dispute`` so no caller can skip it. The general
limiter is a router dependency, so it covers reads, the governance routes that never
touch storage, and anything added later; it is keyed by the visitor's workspace cookie
and falls back to their address. ``/health`` and ``POST /session`` stay outside it.
The intake limiter on the three model routes is untouched. Nothing here calls a model.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.interpreter import Interpretation
from app.pipeline import interpret_intake
from app.rate_limit import RateLimiter
from app.recourse import AlreadyDisputed, disputed_rules, record_rule_dispute

from .test_rename_and_dispute import _rejected, _steps, stub_no_findings

MODEL = "claude-sonnet-4-6"

# Refused by the naming rule on the word "in" and by the property rule on "Product ID".
TWICE_REJECTED = {
    "name": "Back in Stock Alert Requested",
    "category": "Browsing",
    "description": "Shopper asked to be emailed when a sold-out product returns.",
    "properties": [{"name": "Product ID", "type": "string", "required": True}],
}


def _twice_rejected(storage) -> int:
    def interpret(_raw, **_):
        return Interpretation(MODEL, TWICE_REJECTED, json.dumps(TWICE_REJECTED), None)

    rid = interpret_intake(
        "email me when a sold-out product is back in stock",
        storage,
        interpret_fn=interpret,
        duplicate_fn=stub_no_findings,
        submitter_name="Sam",
        submitter_team="Marketing",
        call_type="track",
        side="Client",
        business_value="win back demand lost to stockouts",
        destinations=["engagement"],
    )
    assert storage.get_request(rid)["status"] == "rejected"
    return rid


def _dispute(client, rid, rule="event_naming"):
    return client.post(
        f"/requests/{rid}/dispute-rule", json={"rule": rule, "note": "wrong for us"}
    )


def _visitor() -> TestClient:
    from app.main import app

    client = TestClient(app)
    assert client.post("/session").status_code == 200
    return client


# --- one dispute per rule per request ---------------------------------------------


def test_a_second_dispute_of_the_same_rule_is_refused_with_409(client, storage):
    rid = _rejected(storage)
    assert _dispute(client, rid).status_code == 200

    repeat = _dispute(client, rid)
    assert repeat.status_code == 409
    assert "already disputed" in repeat.json()["detail"]
    assert _steps(storage, rid).count("rule_disputed") == 1
    assert len(client.get("/disputes").json()) == 1


def test_the_cap_is_enforced_below_the_route(storage):
    rid = _rejected(storage)
    record_rule_dispute(rid, "event_naming", "first", storage)
    with pytest.raises(AlreadyDisputed):
        record_rule_dispute(rid, "event_naming", "second", storage)
    assert disputed_rules(storage, rid) == ["event_naming"]


def test_a_different_failed_rule_on_the_same_request_can_still_be_disputed(
    client, storage
):
    rid = _twice_rejected(storage)
    assert _dispute(client, rid, "event_naming").status_code == 200
    assert _dispute(client, rid, "property_naming").status_code == 200
    assert _dispute(client, rid, "property_naming").status_code == 409
    assert sorted(disputed_rules(storage, rid)) == ["event_naming", "property_naming"]


def test_the_cap_is_per_request_not_per_rule(client, storage):
    first, second = _rejected(storage), _rejected(storage)
    assert _dispute(client, first).status_code == 200
    assert _dispute(client, second).status_code == 200


# --- one rate limit over every authenticated route --------------------------------


def test_the_settings_have_their_own_names(monkeypatch):
    monkeypatch.setenv("GENERAL_RATE_LIMIT_MAX", "7")
    monkeypatch.setenv("GENERAL_RATE_LIMIT_WINDOW_SECONDS", "30")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.general_rate_limit_max == 7
        assert settings.general_rate_limit_window_seconds == 30
        assert (settings.rate_limit_max, settings.rate_limit_window_seconds) == (10, 60)
    finally:
        get_settings.cache_clear()


def test_reads_count_and_the_limit_is_per_workspace_cookie(demo_env, monkeypatch):
    monkeypatch.setattr("app.routes._route_limiter", RateLimiter(3, 60))
    visitor = _visitor()
    for _ in range(3):
        assert visitor.get("/requests").status_code == 200

    refused = visitor.get("/requests")
    assert refused.status_code == 429
    assert "too many requests" in refused.json()["detail"]
    # Another visitor at the same address has a budget of their own.
    assert _visitor().get("/requests").status_code == 200


def test_routes_that_never_touch_storage_are_covered(client, storage, monkeypatch):
    monkeypatch.setattr("app.routes._route_limiter", RateLimiter(2, 60))
    assert client.get("/governance/profile").status_code == 200
    assert client.get("/governance/profile").status_code == 200
    assert client.get("/governance/profile").status_code == 429


def test_without_a_workspace_the_limit_is_per_address(client, storage, monkeypatch):
    monkeypatch.setattr("app.routes._route_limiter", RateLimiter(1, 60))
    assert client.get("/requests").status_code == 200
    assert client.get("/catalog").status_code == 429


def test_a_refused_write_changes_nothing(client, storage, monkeypatch):
    rid = _rejected(storage)
    before = _steps(storage, rid)
    monkeypatch.setattr("app.routes._route_limiter", RateLimiter(0, 60))
    assert _dispute(client, rid).status_code == 429
    assert _steps(storage, rid) == before


def test_health_and_session_stay_outside_it(demo_env, monkeypatch):
    from app.main import app

    monkeypatch.setattr("app.routes._route_limiter", RateLimiter(0, 60))
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.post("/session").status_code == 200
    assert client.get("/requests").status_code == 429


def test_the_intake_limiter_is_its_own_budget(client, storage, monkeypatch):
    monkeypatch.setattr("app.routes._limiter", RateLimiter(0, 60))
    refused = client.post(
        "/requests",
        json={
            "raw_intake_text": "a shopper empties their cart",
            "business_value": "measures abandonment",
            "submitter_name": "Ada",
            "submitter_team": "Product",
        },
    )
    assert refused.status_code == 429
    assert refused.json()["detail"] == "rate limit exceeded"
    # The general budget is untouched by the intake limiter's refusal, and vice versa.
    assert client.get("/requests").status_code == 200
