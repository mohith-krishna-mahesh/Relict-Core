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
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

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


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


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
    """

    def __init__(
        self,
        resolver: ObjectiveResolver,
        retriever: EvidenceRetriever,
        planner: StrategicPlanner,
        validator: StrategyValidator,
        analyzer: PostPlanAnalyzer,
        repository: RunRepository,
    ) -> None:
        self._resolver = resolver
        self._retriever = retriever
        self._planner = planner
        self._validator = validator
        self._analyzer = analyzer
        self._repo = repository

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
        """
        run_id = str(uuid.uuid4())
        tracker = ProgressTracker()
        warnings: list[str] = []
        errors: list[str] = []

        # ── PENDING ────────────────────────────────────────────────────
        state = RunState(run_id=run_id, status=RunStatus.PENDING)
        self._repo.save_state(state)

        # ── QUEUED ─────────────────────────────────────────────────────
        state = state.model_copy(
            update={
                "status": RunStatus.QUEUED,
                "timestamps": {**state.timestamps, "queued": _utcnow()},
            }
        )
        self._repo.save_state(state)

        # ── RUNNING ────────────────────────────────────────────────────
        state = state.model_copy(
            update={
                "status": RunStatus.RUNNING,
                "timestamps": {**state.timestamps, "started": _utcnow()},
            }
        )
        self._repo.save_state(state)

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
        state = self._enter_stage(state, PipelineStage.OBJECTIVE_RESOLUTION)
        self._repo.save_state(state)

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

        # ------------------------------------------------------------------
        # Stage 2: KNOWLEDGE RETRIEVAL
        # ------------------------------------------------------------------
        retrieval_ctx = RetrievalContext(
            project_context=project,
            run_configuration=run_config,
            structured_objective=structured_objective,
        )

        state = self._enter_stage(state, PipelineStage.RETRIEVAL)
        self._repo.save_state(state)

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

        # ------------------------------------------------------------------
        # Stage 3: PLANNING
        # ------------------------------------------------------------------
        state = self._enter_stage(state, PipelineStage.PLANNING)
        self._repo.save_state(state)

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

        # ------------------------------------------------------------------
        # Stage 4: VALIDATION
        # ------------------------------------------------------------------
        state = self._enter_stage(state, PipelineStage.VALIDATION)
        self._repo.save_state(state)

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

        # ------------------------------------------------------------------
        # Stage 5: POST-PLAN ANALYSIS
        # ------------------------------------------------------------------
        # Post-Plan failure does NOT short-circuit the run.  A valid
        # Planner + Validator result stays COMPLETE regardless of whether
        # Post-Plan Analysis completes, partially completes, or fails.
        post_plan_status = PostPlanAnalysisStatus.RUNNING
        state = self._enter_stage(state, PipelineStage.POST_PLAN)
        state = state.model_copy(update={"post_plan_analysis_status": post_plan_status})
        self._repo.save_state(state)

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
