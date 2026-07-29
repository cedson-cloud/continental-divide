"""The intake-form contract: schema migration, urgency, needed_by, required
submitter fields, and the "Unsure" side value.

Everything runs offline. HTTP cases go through /requests/raw, which skips the
model; the POST /requests cases assert only the validation layer, which rejects
before any model call could happen.
"""

import json
import sqlite3
from pathlib import Path

from app.storage import _ensure_columns

CLEAN_EXAMPLE = Path(__file__).parents[1] / "examples" / "clean_cart_cleared.json"


def _post_raw(client, **overrides):
    payload = {
        "definition": json.loads(CLEAN_EXAMPLE.read_text()),
        "business_value": "measures cart abandonment",
        **overrides,
    }
    return client.post("/requests/raw", json=payload)


def _old_style_table(tmp_path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "old.db")
    conn.execute(
        "CREATE TABLE event_request ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "raw_intake_text TEXT NOT NULL, "
        "status TEXT NOT NULL, "
        "created_at TEXT NOT NULL DEFAULT (datetime('now')), "
        "updated_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    return conn


def _columns(conn) -> set:
    return {row[1] for row in conn.execute("PRAGMA table_info(event_request)")}


def test_ensure_columns_adds_missing_columns(tmp_path):
    conn = _old_style_table(tmp_path)
    _ensure_columns(conn)
    added = _columns(conn)
    assert "urgent" in added
    assert "urgency_reason" in added
    assert "needed_by" in added
    # NOT NULL DEFAULT 0 must hold for rows inserted after the migration.
    conn.execute(
        "INSERT INTO event_request (raw_intake_text, status) VALUES ('x', 'draft')"
    )
    assert conn.execute("SELECT urgent FROM event_request").fetchone()[0] == 0
    conn.close()


def test_ensure_columns_second_call_is_noop(tmp_path):
    conn = _old_style_table(tmp_path)
    _ensure_columns(conn)
    first = _columns(conn)
    _ensure_columns(conn)
    assert _columns(conn) == first
    conn.close()


def test_needed_by_rejects_non_iso(client):
    assert _post_raw(client, needed_by="mid-August").status_code == 422


def test_needed_by_accepts_iso_date(client):
    response = _post_raw(client, needed_by="2026-08-15")
    assert response.status_code == 200
    detail = client.get(f"/requests/{response.json()['id']}").json()
    assert detail["needed_by"] == "2026-08-15"


def test_needed_by_stays_optional(client):
    assert _post_raw(client).status_code == 200
    assert _post_raw(client, needed_by="").status_code == 200


def test_urgent_without_reason_is_422(client):
    assert _post_raw(client, urgent=True).status_code == 422
    assert _post_raw(client, urgent=True, urgency_reason="  ").status_code == 422


def test_urgent_with_reason_round_trips(client):
    response = _post_raw(
        client, urgent=True, urgency_reason="the August launch blocks on this"
    )
    assert response.status_code == 200
    detail = client.get(f"/requests/{response.json()['id']}").json()
    assert detail["urgent"] is True
    assert detail["urgency_reason"] == "the August launch blocks on this"


def test_not_urgent_needs_no_reason(client):
    response = _post_raw(client)
    assert response.status_code == 200
    detail = client.get(f"/requests/{response.json()['id']}").json()
    assert detail["urgent"] is False


def test_submitter_fields_required_on_intake(client):
    body = {"raw_intake_text": "track a thing", "business_value": "worth knowing"}
    assert client.post("/requests", json=body).status_code == 422
    assert (
        client.post(
            "/requests", json={**body, "submitter_team": "Product"}
        ).status_code
        == 422
    )
    assert (
        client.post("/requests", json={**body, "submitter_name": "Ada"}).status_code
        == 422
    )


def test_submitter_fields_stay_optional_on_raw(client):
    assert _post_raw(client).status_code == 200


def test_side_unsure_round_trips(client):
    response = _post_raw(client, side="Unsure")
    assert response.status_code == 200
    detail = client.get(f"/requests/{response.json()['id']}").json()
    assert detail["side"] == "Unsure"
