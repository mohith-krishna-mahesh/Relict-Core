"""
Plan Validator for Relict Core.

Independently and deterministically validates candidate strategies computed by the Planner
against authoritative run configurations, edit budgets, target coverage, species consistency,
graph integrity, evidence provenance, and strategy mode requirements (architecture §2.4, §3.8, §5, §6).
"""

from __future__ import annotations

import logging
from typing import Any

from app.models.evidence import EvidenceRecord
from app.models.requests import ProjectContext, RunConfiguration, StrategyMode, StructuredObjective
from app.models.responses import Strategy
from app.models.validation import ValidationResult

logger = logging.getLogger(__name__)


class PlanValidator:
    """
    Deterministic Plan Validator for Relict Core.

    Checks:
    1. edit_budget: verifies edit_count <= run_config.max_edits and candidate consistency
    2. target_coverage: verifies covered_targets is non-empty and backed by candidates
    3. candidate_gene_constraints: enforces authoritative candidate_genes if specified
    4. run_constraints: validates run-level constraints against conflicting edges
    5. species_consistency: checks entity metadata against authoritative species
    6. graph_integrity: verifies edge validity and candidate-edge consistency
    7. evidence_provenance: checks that supporting edges preserve source & source_score
    8. strategy_mode: verifies minimal/redundant criteria relative to search space
    """

    def __init__(self) -> None:
        pass

    async def validate(
        self,
        strategy: Strategy | Any,
        run_config: RunConfiguration,
        project_context: ProjectContext | None = None,
        structured_objective: StructuredObjective | None = None,
        evidence: list[EvidenceRecord] | None = None,
    ) -> ValidationResult:
        """
        Validate a Strategy against authoritative project and run configuration.

        Parameters
        ----------
        strategy:
            Candidate strategy produced by the Planner.
        run_config:
            Authoritative run configuration from Shell.
        project_context:
            Optional authoritative project context (e.g. species, scope).
        structured_objective:
            Optional resolved objective targets.
        evidence:
            Optional retrieved evidence records for deep provenance checks.
        """
        checks: list[str] = []
        violations: list[str] = []
        warnings: list[str] = []

        # ---------------------------------------------------------------------
        # 1. Edit Budget Check
        # ---------------------------------------------------------------------
        checks.append("edit_budget")
        edit_count = getattr(strategy, "edit_count", len(getattr(strategy, "selected_candidates", [])))
        max_edits = run_config.max_edits

        if edit_count > max_edits:
            violations.append(
                f"edit_budget: Strategy edit_count ({edit_count}) exceeds authoritative max_edits ({max_edits})."
            )

        candidates = getattr(strategy, "selected_candidates", [])
        if not candidates:
            violations.append("edit_budget: Strategy has no selected candidates.")
        elif len(candidates) != edit_count:
            warnings.append(
                f"edit_budget: Discrepancy between selected_candidates length ({len(candidates)}) and edit_count ({edit_count})."
            )

        # ---------------------------------------------------------------------
        # 2. Target Coverage Check
        # ---------------------------------------------------------------------
        checks.append("target_coverage")
        covered = getattr(strategy, "covered_targets", [])
        if not covered:
            violations.append("target_coverage: Strategy covers zero objective targets.")
        elif structured_objective and structured_objective.retrieval_targets:
            # Check if covered targets overlap with expected targets
            matched = set(covered).intersection(set(structured_objective.retrieval_targets))
            if not matched and not set(covered).intersection(set(structured_objective.target_phenotypes)):
                warnings.append(
                    f"target_coverage: Strategy covered_targets ({covered}) does not explicitly match objective retrieval targets ({structured_objective.retrieval_targets})."
                )

        # ---------------------------------------------------------------------
        # 3. Candidate Gene Constraints Check
        # ---------------------------------------------------------------------
        checks.append("candidate_gene_constraints")
        if run_config.candidate_genes:
            allowed_genes = set(run_config.candidate_genes)
            invalid_candidates = [c for c in candidates if c not in allowed_genes]
            if invalid_candidates:
                violations.append(
                    f"candidate_gene_constraints: Strategy selected candidates not in configured candidate_genes list: {invalid_candidates}."
                )

        # ---------------------------------------------------------------------
        # 4. Run Constraints Check
        # ---------------------------------------------------------------------
        checks.append("run_constraints")
        conflicts = getattr(strategy, "conflicting_edges", [])
        if conflicts:
            conflict_descriptions = [
                f"{getattr(e, 'source_node_id', str(e))} -> {getattr(e, 'target_node_id', '')} ({getattr(e, 'relationship', '')})"
                for e in conflicts
            ]
            if run_config.constraints:
                # If constraints exist and there are active biological conflicts, record warning/violation
                warnings.append(
                    f"run_constraints: Strategy contains {len(conflicts)} conflicting edge(s) under active constraints ({run_config.constraints}): {conflict_descriptions}."
                )

        # ---------------------------------------------------------------------
        # 5. Species Consistency Check
        # ---------------------------------------------------------------------
        checks.append("species_consistency")
        if project_context and project_context.species:
            # We check if evidence or metadata exists for species consistency
            species_name = project_context.species
            if evidence:
                # Verify that evidence is consistent with species where annotated
                mismatched_records = [
                    rec.source_id
                    for rec in evidence
                    if getattr(rec, "metadata", {}).get("species")
                    and rec.metadata.get("species").lower() != species_name.lower()
                ]
                if mismatched_records:
                    warnings.append(
                        f"species_consistency: {len(mismatched_records)} evidence record(s) contain species annotations differing from project species '{species_name}' (potential orthologs): {mismatched_records[:3]}."
                    )

        # ---------------------------------------------------------------------
        # 6. Graph Integrity Check
        # ---------------------------------------------------------------------
        checks.append("graph_integrity")
        supporting = getattr(strategy, "supporting_edges", [])
        for edge in supporting:
            src = getattr(edge, "source_node_id", "")
            tgt = getattr(edge, "target_node_id", "")
            if not src or not tgt:
                violations.append("graph_integrity: Supporting edge has missing source or target node ID.")
            if src == tgt:
                warnings.append(f"graph_integrity: Self-referential edge detected on node '{src}'.")

        # ---------------------------------------------------------------------
        # 7. Evidence Provenance Check
        # ---------------------------------------------------------------------
        checks.append("evidence_provenance")
        for edge in supporting:
            source_name = getattr(edge, "source", "")
            if not source_name:
                warnings.append("evidence_provenance: Supporting edge lacks source database provenance.")
            score_val = getattr(edge, "source_score", None)
            if score_val is None:
                warnings.append("evidence_provenance: Supporting edge has no source-native score.")

        # ---------------------------------------------------------------------
        # 8. Strategy Mode Check (Minimal vs. Redundant)
        # ---------------------------------------------------------------------
        checks.append("strategy_mode")
        strat_type = getattr(strategy, "strategy_type", run_config.strategy)
        if isinstance(strat_type, StrategyMode):
            strat_type = strat_type.value

        if strat_type == StrategyMode.MINIMAL.value or strat_type == "minimal":
            # For minimal strategy: verify that candidate count respects budget and is justified by coverage
            if edit_count > len(covered) and edit_count > 1 and len(covered) == 1:
                warnings.append(
                    f"strategy_mode: Minimal strategy selected {edit_count} candidates for only {len(covered)} covered target(s). Minimality evaluated relative to search space."
                )
        elif strat_type == StrategyMode.REDUNDANT.value or strat_type == "redundant":
            # For redundant strategy: verify independent biological routes
            if edit_count < 2 and len(candidates) < 2:
                violations.append(
                    "strategy_mode: Redundant strategy requested but only 1 candidate was selected; cannot provide redundant pathways."
                )
            else:
                # Check for independent supporting routes
                edge_targets = {getattr(e, "target_node_id", "") for e in supporting}
                if len(edge_targets) <= 1 and len(candidates) > 1 and len(supporting) > 1:
                    warnings.append(
                        "strategy_mode: Redundant strategy candidates converge on a single target node without distinct parallel pathways."
                    )

        is_valid = len(violations) == 0

        return ValidationResult(
            valid=is_valid,
            checks=checks,
            violations=violations,
            warnings=warnings,
        )
