"""GET /demo/echo: what reaches the backend through the frontend host's proxy
(docs/adr/0010, TASKS D5).

Off by default and 404 when off. On, it names the forwarding headers and cookies that
arrived and echoes the address candidates, so the right DEMO_CLIENT_IP_HEADER can be
chosen from evidence. It reports whether the proxy secret matched as a boolean and never
echoes the secret or a cookie value. It needs no identity, because the point is to check
the path before a visitor has one. Nothing here calls a model.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.routes import ECHO_COOKIE, IP_HEADER_CANDIDATES, PROXY_SECRET_HEADER

from .conftest import DEMO_SECRET

PROXY_SECRET = "proxy-secret-for-tests-" + "y" * 32


def _client(**headers) -> TestClient:
    from app.main import app

    return TestClient(app, headers=headers)


@pytest.fixture
def echo_on(demo_env, monkeypatch):
    monkeypatch.setenv("DEMO_ECHO_ROUTE", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_the_route_is_off_by_default(demo_env):
    assert _client().get("/demo/echo").status_code == 404


def test_the_route_is_off_in_local_mode_too(storage):
    assert _client().get("/demo/echo").status_code == 404


def test_on_it_names_forwarding_headers_and_echoes_the_address_candidates(echo_on):
    response = _client(
        **{
            "x-forwarded-for": "203.0.113.7, 10.0.0.1",
            "x-real-ip": "203.0.113.7",
            "x-vercel-forwarded-for": "203.0.113.7",
            "x-forwarded-proto": "https",
            "accept": "application/json",
        }
    ).get("/demo/echo")
    assert response.status_code == 200
    body = response.json()
    assert body["forwarding_headers"] == [
        "x-forwarded-for",
        "x-forwarded-proto",
        "x-real-ip",
        "x-vercel-forwarded-for",
    ]
    assert body["ip_candidates"] == {
        "x-real-ip": "203.0.113.7",
        "x-vercel-forwarded-for": "203.0.113.7",
        "x-forwarded-for": "203.0.113.7, 10.0.0.1",
    }
    assert set(body["ip_candidates"]) == set(IP_HEADER_CANDIDATES)
    assert body["socket_address"] == "testclient"
    assert body["configured_ip_header"] is None
    assert body["limiter_address"] == "testclient"


def test_a_missing_candidate_is_null_not_absent(echo_on):
    body = _client().get("/demo/echo").json()
    assert body["ip_candidates"] == {name: None for name in IP_HEADER_CANDIDATES}
    assert body["forwarding_headers"] == []


def test_it_shows_what_the_limiter_would_key_on(echo_on, monkeypatch):
    monkeypatch.setenv("DEMO_CLIENT_IP_HEADER", "x-real-ip")
    get_settings.cache_clear()
    body = _client(**{"x-real-ip": "203.0.113.9"}).get("/demo/echo").json()
    assert body["configured_ip_header"] == "x-real-ip"
    assert body["limiter_address"] == "203.0.113.9"


def test_it_sets_a_probe_cookie_and_reports_cookie_names_on_the_way_back(echo_on):
    client = _client()
    first = client.get("/demo/echo")
    assert first.json()["cookie_names"] == []
    set_cookie = first.headers["set-cookie"]
    assert set_cookie.startswith(f"{ECHO_COOKIE}=")
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Secure" not in set_cookie, "DEMO_COOKIE_SECURE=false in the demo fixture"

    client.post("/session")
    second = client.get("/demo/echo")
    assert second.json()["cookie_names"] == [ECHO_COOKIE, "cd_workspace"]


def test_the_probe_cookie_is_secure_by_default(echo_on, monkeypatch):
    monkeypatch.setenv("DEMO_COOKIE_SECURE", "true")
    get_settings.cache_clear()
    assert "Secure" in _client().get("/demo/echo").headers["set-cookie"]


def test_the_secret_matches_only_when_configured_and_sent(echo_on, monkeypatch):
    assert _client().get("/demo/echo").json()["proxy_secret_matched"] is False
    sent = {PROXY_SECRET_HEADER: PROXY_SECRET}
    assert _client(**sent).get("/demo/echo").json()["proxy_secret_matched"] is False, (
        "unconfigured never matches"
    )

    monkeypatch.setenv("DEMO_PROXY_SECRET", PROXY_SECRET)
    get_settings.cache_clear()
    assert _client(**sent).get("/demo/echo").json()["proxy_secret_matched"] is True
    assert _client().get("/demo/echo").json()["proxy_secret_matched"] is False
    wrong = {PROXY_SECRET_HEADER: PROXY_SECRET[:-1] + "z"}
    assert _client(**wrong).get("/demo/echo").json()["proxy_secret_matched"] is False


def test_no_secret_or_cookie_value_ever_appears_in_the_body(echo_on, monkeypatch):
    monkeypatch.setenv("DEMO_PROXY_SECRET", PROXY_SECRET)
    get_settings.cache_clear()
    client = _client(**{PROXY_SECRET_HEADER: PROXY_SECRET})
    client.post("/session")
    workspace_cookie = client.cookies["cd_workspace"]
    text = client.get("/demo/echo").text
    assert PROXY_SECRET not in text
    assert DEMO_SECRET not in text
    assert workspace_cookie not in text
    assert PROXY_SECRET_HEADER not in text, "the secret header is not a forwarding header"
