"""
Contract-shaped Pydantic models for Relict Core's external API.

These models mirror the schemas in ``app/openapi/api.contract.json`` exactly.
They are **only** used at the route boundary -- internal pipeline models in
``app/models/requests.py``, ``graph.py``, ``responses.py``, etc. are
deliberately kept separate and are NOT changed to match this file.

Adapter functions in ``app/routes/contract_adapters.py`` convert internal
models to these contract shapes before they leave the route layer.

Confidence constraint
---------------------
``ContractGraphNode.confidence`` and ``ContractGraphEdge.confidence`` are
typed as ``Literal["evidence", "unknown"]``.  The value ``"model_estimated"``
is **structurally excluded** from this codebase (architecture Sec. 8,
"Evidence is authoritative").  Pydantic will reject any attempt to set
confidence to ``"model_estimated"`` at instantiation time, providing a hard
compile-time and runtime guarantee.

Species / Gene
--------------
Reused from ``app/models/data.py`` without duplication.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Re-export so route modules only need to import from one place
from app.models.data import Gene, Species

__all__ = [
    "Gene",
    "Species",
    "TokenIdentity",
    "VerifyResponse",
    "RunConstraints",
    "ContractRunRequest",
    "StartRunResponse",
    "ContractGraphNode",
    "ContractGraphEdge",
    "ContractStrategy",
    "ContractRunResult",
]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TokenIdentity(BaseModel):
    """Identity information associated with a validated bearer token."""

    model_config = ConfigDict(extra="forbid")

    user_or_org: str = Field(description="User or organisation identifier for this token.")
    scopes: list[str] = Field(
        default_factory=list,
        description="Permission scopes granted to this token.",
    )


class VerifyResponse(BaseModel):
    """Response body for ``POST /v1/auth/verify``."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(description="Verification outcome (e.g. 'verified').")
    core_version: str = Field(description="Running Relict Core version string.")
    instance_type: str = Field(description="Deployment type label for this Core instance.")
    identity: TokenIdentity = Field(description="Identity derived from the presented token.")


# ---------------------------------------------------------------------------
# Search (defined here for completeness; Species/Gene re-exported above)
# ---------------------------------------------------------------------------

# Species -> app/models/data.py::Species
# Gene    -> app/models/data.py::Gene


# ---------------------------------------------------------------------------
# Run request
# ---------------------------------------------------------------------------


class RunConstraints(BaseModel):
    """Constraint block within a ``ContractRunRequest``."""

    model_config = ConfigDict(extra="forbid")

    max_edits: int = Field(gt=0, description="Maximum number of edits permitted in a strategy.")
    preserve_fertility: bool = Field(
        description=(
            "When True, strategies must preserve host fertility. "
            "Mapped to 'preserve_fertility' entry in RunConfiguration.constraints."
        ),
    )
    maximize_diversity: bool = Field(
        description=(
            "When True, the Planner should maximise independent biological routes. "
            "Mapped to 'maximize_diversity' entry in RunConfiguration.constraints."
        ),
    )


class ContractRunRequest(BaseModel):
    """
    Request body for ``POST /v1/runs`` as defined in ``api.contract.json``.

    Scope gap
    ---------
    The contract does not include a ``scope`` field.  Internally,
    ``ProjectContext.scope`` is required and governs which Knowledge
    Retrieval sources are permitted (architecture Sec. 3.1).  Until the
    contract is updated to expose ``scope`` explicitly, the route layer
    applies a **documented default** of ``Scope.DE_EXTINCTION``.

    This is a flagged design decision -- do not change the default without
    raising it back to the product team first.
    """

    model_config = ConfigDict(extra="forbid")

    species: str = Field(
        description="Target species (scientific name, common name, or taxonomy ID)."
    )
    research_objective: str = Field(description="Natural-language research objective.")
    candidate_genes: list[str] = Field(
        default_factory=list,
        description="Optional list of gene symbols to constrain the Planner's candidate space.",
    )
    constraints: RunConstraints = Field(
        description="Run-level biological and operational constraints."
    )
    presets: list[Literal["minimal", "redundant"]] = Field(
        default_factory=list,
        description="Strategy mode presets (minimal=coverage-first, redundant=route-diversity).",
    )


