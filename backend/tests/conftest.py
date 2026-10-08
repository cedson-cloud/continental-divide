"""Shared fixtures.

Each test that touches persistence gets a throwaway SQLite file under pytest's
``tmp_path``, and the Anthropic and Notion env vars are blanked so nothing in the
suite can reach the network or spend API credits, regardless of what backend/.env
contains. Settings and storage caches are cleared on the way in and out so state
never leaks between tests.

Every audit entry needs an actor, so the storage fixture is bound to a fictional tester,
and the client runs in local auth mode as the same person.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.identity import Identity
from app.storage import get_storage, reset_storage, workspace_storage

TESTER_EMAIL = "tester@example.com"
TESTER = Identity(email=TESTER_EMAIL, method="local", verified=False)


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("NOTION_TOKEN", "")
    monkeypatch.setenv("NOTION_APPROVAL_DB_ID", "")
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("LOCAL_IDENTITY_EMAIL", TESTER_EMAIL)
    get_settings.cache_clear()
    yield reset_storage().acting_as(TESTER)
    get_settings.cache_clear()
    get_storage.cache_clear()


@pytest.fixture
def client(storage):
    from app.main import app

    return TestClient(app)


DEMO_SECRET = "test-only-signing-key-" + "x" * 32


@pytest.fixture
def demo_env(tmp_path, monkeypatch):
    """The public demo's configuration (docs/adr/0010), every path under ``tmp_path``.
    Yields ``tmp_path``. The model key is blank, so nothing can spend."""
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.setenv("DEMO_COOKIE_SECRET", DEMO_SECRET)
    monkeypatch.setenv("DEMO_COOKIE_SECURE", "false")
    monkeypatch.setenv("SANDBOX_DIR", str(tmp_path / "sandboxes"))
    monkeypatch.setenv("SPEND_LEDGER_PATH", str(tmp_path / "spend.db"))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "shared.db"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("NOTION_TOKEN", "")
    monkeypatch.setenv("NOTION_APPROVAL_DB_ID", "")
    # The intake limiter lives for the whole process; a fresh one keeps earlier tests'
    # drafts from counting against these.
    from app.rate_limit import RateLimiter

    monkeypatch.setattr("app.routes._limiter", RateLimiter(10, 60))
    _clear_demo_caches()
    yield tmp_path
    _clear_demo_caches()


def _clear_demo_caches():
    from app.routes import _session_limiters

    get_settings.cache_clear()
    get_storage.cache_clear()
    workspace_storage.cache_clear()
    _session_limiters.cache_clear()
