"""
Failure-Path Integration Tests for Relict Core.

Verifies that each failure condition correctly short-circuits the pipeline
and attaches the contractually defined failure code:
A. CLARIFICATION_REQUIRED (Ambiguous objective)
B. INSUFFICIENT_EVIDENCE (Empty / insufficient evidence records)
C. NO_FEASIBLE_PLAN (Zero feasible strategies found by planner)
D. VALIDATION_FAILED (Validator rejects candidate strategy)
E. PARTIAL_ANALYSIS (Optional downstream post-plan tool fails gracefully)
"""

from __future__ import annotations

from typing import Any

import pytest

from app.cache.sqlite_client import ensure_schema, open_connection
from app.cache.sqlite_repository import SQLiteRunRepository
from app.core_model.resolver import CoreModelObjectiveResolver
from app.models.evidence import EffectDirection, EffectType, EvidenceEffect, EvidenceRecord
from app.models.failures import FailureCode
from app.models.post_plan import PostPlanResult, PostPlanStatus
from app.models.requests import (
    ProjectContext,
    RetrievalContext,
    RunConfiguration,
    Scope,
    StrategyMode,
    StructuredObjective,
)
from app.models.responses import RetrievalResult, SourceStatus, Strategy
from app.models.run_state import PostPlanAnalysisStatus, RunStatus
from app.models.validation import ValidationResult
from app.planner.adapter import ProductionStrategicPlanner
from app.post_plan.analyzer import DefaultPostPlanAnalyzer
from app.run_manager.events import InMemoryRunEventBus
from app.run_manager.orchestrator import RunOrchestrator
from app.validator.plan_validator import PlanValidator


@pytest.mark.asyncio
async def test_failure_clarification_required(tmp_path: Any) -> None:
    """Ambiguous objective must terminate pipeline immediately with CLARIFICATION_REQUIRED."""
    conn = open_connection(tmp_path / "test_clarif.db")
    ensure_schema(conn)
    repo = SQLiteRunRepository(conn)
    bus = InMemoryRunEventBus()

    orchestrator = RunOrchestrator(
        resolver=CoreModelObjectiveResolver(),
        retriever=None,  # type: ignore[arg-type]
        planner=None,  # type: ignore[arg-type]
        validator=None,  # type: ignore[arg-type]
        analyzer=None,  # type: ignore[arg-type]
        repository=repo,
        event_bus=bus,
    )

    project = ProjectContext(
        project_id="proj_ambig",
        scope=Scope.CONSERVATION,
        species="Panthera tigris",
        objective="Enhance wild species resilience through modern genomic techniques.",
    )
    config = RunConfiguration(
        max_edits=2,
        strategy=StrategyMode.MINIMAL,
        candidate_genes=[],
        constraints=[],
    )

    result = await orchestrator.execute(project, config)

    assert result.status == RunStatus.FAILED
    assert result.failure is not None
    assert result.failure.code == FailureCode.CLARIFICATION_REQUIRED
    assert result.strategies == []
    conn.close()


@pytest.mark.asyncio
async def test_failure_insufficient_evidence(tmp_path: Any) -> None:
    """Empty retrieval evidence must terminate pipeline with INSUFFICIENT_EVIDENCE."""
    conn = open_connection(tmp_path / "test_insuff.db")
    ensure_schema(conn)
    repo = SQLiteRunRepository(conn)
    bus = InMemoryRunEventBus()

    class EmptyRetrieval:
        async def retrieve(self, ctx: RetrievalContext) -> RetrievalResult:
            return RetrievalResult(
                records=[], source_statuses=[], failure_code=FailureCode.INSUFFICIENT_EVIDENCE
            )

    orchestrator = RunOrchestrator(
        resolver=CoreModelObjectiveResolver(),
        retriever=EmptyRetrieval(),
        planner=None,  # type: ignore[arg-type]
        validator=None,  # type: ignore[arg-type]
        analyzer=None,  # type: ignore[arg-type]
        repository=repo,
        event_bus=bus,
    )

    project = ProjectContext(
        project_id="proj_no_ev",
        scope=Scope.PRECISION_MEDICINE,
        species="Homo sapiens",
        objective="Correct homozygous F508del triplet deletion in CFTR to restore chloride transport",
    )
    config = RunConfiguration(
        max_edits=2,
        strategy=StrategyMode.MINIMAL,
        candidate_genes=["CFTR"],
        constraints=[],
    )

    result = await orchestrator.execute(project, config)

    assert result.status == RunStatus.FAILED
    assert result.failure is not None
    assert result.failure.code == FailureCode.INSUFFICIENT_EVIDENCE
    assert result.strategies == []
    conn.close()


