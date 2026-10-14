"""The proxy secret is required in demo mode (docs/adr/0010, TASKS D5).

The browser reaches the demo backend only through the frontend host's proxy, which adds
the secret and the visitor's address. Without the secret the backend could be called
directly, around the proxy, with any address a caller cared to write. So in demo mode
every route but /health refuses a request that lacks it, before any route runs, and a
deploy that forgot to configure it refuses everything. Local mode is unchanged. Nothing
here calls a model.
"""

import pytest

from app.config import get_settings
from app.routes import PROXY_SECRET_HEADER

from .conftest import PROXY_SECRET, bare_client, demo_client


def _documented_routes():
    from app.main import app

    for path, operations in app.openapi()["paths"].items():
        for method in operations:
            yield method.upper(), path.replace("{request_id}", "1")


def test_without_the_secret_every_route_but_health_is_refused_and_writes_nothing(
    demo_env, monkeypatch
):
    monkeypatch.setenv("DEMO_ECHO_ROUTE", "true")
    get_settings.cache_clear()
    routes = [route for route in _documented_routes() if route[1] != "/health"]
    assert len(routes) > 10

    client = bare_client()
    for method, path in routes:
        response = client.request(method, path, json={})
        assert response.status_code == 403, (method, path, response.status_code)
        assert "set-cookie" not in response.headers, (method, path)

    assert list((demo_env / "sandboxes").glob("*")) == []


@pytest.mark.parametrize("path", ["/docs", "/openapi.json", "/no-such-route"])
def test_it_stands_in_front_of_routing_so_undocumented_paths_are_refused_too(
    demo_env, path
):
    assert bare_client().get(path).status_code == 403


def test_health_answers_without_the_secret_for_the_hosts_health_check(demo_env):
    assert bare_client().get("/health").status_code == 200


def test_a_wrong_secret_is_refused(demo_env):
    wrong = {PROXY_SECRET_HEADER: PROXY_SECRET[:-1] + "z"}
    response = bare_client(**wrong).post("/session")
    assert response.status_code == 403
    assert response.json() == {"detail": "this service answers only through the demo site"}


def test_with_the_secret_a_visitor_gets_through(demo_env):
    visitor = demo_client()
    assert visitor.post("/session").status_code == 200
    assert visitor.get("/requests").json() == []


def test_demo_mode_without_a_configured_secret_refuses_everything_but_health(
    demo_env, monkeypatch
):
    monkeypatch.setenv("DEMO_PROXY_SECRET", "")
    get_settings.cache_clear()
    for client in (bare_client(), bare_client(**{PROXY_SECRET_HEADER: ""}), demo_client()):
        response = client.post("/session")
        assert response.status_code == 503
        assert response.json() == {"detail": "the demo's proxy secret is not configured"}
    assert bare_client().get("/health").status_code == 200


def test_local_mode_needs_no_secret(client):
    assert client.get("/requests").status_code == 200
