"""
Deterministic Strategy Explanations for Relict Core.

Generates structured strategy-level synthesis explanations grounded in
the validated strategy, candidate targets, supporting evidence, conflicting evidence,
and validation checks without invoking an LLM (architecture §2.5, §15, §20, §21, §22).
"""

from __future__ import annotations

from typing import Any

from app.models.evidence import EvidenceRecord
from app.models.requests import ProjectContext, RunConfiguration, StructuredObjective
from app.models.responses import Strategy
from app.models.validation import ValidationResult


def explain_strategy(
    strategy: Strategy | Any,
    run_config: RunConfiguration,
    validation: ValidationResult | None = None,
    project_context: ProjectContext | None = None,
    structured_objective: StructuredObjective | None = None,
    evidence: list[EvidenceRecord] | None = None,
    known_limitations: list[str] | None = None,
) -> str:
    """
    Produce a deterministic, structured whole-strategy explanation grounded strictly in evidence.

    Synthesizes:
    - Objective being addressed
    - Selected candidate interventions & edit budget
    - Biological relationships supporting each candidate
    - Evidence supporting direction and target coverage
    - Explicit conflicting evidence representation (if opposing evidence records exist)
    - Validation checks and outcome
    - Configured biological and operational constraints
    """
    strat_type = getattr(strategy, "strategy_type", run_config.strategy)
    strat_mode_str = strat_type.value if hasattr(strat_type, "value") else str(strat_type)
    candidates = list(getattr(strategy, "selected_candidates", []))
    covered = list(getattr(strategy, "covered_targets", []))
    edit_count = getattr(strategy, "edit_count", len(candidates))
    rationale = getattr(strategy, "rationale", "")
    supporting_edges = getattr(strategy, "supporting_edges", [])
    conflicting_edges = getattr(strategy, "conflicting_edges", [])

    candidates_str = ", ".join(candidates) if candidates else "None"
    covered_str = ", ".join(covered) if covered else "None"
    val_status = (
        "Valid (Passed all checks)"
        if (validation and validation.valid)
        else "Unvalidated / Violations present"
    )

    constraints_str = (
        ", ".join(run_config.constraints) if run_config.constraints else "None specified"
    )
    limitations = known_limitations or [
        "Computational strategy feasibility does not guarantee in-vivo biological efficacy.",
        "Candidate selection is conditioned on available source evidence in the Knowledge Graph.",
    ]

    lines = [
        "Strategy Synthesis Summary",
        "==========================",
        f"Planning Mode: {strat_mode_str}",
        f"Target Coverage: {covered_str}",
        f"Selected Candidates: {candidates_str}",
    ]

    if project_context:
        lines.append(f"Target Species: {project_context.species}")
        lines.append(f"Research Objective: {project_context.objective}")

    if structured_objective and getattr(structured_objective, "desired_change", None):
        lines.append(f"Desired Change: {structured_objective.desired_change}")

    if rationale:
        lines.append(f"Planner Rationale: {rationale}")

    lines.append(f"Validation Outcome: {val_status}")

    # Biological Evidence Backing
    if supporting_edges:
        lines.append(
            f"Supporting Evidence: {len(supporting_edges)} source-backed relationship edge(s)"
        )
        for edge in sorted(
            supporting_edges,
            key=lambda e: (getattr(e, "source_node_id", ""), getattr(e, "target_node_id", "")),
        ):
            src = getattr(edge, "source_node_id", "")
            tgt = getattr(edge, "target_node_id", "")
            rel = getattr(edge, "relationship", "associated_with")
            db = getattr(edge, "source", "evidence")
            score = getattr(edge, "source_score", None)
            score_str = f" [score: {score:.2f}]" if score is not None else ""
            lines.append(f"  * {src} --({rel})--> {tgt} (source: {db}{score_str})")

    # Conflicting Evidence Representation
    if conflicting_edges:
        lines.append(f"Conflicting / Contrary Evidence: {len(conflicting_edges)} edge(s)")
        for edge in sorted(
            conflicting_edges,
            key=lambda e: (getattr(e, "source_node_id", ""), getattr(e, "target_node_id", "")),
        ):
            src = getattr(edge, "source_node_id", "")
            tgt = getattr(edge, "target_node_id", "")
            rel = getattr(edge, "relationship", "inhibits")
            db = getattr(edge, "source", "evidence")
            lines.append(f"  * Conflict noted: {src} --({rel})--> {tgt} reported by {db}")

    lines.append(f"Configured Constraints: {constraints_str}")
    lines.append("Known Limitations & Assumptions:")
    for lim in limitations:
        lines.append(f"  * {lim}")

    return "\n".join(lines)
