"""PostPlanResult: output contract of the Post-Plan Analysis stage."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class PostPlanStatus(StrEnum):
    """
    Terminal status values for PostPlanResult (architecture §3.9).

    Unlike PostPlanAnalysisStatus in run_state (which includes PENDING and
    RUNNING for in-progress tracking), these are the three terminal outcomes
    that a completed PostPlanResult can report.

    PARTIAL means at least one optional tool was unavailable; the available
    outputs are still retained and valid.
    """

    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class PostPlanResult(BaseModel):
    """
    Aggregate result of the Post-Plan Analysis stage (architecture §3.9).

    Post-Plan Analysis runs only after a strategy has passed validation.
    Its ``status`` is independent of the primary run status — a run with
    ``run.status = COMPLETE`` may have ``post_plan.status = PARTIAL`` when
    one or more optional downstream tools (CRISPOR, CHOPCHOP, Evo 2) were
    unavailable.  In that case FailureCode.PARTIAL_ANALYSIS is recorded on
    the RunResult.

    Fields that are ``None`` indicate the corresponding sub-stage did not
    produce output (either not applicable or failed/unavailable).

    Fields
    ------
    status
        Terminal outcome; see PostPlanStatus.
    guide_risk
        Raw output from Guide & Risk Analysis (CRISPOR / CHOPCHOP / Evo 2).
        Structure is tool-specific and intentionally left as a flexible mapping
        until the guide-risk sub-stage defines its own contract.
    population_analysis
        Raw output from Population Propagation.  Same flexibility rationale.
    node_explanations
        Mapping of ``node_id`` → explanation text produced by Explanation
        Generation (deterministic templates for individual graph nodes).
    edge_explanations
        Mapping of edge key → explanation text for individual graph edges.
    strategy_explanation
        Whole-strategy synthesis produced by Core Model Task 2, grounded
        in the validated strategy, retrieved evidence, and Planner rationale.
    """

    status: PostPlanStatus
    guide_risk: dict[str, Any] | None = None
    population_analysis: dict[str, Any] | None = None
    node_explanations: dict[str, str] | None = None
    edge_explanations: dict[str, str] | None = None
    strategy_explanation: str | None = None