@pytest.mark.asyncio
async def test_failure_no_feasible_plan(tmp_path: Any) -> None:
    """Conflicting constraints yielding 0 strategies must terminate with NO_FEASIBLE_PLAN."""
    conn = open_connection(tmp_path / "test_no_plan.db")
    ensure_schema(conn)
    repo = SQLiteRunRepository(conn)
    bus = InMemoryRunEventBus()

    class MockRetrieval:
        async def retrieve(self, ctx: RetrievalContext) -> RetrievalResult:
            rec = EvidenceRecord(
                entity_a="GENE_A",
                relationship="inhibits",
                entity_b="TRAIT_B",
                source="ensembl",
                source_id="E001",
                source_score=0.9,
                effect=EvidenceEffect(
                    type=EffectType.INHIBITION, direction=EffectDirection.DECREASES
                ),
            )
            return RetrievalResult(records=[rec], source_statuses=[], failure_code=None)

    class EmptyPlanner:
        async def plan(self, ctx: RetrievalContext, ev: list[EvidenceRecord]) -> list[Strategy]:
            return []

    orchestrator = RunOrchestrator(
        resolver=CoreModelObjectiveResolver(),
        retriever=MockRetrieval(),
        planner=EmptyPlanner(),
        validator=None,  # type: ignore[arg-type]
        analyzer=None,  # type: ignore[arg-type]
        repository=repo,
        event_bus=bus,
    )

    project = ProjectContext(
        project_id="proj_no_plan",
        scope=Scope.AGRICULTURE,
        species="Oryza sativa",
        objective="Introgress DRO1 to establish deep rooting architecture under drought",
    )
    config = RunConfiguration(
        max_edits=1,
        strategy=StrategyMode.MINIMAL,
        candidate_genes=["DRO1"],
        constraints=[],
    )

    result = await orchestrator.execute(project, config)

    assert result.status == RunStatus.FAILED
    assert result.failure is not None
    assert result.failure.code == FailureCode.NO_FEASIBLE_PLAN
    conn.close()


