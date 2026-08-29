"""
Dependency-injection helpers for Relict Core route handlers.

All three functions read from ``request.app.state``, which is populated
during the FastAPI ``lifespan`` context in ``app.main``.  Route handlers
declare them with ``Depends(get_orchestrator)`` / ``Depends(get_repository)``
/ ``Depends(get_event_bus)``.

This indirection lets tests override the dependency via
``app.dependency_overrides`` without patching ``app.state`` directly.

Phase 2D note
-------------
``get_repository`` previously returned ``RunRepository`` (the in-memory
class).  The application now uses ``SQLiteRunRepository`` (Phase 2D) via
``app.state.repository``.  Both classes share the same duck-typed interface
(``save_state`` / ``load_state`` / ``save_result`` / ``load_result`` /
``has_result`` / ``all_states``).  The return annotation is kept as
``RunRepository`` for backwards compatibility with the existing type
annotations in routes — but callers should only rely on the shared
interface, not on the concrete type.

Tests that use ``app.dependency_overrides[get_repository] = lambda: repo``
with an in-memory ``RunRepository`` instance continue to work unchanged.
"""

from __future__ import annotations

from fastapi import Request

from app.run_manager.events import InMemoryRunEventBus
from app.run_manager.orchestrator import RunOrchestrator
from app.run_manager.repository import RunRepository


def get_orchestrator(request: Request) -> RunOrchestrator:
    """Return the application-scoped ``RunOrchestrator`` singleton."""
    return request.app.state.orchestrator  # type: ignore[no-any-return]


def get_repository(request: Request) -> RunRepository:
    """Return the application-scoped repository singleton.

    In production this is a ``SQLiteRunRepository``; in tests it is
    overridden to an in-memory ``RunRepository`` via
    ``app.dependency_overrides``.
    """
    return request.app.state.repository  # type: ignore[no-any-return]


def get_event_bus(request: Request) -> InMemoryRunEventBus:
    """Return the application-scoped ``InMemoryRunEventBus`` singleton."""
    return request.app.state.event_bus  # type: ignore[no-any-return]
