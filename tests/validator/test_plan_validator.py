"""
Unit tests for PlanValidator in Relict Core.
"""

from __future__ import annotations

import pytest

from app.models.evidence import EvidenceRecord
from app.models.graph import GraphEdge
from app.models.requests import (
    ProjectContext,
    RunConfiguration,
    Scope,
    StrategyMode,
    StructuredObjective,
)
from app.models.responses import Strategy
from app.validator.plan_validator import PlanValidator


@pytest.fixture
def plan_validator() -> PlanValidator:
    return PlanValidator()


@pytest.fixture
def sample_strategy() -> Strategy:
    edge = GraphEdge(
        source_node_id="gene:TYRP1",
        target_node_id="gene:DCT",
        relationship="functional_association",
        source="STRING",
        source_score=0.91,
    )
    return Strategy(
        strategy_type=StrategyMode.MINIMAL,
        selected_candidates=["TYRP1", "DCT"],
        covered_targets=["coat pigmentation"],
        edit_count=2,
        score=0.92,
        supporting_edges=[edge],
        conflicting_edges=[],
        rationale="Two-gene pigmentation strategy.",
    )


@pytest.fixture
def sample_run_config() -> RunConfiguration:
    return RunConfiguration(
        candidate_genes=[],
        max_edits=3,
        constraints=["preserve fertility"],
        strategy=StrategyMode.MINIMAL,
    )


@pytest.fixture
def sample_project() -> ProjectContext:
    return ProjectContext(
        project_id="proj_1",
        species="Canis lupus",
        scope=Scope.DE_EXTINCTION,
        objective="Make coat white",
    )


@pytest.mark.asyncio
async def test_valid_minimal_strategy(
    plan_validator: PlanValidator,
    sample_strategy: Strategy,
    sample_run_config: RunConfiguration,
    sample_project: ProjectContext,
):
    """Test validation of a valid minimal strategy."""
    res = await plan_validator.validate(
        strategy=sample_strategy,
        run_config=sample_run_config,
        project_context=sample_project,
    )

    assert res.valid is True
    assert len(res.violations) == 0
    assert "edit_budget" in res.checks
    assert "target_coverage" in res.checks
    assert "strategy_mode" in res.checks


@pytest.mark.asyncio
async def test_edit_budget_exceeded(
    plan_validator: PlanValidator,
    sample_strategy: Strategy,
    sample_project: ProjectContext,
):
    """Test validation failure when edit_count exceeds max_edits."""
    strict_config = RunConfiguration(
        candidate_genes=[],
        max_edits=1,  # Strategy has edit_count=2
        constraints=[],
        strategy=StrategyMode.MINIMAL,
    )

    res = await plan_validator.validate(
        strategy=sample_strategy,
        run_config=strict_config,
        project_context=sample_project,
    )

    assert res.valid is False
    assert any("edit_budget" in v for v in res.violations)


@pytest.mark.asyncio
async def test_empty_candidates(
    plan_validator: PlanValidator,
    sample_run_config: RunConfiguration,
    sample_project: ProjectContext,
):
    """Test validation failure when strategy has no candidates."""
    empty_strat = Strategy(
        strategy_type=StrategyMode.MINIMAL,
        selected_candidates=[],
        covered_targets=["coat pigmentation"],
        edit_count=0,
        score=0.0,
        supporting_edges=[],
        conflicting_edges=[],
        rationale="Empty strategy",
    )

    res = await plan_validator.validate(
        strategy=empty_strat,
        run_config=sample_run_config,
        project_context=sample_project,
    )

    assert res.valid is False
    assert any("no selected candidates" in v for v in res.violations)


@pytest.mark.asyncio
async def test_missing_target_coverage(
    plan_validator: PlanValidator,
    sample_strategy: Strategy,
    sample_run_config: RunConfiguration,
    sample_project: ProjectContext,
):
    """Test validation failure when covered_targets is empty."""
    no_target_strat = sample_strategy.model_copy(update={"covered_targets": []})

    res = await plan_validator.validate(
        strategy=no_target_strat,
        run_config=sample_run_config,
        project_context=sample_project,
    )

    assert res.valid is False
    assert any("target_coverage" in v for v in res.violations)


@pytest.mark.asyncio
async def test_candidate_genes_constraint_violation(
    plan_validator: PlanValidator,
    sample_strategy: Strategy,
    sample_project: ProjectContext,
):
    """Test violation when candidate is not in configured candidate_genes list."""
    restricted_config = RunConfiguration(
        candidate_genes=["MC1R", "ASIP"],  # TYRP1 and DCT are not in this list
        max_edits=3,
        constraints=[],
        strategy=StrategyMode.MINIMAL,
    )

    res = await plan_validator.validate(
        strategy=sample_strategy,
        run_config=restricted_config,
        project_context=sample_project,
    )

    assert res.valid is False
    assert any("candidate_gene_constraints" in v for v in res.violations)


@pytest.mark.asyncio
async def test_redundant_strategy_validation(
    plan_validator: PlanValidator,
    sample_project: ProjectContext,
):
    """Test redundant strategy checks."""
    edge1 = GraphEdge(
        source_node_id="gene:TYRP1",
        target_node_id="pathway:melanogenesis",
        relationship="pathway_member",
        source="KEGG",
        source_score=1.0,
    )
    edge2 = GraphEdge(
        source_node_id="gene:MC1R",
        target_node_id="pathway:signaling",
        relationship="pathway_member",
        source="Reactome",
        source_score=0.95,
    )

    redundant_strat = Strategy(
        strategy_type=StrategyMode.REDUNDANT,
        selected_candidates=["TYRP1", "MC1R"],
        covered_targets=["coat pigmentation"],
        edit_count=2,
        score=0.95,
        supporting_edges=[edge1, edge2],
        conflicting_edges=[],
        rationale="Two independent routes to pigmentation.",
    )

    redundant_config = RunConfiguration(
        candidate_genes=[],
        max_edits=4,
        constraints=[],
        strategy=StrategyMode.REDUNDANT,
    )

    res = await plan_validator.validate(
        strategy=redundant_strat,
        run_config=redundant_config,
        project_context=sample_project,
    )

    assert res.valid is True
    assert len(res.violations) == 0


@pytest.mark.asyncio
async def test_redundant_strategy_single_candidate_violation(
    plan_validator: PlanValidator,
    sample_project: ProjectContext,
):
    """Test violation when redundant strategy has only 1 candidate."""
    single_strat = Strategy(
        strategy_type=StrategyMode.REDUNDANT,
        selected_candidates=["TYRP1"],
        covered_targets=["coat pigmentation"],
        edit_count=1,
        score=0.8,
        supporting_edges=[],
        conflicting_edges=[],
        rationale="Single gene cannot be redundant.",
    )

    redundant_config = RunConfiguration(
        candidate_genes=[],
        max_edits=4,
        constraints=[],
        strategy=StrategyMode.REDUNDANT,
    )

    res = await plan_validator.validate(
        strategy=single_strat,
        run_config=redundant_config,
        project_context=sample_project,
    )

    assert res.valid is False
    assert any("Redundant strategy requested but only 1 candidate" in v for v in res.violations)
