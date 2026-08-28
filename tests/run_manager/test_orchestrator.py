"""
Tests for ``app.run_manager`` — RunOrchestrator, RunRepository, ProgressTracker.

Coverage
--------
- Successful end-to-end run (all fields, timestamps, repository)
- All five defined failure paths with short-circuit verification
- State transitions (PENDING → QUEUED → RUNNING → COMPLETE | FAILED)
- Progress tracking (weights, monotonicity, partial / full)
- Pipeline ordering and short-circuit behavior
- Repository persistence (save, load, overwrite, has_result)
"""

from __future__ import annotations

import pytest

from app.models.evidence import EvidenceRecord
from app.models.failures import FailureCode
from app.models.post_plan import PostPlanResult, PostPlanStatus
from app.models.requests import (
    AmbiguityStatus,
    ProjectContext,
    RunConfiguration,
    Scope,
    StrategyMode,
)
from app.models.responses import RunResult, Strategy
from app.models.run_state import PostPlanAnalysisStatus, RunState, RunStatus
from app.run_manager import RunOrchestrator, RunRepository
from app.run_manager.progress import ProgressTracker
from app.run_manager.repository import RunNotFoundError
from app.run_manager.state import STAGE_ORDER, PipelineStage
from app.run_manager.stubs import (
    StubEvidenceRetriever,
    StubObjectiveResolver,
    StubPostPlanAnalyzer,
    StubStrategicPlanner,
    StubStrategyValidator,
)

# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def _project() -> ProjectContext:
    return ProjectContext(
        project_id="test-proj-001",
        species="Canis lupus",
        scope=Scope.DE_EXTINCTION,
        objective="Make the coat white.",
    )


def _run_config() -> RunConfiguration:
    return RunConfiguration(max_edits=3, strategy=StrategyMode.MINIMAL)


def _make_orchestrator(
    *,
    resolver: object | None = None,
    retriever: object | None = None,
    planner: object | None = None,
    validator: object | None = None,
    analyzer: object | None = None,
) -> tuple[RunOrchestrator, RunRepository]:
    """Build an orchestrator with all-default stubs; individual stages are overrideable."""
    repo = RunRepository()
    orch = RunOrchestrator(
        resolver=resolver or StubObjectiveResolver(),  # type: ignore[arg-type]
        retriever=retriever or StubEvidenceRetriever(),  # type: ignore[arg-type]
        planner=planner or StubStrategicPlanner(),  # type: ignore[arg-type]
        validator=validator or StubStrategyValidator(),  # type: ignore[arg-type]
        analyzer=analyzer or StubPostPlanAnalyzer(),  # type: ignore[arg-type]
        repository=repo,
    )
    return orch, repo


class _AnalyzerCallTracker:
    """Wraps ``StubPostPlanAnalyzer`` to detect whether ``analyze()`` was invoked."""

    def __init__(self, *, return_status: str = "complete") -> None:
        self.called = False
        self._inner = StubPostPlanAnalyzer(return_status=return_status)

    async def analyze(
        self,
        strategy: Strategy,
        evidence: list[EvidenceRecord],
        run_config: RunConfiguration,
    ) -> PostPlanResult:
        self.called = True
        return await self._inner.analyze(strategy, evidence, run_config)


# ===========================================================================
# Successful run
# ===========================================================================


