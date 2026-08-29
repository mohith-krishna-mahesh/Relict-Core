"""RunRepository: persistence layer for ``RunState`` and ``RunResult`` records."""

from __future__ import annotations

from typing import Protocol

from app.models.responses import RunResult
from app.models.run_state import RunState


class RunNotFoundError(KeyError):
    """Raised when a ``run_id`` is not present in the repository."""


class RunRepositoryProtocol(Protocol):
    """Protocol defining the persistence layer interface."""

    def save_state(self, state: RunState) -> None: ...

    def load_state(self, run_id: str) -> RunState: ...

    def all_states(self) -> list[RunState]: ...

    def save_result(self, result: RunResult) -> None: ...

    def load_result(self, run_id: str) -> RunResult: ...

    def has_result(self, run_id: str) -> bool: ...


class RunRepository:
    """In-memory repository keyed by ``run_id``."""

    def __init__(self) -> None:
        self._states: dict[str, RunState] = {}
        self._results: dict[str, RunResult] = {}

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
