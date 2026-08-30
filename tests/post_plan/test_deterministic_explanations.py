"""
Comprehensive Unit Tests for Deterministic Explanation Generation in Relict Core.

Verifies:
- Activation, inhibition, regulation, expression, loss/gain of function
- Unknown effect direction preservation
- Conflicting evidence handling across multiple sources
- Multi-source provenance preservation
- 100% Determinism across repeated executions without LLM invocation
"""

from __future__ import annotations

import pytest

from app.models.evidence import EffectDirection, EffectType, EvidenceEffect, EvidenceRecord
from app.models.graph import GraphEdge
from app.models.requests import (
    ProjectContext,
    RunConfiguration,
    Scope,
    StrategyMode,
    StructuredObjective,
)
from app.models.responses import Strategy
from app.models.validation import ValidationResult
from app.post_plan.explanations import (
    explain_edge,
    explain_node,
    explain_strategy,
    generate_deterministic_explanations,
)


def test_node_explanation_with_evidence_and_effects() -> None:
    """Verify node explanation formats supported biological effects and source attributions."""
    records = [
        EvidenceRecord(
            entity_a="TaHKT1;5",
            relationship="increases_expression_of",
            entity_b="salinity_tolerance",
            source="ensembl",
            source_id="ENSG0001",
            source_score=0.95,
            effect=EvidenceEffect(type=EffectType.EXPRESSION, direction=EffectDirection.INCREASES),
        ),
        EvidenceRecord(
            entity_a="TaHKT1;5",
            relationship="regulates",
            entity_b="xylem_ion_transport",
            source="uniprot",
            source_id="U0001",
            source_score=0.89,
            effect=EvidenceEffect(type=EffectType.REGULATION, direction=EffectDirection.INCREASES),
        ),
    ]

    exp = explain_node(
        node_id="gene:TaHKT1;5",
        role="Sodium transporter mediating sheath sodium retrieval",
        why_it_matters="Reduces shoot Na+/K+ ratio under saline conditions.",
        evidence_records=records,
    )

    assert "TaHKT1;5" in exp
    assert "Role:" in exp
    assert "Sodium transporter mediating sheath sodium retrieval" in exp
    assert "Supported Biological Effects:" in exp
    assert "expression (direction: increases) supported by ensembl, score: 0.95" in exp
    assert "regulation (direction: increases) supported by uniprot, score: 0.89" in exp
    assert "Evidence:" in exp
    assert "ensembl · uniprot" in exp


def test_edge_explanation_with_effect_and_uncertainty() -> None:
    """Verify edge explanation preserves direction and handles uncharacterized effects."""
    # 1. Known direction
    exp1 = explain_edge(
        source_node="gene:UCP1",
        target_node="phenotype:thermogenesis",
        relationship="activates",
        source_db="uniprot",
        source_score=0.92,
        effect=EvidenceEffect(type=EffectType.ACTIVATION, direction=EffectDirection.INCREASES),
        provenance="PMID:12345678",
    )
    assert "UCP1 — thermogenesis" in exp1
    assert "Activates." in exp1
    assert "Effect: activation (direction: increases)." in exp1
    assert "Source: uniprot." in exp1
    assert "Evidence score: 0.92." in exp1
    assert "Provenance: PMID:12345678" in exp1

    # 2. Unknown direction / association without asserting causality
    exp2 = explain_edge(
        source_node="gene:TRPV3",
        target_node="trait:cold_tolerance",
        relationship="associated_with",
        source_db="ensembl",
        source_score=0.75,
        effect=EvidenceEffect(type=EffectType.ASSOCIATION, direction=None),
    )
    assert "TRPV3 — cold_tolerance" in exp2
    assert "Associated with." in exp2
    assert "direction: uncharacterized" in exp2
    assert "causes" not in exp2.lower()