class TestSuccessfulRun:
    async def test_status_is_complete(self) -> None:
        orch, _ = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        assert result.status == RunStatus.COMPLETE

    async def test_run_id_is_non_empty_string(self) -> None:
        orch, _ = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        assert isinstance(result.run_id, str)
        assert len(result.run_id) > 0

    async def test_unique_run_ids(self) -> None:
        orch, _ = _make_orchestrator()
        result_a = await orch.execute(_project(), _run_config())
        result_b = await orch.execute(_project(), _run_config())
        assert result_a.run_id != result_b.run_id

    async def test_result_persisted_in_repository(self) -> None:
        orch, repo = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        loaded = repo.load_result(result.run_id)
        assert loaded.run_id == result.run_id

    async def test_structured_objective_present(self) -> None:
        orch, _ = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        assert result.structured_objective is not None
        assert result.structured_objective.ambiguity_status == AmbiguityStatus.CLEAR

    async def test_strategies_present(self) -> None:
        orch, _ = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        assert len(result.strategies) > 0

    async def test_selected_strategy_is_first_ranked(self) -> None:
        orch, _ = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        assert result.selected_strategy is not None
        assert result.selected_strategy == result.strategies[0]

    async def test_validation_present_and_passed(self) -> None:
        orch, _ = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        assert result.validation is not None
        assert result.validation.valid is True

    async def test_post_plan_present_and_complete(self) -> None:
        orch, _ = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        assert result.post_plan is not None
        assert result.post_plan.status == PostPlanStatus.COMPLETE

    async def test_no_failure_detail_on_full_success(self) -> None:
        orch, _ = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        assert result.failure is None

    async def test_project_context_echoed(self) -> None:
        orch, _ = _make_orchestrator()
        project = _project()
        result = await orch.execute(project, _run_config())
        assert result.project_context.species == project.species

    async def test_run_configuration_echoed(self) -> None:
        orch, _ = _make_orchestrator()
        cfg = _run_config()
        result = await orch.execute(_project(), cfg)
        assert result.run_configuration.max_edits == cfg.max_edits

    async def test_final_state_in_repo_is_complete(self) -> None:
        orch, repo = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        assert repo.load_state(result.run_id).status == RunStatus.COMPLETE

    async def test_final_state_progress_is_one(self) -> None:
        orch, repo = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        assert repo.load_state(result.run_id).progress == pytest.approx(1.0)

    async def test_timestamps_queued_started_completed(self) -> None:
        orch, repo = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        state = repo.load_state(result.run_id)
        assert "queued" in state.timestamps
        assert "started" in state.timestamps
        assert "completed" in state.timestamps

    async def test_post_plan_analysis_status_complete_in_state(self) -> None:
        orch, repo = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        state = repo.load_state(result.run_id)
        assert state.post_plan_analysis_status == PostPlanAnalysisStatus.COMPLETE


# ===========================================================================
# Failure path: CLARIFICATION_REQUIRED
# ===========================================================================


class TestClarificationRequired:
    async def test_status_is_failed(self) -> None:
        orch, _ = _make_orchestrator(
            resolver=StubObjectiveResolver(clarification_required=True)
        )
        result = await orch.execute(_project(), _run_config())
        assert result.status == RunStatus.FAILED

    async def test_failure_code(self) -> None:
        orch, _ = _make_orchestrator(
            resolver=StubObjectiveResolver(clarification_required=True)
        )
        result = await orch.execute(_project(), _run_config())
        assert result.failure is not None
        assert result.failure.code == FailureCode.CLARIFICATION_REQUIRED

    async def test_structured_objective_returned(self) -> None:
        """Resolver produced a StructuredObjective before returning CLARIFICATION_REQUIRED."""
        orch, _ = _make_orchestrator(
            resolver=StubObjectiveResolver(clarification_required=True)
        )
        result = await orch.execute(_project(), _run_config())
        assert result.structured_objective is not None
        assert (
            result.structured_objective.ambiguity_status
            == AmbiguityStatus.CLARIFICATION_REQUIRED
        )

    async def test_no_strategies(self) -> None:
        orch, _ = _make_orchestrator(
            resolver=StubObjectiveResolver(clarification_required=True)
        )
        result = await orch.execute(_project(), _run_config())
        assert result.strategies == []

    async def test_post_plan_not_executed(self) -> None:
        tracker = _AnalyzerCallTracker()
        orch, _ = _make_orchestrator(
            resolver=StubObjectiveResolver(clarification_required=True),
            analyzer=tracker,
        )
        await orch.execute(_project(), _run_config())
        assert tracker.called is False

    async def test_state_in_repo_is_failed(self) -> None:
        orch, repo = _make_orchestrator(
            resolver=StubObjectiveResolver(clarification_required=True)
        )
        result = await orch.execute(_project(), _run_config())
        assert repo.load_state(result.run_id).status == RunStatus.FAILED

    async def test_failed_timestamp_present(self) -> None:
        orch, repo = _make_orchestrator(
            resolver=StubObjectiveResolver(clarification_required=True)
        )
        result = await orch.execute(_project(), _run_config())
        assert "failed" in repo.load_state(result.run_id).timestamps


