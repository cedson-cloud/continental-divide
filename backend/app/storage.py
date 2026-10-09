"""Persistence behind a thin interface.

The rest of the app talks to a :class:`Storage` instance and never writes SQL inline,
so a Postgres-backed implementation can replace :class:`SqliteStorage` later without
touching callers. The audit log is append-only: there are read and append helpers and
no update or delete, and database triggers reject any attempt to mutate audit rows.

Every audit entry names its actor. A storage writes entries only once it has been bound to
the acting identity with :meth:`Storage.acting_as`; the actor is recorded inside each
entry's detail, so the audit_log table itself is unchanged.
"""

from __future__ import annotations

import copy
import json
import os
import sqlite3
import time
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Any, Collection, Optional

from .config import get_settings, repo_path
from .identity import Identity
from .workspace import is_workspace_id

_SCHEMA = """
CREATE TABLE IF NOT EXISTS event_request (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_intake_text TEXT NOT NULL,
    parsed_definition TEXT,
    category TEXT,
    status TEXT NOT NULL,
    pii_flagged INTEGER NOT NULL DEFAULT 0,
    pii_details TEXT,
    pii_reasons TEXT,
    duplicate_candidates TEXT,
    submitter_name TEXT,
    submitter_team TEXT,
    call_type TEXT,
    side TEXT,
    business_value TEXT,
    urgent INTEGER NOT NULL DEFAULT 0,
    urgency_reason TEXT,
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


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Add any event_request column the schema declares but the live table lacks.

    CREATE TABLE IF NOT EXISTS never alters an existing table, so a database created
    under an older schema silently misses new columns. Idempotent: a column is only
    added when absent. Touches event_request only — never audit_log or its
    append-only triggers.
    """
    declared = sqlite3.connect(":memory:")
    try:
        declared.executescript(_SCHEMA)
        wanted = declared.execute("PRAGMA table_info(event_request)").fetchall()
    finally:
        declared.close()
    existing = {row[1] for row in conn.execute("PRAGMA table_info(event_request)")}
    for _cid, name, col_type, notnull, default, pk in wanted:
        if name in existing or pk:
            continue
        clause = f"ALTER TABLE event_request ADD COLUMN {name} {col_type}"
        if notnull:
            clause += " NOT NULL"
        if default is not None:
            clause += f" DEFAULT ({default})"
        conn.execute(clause)


class UnattributedAuditEntry(Exception):
    """An audit entry was written with no actor bound to the storage."""


