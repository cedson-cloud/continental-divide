"""The public demo never pushes to Notion, and a sandbox unused for 7 days is discarded
(docs/adr/0010, TASKS D4).

Expiry deletes the sandbox's whole file. No row is ever deleted, so the audit log's
append-only triggers stay exactly as they are. The model and Notion are faked throughout —
no test here can reach the network.
"""

import os
import re
import time

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.storage import discard_idle_sandboxes
from app.workspace import COOKIE_NAME, new_workspace_id

from .test_spend_controls import _draft, _fake_model, _raw, priced  # noqa: F401

DAY = 24 * 60 * 60


def _visitor() -> TestClient:
    from app.main import app

    client = TestClient(app)
    assert client.post("/session").status_code == 200
    return client


def _workspace(client: TestClient) -> str:
    return client.cookies[COOKIE_NAME].split(".")[0]


def _sandbox_file(demo_env, workspace_id: str):
    return demo_env / "sandboxes" / f"{workspace_id}.db"


def _age(path, days: float) -> None:
    then = time.time() - days * DAY
    os.utime(path, (then, then))


# --- Notion is off ----------------------------------------------------------------------


@pytest.fixture
def notion_configured(monkeypatch):
    """A Notion token and board are configured, and every client Notion would build is
    recorded instead of reaching the network."""
    monkeypatch.setenv("NOTION_TOKEN", "test-token-not-real")
    monkeypatch.setenv("NOTION_APPROVAL_DB_ID", "test-board")
    get_settings.cache_clear()
    built = []

    class FakeNotion:
        def __init__(self, auth=None):
            built.append(self)
            self.pages = self

        def create(self, **kwargs):
            return {"url": "https://notion.example/page"}

    monkeypatch.setattr("notion_client.Client", FakeNotion)
    return built


def _submit_a_draft(client: TestClient) -> list:
    drafted = _draft(client)
    assert drafted.status_code == 200, drafted.text
    request_id = drafted.json()["id"]
    submitted = client.post(f"/requests/{request_id}/submit")
    assert submitted.json()["status"] == "pending_approval"
    return client.get(f"/requests/{request_id}").json()["audit_log"]


def test_a_demo_submission_never_reaches_notion_even_with_a_token_set(
    priced, notion_configured, monkeypatch
):
    _fake_model(monkeypatch, [])
    audit_log = _submit_a_draft(_visitor())

    assert notion_configured == []
    assert not [e for e in audit_log if e["step"].startswith("notion_")]


def test_outside_the_demo_the_same_submission_does_push(
    storage, client, notion_configured, monkeypatch
):
    from app.rate_limit import RateLimiter

    monkeypatch.setattr("app.routes._limiter", RateLimiter(10, 60))
    _fake_model(monkeypatch, [])
    audit_log = _submit_a_draft(client)

    assert len(notion_configured) == 1
    assert "notion_pushed" in [e["step"] for e in audit_log]


# --- sandboxes expire ---------------------------------------------------------------


def test_a_sandbox_unused_for_seven_days_is_deleted_as_a_whole_file(demo_env):
    visitor = _visitor()
    _raw(visitor)
    path = _sandbox_file(demo_env, _workspace(visitor))
    _age(path, 7.1)

    assert discard_idle_sandboxes() == [_workspace(visitor)]
    assert not path.exists()


def test_a_sandbox_used_within_seven_days_is_kept(demo_env):
    visitor = _visitor()
    _raw(visitor)
    path = _sandbox_file(demo_env, _workspace(visitor))
    _age(path, 6.9)

    assert discard_idle_sandboxes() == []
    assert path.exists()


def test_viewing_a_sandbox_counts_as_using_it(demo_env):
    visitor = _visitor()
    _raw(visitor)
    path = _sandbox_file(demo_env, _workspace(visitor))
    _age(path, 7.1)

    assert visitor.get("/requests").status_code == 200

    assert discard_idle_sandboxes() == []
    assert len(visitor.get("/requests").json()) == 1


def test_using_a_sandbox_restarts_the_cookies_seven_days(demo_env):
    visitor = _visitor()
    response = visitor.get("/requests")

    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith(f"{COOKIE_NAME}={visitor.cookies[COOKIE_NAME]};")
    assert re.search(r"Max-Age=604800\b", set_cookie)
    assert "HttpOnly" in set_cookie


def test_the_idle_period_follows_configuration(demo_env, monkeypatch):
    monkeypatch.setenv("DEMO_SANDBOX_IDLE_DAYS", "2")
    get_settings.cache_clear()
    visitor = _visitor()
    _raw(visitor)
    _age(_sandbox_file(demo_env, _workspace(visitor)), 2.1)

    assert discard_idle_sandboxes() == [_workspace(visitor)]
    assert "Max-Age=172800" in visitor.get("/requests").headers["set-cookie"]


def test_issuing_a_new_sandbox_discards_idle_ones(demo_env):
    old = _visitor()
    _raw(old)
    path = _sandbox_file(demo_env, _workspace(old))
    _age(path, 8)

    _visitor()

    assert not path.exists()


def test_a_visitor_returning_after_expiry_finds_an_empty_sandbox(demo_env):
    visitor = _visitor()
    _raw(visitor)
    assert len(visitor.get("/requests").json()) == 1
    _age(_sandbox_file(demo_env, _workspace(visitor)), 8)

    discard_idle_sandboxes()

    assert visitor.get("/requests").json() == []
    assert _raw(visitor).status_code == 200


def test_only_files_named_by_a_workspace_id_are_ever_deleted(demo_env):
    sandboxes = demo_env / "sandboxes"
    sandboxes.mkdir()
    bystanders = [sandboxes / "notes.db", sandboxes / ("A" * 32 + ".db"), sandboxes / "x.txt"]
    for path in bystanders:
        path.write_text("not a sandbox")
        _age(path, 30)
    (demo_env / "shared.db").write_text("the shared database")
    _age(demo_env / "shared.db", 30)

    assert discard_idle_sandboxes() == []
    assert all(path.exists() for path in bystanders)
    assert (demo_env / "shared.db").exists()


def test_a_leftover_journal_goes_with_its_sandbox(demo_env):
    workspace_id = new_workspace_id()
    sandboxes = demo_env / "sandboxes"
    sandboxes.mkdir()
    db, journal = sandboxes / f"{workspace_id}.db", sandboxes / f"{workspace_id}.db-journal"
    for path in (db, journal):
        path.write_bytes(b"")
        _age(path, 8)

    assert discard_idle_sandboxes() == [workspace_id]
    assert not db.exists() and not journal.exists()


def test_with_no_sandbox_directory_there_is_nothing_to_discard(demo_env):
    assert discard_idle_sandboxes() == []