# ===========================================================================
# Failure path: INSUFFICIENT_EVIDENCE
# ===========================================================================


class TestInsufficientEvidence:
    async def test_status_is_failed(self) -> None:
        orch, _ = _make_orchestrator(retriever=StubEvidenceRetriever(return_empty=True))
        result = await orch.execute(_project(), _run_config())
        assert result.status == RunStatus.FAILED

    async def test_failure_code(self) -> None:
        orch, _ = _make_orchestrator(retriever=StubEvidenceRetriever(return_empty=True))
        result = await orch.execute(_project(), _run_config())
        assert result.failure is not None
        assert result.failure.code == FailureCode.INSUFFICIENT_EVIDENCE

    async def test_structured_objective_present(self) -> None:
        """Objective resolution succeeded; StructuredObjective is in the result."""
        orch, _ = _make_orchestrator(retriever=StubEvidenceRetriever(return_empty=True))
        result = await orch.execute(_project(), _run_config())
        assert result.structured_objective is not None

    async def test_no_strategies(self) -> None:
        orch, _ = _make_orchestrator(retriever=StubEvidenceRetriever(return_empty=True))
        result = await orch.execute(_project(), _run_config())
        assert result.strategies == []

    async def test_post_plan_not_executed(self) -> None:
        tracker = _AnalyzerCallTracker()
        orch, _ = _make_orchestrator(
            retriever=StubEvidenceRetriever(return_empty=True),
            analyzer=tracker,
        )
        await orch.execute(_project(), _run_config())
        assert tracker.called is False


# ===========================================================================
# Failure path: NO_FEASIBLE_PLAN
# ===========================================================================


class TestNoFeasiblePlan:
    async def test_status_is_failed(self) -> None:
        orch, _ = _make_orchestrator(planner=StubStrategicPlanner(return_empty=True))
        result = await orch.execute(_project(), _run_config())
        assert result.status == RunStatus.FAILED

    async def test_failure_code(self) -> None:
        orch, _ = _make_orchestrator(planner=StubStrategicPlanner(return_empty=True))
        result = await orch.execute(_project(), _run_config())
        assert result.failure is not None
        assert result.failure.code == FailureCode.NO_FEASIBLE_PLAN

    async def test_post_plan_not_executed(self) -> None:
        tracker = _AnalyzerCallTracker()
        orch, _ = _make_orchestrator(
            planner=StubStrategicPlanner(return_empty=True),
            analyzer=tracker,
        )
        await orch.execute(_project(), _run_config())
        assert tracker.called is False

    async def test_validation_not_present(self) -> None:
        """Validation stage was never reached."""
        orch, _ = _make_orchestrator(planner=StubStrategicPlanner(return_empty=True))
        result = await orch.execute(_project(), _run_config())
        assert result.validation is None


# ===========================================================================
# Failure path: VALIDATION_FAILED
# ===========================================================================


