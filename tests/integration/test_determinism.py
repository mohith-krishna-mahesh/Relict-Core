"""
Determinism Tests for Relict Core Strategic Planner.

Verifies that for identical inputs:
- ProjectContext
- RunConfiguration
- StructuredObjective
- EvidenceRecord[]

The Planner produces identical:
- Selected candidate genes
- Covered targets
- Strategy scores
- Strategy ordering and ranking
"""

from __future__ import annotations

import pytest

from app.models.evidence import EffectDirection, EffectType, EvidenceEffect, EvidenceRecord
from app.models.requests import (
    AmbiguityStatus,
    ProjectContext,
    RetrievalContext,
    RunConfiguration,
    Scope,
    StrategyMode,
    StructuredObjective,
)
from app.planner.adapter import ProductionStrategicPlanner


@pytest.mark.asyncio
async def test_planner_determinism() -> None:
    """Verify that multiple executions of the planner with identical inputs return identical outputs."""
    planner = ProductionStrategicPlanner()

    project = ProjectContext(
        project_id="det_proj_01",
        scope=Scope.AGRICULTURE,
        species="Triticum aestivum",
        objective="Introduce TaHKT1;5 to enhance sheath sodium retrieval under salinity stress",
    )
    config = RunConfiguration(
        max_edits=3,
        strategy=StrategyMode.MINIMAL,
        candidate_genes=["TaHKT1;5", "GPC-B1", "TaDREB1"],
        constraints=[],
    )
    obj = StructuredObjective(
        target_phenotypes=["salinity tolerance", "sodium retrieval"],
        biological_processes=["xylem sodium retrieval", "osmotic balance"],
        desired_change="upregulate TaHKT1;5 expression to reduce leaf Na+/K+ ratio",
        relevant_concepts=["salinity tolerance", "TaHKT1;5", "xylem transport"],
        retrieval_targets=["TaHKT1;5 functional annotation", "xylem ion transport"],
        ambiguity_status=AmbiguityStatus.CLEAR,
    )
    ctx = RetrievalContext(
        project_context=project,
        run_configuration=config,
        structured_objective=obj,
    )

    evidence = [
        EvidenceRecord(
            entity_a="TaHKT1;5",
            relationship="increases",
            entity_b="sodium retrieval",
            source="ensembl",
            source_id="E01",
            source_score=0.95,
            effect=EvidenceEffect(type=EffectType.EXPRESSION, direction=EffectDirection.INCREASES),
        ),
        EvidenceRecord(
            entity_a="GPC-B1",
            relationship="increases",
            entity_b="salinity tolerance",
            source="uniprot",
            source_id="U01",
            source_score=0.88,
            effect=EvidenceEffect(type=EffectType.REGULATION, direction=EffectDirection.INCREASES),
        ),
        EvidenceRecord(
            entity_a="TaDREB1",
            relationship="activates",
            entity_b="osmotic balance",
            source="ncbi_datasets",
            source_id="N01",
            source_score=0.91,
            effect=EvidenceEffect(type=EffectType.ACTIVATION, direction=EffectDirection.INCREASES),
        ),
    ]

    runs = []
    for _ in range(5):
        strats = await planner.plan(ctx, evidence)
        runs.append(strats)

    # Compare run 0 with all subsequent runs
    ref_strats = runs[0]
    assert len(ref_strats) > 0

    for i in range(1, len(runs)):
        comp_strats = runs[i]
        assert len(comp_strats) == len(ref_strats)
        for s1, s2 in zip(ref_strats, comp_strats):
            assert s1.strategy_type == s2.strategy_type
            assert s1.selected_candidates == s2.selected_candidates
            assert s1.covered_targets == s2.covered_targets
            assert s1.edit_count == s2.edit_count
            assert s1.score == s2.score
            assert s1.rationale == s2.rationale
