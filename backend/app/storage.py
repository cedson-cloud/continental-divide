"""Persistence behind a thin interface.

The rest of the app talks to a :class:`Storage` instance and never writes SQL inline,
so a Postgres-backed implementation can replace :class:`SqliteStorage` later without
touching callers. The audit log is append-only: there are read and append helpers and
no update or delete, and database triggers reject any attempt to mutate audit rows.
"""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from .config import get_settings

_REPO_ROOT = Path(__file__).resolve().parents[2]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS event_request (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_intake_text TEXT NOT NULL,
    parsed_definition TEXT,
    category TEXT,
    status TEXT NOT NULL,
    pii_flagged INTEGER NOT NULL DEFAULT 0,
    pii_details TEXT,
    duplicate_candidates TEXT,
    submitter_name TEXT,
    submitter_team TEXT,
    call_type TEXT,
    side TEXT,
    business_value TEXT,
    needed_by TEXT,
    request_kind TEXT,
    existing_event TEXT,
    destinations TEXT,
    published_artifact TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL REFERENCES event_request(id),
    step TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TRIGGER IF NOT EXISTS audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only');
END;

CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only');
END;
"""


class Storage(ABC):
    @abstractmethod
    def create_request(
        self,
        raw_intake_text: str,
        parsed_definition: Optional[dict] = None,
        category: Optional[str] = None,
        status: str = "pending_approval",
        submitter_name: Optional[str] = None,
        submitter_team: Optional[str] = None,
        call_type: Optional[str] = None,
        side: Optional[str] = None,
        business_value: Optional[str] = None,
        needed_by: Optional[str] = None,
        request_kind: Optional[str] = None,
        existing_event: Optional[str] = None,
        destinations: Optional[list] = None,
    ) -> int:
        ...

    @abstractmethod
    def get_request(self, request_id: int) -> Optional[dict]:
        ...

    @abstractmethod
    def list_requests(self) -> list:
        ...

    @abstractmethod
    def update_request_status(self, request_id: int, status: str) -> None:
        ...

    @abstractmethod
    def set_parsed_definition(
        self, request_id: int, parsed_definition: dict, category: str
    ) -> None:
        ...

    @abstractmethod
    def set_pii_flags(
        self, request_id: int, pii_flagged: bool, pii_details: str
    ) -> None:
        ...

    @abstractmethod
    def set_duplicate_candidates(
        self, request_id: int, candidates: list[dict]
    ) -> None:
        ...

    @abstractmethod
    def set_publish_result(self, request_id: int, artifact: dict) -> None:
        ...

    @abstractmethod
    def add_audit_entry(
        self, request_id: int, step: str, detail: Optional[dict] = None
    ) -> int:
        ...

    @abstractmethod
    def get_audit_log(self, request_id: int) -> list:
        ...


class SqliteStorage(Storage):
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            # CREATE TABLE IF NOT EXISTS does not add columns to a database created
            # before they existed in the schema above.
            existing = {
                row[1] for row in conn.execute("PRAGMA table_info(event_request)")
            }
            for column in (
                "business_value",
                "needed_by",
                "request_kind",
                "existing_event",
                "destinations",
                "duplicate_candidates",
            ):
                if column not in existing:
                    conn.execute(f"ALTER TABLE event_request ADD COLUMN {column} TEXT")

    def create_request(
        self,
        raw_intake_text: str,
        parsed_definition: Optional[dict] = None,
        category: Optional[str] = None,
        status: str = "pending_approval",
        submitter_name: Optional[str] = None,
        submitter_team: Optional[str] = None,
        call_type: Optional[str] = None,
        side: Optional[str] = None,
        business_value: Optional[str] = None,
        needed_by: Optional[str] = None,
        request_kind: Optional[str] = None,
        existing_event: Optional[str] = None,
        destinations: Optional[list] = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO event_request "
                "(raw_intake_text, parsed_definition, category, status, "
                "submitter_name, submitter_team, call_type, side, "
                "business_value, needed_by, request_kind, existing_event, destinations) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    raw_intake_text,
                    json.dumps(parsed_definition) if parsed_definition else None,
                    category,
                    status,
                    submitter_name,
                    submitter_team,
                    call_type,
                    side,
                    business_value,
                    needed_by,
                    request_kind,
                    existing_event,
                    json.dumps(destinations) if destinations else None,
                ),
            )
            return int(cursor.lastrowid)

    def get_request(self, request_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM event_request WHERE id = ?", (request_id,)
            ).fetchone()
        return self._request_row(row) if row else None

    def list_requests(self) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM event_request ORDER BY id"
            ).fetchall()
        return [self._request_row(row) for row in rows]

    def update_request_status(self, request_id: int, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE event_request SET status = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (status, request_id),
            )

    def set_parsed_definition(
        self, request_id: int, parsed_definition: dict, category: str
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE event_request "
                "SET parsed_definition = ?, category = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (json.dumps(parsed_definition), category, request_id),
            )

    def set_pii_flags(
        self, request_id: int, pii_flagged: bool, pii_details: str
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE event_request "
                "SET pii_flagged = ?, pii_details = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (1 if pii_flagged else 0, pii_details, request_id),
            )

    def set_duplicate_candidates(
        self, request_id: int, candidates: list[dict]
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE event_request "
                "SET duplicate_candidates = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (json.dumps(candidates), request_id),
            )

    def set_publish_result(self, request_id: int, artifact: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE event_request "
                "SET published_artifact = ?, updated_at = datetime('now') WHERE id = ?",
                (json.dumps(artifact), request_id),
            )

    def add_audit_entry(
        self, request_id: int, step: str, detail: Optional[dict] = None
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO audit_log (request_id, step, detail) VALUES (?, ?, ?)",
                (request_id, step, json.dumps(detail) if detail is not None else None),
            )
            return int(cursor.lastrowid)

    def get_audit_log(self, request_id: int) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE request_id = ? ORDER BY id",
                (request_id,),
            ).fetchall()
        return [self._audit_row(row) for row in rows]

    @staticmethod
    def _request_row(row: sqlite3.Row) -> dict:
        data: dict[str, Any] = dict(row)
        data["pii_flagged"] = bool(data.get("pii_flagged"))
        data["duplicate_candidates"] = (
            json.loads(data["duplicate_candidates"])
            if data.get("duplicate_candidates")
            else []
        )
        if data.get("parsed_definition"):
            data["parsed_definition"] = json.loads(data["parsed_definition"])
        if data.get("published_artifact"):
            data["published_artifact"] = json.loads(data["published_artifact"])
        if data.get("destinations"):
            data["destinations"] = json.loads(data["destinations"])
        return data

    @staticmethod
    def _audit_row(row: sqlite3.Row) -> dict:
        data: dict[str, Any] = dict(row)
        if data.get("detail") is not None:
            data["detail"] = json.loads(data["detail"])
        return data


def _resolve_db_path() -> Path:
    raw = get_settings().database_path
    path = Path(raw)
    return path if path.is_absolute() else _REPO_ROOT / path


@lru_cache
def get_storage() -> Storage:
    return SqliteStorage(_resolve_db_path())


def reset_storage() -> Storage:
    """Drop and recreate the tables. For demos and tests, not request handling."""
    get_storage.cache_clear()
    path = _resolve_db_path()
    if path.exists():
        path.unlink()
    return get_storage()