class TestValidationFailed:
    async def test_status_is_failed(self) -> None:
        orch, _ = _make_orchestrator(validator=StubStrategyValidator(return_valid=False))
        result = await orch.execute(_project(), _run_config())
        assert result.status == RunStatus.FAILED

    async def test_failure_code(self) -> None:
        orch, _ = _make_orchestrator(validator=StubStrategyValidator(return_valid=False))
        result = await orch.execute(_project(), _run_config())
        assert result.failure is not None
        assert result.failure.code == FailureCode.VALIDATION_FAILED

    async def test_validation_result_present(self) -> None:
        """ValidationResult is included in the RunResult even when validation failed."""
        orch, _ = _make_orchestrator(validator=StubStrategyValidator(return_valid=False))
        result = await orch.execute(_project(), _run_config())
        assert result.validation is not None
        assert result.validation.valid is False

    async def test_post_plan_not_executed(self) -> None:
        tracker = _AnalyzerCallTracker()
        orch, _ = _make_orchestrator(
            validator=StubStrategyValidator(return_valid=False),
            analyzer=tracker,
        )
        await orch.execute(_project(), _run_config())
        assert tracker.called is False

    async def test_strategies_present(self) -> None:
        """Planner succeeded; strategies are accessible even though validation failed."""
        orch, _ = _make_orchestrator(validator=StubStrategyValidator(return_valid=False))
        result = await orch.execute(_project(), _run_config())
        assert len(result.strategies) > 0


# ===========================================================================
# Partial Post-Plan Analysis (run stays COMPLETE)
# ===========================================================================


class TestPartialAnalysis:
    async def test_run_status_is_complete(self) -> None:
        """
        Architecture §3.10: run.status is independent of post_plan_analysis_status.
        A valid Planner + Validator result stays COMPLETE with PARTIAL analysis.
        """
        orch, _ = _make_orchestrator(analyzer=StubPostPlanAnalyzer(return_status="partial"))
        result = await orch.execute(_project(), _run_config())
        assert result.status == RunStatus.COMPLETE

    async def test_post_plan_status_is_partial(self) -> None:
        orch, _ = _make_orchestrator(analyzer=StubPostPlanAnalyzer(return_status="partial"))
        result = await orch.execute(_project(), _run_config())
        assert result.post_plan is not None
        assert result.post_plan.status == PostPlanStatus.PARTIAL

    async def test_failure_code_is_partial_analysis(self) -> None:
        orch, _ = _make_orchestrator(analyzer=StubPostPlanAnalyzer(return_status="partial"))
        result = await orch.execute(_project(), _run_config())
        assert result.failure is not None
        assert result.failure.code == FailureCode.PARTIAL_ANALYSIS

    async def test_post_plan_analysis_status_in_state(self) -> None:
        orch, repo = _make_orchestrator(
            analyzer=StubPostPlanAnalyzer(return_status="partial")
        )
        result = await orch.execute(_project(), _run_config())
        state = repo.load_state(result.run_id)
        assert state.post_plan_analysis_status == PostPlanAnalysisStatus.PARTIAL

    async def test_statuses_are_independent(self) -> None:
        """run.status=COMPLETE and post_plan_analysis_status=PARTIAL simultaneously."""
        orch, repo = _make_orchestrator(
            analyzer=StubPostPlanAnalyzer(return_status="partial")
        )
        result = await orch.execute(_project(), _run_config())
        state = repo.load_state(result.run_id)
        assert state.status == RunStatus.COMPLETE
        assert state.post_plan_analysis_status == PostPlanAnalysisStatus.PARTIAL

    async def test_validation_still_passed(self) -> None:
        orch, _ = _make_orchestrator(analyzer=StubPostPlanAnalyzer(return_status="partial"))
        result = await orch.execute(_project(), _run_config())
        assert result.validation is not None
        assert result.validation.valid is True


# ===========================================================================
# Progress tracking
# ===========================================================================


