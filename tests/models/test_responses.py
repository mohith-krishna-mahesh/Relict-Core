"""Tests for app.models.responses — Strategy and RunResult."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.failures import FailureCode, FailureDetail
from app.models.graph import GraphEdge
from app.models.post_plan import PostPlanResult, PostPlanStatus
from app.models.requests import (
    ProjectContext,
    RunConfiguration,
    Scope,
    StrategyMode,
    StructuredObjective,
)
from app.models.responses import RunResult, Strategy
from app.models.run_state import RunStatus
from app.models.validation import ValidationResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _project() -> ProjectContext:
    return ProjectContext(
        project_id="proj-001",
        species="Canis lupus",
        scope=Scope.DE_EXTINCTION,
        objective="Make the coat white.",
    )


def _run_config() -> RunConfiguration:
    return RunConfiguration(max_edits=3, strategy=StrategyMode.MINIMAL)


def _edge() -> GraphEdge:
    return GraphEdge(
        source_node_id="gene:TYRP1",
        target_node_id="gene:DCT",
        relationship="functional_association",
        source="STRING",
        source_score=0.91,
    )


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------


class TestStrategy:
    def test_minimal_valid_instance(self) -> None:
        s = Strategy(
            strategy_type=StrategyMode.MINIMAL,
            edit_count=2,
            score=0.85,
            rationale="Covers primary pigmentation pathway with two edits.",
        )
        assert s.strategy_type == StrategyMode.MINIMAL
        assert s.edit_count == 2
        assert s.selected_candidates == []
        assert s.supporting_edges == []
        assert s.conflicting_edges == []

    def test_full_valid_instance(self) -> None:
        edge = _edge()
        s = Strategy(
            strategy_type=StrategyMode.REDUNDANT,
            selected_candidates=["TYRP1", "DCT"],
            covered_targets=["coat_pigmentation"],
            edit_count=2,
            score=0.92,
            supporting_edges=[edge],
            conflicting_edges=[],
            rationale="Two independent routes to pigmentation suppression.",
        )
        assert s.strategy_type == StrategyMode.REDUNDANT
        assert len(s.supporting_edges) == 1

    def test_missing_edit_count_raises(self) -> None:
        with pytest.raises(ValidationError):
            Strategy(  # type: ignore[call-arg]
                strategy_type=StrategyMode.MINIMAL, score=0.5, rationale="x"
            )

    def test_missing_score_raises(self) -> None:
        with pytest.raises(ValidationError):
            Strategy(  # type: ignore[call-arg]
                strategy_type=StrategyMode.MINIMAL, edit_count=1, rationale="x"
            )

    def test_missing_rationale_raises(self) -> None:
        with pytest.raises(ValidationError):
            Strategy(  # type: ignore[call-arg]
                strategy_type=StrategyMode.MINIMAL, edit_count=1, score=0.5
            )

    def test_wrong_strategy_type_raises(self) -> None:
        with pytest.raises((ValueError, ValidationError)):
            Strategy(
                strategy_type="optimal",  # type: ignore
                edit_count=1,
                score=0.5,
                rationale="x",
            )


# ---------------------------------------------------------------------------
# RunResult
# ---------------------------------------------------------------------------


class TestRunResult:
    def test_minimal_failed_run(self) -> None:
        """Short-circuit failure path: most optional fields are None/empty."""
        result = RunResult(
            run_id="run-001",
            status=RunStatus.FAILED,
            project_context=_project(),
            run_configuration=_run_config(),
            failure=FailureDetail(
                code=FailureCode.INSUFFICIENT_EVIDENCE,
                message="Not enough evidence.",
                stage="knowledge_retrieval",
            ),
        )
        assert result.status == RunStatus.FAILED
        assert result.failure is not None
        assert result.failure.code == FailureCode.INSUFFICIENT_EVIDENCE
        assert result.structured_objective is None
        assert result.strategies == []
        assert result.validation is None
        assert result.post_plan is None

    def test_successful_run_with_all_fields(self) -> None:
        strat = Strategy(
            strategy_type=StrategyMode.MINIMAL,
            selected_candidates=["TYRP1"],
            covered_targets=["coat_pigmentation"],
            edit_count=1,
            score=0.9,
            supporting_edges=[_edge()],
            conflicting_edges=[],
            rationale="Single edit covers primary target.",
        )
        result = RunResult(
            run_id="run-002",
            status=RunStatus.COMPLETE,
            project_context=_project(),
            run_configuration=_run_config(),
            structured_objective=StructuredObjective(desired_change="white coat"),
            strategies=[strat],
            selected_strategy=strat,
            validation=ValidationResult(valid=True, checks=["edit_budget"]),
            post_plan=PostPlanResult(
                status=PostPlanStatus.COMPLETE,
                strategy_explanation="Targets pigmentation via TYRP1.",
            ),
            failure=None,
            warnings=["Ortholog confidence below 0.8 for DCT."],
        )
        assert result.status == RunStatus.COMPLETE
        assert len(result.strategies) == 1
        assert result.validation is not None
        assert result.validation.valid is True
        assert result.post_plan is not None

    def test_complete_run_partial_analysis(self) -> None:
        """
        Status=COMPLETE with PostPlanResult.status=PARTIAL and
        FailureCode.PARTIAL_ANALYSIS on failure is a valid RunResult.
        """
        result = RunResult(
            run_id="run-003",
            status=RunStatus.COMPLETE,
            project_context=_project(),
            run_configuration=_run_config(),
            structured_objective=StructuredObjective(desired_change="white coat"),
            strategies=[
                Strategy(
                    strategy_type=StrategyMode.MINIMAL,
                    edit_count=1,
                    score=0.88,
                    rationale="r",
                )
            ],
            validation=ValidationResult(valid=True),
            post_plan=PostPlanResult(
                status=PostPlanStatus.PARTIAL,
                strategy_explanation="Explanation generated.",
            ),
            failure=FailureDetail(
                code=FailureCode.PARTIAL_ANALYSIS,
                message="CRISPOR unavailable.",
                stage="guide_risk",
            ),
        )
        assert result.status == RunStatus.COMPLETE
        assert result.post_plan is not None
        assert result.post_plan.status == PostPlanStatus.PARTIAL
        assert result.failure is not None
        assert result.failure.code == FailureCode.PARTIAL_ANALYSIS

    def test_missing_run_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            RunResult(
                status=RunStatus.PENDING,
                project_context=_project(),
                run_configuration=_run_config(),
            )  # type: ignore[call-arg]

    def test_missing_project_context_raises(self) -> None:
        with pytest.raises(ValidationError):
            RunResult(
                run_id="x",
                status=RunStatus.PENDING,
                run_configuration=_run_config(),
            )  # type: ignore[call-arg]
