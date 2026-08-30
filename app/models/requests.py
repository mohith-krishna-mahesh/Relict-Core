"""
Request models and pipeline-input data contracts for Relict Core.

This module contains:
  - Enums: StrategyMode, Scope, AmbiguityStatus
  - Pipeline inputs: ProjectContext, RunConfiguration, StructuredObjective,
    RetrievalContext
  - API request body: CreateRunRequest (POST /v1/runs)

ProjectContext and RunConfiguration are derived from the API request by the
Core API layer and are then passed unchanged through the pipeline.  They are
authoritative: the Core Model must not infer or overwrite their fields.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StrategyMode(StrEnum):
    """
    Planning strategy modes (architecture §3.2).

    MINIMAL    — maximise coverage and evidence, minimise edits.
    REDUNDANT  — maximise independent biological routes within budget.
    """

    MINIMAL = "minimal"
    REDUNDANT = "redundant"


class Scope(StrEnum):
    """
    Relict project scopes that determine which retrieval sources are active
    for a run (architecture §2.2 source table).
    """

    CONSERVATION = "conservation"
    DE_EXTINCTION = "de-extinction"
    AGRICULTURE = "agriculture"
    SYNTHETIC_BIOLOGY = "synthetic-biology"
    POPULATION_CONTROL = "population-control"
    PRECISION_MEDICINE = "precision-medicine"


class AmbiguityStatus(StrEnum):
    """
    Objective resolution outcome produced by Core Model Task 1.

    CLEAR                  — the objective was resolved without guessing.
    CLARIFICATION_REQUIRED — the objective is ambiguous; Shell must prompt
                             the researcher before the run can continue.
    """

    CLEAR = "clear"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"


# ---------------------------------------------------------------------------
# Pipeline-input data contracts
# ---------------------------------------------------------------------------


class ProjectContext(BaseModel):
    """
    Authoritative project-level inputs supplied by Shell (architecture §3.1).

    Fields are not inferred or overwritten by the Core Model.

    Fields
    ------
    project_id
        Server-generated unique identifier for the project.
    species
        Biological system being analysed (e.g. ``"Canis lupus"``).
    scope
        Selected Relict scope; determines retrieval source set.
    objective
        Researcher's natural-language biological objective.
        This is the input to Core Model Task 1.
    """

    project_id: str
    species: str
    scope: Scope
    objective: str


class RunConfiguration(BaseModel):
    """
    Authoritative run-level configuration supplied by Shell (architecture §3.2).

    Fields are not model-generated.

    Fields
    ------
    candidate_genes
        Optional list of gene identifiers that constrain the Planner's
        candidate space.  Empty list means no candidate constraint.
    max_edits
        Permitted edit budget (must be ≥ 1).
    constraints
        Free-text run-specific requirements the Planner and Validator must
        respect (e.g. ``"preserve fertility"``).
    strategy
        Planning objective mode; see StrategyMode.
    """

    candidate_genes: list[str] = Field(default_factory=list)
    max_edits: int = Field(gt=0)
    constraints: list[str] = Field(default_factory=list)
    strategy: StrategyMode


class StructuredObjective(BaseModel):
    """
    Produced by Core Model Task 1 from ProjectContext.objective
    (architecture §3.3).

    The model resolves the biological meaning of the objective but does NOT
    decide species, scope, candidate_genes, max_edits, constraints, or
    strategy — those remain as supplied by Shell.

    When ambiguity_status is CLARIFICATION_REQUIRED the run halts and
    Core returns the missing/ambiguous fields to Shell.

    Fields
    ------
    target_phenotypes
        Resolved target phenotypes or traits.
    biological_processes
        Relevant biological processes identified in the objective.
    desired_change
        The specific change the researcher wants to achieve.
    relevant_concepts
        Other biological concepts surfaced from the objective.
    retrieval_targets
        Gene names, pathway identifiers, etc. that Knowledge Retrieval
        should fetch evidence for.  These are retrieval hints, NOT evidence.
    ambiguity_status
        CLEAR when resolved; CLARIFICATION_REQUIRED when the model cannot
        resolve the objective without guessing.
    """

    target_phenotypes: list[str] = Field(default_factory=list)
    biological_processes: list[str] = Field(default_factory=list)
    desired_change: str
    relevant_concepts: list[str] = Field(default_factory=list)
    retrieval_targets: list[str] = Field(default_factory=list)
    ambiguity_status: AmbiguityStatus = AmbiguityStatus.CLEAR


class RetrievalContext(BaseModel):
    """
    Input contract to the Knowledge Retrieval stage (architecture §3.4).

    Combines ProjectContext, RunConfiguration, and StructuredObjective.
    Knowledge Retrieval uses these to determine the biological system,
    permitted source set, and required evidence.  It does not modify them.
    """

    project_context: ProjectContext
    run_configuration: RunConfiguration
    structured_objective: StructuredObjective


# ---------------------------------------------------------------------------
# API request body models  (internal helpers prefixed with _)
# ---------------------------------------------------------------------------


class _ProjectInput(BaseModel):
    """Project fields as supplied in the POST /v1/runs request body."""

    species: str
    scope: Scope


class _RunInput(BaseModel):
    """Run fields as supplied in the POST /v1/runs request body."""

    objective: str
    candidate_genes: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    max_edits: int = Field(gt=0)
    strategy: StrategyMode


class CreateRunRequest(BaseModel):
    """
    Request body for POST /v1/runs (architecture §2.7).

    The API accepts project and run configuration in a single payload.
    The Core API layer separates them into ProjectContext and
    RunConfiguration before execution.  project_id is generated server-side
    and must not be supplied by the caller.
    """

    project: _ProjectInput
    run: _RunInput
