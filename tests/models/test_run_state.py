"""Tests for app.models.run_state — RunStatus, PostPlanAnalysisStatus, RunState."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.run_state import PostPlanAnalysisStatus, RunState, RunStatus

# ---------------------------------------------------------------------------
# RunStatus enum
# ---------------------------------------------------------------------------


class TestRunStatus:
    def test_all_values_present(self) -> None:
        values = {rs.value for rs in RunStatus}
        assert values == {"pending", "queued", "running", "complete", "failed"}

    def test_string_equality(self) -> None:
        assert RunStatus.COMPLETE == "complete"
        assert RunStatus.FAILED == "failed"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises((ValueError, ValidationError)):
            RunState(run_id="x", status="nonexistent")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PostPlanAnalysisStatus enum
# ---------------------------------------------------------------------------


class TestPostPlanAnalysisStatus:
    def test_all_values_present(self) -> None:
        values = {s.value for s in PostPlanAnalysisStatus}
        assert values == {"pending", "running", "complete", "partial", "failed"}

    def test_partial_value_exists(self) -> None:
        assert PostPlanAnalysisStatus.PARTIAL == "partial"


# ---------------------------------------------------------------------------
# RunState model — mandatory cross-field independence test
# ---------------------------------------------------------------------------


class TestRunState:
    def test_complete_with_partial_analysis_is_valid(self) -> None:
        """
        Architecture §3.10 explicitly states:
            status = complete  AND  post_plan_analysis_status = partial
        must be a valid combination.  This test asserts it raises no error.
        """
        state = RunState(
            run_id="run-001",
            status=RunStatus.COMPLETE,
            post_plan_analysis_status=PostPlanAnalysisStatus.PARTIAL,
        )
        assert state.status == RunStatus.COMPLETE
        assert state.post_plan_analysis_status == PostPlanAnalysisStatus.PARTIAL

    def test_minimal_valid_instance(self) -> None:
        state = RunState(run_id="run-002", status=RunStatus.PENDING)
        assert state.run_id == "run-002"
        assert state.status == RunStatus.PENDING
        assert state.post_plan_analysis_status == PostPlanAnalysisStatus.PENDING
        assert state.progress == 0.0
        assert state.current_stage is None
        assert state.timestamps == {}
        assert state.errors == []

    def test_full_valid_instance(self) -> None:
        now = datetime.now(tz=UTC)
        state = RunState(
            run_id="run-003",
            status=RunStatus.RUNNING,
            current_stage="knowledge_retrieval",
            progress=0.35,
            post_plan_analysis_status=PostPlanAnalysisStatus.PENDING,
            timestamps={"queued": now, "started": now},
            errors=[],
        )
        assert state.progress == 0.35
        assert state.current_stage == "knowledge_retrieval"

    def test_progress_below_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            RunState(run_id="x", status=RunStatus.PENDING, progress=-0.1)

    def test_progress_above_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            RunState(run_id="x", status=RunStatus.PENDING, progress=1.01)

    def test_missing_run_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            RunState(status=RunStatus.PENDING)  # type: ignore[call-arg]

    def test_missing_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            RunState(run_id="x")  # type: ignore[call-arg]

    def test_invalid_status_string_raises(self) -> None:
        with pytest.raises(ValidationError):
            RunState(run_id="x", status="invalid_status")  # type: ignore[arg-type]

    def test_failed_run_with_errors(self) -> None:
        state = RunState(
            run_id="run-004",
            status=RunStatus.FAILED,
            errors=["Planner found no feasible strategy."],
        )
        assert len(state.errors) == 1
        assert state.status == RunStatus.FAILED