class RequestQuotaReached(Exception):
    """A demo sandbox already holds as many requests as it is allowed (docs/adr/0010)."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"this sandbox has used all {limit} requests the demo allows")
        self.limit = limit


class Storage(ABC):
    @abstractmethod
    def acting_as(self, identity: Identity) -> "Storage":
        """The same storage, recording ``identity`` as the actor of every audit entry."""
        ...

    @property
    @abstractmethod
    def actor(self) -> Optional[Identity]:
        """The identity bound by :meth:`acting_as`, or None if none is bound."""
        ...

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
        urgent: bool = False,
        urgency_reason: Optional[str] = None,
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
    def transition(
        self, request_id: int, from_statuses: Collection[str], to_status: str
    ) -> bool:
        """Move the request to ``to_status`` only if its status is still one of
        ``from_statuses``, as one atomic step. False means someone else moved it first."""
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
    def set_pii_reasons(self, request_id: int, reasons: dict[str, str]) -> None:
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
    def __init__(self, db_path: Path, max_requests: Optional[int] = None) -> None:
        self.db_path = db_path
        self.max_requests = max_requests
        self._actor: Optional[Identity] = None
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def acting_as(self, identity: Identity) -> "SqliteStorage":
        bound = copy.copy(self)
        bound._actor = identity
        return bound

    @property
    def actor(self) -> Optional[Identity]:
        return self._actor

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            _ensure_columns(conn)

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
        urgent: bool = False,
        urgency_reason: Optional[str] = None,
        needed_by: Optional[str] = None,
        request_kind: Optional[str] = None,
        existing_event: Optional[str] = None,
        destinations: Optional[list] = None,
    ) -> int:
        # One statement, so the count and the insert cannot be split by a second
        # request arriving at the same moment.
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO event_request "
                "(raw_intake_text, parsed_definition, category, status, "
                "submitter_name, submitter_team, call_type, side, "
                "business_value, urgent, urgency_reason, needed_by, "
                "request_kind, existing_event, destinations) "
                "SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? "
                "WHERE ? IS NULL OR (SELECT COUNT(*) FROM event_request) < ?",
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
                    1 if urgent else 0,
                    urgency_reason,
                    needed_by,
                    request_kind,
                    existing_event,
                    json.dumps(destinations) if destinations else None,
                    self.max_requests,
                    self.max_requests,
                ),
            )
            if cursor.rowcount == 0:
                raise RequestQuotaReached(self.max_requests)
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

    def transition(
        self, request_id: int, from_statuses: Collection[str], to_status: str
    ) -> bool:
        expected = list(from_statuses)
        placeholders = ", ".join("?" for _ in expected)
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE event_request SET status = ?, updated_at = datetime('now') "
                f"WHERE id = ? AND status IN ({placeholders})",
                (to_status, request_id, *expected),
            )
            return cursor.rowcount == 1

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

    def set_pii_reasons(self, request_id: int, reasons: dict[str, str]) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE event_request "
                "SET pii_reasons = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (json.dumps(reasons), request_id),
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
        if self._actor is None:
            raise UnattributedAuditEntry(
                f"'{step}' on request {request_id} has no actor; bind one with acting_as()"
            )
        if detail and "actor" in detail:
            raise ValueError(f"'{step}' detail may not set its own actor")
        actor = self._actor
        detail = {
            **(detail or {}),
            "actor": {"email": actor.email, "method": actor.method, "verified": actor.verified},
        }
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO audit_log (request_id, step, detail) VALUES (?, ?, ?)",
                (request_id, step, json.dumps(detail)),
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
        data["urgent"] = bool(data.get("urgent"))
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
        if data.get("pii_reasons"):
            data["pii_reasons"] = json.loads(data["pii_reasons"])
        return data

    @staticmethod
    def _audit_row(row: sqlite3.Row) -> dict:
        data: dict[str, Any] = dict(row)
        if data.get("detail") is not None:
            data["detail"] = json.loads(data["detail"])
        return data


def _resolve_db_path() -> Path:
    return repo_path(get_settings().database_path)


@lru_cache
def get_storage() -> Storage:
    return SqliteStorage(_resolve_db_path())


def _sandbox_path(workspace_id: str) -> Path:
    if not is_workspace_id(workspace_id):
        raise ValueError("a workspace id is 32 lowercase hex characters")
    return repo_path(get_settings().sandbox_dir) / f"{workspace_id}.db"


@lru_cache(maxsize=256)
def workspace_storage(workspace_id: str) -> Storage:
    """A demo visitor's sandbox: a SQLite file of its own under SANDBOX_DIR (docs/adr/0010).
    Discarding a sandbox removes the file; nothing ever deletes audit rows."""
    return SqliteStorage(
        _sandbox_path(workspace_id),
        max_requests=get_settings().demo_requests_per_visitor,
    )


def use_sandbox(workspace_id: str) -> Storage:
    """A visitor's sandbox, marked as used now. Reads leave a SQLite file's modified time
    alone, so it is set here: that time is what :func:`discard_idle_sandboxes` reads."""
    storage = workspace_storage(workspace_id)
    os.utime(_sandbox_path(workspace_id))
    return storage


def discard_idle_sandboxes() -> list[str]:
    """Delete every sandbox unused for DEMO_SANDBOX_IDLE_DAYS, a whole file at a time, and
    return their workspace ids. No row is deleted, so the audit log's triggers never need an
    exception (docs/adr/0010). Only files named by a workspace id are ever touched."""
    settings = get_settings()
    directory = repo_path(settings.sandbox_dir)
    if not directory.is_dir():
        return []
    cutoff = time.time() - settings.demo_sandbox_idle_days * 24 * 60 * 60
    discarded = []
    for path in sorted(directory.glob("*.db")):
        if not is_workspace_id(path.stem) or path.stat().st_mtime > cutoff:
            continue
        path.unlink(missing_ok=True)
        path.with_name(f"{path.name}-journal").unlink(missing_ok=True)
        discarded.append(path.stem)
    if discarded:
        workspace_storage.cache_clear()
    return discarded


def reset_storage() -> Storage:
    """Drop and recreate the tables. For demos and tests, not request handling."""
    get_storage.cache_clear()
    path = _resolve_db_path()
    if path.exists():
        path.unlink()
    return get_storage()
