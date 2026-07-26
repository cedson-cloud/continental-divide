"""Shared fixtures.

Each test that touches persistence gets a throwaway SQLite file under pytest's
``tmp_path``, and the Anthropic and Notion env vars are blanked so nothing in the
suite can reach the network or spend API credits, regardless of what backend/.env
contains. Settings and storage caches are cleared on the way in and out so state
never leaks between tests.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.storage import get_storage, reset_storage


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("NOTION_TOKEN", "")
    monkeypatch.setenv("NOTION_APPROVAL_DB_ID", "")
    get_settings.cache_clear()
    yield reset_storage()
    get_settings.cache_clear()
    get_storage.cache_clear()


@pytest.fixture
def client(storage):
    from app.main import app

    return TestClient(app)
