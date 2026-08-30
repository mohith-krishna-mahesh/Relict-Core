"""Run status enums and the RunState model for Relict Core."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    """
    Primary run status values (architecture §3.10).

    Transition path:
        PENDING → QUEUED → RUNNING → COMPLETE
                                   ↘ FAILED
    """

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class PostPlanAnalysisStatus(StrEnum):
    """
    Status of the Post-Plan Analysis stage, tracked independently of
    the primary run status (architecture §3.10).

    A valid Planner + Validator result can have:
        run.status                  = COMPLETE
        post_plan_analysis_status   = PARTIAL

    This is not an error condition — it means Post-Plan ran but one or
    more optional downstream tools were unavailable.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class RunState(BaseModel):
    """
    Persistent state record for a single Relict Core run (architecture §3.10).

    Fields
    ------
    run_id
        Unique identifier for this run (server-generated UUID).
    status
        Primary pipeline status; see RunStatus.
    current_stage
        Name of the pipeline stage currently executing, if known.
    progress
        Estimated completion fraction in [0.0, 1.0].
    post_plan_analysis_status
        Post-Plan Analysis status, independent of ``status``.
    timestamps
        Mapping of stage name → UTC datetime for each stage transition.
    errors
        Ordered list of human-readable error messages accumulated during
        the run (may be non-empty even when status=COMPLETE if warnings
        were promoted to errors in a sub-stage).
    """

    run_id: str
    status: RunStatus
    current_stage: str | None = None
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    post_plan_analysis_status: PostPlanAnalysisStatus = PostPlanAnalysisStatus.PENDING
    timestamps: dict[str, datetime] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