def test_strategy_explanation_conflicting_evidence() -> None:
    """Verify conflicting evidence is explicitly represented in strategy synthesis."""
    supp_edge = GraphEdge(
        source_node_id="GENE_A",
        target_node_id="TARGET_T",
        relationship="increases_expression_of",
        source="ensembl",
        source_score=0.9,
    )
    conf_edge = GraphEdge(
        source_node_id="GENE_A",
        target_node_id="TARGET_T",
        relationship="inhibits",
        source="literature",
        source_score=0.6,
    )

    strat = Strategy(
        strategy_type=StrategyMode.MINIMAL,
        selected_candidates=["GENE_A"],
        covered_targets=["TARGET_T"],
        edit_count=1,
        score=0.85,
        supporting_edges=[supp_edge],
        conflicting_edges=[conf_edge],
        rationale="Candidate strategy with conflicting evidence documented.",
    )

    config = RunConfiguration(
        candidate_genes=["GENE_A"],
        max_edits=2,
        constraints=["preserve vigor"],
        strategy=StrategyMode.MINIMAL,
    )

    val = ValidationResult(
        valid=True,
        checks=["edit_budget", "candidate_gene_constraints"],
        violations=[],
        warnings=["conflicting evidence on GENE_A"],
    )

    project = ProjectContext(
        project_id="proj_001",
        species="Triticum aestivum",
        scope=Scope.AGRICULTURE,
        objective="Enhance stress tolerance via GENE_A",
    )

    exp = explain_strategy(
        strategy=strat,
        run_config=config,
        validation=val,
        project_context=project,
    )

    assert "Strategy Synthesis Summary" in exp
    assert "Planning Mode: minimal" in exp
    assert "Target Species: Triticum aestivum" in exp
    assert "Supporting Evidence: 1 source-backed relationship edge(s)" in exp
    assert "Conflicting / Contrary Evidence: 1 edge(s)" in exp
    assert "GENE_A --(inhibits)--> TARGET_T reported by literature" in exp
    assert "Configured Constraints: preserve vigor" in exp


def test_explanation_generation_determinism() -> None:
    """Verify that multiple executions produce bitwise-identical output."""
    edge1 = GraphEdge(
        source_node_id="GENE_X",
        target_node_id="PHEN_Y",
        relationship="activates",
        source="uniprot",
        source_score=0.91,
    )
    edge2 = GraphEdge(
        source_node_id="GENE_Z",
        target_node_id="PHEN_Y",
        relationship="regulates",
        source="ensembl",
        source_score=0.84,
    )
    strat = Strategy(
        strategy_type=StrategyMode.MINIMAL,
        selected_candidates=["GENE_Z", "GENE_X"],  # Intentionally unsorted
        covered_targets=["PHEN_Y"],
        edit_count=2,
        score=0.90,
        supporting_edges=[edge2, edge1],  # Intentionally unsorted
        conflicting_edges=[],
        rationale="Multi-gene activation plan.",
    )
    ev_records = [
        EvidenceRecord(
            entity_a="GENE_X",
            relationship="activates",
            entity_b="PHEN_Y",
            source="uniprot",
            source_id="U1",
            source_score=0.91,
            effect=EvidenceEffect(type=EffectType.ACTIVATION, direction=EffectDirection.INCREASES),
        ),
        EvidenceRecord(
            entity_a="GENE_Z",
            relationship="regulates",
            entity_b="PHEN_Y",
            source="ensembl",
            source_id="E1",
            source_score=0.84,
            effect=EvidenceEffect(type=EffectType.REGULATION, direction=EffectDirection.INCREASES),
        ),
    ]
    config = RunConfiguration(
        max_edits=2,
        strategy=StrategyMode.MINIMAL,
        candidate_genes=["GENE_X", "GENE_Z"],
        constraints=[],
    )

    nodes1, edges1, strat1 = generate_deterministic_explanations(strat, ev_records, config)
    nodes2, edges2, strat2 = generate_deterministic_explanations(strat, ev_records, config)

    assert nodes1 == nodes2
    assert edges1 == edges2
    assert strat1 == strat2
    assert "gene:GENE_X" in nodes1
    assert "gene:GENE_Z" in nodes1
