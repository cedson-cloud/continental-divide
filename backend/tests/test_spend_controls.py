"""The public demo's spend controls (docs/adr/0010, TASKS D3).

Five requests per sandbox, however they are created; a daily model budget for the whole
instance, counted from token usage; a limit on minting new sandboxes; and a size cap on
every request body. The model is faked throughout — no test here can reach the network.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.spend import get_meter
from app.storage import RequestQuotaReached, workspace_storage
from app.workspace import new_workspace_id

from .conftest import TESTER

CLEAN_EXAMPLE = json.loads(
    (Path(__file__).parents[1] / "examples" / "clean_cart_cleared.json").read_text()
)
# Made-up prices that keep the arithmetic readable. Not any model's real price.
INPUT_PRICE, OUTPUT_PRICE = 3.0, 15.0


@pytest.fixture
def priced(demo_env, monkeypatch):
    monkeypatch.setenv("DEMO_DAILY_BUDGET_USD", "1.00")
    monkeypatch.setenv("MODEL_INPUT_USD_PER_MTOK", str(INPUT_PRICE))
    monkeypatch.setenv("MODEL_OUTPUT_USD_PER_MTOK", str(OUTPUT_PRICE))
    get_settings.cache_clear()
    return demo_env


def _fake_model(monkeypatch, calls):
    """Drafting answers with the clean example; the review answers with no findings.
    Every call reports 1,000 input and 500 output tokens."""

    def create(**kwargs):
        calls.append(kwargs)
        is_review = "findings" in kwargs["system"]
        payload = {"findings": []} if is_review else CLEAN_EXAMPLE
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(payload))],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=500),
        )

    class FakeClient:
        def __init__(self, api_key=None):
            self.messages = SimpleNamespace(create=create)

    monkeypatch.setattr("app.catalog.anthropic.Anthropic", FakeClient)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    get_settings.cache_clear()


def _visitor(**headers) -> TestClient:
    from app.main import app

    client = TestClient(app, headers=headers)
    assert client.post("/session").status_code == 200
    return client


def _raw(client):
    return client.post(
        "/requests/raw",
        json={"definition": CLEAN_EXAMPLE, "business_value": "measures cart abandonment"},
    )


def _draft(client):
    return client.post(
        "/requests",
        json={
            "raw_intake_text": "a shopper empties their cart in one go",
            "business_value": "measures cart abandonment",
            "submitter_name": "Ada",
            "submitter_team": "Product",
        },
    )


# --- five requests per sandbox ------------------------------------------------------


def test_the_sixth_request_in_a_sandbox_is_refused_and_writes_nothing(demo_env):
    visitor = _visitor()
    for _ in range(5):
        assert _raw(visitor).status_code == 200

    refused = _raw(visitor)
    assert refused.status_code == 429
    assert "5 requests" in refused.json()["detail"]
    assert len(visitor.get("/requests").json()) == 5


def test_drafted_and_raw_requests_share_one_allowance(priced, monkeypatch):
    calls = []
    _fake_model(monkeypatch, calls)
    visitor = _visitor()
    for _ in range(3):
        assert _raw(visitor).status_code == 200
    for _ in range(2):
        assert _draft(visitor).status_code == 200
    made = len(calls)

    assert _draft(visitor).status_code == 429
    assert len(calls) == made, "a refused request must not reach the model"


def test_the_allowance_is_per_sandbox(demo_env):
    alice, bob = _visitor(), _visitor()
    for _ in range(5):
        _raw(alice)
    assert _raw(bob).status_code == 200


def test_the_storage_itself_enforces_the_allowance(demo_env):
    storage = workspace_storage(new_workspace_id()).acting_as(TESTER)
    for _ in range(5):
        storage.create_request(raw_intake_text="x")
    with pytest.raises(RequestQuotaReached):
        storage.create_request(raw_intake_text="x")
    assert len(storage.list_requests()) == 5


def test_localhost_has_no_allowance(storage, client):
    for _ in range(6):
        assert _raw(client).status_code == 200


# --- the daily model budget -------------------------------------------------------


def test_every_model_call_is_charged_from_its_token_usage(priced, monkeypatch):
    calls = []
    _fake_model(monkeypatch, calls)
    assert _draft(_visitor()).status_code == 200

    per_call = (1000 * INPUT_PRICE + 500 * OUTPUT_PRICE) / 1_000_000
    assert len(calls) == 2, "the draft and its duplicate review"
    assert get_meter().spent_today() == pytest.approx(2 * per_call)


def test_at_the_cap_drafting_is_refused_before_anything_is_written(priced, monkeypatch):
    calls = []
    _fake_model(monkeypatch, calls)
    get_meter().record("test-model", input_tokens=1_000_000, output_tokens=0)  # $3 > $1
    visitor = _visitor()

    refused = _draft(visitor)
    assert refused.status_code == 503
    assert "daily" in refused.json()["detail"]
    assert calls == []
    assert visitor.get("/requests").json() == [], "a refusal does not use up the allowance"


def test_at_the_cap_the_model_free_path_stays_open(priced, monkeypatch):
    calls = []
    _fake_model(monkeypatch, calls)
    get_meter().record("test-model", input_tokens=1_000_000, output_tokens=0)

    assert _raw(_visitor()).status_code == 200
    assert calls == []


def test_at_the_cap_the_review_fails_advisory_and_says_why(priced, monkeypatch):
    calls = []
    _fake_model(monkeypatch, calls)
    get_meter().record("test-model", input_tokens=1_000_000, output_tokens=0)

    from app.catalog import DuplicateReviewError, review_against_catalog
    from app.models import EventDefinition

    with pytest.raises(DuplicateReviewError, match="daily"):
        review_against_catalog(EventDefinition.model_validate(CLEAN_EXAMPLE))
    assert calls == []


@pytest.mark.parametrize(
    "unset", ["DEMO_DAILY_BUDGET_USD", "MODEL_INPUT_USD_PER_MTOK", "MODEL_OUTPUT_USD_PER_MTOK"]
)
def test_demo_mode_without_a_budget_and_prices_never_calls_the_model(
    priced, monkeypatch, unset
):
    calls = []
    _fake_model(monkeypatch, calls)
    monkeypatch.delenv(unset)
    get_settings.cache_clear()

    assert _draft(_visitor()).status_code == 503
    assert calls == []


def test_localhost_is_not_metered(storage):
    assert get_meter() is None


# --- minting sandboxes ------------------------------------------------------------


def test_new_sandboxes_are_limited_per_client(demo_env, monkeypatch):
    monkeypatch.setenv("DEMO_SESSIONS_PER_IP_PER_HOUR", "2")
    monkeypatch.setenv("DEMO_CLIENT_IP_HEADER", "x-forwarded-for")
    get_settings.cache_clear()
    from app.main import app

    first = _visitor(**{"x-forwarded-for": "203.0.113.7, 10.0.0.1"})
    _visitor(**{"x-forwarded-for": "203.0.113.7"})
    third = TestClient(app, headers={"x-forwarded-for": "203.0.113.7"})
    assert third.post("/session").status_code == 429

    assert first.post("/session").status_code == 200, "a returning visitor is not counted"
    _visitor(**{"x-forwarded-for": "198.51.100.4"})


def test_new_sandboxes_are_limited_across_all_clients(demo_env, monkeypatch):
    monkeypatch.setenv("DEMO_SESSIONS_PER_HOUR", "2")
    monkeypatch.setenv("DEMO_CLIENT_IP_HEADER", "x-forwarded-for")
    get_settings.cache_clear()
    from app.main import app

    _visitor(**{"x-forwarded-for": "203.0.113.1"})
    _visitor(**{"x-forwarded-for": "203.0.113.2"})
    third = TestClient(app, headers={"x-forwarded-for": "203.0.113.3"})
    assert third.post("/session").status_code == 429


# --- request size -----------------------------------------------------------------


def test_an_oversized_body_is_refused_before_any_route_reads_it(demo_env, monkeypatch):
    monkeypatch.setenv("MAX_REQUEST_BYTES", "2048")
    get_settings.cache_clear()
    visitor = _visitor()

    padded = {**CLEAN_EXAMPLE, "description": "x" * 4096}
    response = visitor.post("/requests/raw", json={"definition": padded})
    assert response.status_code == 413
    assert visitor.get("/requests").json() == []


def test_an_oversized_body_without_a_length_header_is_refused(demo_env, monkeypatch):
    monkeypatch.setenv("MAX_REQUEST_BYTES", "2048")
    get_settings.cache_clear()
    visitor = _visitor()

    body = json.dumps({"definition": {**CLEAN_EXAMPLE, "description": "x" * 4096}}).encode()
    chunks = (body[i : i + 512] for i in range(0, len(body), 512))
    response = visitor.post(
        "/requests/raw", content=chunks, headers={"content-type": "application/json"}
    )
    assert response.status_code == 413
    assert visitor.get("/requests").json() == []
