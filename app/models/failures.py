"""Failure codes and failure detail models for the Relict Core pipeline."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class FailureCode(StrEnum):
    """
    Shared enum for defined pipeline failure conditions.

    Six values — five biological-pipeline failures (architecture §3.12) plus
    one server-side infrastructure failure added in Phase 2E:

        CLARIFICATION_REQUIRED  — Core Model could not resolve the objective.
        INSUFFICIENT_EVIDENCE   — Knowledge Retrieval returned too little evidence.
        NO_FEASIBLE_PLAN        — Planner found no strategy satisfying constraints.
        VALIDATION_FAILED       — Plan Validator rejected the strategy.
        PARTIAL_ANALYSIS        — One or more optional Post-Plan tools were unavailable.
        RUN_TIMEOUT             — Run exceeded its wall-clock time budget.

    PARTIAL_ANALYSIS does NOT invalidate an otherwise successful Planner +
    Validator result. run.status can be COMPLETE while this code is present.

    RUN_TIMEOUT always sets run.status = FAILED.  It is an infrastructure-level
    concern separate from the five biological-pipeline codes; the distinction
    allows Shell to surface appropriate guidance to the researcher.
    """

    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NO_FEASIBLE_PLAN = "NO_FEASIBLE_PLAN"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    PARTIAL_ANALYSIS = "PARTIAL_ANALYSIS"
    RUN_TIMEOUT = "RUN_TIMEOUT"


class FailureDetail(BaseModel):
    """
    Structured failure information attached to a RunResult.

    Carries the machine-readable FailureCode alongside a human-readable
    message and the pipeline stage where the failure occurred.
    """

    code: FailureCode
    message: str
    stage: str | None = None
