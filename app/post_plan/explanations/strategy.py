"""
Deterministic Strategy Explanations for Relict Core.

Generates structured strategy-level synthesis explanations grounded in
the validated strategy, candidate targets, supporting evidence, and validation checks
(architecture §2.5, §15).
"""

from __future__ import annotations

from typing import Any

from app.models.requests import RunConfiguration
from app.models.responses import Strategy
from app.models.validation import ValidationResult


def explain_strategy(
    strategy: Strategy | Any,
    run_config: RunConfiguration,
    validation: ValidationResult | None = None,
    known_limitations: list[str] | None = None,
) -> str:
    """
    Produce a deterministic, structured whole-strategy explanation.

    Format:
    Strategy Synthesis:
    - Mode: minimal | redundant
    - Target Coverage: [targets]
    - Selected Candidates: [candidates] (Edits: N / max_edits)
    - Planner Rationale: ...
    - Validation Status: Passed / Failed
    - Supporting Evidence: N edges
    - Constraints: ...
    - Known Limitations: ...
    """
    strat_type = getattr(strategy, "strategy_type", run_config.strategy)
    candidates = getattr(strategy, "selected_candidates", [])
    covered = getattr(strategy, "covered_targets", [])
    edit_count = getattr(strategy, "edit_count", len(candidates))
    rationale = getattr(strategy, "rationale", "")
    supporting = getattr(strategy, "supporting_edges", [])

    candidates_str = ", ".join(candidates) if candidates else "None"
    covered_str = ", ".join(covered) if covered else "None"
    val_status = "Valid (Passed all checks)" if (validation and validation.valid) else "Unvalidated / Violations present"

    constraints_str = ", ".join(run_config.constraints) if run_config.constraints else "None specified"
    limitations = known_limitations or [
        "Computational strategy feasibility does not guarantee in-vivo biological efficacy.",
        "Candidate selection is conditioned on available source evidence in the Knowledge Graph.",
    ]
    limitations_str = "\n".join(f"  * {lim}" for lim in limitations)

    lines = [
        "Strategy Synthesis Summary",
        "==========================",
        f"Planning Mode: {strat_type}",
        f"Target Coverage: {covered_str}",
        f"Selected Candidates: {candidates_str} (Edit Budget: {edit_count} / {run_config.max_edits})",
        f"Planner Rationale: {rationale}",
        f"Validation Outcome: {val_status}",
        f"Supporting Evidence Edges: {len(supporting)}",
        f"Configured Constraints: {constraints_str}",
        "Known Limitations & Assumptions:",
        limitations_str,
    ]

    return "\n".join(lines)
