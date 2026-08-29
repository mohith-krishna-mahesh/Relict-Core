"""
SQLiteRunRepository — the SQLite-backed implementation of the run persistence
interface defined duck-typed in ``app/run_manager/repository.py``.

This file is intentionally separate from both:
- ``app/cache/sqlite_client.py`` (the connection helper / schema DDL), and
- ``app/run_manager/repository.py`` (``RunNotFoundError`` + the in-memory
  ``RunRepository`` that remains the test double for the rest of the suite).

The split keeps infrastructure code (SQLite wiring) out of the run-manager
package and keeps the in-memory implementation close to the protocol it
implements — both of which remain unchanged by Phase 2D.

Interface
---------
``SQLiteRunRepository`` exposes the same duck-typed interface as
``RunRepository``:

    save_state(state)   load_state(run_id)   all_states()
    save_result(result) load_result(run_id)  has_result(run_id)

All method signatures are identical.  ``RunOrchestrator`` holds a reference
typed as ``RunRepository`` but accepts either implementation; it does not need
to change because this phase is a swap behind an existing interface.

Additionally ``list_run_ids()`` is provided — it returns ``list[str]`` of
all stored run IDs and is the name used in higher-level specs.  ``all_states``
remains the primary name so existing callers (routes, orchestrator, tests) are
unaffected.

Serialization
-------------
``RunState``  →  ``state.model_dump_json()``  →  TEXT column
``RunResult`` →  ``result.model_dump_json()`` →  TEXT column

Deserialized with ``RunState.model_validate_json(...)`` /
``RunResult.model_validate_json(...)``.  No second serialization scheme.

Upserts
-------
``save_state`` / ``save_result`` use ``INSERT ... ON CONFLICT(run_id) DO
UPDATE ...`` so calling save twice with the same ``run_id`` overwrites rather
than raising an integrity error — identical semantics to ``RunRepository``.

Concurrency note (Phase 2E)
---------------------------
WAL mode (set by ``open_connection`` in ``sqlite_client.py``) allows one
writer and multiple concurrent readers.  For Phase 2D this is sufficient
because ``RunOrchestrator.execute()`` runs inline.  Phase 2E will add
concurrent pipeline execution; SQLite serialises writes, so truly concurrent
runs will queue at the DB layer.  Evaluate whether an ``asyncio.Lock`` or a
process-safe backend is required at that point.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from app.models.responses import RunResult
from app.models.run_state import RunState
from app.run_manager.repository import RunNotFoundError


def _utcnow_iso() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(tz=UTC).isoformat()


class SQLiteRunRepository:
    """
    On-disk SQLite-backed run repository.

    Parameters
    ----------
    conn:
        An open ``sqlite3.Connection`` with the run-store schema already
        applied (call ``app.cache.sqlite_client.ensure_schema(conn)`` first).
        Pass ``sqlite3.connect(":memory:")`` for fast, filesystem-free unit
        tests without touching the real database or ``app.config.settings``.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # RunState
    # ------------------------------------------------------------------

    def save_state(self, state: RunState) -> None:
        """Persist (or overwrite) the ``RunState`` for ``state.run_id``."""
        self._conn.execute(
            """
            INSERT INTO run_states (run_id, state_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
            """,
            (state.run_id, state.model_dump_json(), _utcnow_iso()),
        )
        self._conn.commit()

    def load_state(self, run_id: str) -> RunState:
        """Return the latest ``RunState`` for *run_id*, or raise ``RunNotFoundError``."""
        row = self._conn.execute(
            "SELECT state_json FROM run_states WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise RunNotFoundError(run_id)
        return RunState.model_validate_json(row[0])

    def all_states(self) -> list[RunState]:
        """Return all currently stored ``RunState`` records."""
        rows = self._conn.execute("SELECT state_json FROM run_states").fetchall()
        return [RunState.model_validate_json(row[0]) for row in rows]

    def list_run_ids(self) -> list[str]:
        """Return all known run IDs (unordered)."""
        rows = self._conn.execute("SELECT run_id FROM run_states").fetchall()
        return [row[0] for row in rows]

    # ------------------------------------------------------------------
    # RunResult
    # ------------------------------------------------------------------

    def save_result(self, result: RunResult) -> None:
        """Persist (or overwrite) the ``RunResult`` for ``result.run_id``."""
        self._conn.execute(
            """
            INSERT INTO run_results (run_id, result_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                result_json = excluded.result_json,
                updated_at  = excluded.updated_at
            """,
            (result.run_id, result.model_dump_json(), _utcnow_iso()),
        )
        self._conn.commit()

    def load_result(self, run_id: str) -> RunResult:
        """Return the ``RunResult`` for *run_id*, or raise ``RunNotFoundError``."""
        row = self._conn.execute(
            "SELECT result_json FROM run_results WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise RunNotFoundError(run_id)
        return RunResult.model_validate_json(row[0])

    def has_result(self, run_id: str) -> bool:
        """Return ``True`` if a ``RunResult`` exists for *run_id*."""
        row = self._conn.execute(
            "SELECT 1 FROM run_results WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        return row is not None