class TestProgressTracker:
    def test_starts_at_zero(self) -> None:
        tracker = ProgressTracker()
        assert tracker.progress == 0.0

    def test_advances_after_first_stage(self) -> None:
        tracker = ProgressTracker()
        tracker.stage_completed(PipelineStage.OBJECTIVE_RESOLUTION)
        assert tracker.progress > 0.0

    def test_all_stages_reach_one(self) -> None:
        tracker = ProgressTracker()
        for stage in STAGE_ORDER:
            tracker.stage_completed(stage)
        assert tracker.progress == pytest.approx(1.0)

    def test_complete_sets_to_one(self) -> None:
        tracker = ProgressTracker()
        tracker.complete()
        assert tracker.progress == pytest.approx(1.0)

    def test_monotonically_increases(self) -> None:
        tracker = ProgressTracker()
        prev = 0.0
        for stage in STAGE_ORDER:
            tracker.stage_completed(stage)
            assert tracker.progress >= prev
            prev = tracker.progress

    async def test_successful_run_final_progress_is_one(self) -> None:
        orch, repo = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        assert repo.load_state(result.run_id).progress == pytest.approx(1.0)

    async def test_failed_run_has_nonzero_progress_after_first_stage(self) -> None:
        """After OBJECTIVE_RESOLUTION completes and RETRIEVAL fails, progress > 0."""
        orch, repo = _make_orchestrator(
            retriever=StubEvidenceRetriever(return_empty=True)
        )
        result = await orch.execute(_project(), _run_config())
        assert repo.load_state(result.run_id).progress > 0.0


# ===========================================================================
# State transitions
# ===========================================================================


class TestStateTransitions:
    async def test_complete_for_successful_run(self) -> None:
        orch, repo = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        assert repo.load_state(result.run_id).status == RunStatus.COMPLETE

    async def test_failed_for_clarification_required(self) -> None:
        orch, repo = _make_orchestrator(
            resolver=StubObjectiveResolver(clarification_required=True)
        )
        result = await orch.execute(_project(), _run_config())
        assert repo.load_state(result.run_id).status == RunStatus.FAILED

    async def test_failed_for_insufficient_evidence(self) -> None:
        orch, repo = _make_orchestrator(retriever=StubEvidenceRetriever(return_empty=True))
        result = await orch.execute(_project(), _run_config())
        assert repo.load_state(result.run_id).status == RunStatus.FAILED

    async def test_failed_for_no_feasible_plan(self) -> None:
        orch, repo = _make_orchestrator(planner=StubStrategicPlanner(return_empty=True))
        result = await orch.execute(_project(), _run_config())
        assert repo.load_state(result.run_id).status == RunStatus.FAILED

    async def test_failed_for_validation_failed(self) -> None:
        orch, repo = _make_orchestrator(validator=StubStrategyValidator(return_valid=False))
        result = await orch.execute(_project(), _run_config())
        assert repo.load_state(result.run_id).status == RunStatus.FAILED

    async def test_queued_timestamp_present(self) -> None:
        orch, repo = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        assert "queued" in repo.load_state(result.run_id).timestamps

    async def test_started_timestamp_present(self) -> None:
        orch, repo = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        assert "started" in repo.load_state(result.run_id).timestamps

    async def test_completed_timestamp_for_successful_run(self) -> None:
        orch, repo = _make_orchestrator()
        result = await orch.execute(_project(), _run_config())
        assert "completed" in repo.load_state(result.run_id).timestamps

    async def test_failed_timestamp_for_failed_run(self) -> None:
        orch, repo = _make_orchestrator(
            resolver=StubObjectiveResolver(clarification_required=True)
        )
        result = await orch.execute(_project(), _run_config())
        assert "failed" in repo.load_state(result.run_id).timestamps


# ===========================================================================
# Pipeline ordering / short-circuit behavior
# ===========================================================================


