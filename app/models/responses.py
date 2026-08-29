"""Response models for Relict Core API endpoints and pipeline stages."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.evidence import EvidenceRecord
from app.models.failures import FailureCode, FailureDetail
from app.models.graph import GraphEdge
from app.models.post_plan import PostPlanResult
from app.models.requests import ProjectContext, RunConfiguration, StrategyMode, StructuredObjective
from app.models.run_state import RunStatus
from app.models.validation import ValidationResult


class Strategy(BaseModel):
    """
    One candidate strategy produced and ranked by the Planner
    (architecture §3.7).

    A run may contain multiple candidate strategies (``Strategy[]``).
    The Planner ranks feasible strategies; ``RunResult.selected_strategy``
    identifies the one chosen for downstream analysis.

    Fields
    ------
    strategy_type
        Planning mode used (minimal or redundant).
    selected_candidates
        Ordered list of gene/entity identifiers selected by the Planner.
    covered_targets
        Subset of retrieval targets covered by this strategy.
    edit_count
        Number of edits required (must be ≤ RunConfiguration.max_edits).
    score
        Planner-assigned ranking score (higher is better).
    supporting_edges
        Evidence Graph edges that support this strategy.
    conflicting_edges
        Evidence Graph edges that represent conflicts within this strategy.
    rationale
        Human-readable Planner rationale for this strategy selection.
    """

    strategy_type: StrategyMode
    selected_candidates: list[str] = Field(default_factory=list)
    covered_targets: list[str] = Field(default_factory=list)
    edit_count: int
    score: float
    supporting_edges: list[GraphEdge] = Field(default_factory=list)
    conflicting_edges: list[GraphEdge] = Field(default_factory=list)
    rationale: str


class SourceStatus(BaseModel):
    """Status report for a single source during a retrieval run."""

    source_name: str
    success: bool
    record_count: int = 0
    error_message: str | None = None


class RetrievalResult(BaseModel):
    """Output of the Knowledge Retrieval subsystem."""

    records: list[EvidenceRecord] = Field(default_factory=list)
    source_statuses: list[SourceStatus] = Field(default_factory=list)
    failure_code: FailureCode | None = Field(
        default=None,
        description=(
            "Set to INSUFFICIENT_EVIDENCE when the aggregate evidence "
            "from all permitted sources is insufficient."
        ),
    )


class RunResult(BaseModel):
    """
    Final aggregate returned by Core API to Shell (architecture §3.11).

    Supports both successful and failed runs.  Fields that are ``None``
    indicate the corresponding pipeline stage did not complete due to a
    short-circuit failure at an earlier stage.  Unavailable downstream
    artifacts are omitted rather than fabricated.

    Fields
    ------
    run_id
        Unique run identifier (matches RunState.run_id).
    status
        Primary run status at the time this result was produced.
    project_context
        Authoritative project-level inputs; echoed back for provenance.
    run_configuration
        Authoritative run-level configuration; echoed back for provenance.
    structured_objective
        Output of Core Model Task 1.  None if the model stage was not
        reached (e.g. configuration error before the run started).
    strategies
        Ranked candidate strategies produced by the Planner.
    selected_strategy
        The strategy selected for Post-Plan Analysis, if applicable.
    validation
        ValidationResult from the Plan Validator.  None if validation
        was not reached.
    post_plan
        PostPlanResult from Post-Plan Analysis.  None if analysis was
        not reached (e.g. validation failed).
    failure
        Structured failure detail if the run terminated with a known
        failure code.  None for fully successful runs.
    warnings
        Non-fatal observations accumulated across all pipeline stages.
    """

    run_id: str
    status: RunStatus
    project_context: ProjectContext
    run_configuration: RunConfiguration
    structured_objective: StructuredObjective | None = None
    strategies: list[Strategy] = Field(default_factory=list)
    selected_strategy: Strategy | None = None
    validation: ValidationResult | None = None
    post_plan: PostPlanResult | None = None
    failure: FailureDetail | None = None
    warnings: list[str] = Field(default_factory=list)
