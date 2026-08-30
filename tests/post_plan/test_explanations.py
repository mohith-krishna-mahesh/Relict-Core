"""
Unit tests for deterministic Explanation Generation in Relict Core.
"""

from __future__ import annotations

import pytest

from app.models.graph import GraphEdge
from app.models.requests import RunConfiguration, StrategyMode
from app.models.responses import Strategy
from app.models.validation import ValidationResult
from app.post_plan.explanations import explain_edge, explain_node, explain_strategy


def test_node_explanation():
    """Test deterministic node explanation formatting."""
    exp = explain_node(
        node_id="gene:TYRP1",
        role="Enzyme involved in eumelanin biosynthesis",
        why_it_matters="Catalyzes oxidation of 5,6-dihydroxyindole-2-carboxylic acid.",
        evidence_sources=["STRING", "Ensembl", "Reactome"],
    )

    assert "TYRP1" in exp
    assert "Role:" in exp
    assert "Enzyme involved in eumelanin biosynthesis" in exp
    assert "Why it matters:" in exp
    assert "Evidence:" in exp
    assert "STRING · Ensembl · Reactome" in exp


def test_edge_explanation():
    """Test deterministic edge explanation formatting."""
    exp = explain_edge(
        source_node="gene:TYRP1",
        target_node="gene:DCT",
        relationship="functional_association",
        source_db="STRING",
        source_score=0.91,
    )

    assert "TYRP1 — DCT" in exp
    assert "Functional association." in exp
    assert "Source: STRING." in exp
    assert "Evidence score: 0.91." in exp


def test_strategy_explanation():
    """Test deterministic whole-strategy synthesis explanation."""
    edge = GraphEdge(
        source_node_id="gene:TYRP1",
        target_node_id="gene:DCT",
        relationship="functional_association",
        source="STRING",
        source_score=0.91,
    )
    strat = Strategy(
        strategy_type=StrategyMode.MINIMAL,
        selected_candidates=["TYRP1", "DCT"],
        covered_targets=["coat pigmentation"],
        edit_count=2,
        score=0.92,
        supporting_edges=[edge],
        conflicting_edges=[],
        rationale="Two-gene pigmentation strategy.",
    )
    config = RunConfiguration(
        candidate_genes=[],
        max_edits=3,
        constraints=["preserve fertility"],
        strategy=StrategyMode.MINIMAL,
    )
    val_res = ValidationResult(
        valid=True,
        checks=["edit_budget", "target_coverage"],
        violations=[],
        warnings=[],
    )

    exp = explain_strategy(
        strategy=strat,
        run_config=config,
        validation=val_res,
    )

    assert "Strategy Synthesis Summary" in exp
    assert "Planning Mode: minimal" in exp
    assert "Target Coverage: coat pigmentation" in exp
    assert "Selected Candidates: TYRP1, DCT" in exp
    assert "Validation Outcome: Valid (Passed all checks)" in exp
    assert "Configured Constraints: preserve fertility" in exp
    assert "Known Limitations & Assumptions:" in exp
