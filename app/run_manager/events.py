"""
In-process, in-memory run event bus for the Phase 2C SSE streaming endpoint.

Design
------
``InMemoryRunEventBus`` is the sole event transport for Phase 2C.  It mirrors
``InMemoryRunRepository`` in scope: single-process, in-memory, no persistence,
no cross-process fan-out.  Phase 3+ will replace this with a real pub/sub
backend when Core runs continuously and potentially across multiple processes.

``RunEvent`` is a frozen dataclass — not a Pydantic model — because it is an
internal transport object rather than an API contract.  Wire serialization
(dataclass → JSON string for SSE ``data``) is handled in ``routes/stream.py``.

Limitations (Phase 2C)
----------------------
- Single-process only: subscribers and publishers must share the same Python
  interpreter.  This is acceptable because ``RunOrchestrator.execute()`` still
  runs inline in Phase 2C; there are no background workers.
- Event history is kept in memory indefinitely (no TTL / eviction).  Acceptable
  at this scale; Phase 3+ will need explicit cleanup.
- ``subscribe`` replays buffered history first, so a client connecting *after*
  a run has already finished still receives the full event sequence.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal

from app.models.failures import FailureDetail
from app.models.run_state import PostPlanAnalysisStatus, RunStatus


@dataclass(frozen=True)
class RunEvent:
    """
    A single state-change notification emitted by the Run Manager pipeline.

    ``event_type`` maps directly to the SSE ``event:`` field:
        "stage"    — an intermediate pipeline stage transition
        "complete" — terminal success
        "failed"   — terminal failure / short-circuit

    All other fields mirror ``RunState`` fields so that a subscriber can render
    a complete progress snapshot from any single event without keeping state.
    """

    event_type: Literal["stage", "complete", "failed"]
    run_id: str
    status: RunStatus
    current_stage: str | None
    progress: float
    post_plan_analysis_status: PostPlanAnalysisStatus
    failure: FailureDetail | None = None
    warnings: list[str] = field(default_factory=list)


class InMemoryRunEventBus:
    """
    In-memory event bus for run progress notifications.

    Thread / coroutine safety
    -------------------------
    All methods are called from a single asyncio event loop (the FastAPI event
    loop).  No locking is needed because asyncio is single-threaded within one
    loop, and ``asyncio.Queue`` is safe for use within that loop.

    Public API
    ----------
    publish(run_id, event)
        Append *event* to that run's history and push it onto every live
        subscriber queue for *run_id*.

    subscribe(run_id) -> AsyncIterator[RunEvent]
        Async generator that first replays all buffered history for *run_id*,
        then yields new events as they arrive, and stops after a terminal event
        (``event_type`` in ``{"complete", "failed"}``) has been yielded.
    """

    _TERMINAL: frozenset[str] = frozenset({"complete", "failed"})

    def __init__(self) -> None:
        # run_id -> ordered list of all events ever published for that run
        self._history: dict[str, list[RunEvent]] = {}
        # run_id -> list of live subscriber queues (one per active SSE connection)
        self._queues: dict[str, list[asyncio.Queue[RunEvent]]] = {}

    def publish(self, run_id: str, event: RunEvent) -> None:
        """
        Append *event* to history and notify all live subscribers for *run_id*.
        """
        # Append to history (create list on first publish for this run_id).
        if run_id not in self._history:
            self._history[run_id] = []
        self._history[run_id].append(event)

        # Push to every live subscriber queue.
        for q in self._queues.get(run_id, []):
            q.put_nowait(event)

    async def subscribe(self, run_id: str) -> AsyncIterator[RunEvent]:
        """
        Async generator yielding all events for *run_id*, past and future.

        Algorithm
        ---------
        1. Snapshot the current history length *before* registering the queue,
           so we know how many events to replay without re-fetching from the
           queue.
        2. Register a new ``asyncio.Queue`` for live events.
        3. Yield all buffered events up to the snapshot point.
           If any is terminal -> stop immediately (run already finished).
        4. Consume live events from the queue until a terminal event is yielded.
        5. Deregister the queue (cleanup).

        This ordering guarantees that no events are lost between the history
        snapshot and the queue registration: any event published after step 2
        goes into the queue; events published before step 2 are in history.
        """
        # Snapshot history length before registering the queue.
        history = self._history.get(run_id, [])
        history_snapshot_len = len(history)

        # Register subscriber queue.
        q: asyncio.Queue[RunEvent] = asyncio.Queue()
        if run_id not in self._queues:
            self._queues[run_id] = []
        self._queues[run_id].append(q)

        try:
            # --- Phase 1: replay buffered history ---
            for event in history[:history_snapshot_len]:
                yield event
                if event.event_type in self._TERMINAL:
                    return

            # --- Phase 2: consume live events ---
            while True:
                event = await q.get()
                yield event
                if event.event_type in self._TERMINAL:
                    return
        finally:
            # Always clean up the queue reference, even on generator close.
            queues_for_run = self._queues.get(run_id, [])
            if q in queues_for_run:
                queues_for_run.remove(q)
            if not queues_for_run and run_id in self._queues:
                del self._queues[run_id]
