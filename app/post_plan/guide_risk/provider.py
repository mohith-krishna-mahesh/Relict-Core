"""
Guide & Risk Analysis Provider for Relict Core.

Orchestrates downstream guide design and sequence risk assessment across CRISPOR,
CHOPCHOP, and Evo 2 for loci selected by the Planner and validated by the Plan Validator.

Architecture constraints (Relict Core architecture §2.5, §3.9):
- Operates ONLY on validated strategies.
- Does NOT modify primary strategies, candidates, constraints, or evidence graph.
- If optional tools (CRISPOR / CHOPCHOP / Evo 2) fail or are unavailable, aggregates
  available results and sets status to PARTIAL_ANALYSIS without fabricating missing outputs.
"""

from __future__ import annotations

import logging
from typing import Any

from app.models.post_plan import PostPlanStatus
from app.post_plan.guide_risk.chopchop import CHOPCHOPAdapter, ProviderStatus as ChopchopStatus
from app.post_plan.guide_risk.crispor import CRISPORAdapter, ProviderStatus as CrisporStatus
from app.post_plan.guide_risk.evo2 import Evo2Adapter, ProviderStatus as Evo2Status

logger = logging.getLogger(__name__)


class GuideRiskProvider:
    """
    Unified provider orchestrating CRISPOR, CHOPCHOP, and Evo 2 guide & risk analysis.
    """

    def __init__(
        self,
        crispor_adapter: CRISPORAdapter | None = None,
        chopchop_adapter: CHOPCHOPAdapter | None = None,
        evo2_adapter: Evo2Adapter | None = None,
    ) -> None:
        self.crispor = crispor_adapter or CRISPORAdapter()
        self.chopchop = chopchop_adapter or CHOPCHOPAdapter()
        self.evo2 = evo2_adapter or Evo2Adapter()

    async def evaluate_target(
        self,
        target_identifier: str,
        species: str,
        genome: str,
        sequence: str | None = None,
        pam: str = "NGG",
        include_evo2: bool = False,
    ) -> tuple[dict[str, Any], PostPlanStatus]:
        """
        Evaluate downstream guide design and risk metrics for a single target locus.

        Returns
        -------
        guide_risk_dict:
            Dictionary with 'crispor', 'chopchop', and/or 'evo2' provider results.
        overall_status:
            PostPlanStatus.COMPLETE if all attempted providers succeeded,
            PostPlanStatus.PARTIAL if at least one succeeded and another was unavailable/failed,
            PostPlanStatus.FAILED if all attempted providers failed.
        """
        results: dict[str, Any] = {}
        statuses: list[bool] = []

        # 1. Evaluate via CRISPOR if sequence is provided
        if sequence:
            crispor_res = await self.crispor.analyze_target(
                target_identifier=target_identifier,
                sequence=sequence,
                genome=genome,
                pam=pam,
            )
            results["crispor"] = crispor_res.model_dump()
            statuses.append(crispor_res.provider_status == CrisporStatus.SUCCESS)

        # 2. Evaluate via CHOPCHOP
        chopchop_res = await self.chopchop.analyze_target(
            target=target_identifier,
            species=species,
            genome=genome,
            pam=pam,
        )
        results["chopchop"] = chopchop_res.model_dump()
        statuses.append(chopchop_res.provider_status == ChopchopStatus.SUCCESS)

        # 3. Evaluate via Evo 2 if requested and sequence is provided
        if include_evo2 and sequence:
            evo2_res = await self.evo2.analyze_sequence(
                target_id=target_identifier,
                sequence=sequence,
                species=species,
                assembly=genome,
            )
            results["evo2"] = evo2_res.model_dump()
            statuses.append(evo2_res.provider_status == Evo2Status.SUCCESS)

        if all(statuses):
            return results, PostPlanStatus.COMPLETE
        elif any(statuses):
            return results, PostPlanStatus.PARTIAL
        else:
            return results, PostPlanStatus.FAILED
