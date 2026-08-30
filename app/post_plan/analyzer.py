"""
Post-Plan Analysis Orchestrator for Relict Core.

Implements the PostPlanAnalyzer protocol (app.run_manager.stages.PostPlanAnalyzer)
orchestrating Guide/Risk Analysis (CRISPOR / CHOPCHOP / Evo 2), Population Propagation simulation,
and Explanation Generation downstream of a ValidatedStrategy (architecture §2.5, §3.9).
"""

from __future__ import annotations

import logging
from typing import Any

from app.models.evidence import EvidenceRecord
from app.models.post_plan import PostPlanResult, PostPlanStatus
from app.models.requests import RunConfiguration
from app.models.responses import Strategy
from app.models.validation import ValidationResult
from app.post_plan.explanations import explain_edge, explain_node, explain_strategy
from app.post_plan.guide_risk import GuideRiskProvider
from app.post_plan.population import PopulationParameters, PopulationSimulator

logger = logging.getLogger(__name__)


class DefaultPostPlanAnalyzer:
    """
    Production Post-Plan Analyzer for Relict Core.

    Orchestrates:
    1. Guide & Risk Analysis across CRISPOR, CHOPCHOP, and Evo 2
    2. Mathematical Population Propagation simulation
    3. Deterministic Node, Edge, and Whole-Strategy Explanation generation
    """

    def __init__(
        self,
        guide_risk_provider: GuideRiskProvider | None = None,
        population_simulator: PopulationSimulator | None = None,
    ) -> None:
        self.guide_risk_provider = guide_risk_provider or GuideRiskProvider()
        self.population_simulator = population_simulator or PopulationSimulator()

    async def analyze(
        self,
        strategy: Strategy,
        evidence: list[EvidenceRecord],
        run_config: RunConfiguration,
        validation: ValidationResult | None = None,
        species: str = "Unknown",
        genome: str = "Unknown",
    ) -> PostPlanResult:
        """
        Execute downstream analysis for a validated strategy.

        Parameters
        ----------
        strategy:
            Strategy validated by PlanValidator.
        evidence:
            Source-backed evidence records.
        run_config:
            Authoritative run configuration from Shell.
        validation:
            ValidationResult from PlanValidator.
        species:
            Authoritative species from ProjectContext.
        genome:
            Resolved genome assembly identifier.
        """
        overall_status = PostPlanStatus.COMPLETE

        # ---------------------------------------------------------------------
        # 1. Guide & Risk Analysis
        # ---------------------------------------------------------------------
        guide_risk_results: dict[str, Any] = {}
        for candidate in strategy.selected_candidates:
            # Evaluate target loci through GuideRiskProvider
            res_dict, g_status = await self.guide_risk_provider.evaluate_target(
                target_identifier=candidate,
                species=species,
                genome=genome,
                sequence=None,  # Or sequence if resolved from evidence
                pam="NGG",
            )
            guide_risk_results[candidate] = res_dict
            if g_status == PostPlanStatus.PARTIAL and overall_status == PostPlanStatus.COMPLETE:
                overall_status = PostPlanStatus.PARTIAL
            elif g_status == PostPlanStatus.FAILED and overall_status != PostPlanStatus.PARTIAL:
                overall_status = PostPlanStatus.PARTIAL  # Tool failures degrade to PARTIAL_ANALYSIS

        # ---------------------------------------------------------------------
        # 2. Population Propagation Simulation (baseline)
        # ---------------------------------------------------------------------
        pop_analysis: dict[str, Any] | None = None
        try:
            params = PopulationParameters(
                initial_frequency=0.05,
                population_size=10000,
                generations=30,
            )
            sim_result = self.population_simulator.simulate(params)
            pop_analysis = sim_result.model_dump()
        except Exception as e:
            logger.warning("Population simulation failed: %s", e)
            overall_status = PostPlanStatus.PARTIAL

        # ---------------------------------------------------------------------
        # 3. Deterministic Node & Edge Explanations
        # ---------------------------------------------------------------------
        node_explanations: dict[str, str] = {}
        for candidate in strategy.selected_candidates:
            # Collect evidence sources for candidate
            candidate_sources = [
                rec.source
                for rec in evidence
                if rec.entity_a == candidate or rec.entity_b == candidate
            ]
            node_explanations[f"gene:{candidate}"] = explain_node(
                node_id=candidate,
                role=f"Target candidate for {', '.join(strategy.covered_targets)}",
                why_it_matters=f"Selected in {strategy.strategy_type} strategy with evidence score backing.",
                evidence_sources=list(set(candidate_sources)) if candidate_sources else None,
            )

        edge_explanations: dict[str, str] = {}
        for edge in strategy.supporting_edges:
            src = getattr(edge, "source_node_id", "")
            tgt = getattr(edge, "target_node_id", "")
            edge_key = f"{src} -> {tgt}"
            edge_explanations[edge_key] = explain_edge(
                source_node=src,
                target_node=tgt,
                relationship=getattr(edge, "relationship", "associated_with"),
                source_db=getattr(edge, "source", "Knowledge Base"),
                source_score=getattr(edge, "source_score", None),
            )

        # ---------------------------------------------------------------------
        # 4. Whole-Strategy Explanation
        # ---------------------------------------------------------------------
        strat_explanation = explain_strategy(
            strategy=strategy,
            run_config=run_config,
            validation=validation,
        )

        return PostPlanResult(
            status=overall_status,
            guide_risk=guide_risk_results if guide_risk_results else None,
            population_analysis=pop_analysis,
            node_explanations=node_explanations,
            edge_explanations=edge_explanations,
            strategy_explanation=strat_explanation,
        )
