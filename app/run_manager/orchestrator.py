"""
RunOrchestrator: the persistent orchestration layer for Relict Core.

State transitions
-----------------
::

    PENDING → QUEUED → RUNNING → COMPLETE
                               ↘ FAILED

Pipeline stages (in order)
--------------------------
::

    OBJECTIVE_RESOLUTION → RETRIEVAL → PLANNING → VALIDATION → POST_PLAN

Failure semantics
-----------------
``CLARIFICATION_REQUIRED``
    Ambiguous objective → short-circuit → ``FAILED``
``INSUFFICIENT_EVIDENCE``
    Empty evidence list → short-circuit → ``FAILED``
``NO_FEASIBLE_PLAN``
    No strategies returned → short-circuit → ``FAILED``
``VALIDATION_FAILED``
    Strategy rejected by validator → short-circuit → ``FAILED``
``PARTIAL_ANALYSIS``
    Optional post-plan tool unavailable → run stays ``COMPLETE``;
    ``failure`` detail attached; ``post_plan_analysis_status`` set to
    ``PARTIAL`` or ``FAILED``.

Each stage is injected via a ``Protocol`` interface (see ``stages.py``),
allowing real implementations to replace stubs without altering this file.

Phase 2C addition
-----------------
``RunOrchestrator`` now accepts an optional ``event_bus`` constructor parameter
(``InMemoryRunEventBus``).  After every ``_repo.save_state`` call, the
orchestrator publishes a ``RunEvent`` to the bus.  This is a pure side-channel:
the bus is populated by the same state mutations that already drive persistence,
so the control flow of ``execute()`` is unchanged.

``RunStateTracker`` (mentioned in the Phase 2C spec) does not exist in the
Phase 2A/2B codebase — state is managed inline via ``RunState.model_copy()``.
The ``on_change`` callback described in the spec is therefore wired here,
directly inside ``execute()`` and ``_short_circuit()``, rather than in a
tracker class.  ``state.py`` remains untouched.
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.models.failures import FailureCode, FailureDetail
from app.models.post_plan import PostPlanResult, PostPlanStatus
from app.models.requests import (
    AmbiguityStatus,
    ProjectContext,
    RetrievalContext,
    RunConfiguration,
    StructuredObjective,
)
from app.models.responses import RunResult, Strategy
from app.models.run_state import PostPlanAnalysisStatus, RunState, RunStatus
from app.models.validation import ValidationResult
from app.run_manager.progress import ProgressTracker
from app.run_manager.repository import RunRepository
from app.run_manager.stages import (
    EvidenceRetriever,
    ObjectiveResolver,
    PostPlanAnalyzer,
    StrategicPlanner,
    StrategyValidator,
)
from app.run_manager.state import PipelineStage

if TYPE_CHECKING:
    from app.run_manager.events import InMemoryRunEventBus


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class RunAtCapacityError(Exception):
    """
    Raised by ``RunOrchestrator.execute()`` when the number of active runs
    (status PENDING / QUEUED / RUNNING) is already at the configured maximum.

    The route layer maps this to HTTP 429 Too Many Requests.
    No run_id is generated and no state is persisted when this is raised.
    """


class RunOrchestrator:
    """
    Persistent orchestration backbone for the Relict Core pipeline.

    Parameters
    ----------
    resolver:
        Core Model Task 1 — interprets the natural-language objective.
    retriever:
        Knowledge Retrieval — returns source-backed ``EvidenceRecord`` list.
    planner:
        Planner — builds the evidence graph and returns ranked ``Strategy`` list.
    validator:
        Plan Validator — deterministically checks a candidate ``Strategy``.
    analyzer:
        Post-Plan Analysis — guide/risk, population propagation, explanation.
    repository:
        Persistence layer for ``RunState`` and ``RunResult`` records.
    event_bus:
        Optional Phase 2C event bus.  When provided, a ``RunEvent`` is
        published after every ``_repo.save_state`` call so that SSE
        subscribers receive live (or replayed) progress updates.  When
        ``None``, the orchestrator behaves identically to Phase 2B — the
        parameter is optional so existing tests require no changes.
    """

    def __init__(
        self,
        resolver: ObjectiveResolver,
        retriever: EvidenceRetriever,
        planner: StrategicPlanner,
        validator: StrategyValidator,
        analyzer: PostPlanAnalyzer,
        repository: RunRepository,
        event_bus: InMemoryRunEventBus | None = None,
        max_concurrent_runs: int | None = None,
        run_timeout_seconds: int | None = None,
    ) -> None:
        self._resolver = resolver
        self._retriever = retriever
        self._planner = planner
        self._validator = validator
        self._analyzer = analyzer
        self._repo = repository
        self._event_bus = event_bus

        # Phase 2E — concurrency guard.
        # Defaults read from settings so the running application works without
        # explicit arguments; tests can pass explicit values to avoid touching
        # the filesystem or environment.
        from app.config import settings  # noqa: PLC0415 (avoid circular at module level)

        self._max_concurrent_runs: int = (
            max_concurrent_runs
            if max_concurrent_runs is not None
            else settings.max_concurrent_runs
        )
        self._run_timeout_seconds: int = (
            run_timeout_seconds
            if run_timeout_seconds is not None
            else settings.run_timeout_seconds
        )
        self._active_runs: int = 0
        self._active_runs_lock: threading.Lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(
        self,
        project: ProjectContext,
        run_config: RunConfiguration,
    ) -> RunResult:
        """
        Execute the full pipeline and return the final ``RunResult``.

        Transitions the run through PENDING → QUEUED → RUNNING, then either
        COMPLETE (success or partial post-plan) or FAILED (hard short-circuit).

        Phase 2E additions
        ------------------
        - Raises ``RunAtCapacityError`` (before any state is persisted) when
          the number of active runs is already at ``max_concurrent_runs``.
        - Checks elapsed wall-clock time at each stage boundary and
          short-circuits to FAILED with ``FailureCode.RUN_TIMEOUT`` if the
          budget is exceeded.  This is a between-stages check — a single stage
          that hangs past the timeout will not be interrupted mid-stage
          (known limitation; relevant once Phase 6 wires real slow components).
        """
        # ── CAPACITY CHECK ─────────────────────────────────────────────
        # Atomic: check and increment under the lock.  If already at capacity,
        # raise before generating a run_id or writing any state.
        with self._active_runs_lock:
            if self._active_runs >= self._max_concurrent_runs:
                raise RunAtCapacityError(
                    f"Server is at capacity: {self._active_runs} of "
                    f"{self._max_concurrent_runs} concurrent run(s) active."
                )
            self._active_runs += 1

        try:
            return await self._execute_inner(project, run_config)
        finally:
            with self._active_runs_lock:
                self._active_runs -= 1

    async def _execute_inner(
        self,
        project: ProjectContext,
        run_config: RunConfiguration,
    ) -> RunResult:
        """
        Internal pipeline execution — always called with the active-run counter already
        incremented.
        """
        run_id = str(uuid.uuid4())
        tracker = ProgressTracker()
        warnings: list[str] = []
        errors: list[str] = []

        # ── PENDING ────────────────────────────────────────────────────
        state = RunState(run_id=run_id, status=RunStatus.PENDING)
        self._repo.save_state(state)
        self._publish(state, warnings=warnings)

        # ── QUEUED ─────────────────────────────────────────────────────
        state = state.model_copy(
            update={
                "status": RunStatus.QUEUED,
                "timestamps": {**state.timestamps, "queued": _utcnow()},
            }
        )
        self._repo.save_state(state)
        self._publish(state, warnings=warnings)

        # ── RUNNING ────────────────────────────────────────────────────
        state = state.model_copy(
            update={
                "status": RunStatus.RUNNING,
                "timestamps": {**state.timestamps, "started": _utcnow()},
            }
        )
        self._repo.save_state(state)
        self._publish(state, warnings=warnings)

        # Capture start time for timeout enforcement (monotonic, not wall-clock).
        _run_start = time.monotonic()

        # Pipeline outputs accumulated as each stage completes.
        structured_objective: StructuredObjective | None = None
        strategies: list[Strategy] = []
        selected_strategy: Strategy | None = None
        validation: ValidationResult | None = None
        post_plan: PostPlanResult | None = None
        failure: FailureDetail | None = None
        post_plan_status = PostPlanAnalysisStatus.PENDING

        # ------------------------------------------------------------------
        # Stage 1: OBJECTIVE RESOLUTION
        # ------------------------------------------------------------------
        if time.monotonic() - _run_start >= self._run_timeout_seconds:
            return self._short_circuit(
                run_id=run_id, state=state,
                code=FailureCode.RUN_TIMEOUT,
                message=(
                    f"Run exceeded the {self._run_timeout_seconds}s wall-clock "
                    "budget before stage 1."
                ),
                stage=PipelineStage.OBJECTIVE_RESOLUTION,
                project=project, run_config=run_config, warnings=warnings,
            )
        state = self._enter_stage(state, PipelineStage.OBJECTIVE_RESOLUTION)
        self._repo.save_state(state)
        self._publish(state, warnings=warnings)

        try:
            structured_objective = await self._resolver.resolve(project, run_config)
        except Exception as exc:
            return self._short_circuit(
                run_id=run_id,
                state=state,
                code=FailureCode.CLARIFICATION_REQUIRED,
                message=f"Objective resolution error: {exc}",
                stage=PipelineStage.OBJECTIVE_RESOLUTION,
                project=project,
                run_config=run_config,
                warnings=warnings,
            )

        if structured_objective.ambiguity_status == AmbiguityStatus.CLARIFICATION_REQUIRED:
            return self._short_circuit(
                run_id=run_id,
                state=state,
                code=FailureCode.CLARIFICATION_REQUIRED,
                message=(
                    "Objective is ambiguous; Shell must prompt the researcher "
                    "before the run can continue."
                ),
                stage=PipelineStage.OBJECTIVE_RESOLUTION,
                project=project,
                run_config=run_config,
                structured_objective=structured_objective,
                warnings=warnings,
            )

        tracker.stage_completed(PipelineStage.OBJECTIVE_RESOLUTION)
        state = state.model_copy(update={"progress": tracker.progress})
        self._repo.save_state(state)
        self._publish(state, warnings=warnings)

        # ------------------------------------------------------------------
        # Stage 2: KNOWLEDGE RETRIEVAL
        # ------------------------------------------------------------------
        if time.monotonic() - _run_start >= self._run_timeout_seconds:
            return self._short_circuit(
                run_id=run_id, state=state,
                code=FailureCode.RUN_TIMEOUT,
                message=(
                    f"Run exceeded the {self._run_timeout_seconds}s wall-clock "
                    "budget before stage 2."
                ),
                stage=PipelineStage.RETRIEVAL,
                project=project, run_config=run_config,
                structured_objective=structured_objective, warnings=warnings,
            )
        retrieval_ctx = RetrievalContext(
            project_context=project,
            run_configuration=run_config,
            structured_objective=structured_objective,
        )

        state = self._enter_stage(state, PipelineStage.RETRIEVAL)
        self._repo.save_state(state)
        self._publish(state, warnings=warnings)

        try:
            evidence = await self._retriever.retrieve(retrieval_ctx)
        except Exception as exc:
            return self._short_circuit(
                run_id=run_id,
                state=state,
                code=FailureCode.INSUFFICIENT_EVIDENCE,
                message=f"Knowledge retrieval error: {exc}",
                stage=PipelineStage.RETRIEVAL,
                project=project,
                run_config=run_config,
                structured_objective=structured_objective,
                warnings=warnings,
            )

        if not evidence:
            return self._short_circuit(
                run_id=run_id,
                state=state,
                code=FailureCode.INSUFFICIENT_EVIDENCE,
                message="Knowledge Retrieval returned no evidence records.",
                stage=PipelineStage.RETRIEVAL,
                project=project,
                run_config=run_config,
                structured_objective=structured_objective,
                warnings=warnings,
            )

        tracker.stage_completed(PipelineStage.RETRIEVAL)
        state = state.model_copy(update={"progress": tracker.progress})
        self._repo.save_state(state)
        self._publish(state, warnings=warnings)

        # ------------------------------------------------------------------
        # Stage 3: PLANNING
        # ------------------------------------------------------------------
        if time.monotonic() - _run_start >= self._run_timeout_seconds:
            return self._short_circuit(
                run_id=run_id, state=state,
                code=FailureCode.RUN_TIMEOUT,
                message=(
                    f"Run exceeded the {self._run_timeout_seconds}s wall-clock "
                    "budget before stage 3."
                ),
                stage=PipelineStage.PLANNING,
                project=project, run_config=run_config,
                structured_objective=structured_objective, warnings=warnings,
            )
        state = self._enter_stage(state, PipelineStage.PLANNING)
        self._repo.save_state(state)
        self._publish(state, warnings=warnings)

        try:
            strategies = await self._planner.plan(retrieval_ctx, evidence)
        except Exception as exc:
            return self._short_circuit(
                run_id=run_id,
                state=state,
                code=FailureCode.NO_FEASIBLE_PLAN,
                message=f"Planner error: {exc}",
                stage=PipelineStage.PLANNING,
                project=project,
                run_config=run_config,
                structured_objective=structured_objective,
                warnings=warnings,
            )

        if not strategies:
            return self._short_circuit(
                run_id=run_id,
                state=state,
                code=FailureCode.NO_FEASIBLE_PLAN,
                message=(
                    "Planner found no strategy satisfying the constraints "
                    "and edit budget."
                ),
                stage=PipelineStage.PLANNING,
                project=project,
                run_config=run_config,
                structured_objective=structured_objective,
                warnings=warnings,
            )

        selected_strategy = strategies[0]  # highest-ranked candidate

        tracker.stage_completed(PipelineStage.PLANNING)
        state = state.model_copy(update={"progress": tracker.progress})
        self._repo.save_state(state)
        self._publish(state, warnings=warnings)

        # ------------------------------------------------------------------
        # Stage 4: VALIDATION
        # ------------------------------------------------------------------
        if time.monotonic() - _run_start >= self._run_timeout_seconds:
            return self._short_circuit(
                run_id=run_id, state=state,
                code=FailureCode.RUN_TIMEOUT,
                message=(
                    f"Run exceeded the {self._run_timeout_seconds}s wall-clock "
                    "budget before stage 4."
                ),
                stage=PipelineStage.VALIDATION,
                project=project, run_config=run_config,
                structured_objective=structured_objective,
                strategies=strategies, warnings=warnings,
            )
        state = self._enter_stage(state, PipelineStage.VALIDATION)
        self._repo.save_state(state)
        self._publish(state, warnings=warnings)

        try:
            validation = await self._validator.validate(selected_strategy, run_config)
        except Exception as exc:
            return self._short_circuit(
                run_id=run_id,
                state=state,
                code=FailureCode.VALIDATION_FAILED,
                message=f"Validator error: {exc}",
                stage=PipelineStage.VALIDATION,
                project=project,
                run_config=run_config,
                structured_objective=structured_objective,
                strategies=strategies,
                warnings=warnings,
            )

        if not validation.valid:
            summary = (
                "; ".join(validation.violations)
                if validation.violations
                else "unspecified"
            )
            return self._short_circuit(
                run_id=run_id,
                state=state,
                code=FailureCode.VALIDATION_FAILED,
                message=f"Strategy failed validation: {summary}",
                stage=PipelineStage.VALIDATION,
                project=project,
                run_config=run_config,
                structured_objective=structured_objective,
                strategies=strategies,
                validation=validation,
                warnings=warnings,
            )

        tracker.stage_completed(PipelineStage.VALIDATION)
        state = state.model_copy(update={"progress": tracker.progress})
        self._repo.save_state(state)
        self._publish(state, warnings=warnings)

        # ------------------------------------------------------------------
        # Stage 5: POST-PLAN ANALYSIS
        # ------------------------------------------------------------------
        # Post-Plan failure does NOT short-circuit the run.  A valid
        # Planner + Validator result stays COMPLETE regardless of whether
        # Post-Plan Analysis completes, partially completes, or fails.
        # EXCEPTION: a timeout before this stage short-circuits to FAILED.
        if time.monotonic() - _run_start >= self._run_timeout_seconds:
            return self._short_circuit(
                run_id=run_id, state=state,
                code=FailureCode.RUN_TIMEOUT,
                message=(
                    f"Run exceeded the {self._run_timeout_seconds}s wall-clock "
                    "budget before stage 5."
                ),
                stage=PipelineStage.POST_PLAN,
                project=project, run_config=run_config,
                structured_objective=structured_objective,
                strategies=strategies, validation=validation, warnings=warnings,
            )
        post_plan_status = PostPlanAnalysisStatus.RUNNING
        state = self._enter_stage(state, PipelineStage.POST_PLAN)
        state = state.model_copy(update={"post_plan_analysis_status": post_plan_status})
        self._repo.save_state(state)
        self._publish(state, warnings=warnings)

        try:
            post_plan = await self._analyzer.analyze(selected_strategy, evidence, run_config)
        except Exception as exc:
            errors.append(f"Post-Plan Analysis raised an unexpected error: {exc}")
            post_plan = PostPlanResult(status=PostPlanStatus.FAILED)
            post_plan_status = PostPlanAnalysisStatus.FAILED
            failure = FailureDetail(
                code=FailureCode.PARTIAL_ANALYSIS,
                message=str(exc),
                stage=PipelineStage.POST_PLAN,
            )
        else:
            if post_plan.status == PostPlanStatus.COMPLETE:
                post_plan_status = PostPlanAnalysisStatus.COMPLETE
            elif post_plan.status == PostPlanStatus.PARTIAL:
                post_plan_status = PostPlanAnalysisStatus.PARTIAL
                failure = FailureDetail(
                    code=FailureCode.PARTIAL_ANALYSIS,
                    message="One or more optional Post-Plan tools were unavailable.",
                    stage=PipelineStage.POST_PLAN,
                )
            else:  # PostPlanStatus.FAILED
                post_plan_status = PostPlanAnalysisStatus.FAILED
                failure = FailureDetail(
                    code=FailureCode.PARTIAL_ANALYSIS,
                    message="Post-Plan Analysis failed.",
                    stage=PipelineStage.POST_PLAN,
                )

        tracker.stage_completed(PipelineStage.POST_PLAN)
        tracker.complete()

        # ── COMPLETE ───────────────────────────────────────────────────
        state = state.model_copy(
            update={
                "status": RunStatus.COMPLETE,
                "current_stage": None,
                "progress": tracker.progress,
                "post_plan_analysis_status": post_plan_status,
                "timestamps": {**state.timestamps, "completed": _utcnow()},
                "errors": errors,
            }
        )
        self._repo.save_state(state)
        self._publish(state, failure=failure, warnings=warnings)

        result = RunResult(
            run_id=run_id,
            status=RunStatus.COMPLETE,
            project_context=project,
            run_configuration=run_config,
            structured_objective=structured_objective,
            strategies=strategies,
            selected_strategy=selected_strategy,
            validation=validation,
            post_plan=post_plan,
            failure=failure,
            warnings=warnings,
        )
        self._repo.save_result(result)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _enter_stage(state: RunState, stage: PipelineStage) -> RunState:
        """Return a new ``RunState`` with ``current_stage`` set to *stage*."""
        return state.model_copy(update={"current_stage": stage.value})

    def _publish(
        self,
        state: RunState,
        failure: FailureDetail | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        """
        Publish a ``RunEvent`` derived from *state* to the event bus.

        No-op when ``self._event_bus`` is ``None`` (Phase 2B backwards
        compatibility — tests that don't supply a bus work unchanged).
        """
        if self._event_bus is None:
            return

        # Import here (not at module top) to avoid a circular import between
        # orchestrator.py and events.py — events.py imports from models, and
        # orchestrator.py already imports from models; the TYPE_CHECKING guard
        # above is sufficient for static analysis.
        from app.run_manager.events import RunEvent  # noqa: PLC0415

        status = state.status
        if status == RunStatus.COMPLETE:
            event_type: str = "complete"
        elif status == RunStatus.FAILED:
            event_type = "failed"
        else:
            event_type = "stage"

        event = RunEvent(
            event_type=event_type,  # type: ignore[arg-type]
            run_id=state.run_id,
            status=status,
            current_stage=state.current_stage,
            progress=state.progress,
            post_plan_analysis_status=state.post_plan_analysis_status,
            failure=failure,
            warnings=list(warnings) if warnings else [],
        )
        self._event_bus.publish(state.run_id, event)

    def _short_circuit(
        self,
        *,
        run_id: str,
        state: RunState,
        code: FailureCode,
        message: str,
        stage: PipelineStage,
        project: ProjectContext,
        run_config: RunConfiguration,
        structured_objective: StructuredObjective | None = None,
        strategies: list[Strategy] | None = None,
        validation: ValidationResult | None = None,
        post_plan: PostPlanResult | None = None,
        warnings: list[str] | None = None,
    ) -> RunResult:
        """
        Record a pipeline failure, persist the failed ``RunState``, and return
        a failed ``RunResult``.

        This is the short-circuit exit: no subsequent stage executes after this
        call returns.  Post-Plan Analysis is never reached via this path.
        """
        failure = FailureDetail(code=code, message=message, stage=stage.value)

        failed_state = state.model_copy(
            update={
                "status": RunStatus.FAILED,
                "timestamps": {**state.timestamps, "failed": _utcnow()},
                "errors": [message],
            }
        )
        self._repo.save_state(failed_state)
        self._publish(failed_state, failure=failure, warnings=warnings)

        result = RunResult(
            run_id=run_id,
            status=RunStatus.FAILED,
            project_context=project,
            run_configuration=run_config,
            structured_objective=structured_objective,
            strategies=strategies or [],
            selected_strategy=None,
            validation=validation,
            post_plan=post_plan,
            failure=failure,
            warnings=warnings or [],
        )
        self._repo.save_result(result)
        return result
