"""
Pipeline stage constants for the Run Manager.

``PipelineStage`` names are internal to the Run Manager.  They are stored on
``RunState.current_stage`` (a plain string field) and are distinct from the
publicly-visible ``RunStatus`` / ``PostPlanAnalysisStatus`` enum values defined
in ``app.models.run_state``, which form part of the shared API contract.
"""

from __future__ import annotations

from enum import StrEnum


class PipelineStage(StrEnum):
    """Ordered pipeline stages executed by the Run Manager."""

    OBJECTIVE_RESOLUTION = "objective_resolution"
    RETRIEVAL = "retrieval"
    PLANNING = "planning"
    VALIDATION = "validation"
    POST_PLAN = "post_plan"


# Canonical execution order.  The orchestrator moves through these stages in
# sequence and short-circuits on defined failure conditions.
STAGE_ORDER: tuple[PipelineStage, ...] = (
    PipelineStage.OBJECTIVE_RESOLUTION,
    PipelineStage.RETRIEVAL,
    PipelineStage.PLANNING,
    PipelineStage.VALIDATION,
    PipelineStage.POST_PLAN,
)
