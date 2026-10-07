"""Who acted, and how that was established.

The verifier is the only way a request gets an identity. It fails closed: anything other
than an explicit, complete configuration rejects every request. A bare email header is
never evidence of who someone is.
"""

import json
from pathlib import Path

import pytest

from app.config import Settings, get_settings
from app.identity import Identity, Unauthenticated, get_verifier
from app.storage import SqliteStorage, UnattributedAuditEntry

CLEAN_EXAMPLE = Path(__file__).parents[1] / "examples" / "clean_cart_cleared.json"
EMAIL_HEADER = {"Cf-Access-Authenticated-User-Email": "someone@example.com"}


def _settings(**values) -> Settings:
    return Settings(_env_file=None, **values)


def test_with_no_auth_mode_every_request_is_rejected():
    verifier = get_verifier(_settings())

    with pytest.raises(Unauthenticated):
        verifier.verify({})
    with pytest.raises(Unauthenticated):
        verifier.verify(EMAIL_HEADER)


def test_local_mode_acts_as_the_configured_person_and_says_it_is_unverified():
    verifier = get_verifier(
        _settings(auth_mode="local", local_identity_email="dev@example.com")
    )

    identity = verifier.verify(EMAIL_HEADER)

    assert identity == Identity(email="dev@example.com", method="local", verified=False)


def test_local_mode_without_an_email_rejects_rather_than_acting_as_nobody():
    verifier = get_verifier(_settings(auth_mode="local", local_identity_email=""))

    with pytest.raises(Unauthenticated):
        verifier.verify({})


@pytest.mark.parametrize("mode", ["access", "Local", "none", "off"])
def test_any_other_auth_mode_rejects_every_request(mode):
    verifier = get_verifier(
        _settings(auth_mode=mode, local_identity_email="dev@example.com")
    )

    with pytest.raises(Unauthenticated):
        verifier.verify(EMAIL_HEADER)


def test_storage_with_no_actor_refuses_to_write_an_audit_entry(tmp_path):
    storage = SqliteStorage(tmp_path / "unbound.db")
    request_id = storage.create_request("clear the whole cart")

    with pytest.raises(UnattributedAuditEntry):
        storage.add_audit_entry(request_id, "received", {"source": "test"})

    assert storage.get_audit_log(request_id) == []


def _unauthenticated(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "")
    get_settings.cache_clear()


def _app_routes():
    """Every route the app documents, wherever it is mounted, so a route added later
    without the identity check fails here."""
    from app.main import app

    for path, operations in app.openapi()["paths"].items():
        if path != "/health":
            for method in operations:
                yield method.upper(), path.replace("{request_id}", "1")


def test_with_auth_unset_every_route_but_health_is_a_401_and_writes_nothing(
    client, storage, monkeypatch
):
    _unauthenticated(monkeypatch)
    routes = list(_app_routes())
    assert len(routes) > 10

    for method, path in routes:
        response = client.request(method, path, json={})
        assert response.status_code == 401, (method, path, response.status_code)

    assert client.get("/health").status_code == 200
    assert storage.list_requests() == []


def test_a_bare_email_header_does_not_authenticate(client, monkeypatch):
    _unauthenticated(monkeypatch)

    response = client.get("/requests", headers=EMAIL_HEADER)

    assert response.status_code == 401


def test_every_entry_from_intake_to_publish_names_the_local_actor(client):
    created = client.post(
        "/requests/raw",
        json={
            "definition": json.loads(CLEAN_EXAMPLE.read_text()),
            "business_value": "measures cart abandonment",
        },
    ).json()
    request_id = created["id"]
    decided = client.post(
        f"/requests/{request_id}/decision", json={"decision": "approve"}
    )
    assert decided.status_code == 200

    log = client.get(f"/requests/{request_id}").json()["audit_log"]

    assert log[-1]["step"] == "published"
    assert {json.dumps(entry["detail"]["actor"]) for entry in log} == {
        json.dumps({"email": "tester@example.com", "method": "local", "verified": False})
    }


def test_a_step_cannot_supply_its_own_actor(storage):
    request_id = storage.create_request("clear the whole cart")

    with pytest.raises(ValueError):
        storage.add_audit_entry(request_id, "received", {"actor": "someone else"})

    assert storage.get_audit_log(request_id) == []
