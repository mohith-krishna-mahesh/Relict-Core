"""
RunRepository: persistence layer for ``RunState`` and ``RunResult`` records.

This file contains:

``RunNotFoundError``
    Shared exception raised by all repository implementations when a
    ``run_id`` is not present.  Lives here (not in the SQLite-specific file)
    because it is part of the *interface* contract — any implementation or
    caller that needs to catch it imports from this module.

``RunRepository``
    In-memory dict-backed store.  Fast, zero-setup — the default for the
    test suite and the in-process double for Phases 2A–2C.

The SQLite-backed implementation (``SQLiteRunRepository``) lives in
``app/cache/sqlite_repository.py`` to keep infrastructure code (SQLite
wiring) separate from this domain-level module.

Both implementations share the same duck-typed interface:

    save_state(state)   load_state(run_id)   all_states()
    save_result(result) load_result(run_id)  has_result(run_id)

``RunOrchestrator`` holds a reference typed as ``RunRepository`` but accepts
either implementation; it does not need to change when the concrete class
behind the reference changes — that is the point of this interface.
"""

from __future__ import annotations

from app.models.responses import RunResult
from app.models.run_state import RunState


class RunNotFoundError(KeyError):
    """Raised when a ``run_id`` is not present in the repository."""


class RunRepository:
    """In-memory repository keyed by ``run_id``."""

    def __init__(self) -> None:
        self._states: dict[str, RunState] = {}
        self._results: dict[str, RunResult] = {}

    # ------------------------------------------------------------------
    # RunState
    # ------------------------------------------------------------------

    def save_state(self, state: RunState) -> None:
        """Persist (or overwrite) the ``RunState`` for ``state.run_id``."""
        self._states[state.run_id] = state

    def load_state(self, run_id: str) -> RunState:
        """Return the latest ``RunState`` for *run_id*, or raise ``RunNotFoundError``."""
        try:
            return self._states[run_id]
        except KeyError:
            raise RunNotFoundError(run_id) from None

    def all_states(self) -> list[RunState]:
        """Return all currently stored ``RunState`` records."""
        return list(self._states.values())

    # ------------------------------------------------------------------
    # RunResult
    # ------------------------------------------------------------------

    def save_result(self, result: RunResult) -> None:
        """Persist (or overwrite) the ``RunResult`` for ``result.run_id``."""
        self._results[result.run_id] = result

    def load_result(self, run_id: str) -> RunResult:
        """Return the ``RunResult`` for *run_id*, or raise ``RunNotFoundError``."""
        try:
            return self._results[run_id]
        except KeyError:
            raise RunNotFoundError(run_id) from None

    def has_result(self, run_id: str) -> bool:
        """Return ``True`` if a ``RunResult`` exists for *run_id*."""
        return run_id in self._results