class TestPipelineOrdering:
    async def test_post_plan_skipped_on_objective_failure(self) -> None:
        tracker = _AnalyzerCallTracker()
        orch, _ = _make_orchestrator(
            resolver=StubObjectiveResolver(clarification_required=True),
            analyzer=tracker,
        )
        await orch.execute(_project(), _run_config())
        assert tracker.called is False

    async def test_post_plan_skipped_on_retrieval_failure(self) -> None:
        tracker = _AnalyzerCallTracker()
        orch, _ = _make_orchestrator(
            retriever=StubEvidenceRetriever(return_empty=True),
            analyzer=tracker,
        )
        await orch.execute(_project(), _run_config())
        assert tracker.called is False

    async def test_post_plan_skipped_on_planning_failure(self) -> None:
        tracker = _AnalyzerCallTracker()
        orch, _ = _make_orchestrator(
            planner=StubStrategicPlanner(return_empty=True),
            analyzer=tracker,
        )
        await orch.execute(_project(), _run_config())
        assert tracker.called is False

    async def test_post_plan_skipped_on_validation_failure(self) -> None:
        tracker = _AnalyzerCallTracker()
        orch, _ = _make_orchestrator(
            validator=StubStrategyValidator(return_valid=False),
            analyzer=tracker,
        )
        await orch.execute(_project(), _run_config())
        assert tracker.called is False

    async def test_post_plan_executed_when_all_prior_stages_pass(self) -> None:
        tracker = _AnalyzerCallTracker()
        orch, _ = _make_orchestrator(analyzer=tracker)
        await orch.execute(_project(), _run_config())
        assert tracker.called is True

    def test_stage_order_starts_with_objective_resolution(self) -> None:
        assert STAGE_ORDER[0] == PipelineStage.OBJECTIVE_RESOLUTION

    def test_stage_order_ends_with_post_plan(self) -> None:
        assert STAGE_ORDER[-1] == PipelineStage.POST_PLAN

    def test_stage_order_has_five_stages(self) -> None:
        assert len(STAGE_ORDER) == 5


# ===========================================================================
# Repository
# ===========================================================================


class TestRunRepository:
    def test_save_and_load_state(self) -> None:
        repo = RunRepository()
        state = RunState(run_id="r1", status=RunStatus.PENDING)
        repo.save_state(state)
        loaded = repo.load_state("r1")
        assert loaded.run_id == "r1"
        assert loaded.status == RunStatus.PENDING

    def test_load_state_raises_for_unknown_id(self) -> None:
        repo = RunRepository()
        with pytest.raises(RunNotFoundError):
            repo.load_state("nonexistent")

    def test_save_and_load_result(self) -> None:
        repo = RunRepository()
        result = RunResult(
            run_id="r2",
            status=RunStatus.FAILED,
            project_context=_project(),
            run_configuration=_run_config(),
        )
        repo.save_result(result)
        loaded = repo.load_result("r2")
        assert loaded.run_id == "r2"

    def test_load_result_raises_for_unknown_id(self) -> None:
        repo = RunRepository()
        with pytest.raises(RunNotFoundError):
            repo.load_result("nonexistent")

    def test_has_result_false_before_save(self) -> None:
        repo = RunRepository()
        assert repo.has_result("nonexistent") is False

    def test_has_result_true_after_save(self) -> None:
        repo = RunRepository()
        result = RunResult(
            run_id="r3",
            status=RunStatus.COMPLETE,
            project_context=_project(),
            run_configuration=_run_config(),
        )
        repo.save_result(result)
        assert repo.has_result("r3") is True

    def test_all_states_empty_initially(self) -> None:
        repo = RunRepository()
        assert repo.all_states() == []

    def test_all_states_returns_all_saved(self) -> None:
        repo = RunRepository()
        repo.save_state(RunState(run_id="r4", status=RunStatus.PENDING))
        repo.save_state(RunState(run_id="r5", status=RunStatus.RUNNING))
        assert len(repo.all_states()) == 2

    def test_state_overwritten_on_re_save(self) -> None:
        repo = RunRepository()
        repo.save_state(RunState(run_id="r6", status=RunStatus.PENDING))
        repo.save_state(RunState(run_id="r6", status=RunStatus.COMPLETE))
        assert repo.load_state("r6").status == RunStatus.COMPLETE
