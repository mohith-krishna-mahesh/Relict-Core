"""
Run lifecycle endpoints.

POST /v1/runs
    Accept a contract-shaped ``ContractRunRequest``, admit the run, and
    return ``StartRunResponse{run_id}`` **immediately** without waiting for
    pipeline completion.  The pipeline executes as an ``asyncio`` background
    task.

    Scope gap (flagged design decision)
    ------------------------------------
    The contract's ``RunRequest`` has no ``scope`` field.  Internally,
    ``ProjectContext.scope`` is required.  Until the contract is updated,
    the route uses ``Scope.DE_EXTINCTION`` as the documented default.  Do not
    change this default without raising it back to the product team.

    Async dispatch pattern
    ----------------------
    1. Generate ``route_run_id`` (UUID) at the route layer.
    2. Save ``RunState(QUEUED)`` to the repository under ``route_run_id``.
    3. Capacity check via active-state count in the repository.  If at
       capacity, delete the pre-saved state and return HTTP 429.
    4. ``asyncio.create_task(_background_execute(...))`` -- pipeline runs
       in background.
    5. Return ``StartRunResponse(run_id=route_run_id)`` immediately.
    6. Background task: awaits ``orchestrator.execute()``, re-keys the result
       under ``route_run_id``, and updates repository state.

    The orchestrator's own admission control (``_active_runs`` counter) still
    applies inside ``execute()`` -- ``RunAtCapacityError`` is caught by the
    background task and stored as a FAILED state.  The route-layer capacity
    pre-check is a best-effort guard; if both fire, the task's error handler
    updates the repository state to FAILED.

GET /v1/runs/{run_id}
    Returns the contract-shaped ``ContractRunResult`` for a run.

    For in-progress runs (no stored result yet), returns a partial
    ``ContractRunResult`` with the current status and empty nodes/edges/
    strategies -- satisfying the contract schema without returning HTTP 404
    for a known run.

    Returns HTTP 404 when the ``run_id`` is unknown.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_bearer_token, get_orchestrator, get_repository
from app.models.contract import ContractRunRequest, ContractRunResult, StartRunResponse
from app.models.requests import ProjectContext, RunConfiguration, Scope, StrategyMode
from app.models.run_state import RunState, RunStatus
from app.routes.contract_adapters import adapt_run_result, make_partial_run_result
from app.run_manager.orchestrator import RunAtCapacityError, RunOrchestrator
from app.run_manager.repository import RunNotFoundError, RunRepository

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Active status set -- used for capacity pre-check
# ---------------------------------------------------------------------------

_ACTIVE_STATUSES = frozenset([RunStatus.PENDING, RunStatus.QUEUED, RunStatus.RUNNING])

# ---------------------------------------------------------------------------
# Background task shim
# ---------------------------------------------------------------------------


async def _background_execute(
    route_run_id: str,
    orchestrator: RunOrchestrator,
    repository: RunRepository,
    project: ProjectContext,
    run_config: RunConfiguration,
    objective: str,
) -> None:
    """
    Background coroutine: run the pipeline and store results under ``route_run_id``.

    The orchestrator generates its own internal ``run_id``; this shim re-keys
    the result and final state to ``route_run_id`` so that ``GET /v1/runs/{run_id}``
    always resolves correctly.
    """
    try:
        internal_result = await orchestrator.execute(project, run_config)

        # Re-key result under the route-provided ID
        rekeyed = internal_result.model_copy(update={"run_id": route_run_id})
        repository.save_result(rekeyed)

        # Update the pre-saved RunState to the final status
        final_state = RunState(
            run_id=route_run_id,
            status=internal_result.status,
            timestamps={"completed": datetime.now(tz=UTC)},
            errors=internal_result.warnings,
        )
        repository.save_state(final_state)

    except RunAtCapacityError as exc:
        logger.warning("Background run %s rejected (capacity): %s", route_run_id, exc)
        failed_state = RunState(
            run_id=route_run_id,
            status=RunStatus.FAILED,
            errors=[str(exc)],
        )
        repository.save_state(failed_state)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Background run %s raised an unexpected error: %s", route_run_id, exc)
        failed_state = RunState(
            run_id=route_run_id,
            status=RunStatus.FAILED,
            errors=[f"Unexpected pipeline error: {exc}"],
        )
        repository.save_state(failed_state)


# ---------------------------------------------------------------------------
# POST /v1/runs
# ---------------------------------------------------------------------------


def _map_presets(presets: list[str]) -> StrategyMode:
    """Map contract presets list to internal StrategyMode."""
    if "redundant" in presets:
        return StrategyMode.REDUNDANT
    return StrategyMode.MINIMAL


def _build_constraints(cr: RunConfiguration, body: ContractRunRequest) -> list[str]:
    """Build the internal constraints list from contract RunConstraints."""
    extra: list[str] = []
    if body.constraints.preserve_fertility:
        extra.append("preserve_fertility")
    if body.constraints.maximize_diversity:
        extra.append("maximize_diversity")
    return extra


@router.post(
    "/runs",
    response_model=StartRunResponse,
    status_code=200,
    summary="Submit a pipeline run (async)",
    description=(
        "Accepts a run request and returns ``{run_id}`` immediately. "
        "The pipeline executes in the background; poll "
        "``GET /v1/runs/{run_id}`` or subscribe to "
        "``GET /v1/runs/{run_id}/stream`` for progress. "
        "HTTP 429 is returned when the server is already handling its "
        "maximum number of concurrent runs."
    ),
    tags=["runs"],
)
async def submit_run(
    body: ContractRunRequest,
    orchestrator: RunOrchestrator = Depends(get_orchestrator),  # noqa: B008
    repository: RunRepository = Depends(get_repository),  # noqa: B008
    _token: str = Depends(get_bearer_token),  # noqa: B008
) -> StartRunResponse:
    """
    Admit a run and return its ``run_id`` immediately.

    Scope default: ``Scope.DE_EXTINCTION`` (flagged design decision -- the
    contract has no ``scope`` field; do not change without product review).
    """
    from app.config import settings  # noqa: PLC0415

    # ── CAPACITY PRE-CHECK ────────────────────────────────────────────
    # Best-effort check before creating the background task. Counts
    # states with PENDING/QUEUED/RUNNING status in the repository.
    max_limit = getattr(orchestrator, "_max_concurrent_runs", settings.max_concurrent_runs)
    active_count = sum(1 for s in repository.all_states() if s.status in _ACTIVE_STATUSES)
    if active_count >= max_limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Server is at capacity: {active_count} of "
                f"{max_limit} concurrent run(s) active."
            ),
        )

    # ── GENERATE ROUTE RUN ID ─────────────────────────────────────────
    route_run_id = str(uuid.uuid4())

    # ── BUILD INTERNAL MODELS ─────────────────────────────────────────
    # Scope gap: use DE_EXTINCTION as documented default.
    # Product decision required before changing this default.
    logger.warning(
        "POST /v1/runs: contract has no scope field; using default scope=de-extinction for run %s",
        route_run_id,
    )

    project = ProjectContext(
        project_id=route_run_id,
        species=body.species,
        scope=Scope.DE_EXTINCTION,
        objective=body.research_objective,
    )

    strategy_mode = _map_presets(list(body.presets))
    extra_constraints: list[str] = []
    if body.constraints.preserve_fertility:
        extra_constraints.append("preserve_fertility")
    if body.constraints.maximize_diversity:
        extra_constraints.append("maximize_diversity")

    run_config = RunConfiguration(
        candidate_genes=list(body.candidate_genes),
        max_edits=body.constraints.max_edits,
        constraints=extra_constraints,
        strategy=strategy_mode,
    )

    # ── SAVE INITIAL STATE ────────────────────────────────────────────
    initial_state = RunState(
        run_id=route_run_id,
        status=RunStatus.QUEUED,
        timestamps={"queued": datetime.now(tz=UTC)},
    )
    repository.save_state(initial_state)

    # ── DISPATCH BACKGROUND TASK ──────────────────────────────────────
    asyncio.create_task(
        _background_execute(
            route_run_id=route_run_id,
            orchestrator=orchestrator,
            repository=repository,
            project=project,
            run_config=run_config,
            objective=body.research_objective,
        )
    )

    return StartRunResponse(run_id=route_run_id)


# ---------------------------------------------------------------------------
# GET /v1/runs/{run_id}
# ---------------------------------------------------------------------------


@router.get(
    "/runs/{run_id}",
    response_model=ContractRunResult,
    summary="Get run result",
    description=(
        "Returns the contract-shaped ``RunResult`` for *run_id*. "
        "For in-progress runs, returns current status with empty nodes/edges/strategies. "
        "Returns HTTP 404 if the run is not known to this Core instance."
    ),
    tags=["runs"],
)
async def get_run_result(
    run_id: str,
    repository: RunRepository = Depends(get_repository),  # noqa: B008
    _token: str = Depends(get_bearer_token),  # noqa: B008
) -> ContractRunResult:
    """Return contract-shaped ``RunResult`` for *run_id*."""
    try:
        state = repository.load_state(run_id)
    except RunNotFoundError:
        raise HTTPException(status_code=404, detail="run not found") from None

    if repository.has_result(run_id):
        internal_result = repository.load_result(run_id)
        return adapt_run_result(internal_result, route_run_id=run_id)

    # Run is in progress (or failed before result was saved)
    return make_partial_run_result(run_id, state)