@pytest.mark.asyncio
async def test_failure_validation_failed(tmp_path: Any) -> None:
    """Strategy rejected by validator must terminate pipeline with VALIDATION_FAILED."""
    conn = open_connection(tmp_path / "test_val_fail.db")
    ensure_schema(conn)
    repo = SQLiteRunRepository(conn)
    bus = InMemoryRunEventBus()

    class MockRetrieval:
        async def retrieve(self, ctx: RetrievalContext) -> RetrievalResult:
            rec = EvidenceRecord(
                entity_a="GENE_X",
                relationship="activates",
                entity_b="TRAIT_Y",
                source="uniprot",
                source_id="U001",
                source_score=0.9,
                effect=EvidenceEffect(
                    type=EffectType.ACTIVATION, direction=EffectDirection.INCREASES
                ),
            )
            return RetrievalResult(records=[rec], source_statuses=[], failure_code=None)

    class MockPlanner:
        async def plan(self, ctx: RetrievalContext, ev: list[EvidenceRecord]) -> list[Strategy]:
            return [
                Strategy(
                    strategy_type=StrategyMode.MINIMAL,
                    selected_candidates=["GENE_X", "GENE_Y", "GENE_Z"],  # 3 edits
                    covered_targets=["TRAIT_Y"],
                    edit_count=3,
                    score=0.85,
                    rationale="Over-budget candidate strategy",
                )
            ]

    orchestrator = RunOrchestrator(
        resolver=CoreModelObjectiveResolver(),
        retriever=MockRetrieval(),
        planner=MockPlanner(),
        validator=PlanValidator(),  # Will reject because max_edits=1 but edit_count=3
        analyzer=None,  # type: ignore[arg-type]
        repository=repo,
        event_bus=bus,
    )

    project = ProjectContext(
        project_id="proj_val_fail",
        scope=Scope.SYNTHETIC_BIOLOGY,
        species="Escherichia coli",
        objective="Replace native dxs promoter with synthetic constitutive Anderson promoter",
    )
    config = RunConfiguration(
        max_edits=1,  # Budget is 1
        strategy=StrategyMode.MINIMAL,
        candidate_genes=["dxs"],
        constraints=[],
    )

    result = await orchestrator.execute(project, config)

    assert result.status == RunStatus.FAILED
    assert result.failure is not None
    assert result.failure.code == FailureCode.VALIDATION_FAILED
    assert result.post_plan is None
    conn.close()


@pytest.mark.asyncio
async def test_partial_analysis_preserves_valid_strategy(tmp_path: Any) -> None:
    """Downstream tool failure must result in PARTIAL status without invalidating valid strategy."""
    conn = open_connection(tmp_path / "test_partial.db")
    ensure_schema(conn)
    repo = SQLiteRunRepository(conn)
    bus = InMemoryRunEventBus()

    class MockRetrieval:
        async def retrieve(self, ctx: RetrievalContext) -> RetrievalResult:
            rec = EvidenceRecord(
                entity_a="UCP1",
                relationship="activates",
                entity_b="thermogenesis",
                source="uniprot",
                source_id="U001",
                source_score=0.9,
                effect=EvidenceEffect(
                    type=EffectType.ACTIVATION, direction=EffectDirection.INCREASES
                ),
            )
            return RetrievalResult(records=[rec], source_statuses=[], failure_code=None)

    class MockPlanner:
        async def plan(self, ctx: RetrievalContext, ev: list[EvidenceRecord]) -> list[Strategy]:
            return [
                Strategy(
                    strategy_type=StrategyMode.MINIMAL,
                    selected_candidates=["UCP1"],
                    covered_targets=["thermogenesis"],
                    edit_count=1,
                    score=0.92,
                    rationale="Valid UCP1 plan",
                )
            ]

    class PartialAnalyzer:
        async def analyze(
            self, strat: Strategy, ev: list[EvidenceRecord], cfg: RunConfiguration
        ) -> PostPlanResult:
            return PostPlanResult(
                status=PostPlanStatus.PARTIAL,
                guide_risk=None,
                population=None,
                explanations=None,
            )

    orchestrator = RunOrchestrator(
        resolver=CoreModelObjectiveResolver(),
        retriever=MockRetrieval(),
        planner=MockPlanner(),
        validator=PlanValidator(),
        analyzer=PartialAnalyzer(),
        repository=repo,
        event_bus=bus,
    )

    project = ProjectContext(
        project_id="proj_partial",
        scope=Scope.DE_EXTINCTION,
        species="Mammuthus primigenius",
        objective="Edit UCP1 to confer non-shivering thermogenesis",
    )
    config = RunConfiguration(
        max_edits=2,
        strategy=StrategyMode.MINIMAL,
        candidate_genes=["UCP1"],
        constraints=[],
    )

    result = await orchestrator.execute(project, config)

    assert result.status == RunStatus.COMPLETE
    assert len(result.strategies) == 1
    assert result.post_plan is not None
    assert result.post_plan.status == PostPlanStatus.PARTIAL
    assert result.failure is not None
    assert result.failure.code == FailureCode.PARTIAL_ANALYSIS
    conn.close()
