"""
Unit tests for DefaultPostPlanAnalyzer in Relict Core.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.models.evidence import EvidenceRecord
from app.models.graph import GraphEdge
from app.models.post_plan import PostPlanStatus
from app.models.requests import RunConfiguration, StrategyMode
from app.models.responses import Strategy
from app.models.validation import ValidationResult
from app.post_plan.analyzer import DefaultPostPlanAnalyzer
from app.post_plan.guide_risk import (
    CHOPCHOPAdapter,
    CRISPORAdapter,
    ChopchopAnalysisResult,
    CrisporAnalysisResult,
    GuideRiskProvider,
)
from app.post_plan.guide_risk.chopchop import ProviderStatus as ChopchopStatus
from app.post_plan.guide_risk.crispor import ProviderStatus as CrisporStatus


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
        constraints=[],
        strategy=StrategyMode.MINIMAL,
    )


@pytest.mark.asyncio
async def test_post_plan_analyzer_full_success(
    sample_strategy: Strategy,
    sample_run_config: RunConfiguration,
):
    """Test DefaultPostPlanAnalyzer when all downstream tools succeed."""
    mock_crispor = AsyncMock(spec=CRISPORAdapter)
    mock_crispor.analyze_target.return_value = CrisporAnalysisResult(
        provider_status=CrisporStatus.SUCCESS,
        target_identifier="TYRP1",
        genome="canFam3",
        pam="NGG",
        guide_candidates=[],
        warnings=[],
        errors=[],
        provenance={},
    )

    mock_chopchop = AsyncMock(spec=CHOPCHOPAdapter)
    mock_chopchop.analyze_target.return_value = ChopchopAnalysisResult(
        provider_status=ChopchopStatus.SUCCESS,
        target="TYRP1",
        species="Canis lupus",
        genome="canFam3",
        pam="NGG",
        guide_candidates=[],
        warnings=[],
        errors=[],
        provenance={},
    )

    provider = GuideRiskProvider(
        crispor_adapter=mock_crispor,
        chopchop_adapter=mock_chopchop,
    )

    analyzer = DefaultPostPlanAnalyzer(guide_risk_provider=provider)

    evidence = [
        EvidenceRecord(
            source="STRING",
            source_id="rec_1",
            entity_a="TYRP1",
            entity_b="DCT",
            relationship="functional_association",
            score=0.91,
            confidence="high",
        )
    ]

    val_res = ValidationResult(valid=True, checks=["edit_budget"], violations=[], warnings=[])

    post_plan_res = await analyzer.analyze(
        strategy=sample_strategy,
        evidence=evidence,
        run_config=sample_run_config,
        validation=val_res,
        species="Canis lupus",
        genome="canFam3",
    )

    assert post_plan_res.status == PostPlanStatus.COMPLETE
    assert post_plan_res.guide_risk is not None
    assert "TYRP1" in post_plan_res.guide_risk
    assert post_plan_res.population_analysis is not None
    assert "gene:TYRP1" in post_plan_res.node_explanations
    assert len(post_plan_res.edge_explanations) == 1
    assert "Strategy Synthesis Summary" in post_plan_res.strategy_explanation


@pytest.mark.asyncio
async def test_post_plan_analyzer_partial_status(
    sample_strategy: Strategy,
    sample_run_config: RunConfiguration,
):
    """Test that downstream tool unavailability degrades status to PARTIAL without failing run."""
    mock_chopchop = AsyncMock(spec=CHOPCHOPAdapter)
    mock_chopchop.analyze_target.return_value = ChopchopAnalysisResult(
        provider_status=ChopchopStatus.UNAVAILABLE,
        target="TYRP1",
        species="Canis lupus",
        genome="canFam3",
        pam="NGG",
        guide_candidates=[],
        warnings=[],
        errors=["CHOPCHOP binary not found."],
        provenance={},
    )

    provider = GuideRiskProvider(
        chopchop_adapter=mock_chopchop,
    )

    analyzer = DefaultPostPlanAnalyzer(guide_risk_provider=provider)

    post_plan_res = await analyzer.analyze(
        strategy=sample_strategy,
        evidence=[],
        run_config=sample_run_config,
        validation=None,
    )

    assert post_plan_res.status == PostPlanStatus.PARTIAL
    assert post_plan_res.population_analysis is not None
    assert post_plan_res.strategy_explanation is not None
