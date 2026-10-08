"""The public demo gives each visitor a private sandbox (docs/adr/0010).

A visitor is identified only by a signed cookie, and the workspace id inside it picks a
SQLite file of its own. These tests prove that two visitors never see each other's
requests or audit entries, that a forged or tampered cookie is refused, and that demo
mode fails closed without a signing key.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.storage import workspace_storage
from app.workspace import COOKIE_NAME, sign_workspace

CLEAN_EXAMPLE = Path(__file__).parents[1] / "examples" / "clean_cart_cleared.json"


def _visitor() -> TestClient:
    from app.main import app

    return TestClient(app)


def _start(client: TestClient) -> None:
    response = client.post("/session")
    assert response.status_code == 200


def _raw(client: TestClient) -> int:
    response = client.post(
        "/requests/raw",
        json={
            "definition": json.loads(CLEAN_EXAMPLE.read_text()),
            "business_value": "measures cart abandonment",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_a_visitor_without_a_session_is_refused(demo_env):
    assert _visitor().get("/requests").status_code == 401


def test_a_session_issues_an_httponly_cookie_that_admits_the_visitor(demo_env):
    visitor = _visitor()
    response = visitor.post("/session")

    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith(f"{COOKIE_NAME}=")
    assert "HttpOnly" in set_cookie
    assert "samesite=lax" in set_cookie.lower()
    assert visitor.get("/requests").status_code == 200


def test_the_cookie_is_secure_unless_configured_otherwise(demo_env, monkeypatch):
    monkeypatch.delenv("DEMO_COOKIE_SECURE")
    get_settings.cache_clear()
    response = _visitor().post("/session")
    assert "Secure" in response.headers["set-cookie"]


def test_two_visitors_never_see_each_others_requests_or_audit_log(demo_env):
    alice, bob = _visitor(), _visitor()
    _start(alice)
    _start(bob)

    alices_request = _raw(alice)

    assert [r["id"] for r in alice.get("/requests").json()] == [alices_request]
    assert bob.get("/requests").json() == []
    assert bob.get(f"/requests/{alices_request}").status_code == 404

    bobs_request = _raw(bob)
    assert bobs_request == alices_request, "each sandbox numbers its own requests"
    bobs_log = bob.get(f"/requests/{bobs_request}").json()["audit_log"]
    alices_log = alice.get(f"/requests/{alices_request}").json()["audit_log"]
    assert {e["id"] for e in bobs_log} == {e["id"] for e in alices_log}
    assert all(e["request_id"] == bobs_request for e in bobs_log)
    assert len(alice.get("/requests").json()) == 1


def test_each_visitor_gets_a_file_of_their_own_and_the_shared_database_is_untouched(
    demo_env,
):
    alice, bob = _visitor(), _visitor()
    _start(alice)
    _start(bob)
    _raw(alice)
    _raw(bob)

    files = sorted((demo_env / "sandboxes").glob("*.db"))
    assert len(files) == 2
    assert not (demo_env / "shared.db").exists()


def test_a_returning_visitor_keeps_their_workspace(demo_env):
    visitor = _visitor()
    _start(visitor)
    request_id = _raw(visitor)

    response = visitor.post("/session")
    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    assert visitor.get(f"/requests/{request_id}").status_code == 200


def test_audit_entries_name_an_unverified_demo_visitor(demo_env):
    visitor = _visitor()
    _start(visitor)
    request_id = _raw(visitor)

    actors = [e["detail"]["actor"] for e in visitor.get(f"/requests/{request_id}").json()["audit_log"]]
    assert actors
    for actor in actors:
        assert actor == {"email": "anonymous visitor", "method": "demo", "verified": False}


def test_a_tampered_cookie_is_refused(demo_env):
    visitor = _visitor()
    _start(visitor)
    token = visitor.cookies[COOKIE_NAME]
    workspace_id, signature = token.split(".")
    other_id = ("0" if workspace_id[0] != "0" else "1") + workspace_id[1:]

    forger = _visitor()
    forger.cookies.set(COOKIE_NAME, f"{other_id}.{signature}")
    assert forger.get("/requests").status_code == 401


def test_a_cookie_signed_with_another_key_is_refused(demo_env):
    forger = _visitor()
    forger.cookies.set(COOKIE_NAME, sign_workspace("a" * 32, "some-other-key-" + "y" * 32))
    assert forger.get("/requests").status_code == 401


@pytest.mark.parametrize("secret", ["", "too-short"])
def test_demo_mode_without_a_strong_signing_key_fails_closed(demo_env, monkeypatch, secret):
    monkeypatch.setenv("DEMO_COOKIE_SECRET", secret)
    get_settings.cache_clear()
    visitor = _visitor()
    assert visitor.post("/session").status_code == 503
    assert visitor.get("/requests").status_code == 401


def test_sessions_exist_only_in_demo_mode(storage, client):
    assert client.post("/session").status_code == 404


@pytest.mark.parametrize("bad_id", ["../shared", "A" * 32, "a" * 31, "", "a" * 32 + "/x"])
def test_a_workspace_id_that_is_not_32_hex_characters_never_becomes_a_path(
    demo_env, bad_id
):
    with pytest.raises(ValueError):
        workspace_storage(bad_id)


def test_the_local_frontend_may_send_the_session_cookie(demo_env):
    response = _visitor().options(
        "/requests",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"