class StartRunResponse(BaseModel):
    """Response body for ``POST /v1/runs`` -- returned immediately on run admission."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(description="Server-generated unique identifier for the admitted run.")


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

#: Confidence values this codebase is permitted to emit.
#: ``"model_estimated"`` is structurally excluded (architecture Sec. 8).
_PermittedConfidence = Literal["evidence", "unknown"]


class ContractGraphNode(BaseModel):
    """
    A graph node in the contract-shaped run result.

    Confidence
    ----------
    Always ``"unknown"`` for nodes -- the internal ``GraphNode`` model
    represents biological entities (genes, proteins, pathways) and does not
    carry a per-node confidence source.  Confidence is an edge-level property.

    ``"model_estimated"`` is never produced (architecture Sec. 8, "Evidence is
    authoritative").  The ``Literal`` type enforces this at the Pydantic layer.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable node identifier (maps to internal GraphNode.node_id).")
    type: str = Field(description="Biological entity type (e.g. 'gene', 'pathway').")
    label: str = Field(description="Human-readable display name.")
    rationale: str | None = Field(default=None, description="Optional explanatory rationale.")
    confidence: _PermittedConfidence = Field(
        default="unknown",
        description=(
            "Evidence confidence for this node. "
            "Only 'evidence' or 'unknown' are produced by this codebase. "
            "'model_estimated' is structurally excluded (architecture Sec. 8)."
        ),
    )


class ContractGraphEdge(BaseModel):
    """
    An evidence graph edge in the contract-shaped run result.

    Confidence mapping
    ------------------
    ``"evidence"``       : edge has a real database ``source`` AND either a
                           non-None ``source_score`` or ``provenance`` from
                           Knowledge Retrieval.
    ``"unknown"``        : edge present (Planner retained it) but not backed
                           by a retrievable evidence record.
    ``"model_estimated"``: **never produced** by this codebase.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Edge identifier (derived from source, target, type).")
    source: str = Field(description="Source node ID.")
    target: str = Field(description="Target node ID.")
    type: str = Field(description="Relationship type (e.g. 'functional_association').")
    confidence: _PermittedConfidence = Field(
        description=(
            "Evidence confidence. Only 'evidence' or 'unknown' are produced. "
            "'model_estimated' is structurally excluded (architecture Sec. 8)."
        ),
    )
    weight: float = Field(description="Edge weight (source_score if available, else 0.0).")
    rationale: str | None = Field(default=None, description="Optional explanatory rationale.")


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------


class ContractStrategy(BaseModel):
    """A candidate strategy in the contract-shaped run result."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Strategy identifier.")
    included: list[str] = Field(
        default_factory=list,
        description="Gene/entity identifiers selected by this strategy.",
    )
    excluded: list[str] = Field(
        default_factory=list,
        description="Candidate identifiers considered but excluded by this strategy.",
    )
    risk_score: float = Field(
        description=(
            "Risk score in [0.0, 1.0] -- derived from Planner score as (1 - score). "
            "Lower is safer."
        ),
    )
    rationale: str = Field(description="Human-readable Planner rationale for this strategy.")
    stages: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Optional downstream stage annotations (Post-Plan Analysis output).",
    )


# ---------------------------------------------------------------------------
# Run result
# ---------------------------------------------------------------------------

#: Status values from the contract's RunResult.status enum.
_RunStatus = Literal["queued", "running", "complete", "failed"]


class ContractRunResult(BaseModel):
    """
    Full run result shape as defined in ``api.contract.json``.

    Returned by ``GET /v1/runs/{run_id}``.  For in-progress runs, ``nodes``,
    ``edges``, and ``strategies`` will be empty lists and ``status`` will
    reflect the current pipeline phase (``queued`` or ``running``).
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(description="Unique run identifier.")
    status: _RunStatus = Field(description="Run lifecycle status.")
    objective: str | None = Field(
        default=None,
        description="Research objective echoed back from the run request.",
    )
    created_at: str | None = Field(
        default=None,
        description="ISO-8601 UTC datetime when the run was created.",
    )
    duration_ms: int | None = Field(
        default=None,
        description="Elapsed pipeline duration in milliseconds (set on completion).",
    )
    nodes: list[ContractGraphNode] = Field(
        default_factory=list,
        description="Evidence graph nodes.",
    )
    edges: list[ContractGraphEdge] = Field(
        default_factory=list,
        description="Evidence graph edges.",
    )
    strategies: list[ContractStrategy] = Field(
        default_factory=list,
        description="Ranked candidate strategies.",
    )
