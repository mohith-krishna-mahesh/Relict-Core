"""
SSE streaming endpoint for run progress.

GET /v1/runs/{run_id}/stream
    Subscribe to live (or replayed) progress events for a run.

    Returns a Server-Sent Events stream.  Each event has an ``event:`` type
    (``stage``, ``complete``, or ``failed``) and a JSON ``data:`` payload
    matching the ``RunEvent`` wire contract.

    Because ``InMemoryRunEventBus.subscribe`` replays buffered history before
    yielding live events, a client connecting *after* the run has already
    finished still receives the full event sequence ending in a terminal event,
    after which the stream closes.

    HTTP 404 is returned when the ``run_id`` is unknown to this Core instance
    (same behaviour and error body as ``GET /v1/runs/{run_id}``).

Wire event format
-----------------
::

    event: stage
    data: {"run_id": "...", "status": "running", "current_stage": "retrieval",
            "progress": 0.35, "post_plan_analysis_status": "pending",
            "failure": null, "warnings": []}

    event: complete
    data: {"run_id": "...", "status": "complete", "current_stage": null,
            "progress": 1.0, "post_plan_analysis_status": "complete",
            "failure": null, "warnings": []}

    event: failed
    data: {"run_id": "...", "status": "failed", "current_stage": "retrieval",
            "progress": 0.35, "post_plan_analysis_status": "pending",
            "failure": {"code": "INSUFFICIENT_EVIDENCE", "message": "...",
                        "stage": "retrieval"}, "warnings": []}
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.dependencies import get_event_bus, get_repository
from app.run_manager.events import InMemoryRunEventBus, RunEvent
from app.run_manager.repository import RunNotFoundError, RunRepository

router = APIRouter()


def _event_to_sse(event: RunEvent) -> ServerSentEvent:
    """
    Serialize a ``RunEvent`` to an ``sse_starlette`` ``ServerSentEvent``.

    ``RunEvent`` is a frozen dataclass; we convert it to a JSON-serialisable
    dict manually (StrEnum values coerce to ``str`` automatically via their
    ``__str__``; ``FailureDetail`` is a Pydantic model so ``.model_dump()``
    handles it).
    """
    payload: dict = {
        "run_id": event.run_id,
        "status": str(event.status),
        "current_stage": event.current_stage,
        "progress": event.progress,
        "post_plan_analysis_status": str(event.post_plan_analysis_status),
        "failure": event.failure.model_dump() if event.failure is not None else None,
        "warnings": list(event.warnings),
    }
    return ServerSentEvent(
        data=json.dumps(payload),
        event=event.event_type,
    )


async def _stream_events(
    run_id: str,
    event_bus: InMemoryRunEventBus,
) -> AsyncIterator[ServerSentEvent]:
    """Async generator of ``ServerSentEvent`` objects for *run_id*."""
    async for run_event in event_bus.subscribe(run_id):
        yield _event_to_sse(run_event)


@router.get(
    "/runs/{run_id}/stream",
    summary="Stream run progress via SSE",
    description=(
        "Subscribe to live Server-Sent Events for *run_id*. "
        "Replays full event history for already-finished runs so clients "
        "connecting after completion still receive the complete sequence. "
        "The stream closes after the terminal ``complete`` or ``failed`` event. "
        "Returns HTTP 404 when *run_id* is unknown to this Core instance."
    ),
    tags=["runs"],
    response_class=EventSourceResponse,
)
async def stream_run(
    run_id: str,
    repository: RunRepository = Depends(get_repository),  # noqa: B008
    event_bus: InMemoryRunEventBus = Depends(get_event_bus),  # noqa: B008
) -> EventSourceResponse:
    """Stream ``RunEvent`` objects for *run_id* as Server-Sent Events."""
    # Validate run_id existence using the same repository the GET endpoint uses.
    # Raises the same HTTPException shape so error bodies are identical.
    try:
        repository.load_state(run_id)
    except RunNotFoundError:
        raise HTTPException(status_code=404, detail="run not found") from None

    return EventSourceResponse(_stream_events(run_id, event_bus))
