"""
Deterministic Explanation Generation for Relict Core.

Bypasses Core Model Task 2 to generate 100% deterministic, evidence-grounded
node, edge, and whole-strategy explanations (architecture §2.5, §15, §17).
"""

from __future__ import annotations

from typing import Any

from app.models.evidence import EvidenceRecord
from app.models.requests import ProjectContext, RunConfiguration, StructuredObjective
from app.models.responses import Strategy
from app.models.validation import ValidationResult
from app.post_plan.explanations.edge import explain_edge
from app.post_plan.explanations.node import explain_node
from app.post_plan.explanations.strategy import explain_strategy

__all__ = [
    "explain_node",
    "explain_edge",
    "explain_strategy",
    "generate_deterministic_explanations",
]


def generate_deterministic_explanations(
    strategy: Strategy,
    evidence: list[EvidenceRecord],
    run_config: RunConfiguration,
    project_context: ProjectContext | None = None,
    structured_objective: StructuredObjective | None = None,
    validation: ValidationResult | None = None,
) -> tuple[dict[str, str], dict[str, str], str]:
    """
    Generate complete set of deterministic node, edge, and strategy explanations
    grounded exclusively in source-backed evidence without invoking an LLM.

    Returns
    -------
    tuple[dict[str, str], dict[str, str], str]
        (node_explanations, edge_explanations, strategy_explanation)
    """
    # 1. Node explanations
    node_explanations: dict[str, str] = {}
    for candidate in sorted(strategy.selected_candidates):
        candidate_sources = sorted(
            list(
                set(
                    rec.source
                    for rec in evidence
                    if rec.entity_a == candidate or rec.entity_b == candidate
                )
            )
        )
        node_explanations[f"gene:{candidate}"] = explain_node(
            node_id=candidate,
            role=f"Target candidate intervention for {', '.join(sorted(strategy.covered_targets))}",
            why_it_matters=f"Selected in {strategy.strategy_type} strategy with evidence score backing.",
            evidence_sources=candidate_sources if candidate_sources else None,
            evidence_records=evidence,
        )

    # 2. Edge explanations
    edge_explanations: dict[str, str] = {}
    for edge in sorted(
        strategy.supporting_edges,
        key=lambda e: (getattr(e, "source_node_id", ""), getattr(e, "target_node_id", "")),
    ):
        src = getattr(edge, "source_node_id", "")
        tgt = getattr(edge, "target_node_id", "")
        edge_key = f"{src} -> {tgt}"
        edge_explanations[edge_key] = explain_edge(
            source_node=src,
            target_node=tgt,
            relationship=getattr(edge, "relationship", "associated_with"),
            source_db=getattr(edge, "source", "Knowledge Base"),
            source_score=getattr(edge, "source_score", None),
            provenance=getattr(edge, "provenance", "") or "",
        )

    # 3. Strategy explanation
    strat_explanation = explain_strategy(
        strategy=strategy,
        run_config=run_config,
        validation=validation,
        project_context=project_context,
        structured_objective=structured_objective,
        evidence=evidence,
    )

    return node_explanations, edge_explanations, strat_explanation
