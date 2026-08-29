"""
SQLite connection helper for Relict Core's run persistence layer.

This module owns the low-level SQLite plumbing:
  - opening a connection with safe pragmas
  - creating (or verifying) the run-store schema

It is deliberately thin: no ORM, no migration framework, no connection pool.
The schema stores existing Pydantic models as JSON blobs so the persistence
layer stays decoupled from the model internals — a field rename in RunState
only requires a deserialization round-trip, not a schema migration.

Usage
-----
::

    from app.cache.sqlite_client import open_connection, ensure_schema

    conn = open_connection(Path("data/relict.db"))
    ensure_schema(conn)

The caller is responsible for closing the connection when it is no longer
needed (typically in the FastAPI ``lifespan`` shutdown section).

Phase 2D scope
--------------
Single SQLite file, WAL journal mode (safe for one writer + concurrent
readers), no connection pool.  This is acceptable for Phase 2D because
``RunOrchestrator.execute()`` is still called inline (no background workers).
Phase 2E will add concurrent-run handling; at that point single-writer SQLite
contention may need revisiting (flag: WAL allows one writer at a time — if
multiple pipeline runs execute truly concurrently, writes will queue).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def open_connection(path: Path) -> sqlite3.Connection:
    """
    Open a ``sqlite3.Connection`` to *path*, creating parent directories if
    needed.  Returns the connection with WAL journal mode and foreign-key
    enforcement enabled.

    Parameters
    ----------
    path:
        Filesystem path to the SQLite database file.  Use
        ``Path(":memory:")`` for an in-memory database (useful in tests).

    Returns
    -------
    sqlite3.Connection
        A connection ready for use.  The caller owns the connection and is
        responsible for closing it.
    """
    # Create parent directories for real file paths (skip for ":memory:").
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path), check_same_thread=False)

    # WAL mode: allows concurrent readers while a write is in progress.
    conn.execute("PRAGMA journal_mode=WAL")
    # Enforce FK constraints (SQLite disables them by default).
    conn.execute("PRAGMA foreign_keys=ON")

    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """
    Create the run-store tables if they do not already exist.

    Idempotent: safe to call on an already-initialized database.

    Tables
    ------
    ``run_states``
        Latest ``RunState`` per run, stored as a JSON blob.
    ``run_results``
        Final ``RunResult`` per run, stored as a JSON blob.

    Both tables record an ``updated_at`` timestamp (UTC ISO-8601) so that
    a future cleanup or audit pass can age-out stale entries without
    needing to parse the JSON.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS run_states (
            run_id     TEXT PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS run_results (
            run_id      TEXT PRIMARY KEY,
            result_json TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );
        """
    )
    conn.commit()


def _utcnow_iso() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(tz=UTC).isoformat()
