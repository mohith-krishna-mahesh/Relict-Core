"""
Run lifecycle endpoints.

POST /v1/runs
    Submit a new pipeline run.  Returns the final ``RunResult`` (success or
    failure) synchronously.  In Phase 2B this is adequate because the stubs
    complete in milliseconds.

    TODO: Move execution to a background worker when real biological stages
    are plugged in (Phase 3+).  The route will then return HTTP 202 Accepted
    with a ``run_id`` and Shell will poll ``GET /v1/runs/{run_id}`` or
    subscribe to ``GET /v1/runs/{run_id}/stream``.

GET /v1/runs/{run_id}
    Poll the current ``RunState`` for a run that was previously submitted.
    Returns HTTP 404 when the ``run_id`` is not known to this Core instance.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.dependencies import get_orchestrator, get_repository
from app.models.requests import ProjectContext, RunConfiguration
from app.models.responses import RunResult
from app.models.run_state import RunState
from app.run_manager.orchestrator import RunAtCapacityError, RunOrchestrator
from app.run_manager.repository import RunNotFoundError, RunRepository

router = APIRouter()


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    """
    API entry point for ``POST /v1/runs``.

    Architecture §2.7 — the API accepts project and run configuration in one
    request.  Core separates them before execution; neither block is inferred
    or overwritten by the Core Model.
    """

    model_config = ConfigDict(extra="forbid")

    project: ProjectContext
    run: RunConfiguration


# ---------------------------------------------------------------------------
# POST /v1/runs
# ---------------------------------------------------------------------------


@router.post(
    "/runs",
    response_model=RunResult,
    summary="Submit a pipeline run",
    description=(
        "Executes the full Relict Core pipeline synchronously. "
        "The returned ``RunResult.status`` indicates whether the pipeline "
        "succeeded (``complete``) or short-circuited (``failed``). "
        "HTTP 200 is returned in both cases; inspect ``status`` and "
        "``failure`` fields for the outcome. "
        "HTTP 429 is returned when the server is already handling its "
        "maximum number of concurrent runs."
    ),
    tags=["runs"],
)
async def submit_run(
    body: RunRequest,
    orchestrator: RunOrchestrator = Depends(get_orchestrator),  # noqa: B008
) -> RunResult:
    """Execute the pipeline and return the final ``RunResult``."""
    # TODO: Move to a background worker when real biological stages are active.
    try:
        return await orchestrator.execute(body.project, body.run)
    except RunAtCapacityError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from None


# ---------------------------------------------------------------------------
# GET /v1/runs/{run_id}
# ---------------------------------------------------------------------------


@router.get(
    "/runs/{run_id}",
    response_model=RunState,
    summary="Poll run state",
    description=(
        "Returns the current ``RunState`` for *run_id*. "
        "Returns HTTP 404 if the run is not known to this Core instance."
    ),
    tags=["runs"],
)
async def get_run_state(
    run_id: str,
    repository: RunRepository = Depends(get_repository),  # noqa: B008
) -> RunState:
    """Return the latest ``RunState`` for *run_id*."""
    try:
        return repository.load_state(run_id)
    except RunNotFoundError:
        raise HTTPException(status_code=404, detail="run not found") from None
