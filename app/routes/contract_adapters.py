"""
Adapter functions: convert internal pipeline models -> contract-shaped models.

Architecture rule
-----------------
This module is a pure, stateless mapping layer with NO business logic and NO
side effects.  It exists solely to translate between the internal representation
(used throughout run_manager/, planner/, validator/, post_plan/) and the
external contract (app/models/contract.py) at the route boundary.

Confidence guarantee (architecture Sec. 8 - "Evidence is authoritative")
-------------------------------------------------------------------------
``adapt_graph_edge`` assigns confidence as follows:

  "evidence"  : the internal GraphEdge has a real database ``source`` AND
                either a non-None ``source_score`` or non-None ``provenance``
                from Knowledge Retrieval.  This means an external biological
                database actually supplied this relationship.

  "unknown"   : the edge is present in the graph (Planner retained it) but
                is not backed by a retrievable evidence record -- e.g. an edge
                the Planner inferred from topology without a direct KR source.

  "model_estimated" : **NEVER produced by this function**.  The
                      ContractGraphEdge.confidence type is
                      Literal["evidence", "unknown"], which structurally
                      prevents this value from being set.  If you find
                      yourself needing this value, that is a signal to use
                      "unknown" instead (architecture Sec. 8 -- model output
                      is not biological evidence and must not reach the graph).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models import graph as internal_graph
from app.models import responses as internal_responses
from app.models.contract import (
    ContractGraphEdge,
    ContractGraphNode,
    ContractRunResult,
    ContractStrategy,
)
from app.models.run_state import RunState, RunStatus

# ---------------------------------------------------------------------------
# Graph node
# ---------------------------------------------------------------------------


def adapt_graph_node(internal: internal_graph.GraphNode) -> ContractGraphNode:
    """
    Convert an internal ``GraphNode`` to a contract ``ContractGraphNode``.

    Confidence is always ``"unknown"`` for nodes -- the internal model carries
    no per-node confidence source; confidence is an edge-level property.
    """
    return ContractGraphNode(
        id=internal.node_id,
        type=str(internal.entity_type),
        label=internal.name,
        rationale=internal.metadata.get("rationale") if internal.metadata else None,
        confidence="unknown",
    )


# ---------------------------------------------------------------------------
# Graph edge
# ---------------------------------------------------------------------------


def adapt_graph_edge(internal: internal_graph.GraphEdge) -> ContractGraphEdge:
    """
    Convert an internal ``GraphEdge`` to a contract ``ContractGraphEdge``.

    Confidence rule (architecture Sec. 8):
      - "evidence"  : internal.source is non-empty AND
                      (internal.source_score is not None OR
                       internal.provenance is not None)
      - "unknown"   : otherwise

    "model_estimated" is NEVER produced -- see module docstring.
    """
    has_source = bool(internal.source and internal.source.strip())
    has_evidence = internal.source_score is not None or internal.provenance is not None
    confidence: str = "evidence" if (has_source and has_evidence) else "unknown"

    edge_id = f"{internal.source_node_id}-{internal.target_node_id}-{internal.relationship}"

    return ContractGraphEdge(
        id=edge_id,
        source=internal.source_node_id,
        target=internal.target_node_id,
        type=internal.relationship,
        confidence=confidence,  # type: ignore[arg-type]  # always "evidence" or "unknown"
        weight=internal.source_score if internal.source_score is not None else 0.0,
        rationale=internal.provenance,
    )


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------


def adapt_strategy(internal: internal_responses.Strategy) -> ContractStrategy:
    """
    Convert an internal ``Strategy`` to a contract ``ContractStrategy``.

    Mapping decisions:
      - ``included``   = internal.selected_candidates
      - ``excluded``   = internal.covered_targets minus selected_candidates
                         (targets considered but not included)
      - ``risk_score`` = max(0.0, min(1.0, 1.0 - internal.score))
                         (Planner score is higher-is-better; contract risk
                          is lower-is-better)
      - ``id``         = "{strategy_type}-{uuid4[:8]}" for uniqueness
    """
    included = list(internal.selected_candidates)
    excluded = [t for t in internal.covered_targets if t not in set(included)]
    risk_score = max(0.0, min(1.0, 1.0 - internal.score))
    strategy_id = f"{internal.strategy_type}-{str(uuid.uuid4())[:8]}"

    return ContractStrategy(
        id=strategy_id,
        included=included,
        excluded=excluded,
        risk_score=risk_score,
        rationale=internal.rationale,
        stages=[],
    )


# ---------------------------------------------------------------------------
# Run result
# ---------------------------------------------------------------------------


def _collect_edges(
    strategies: list[internal_responses.Strategy],
) -> tuple[list[ContractGraphEdge], list[ContractGraphNode]]:
    """
    Extract all unique edges and synthesise node stubs from strategy edge lists.

    The internal ``RunResult`` does not carry a top-level node list; nodes must
    be inferred from the edge endpoints.  We create minimal stub nodes from the
    source_node_id and target_node_id on each edge.
    """
    seen_edges: set[str] = set()
    seen_nodes: set[str] = set()
    edges: list[ContractGraphEdge] = []
    nodes: list[ContractGraphNode] = []

    all_internal_edges: list[internal_graph.GraphEdge] = []
    for strat in strategies:
        all_internal_edges.extend(strat.supporting_edges)
        all_internal_edges.extend(strat.conflicting_edges)

    for ie in all_internal_edges:
        ce = adapt_graph_edge(ie)
        if ce.id not in seen_edges:
            seen_edges.add(ce.id)
            edges.append(ce)

        for node_id in (ie.source_node_id, ie.target_node_id):
            if node_id not in seen_nodes:
                seen_nodes.add(node_id)
                nodes.append(
                    ContractGraphNode(
                        id=node_id,
                        type="unknown",
                        label=node_id,
                        confidence="unknown",
                    )
                )

    return edges, nodes


def _map_status(internal_status: RunStatus) -> str:
    """Map internal RunStatus to contract status string."""
    mapping = {
        RunStatus.PENDING: "queued",
        RunStatus.QUEUED: "queued",
        RunStatus.RUNNING: "running",
        RunStatus.COMPLETE: "complete",
        RunStatus.FAILED: "failed",
    }
    return mapping.get(internal_status, "failed")


def adapt_run_result(
    internal: internal_responses.RunResult,
    route_run_id: str,
) -> ContractRunResult:
    """
    Convert a completed internal ``RunResult`` to a contract ``ContractRunResult``.

    The ``route_run_id`` is the ID returned to the caller by ``POST /v1/runs``.
    It may differ from ``internal.run_id`` (the orchestrator-generated UUID)
    because the route pre-generates an ID for the async dispatch pattern.
    """
    edges, nodes = _collect_edges(internal.strategies)
    contract_strategies = [adapt_strategy(s) for s in internal.strategies]

    objective = internal.project_context.objective if internal.project_context else None

    created_ts: str | None = None
    ts = internal.project_context and getattr(internal, "timestamps", None)
    if ts is None:
        created_ts = datetime.now(tz=UTC).isoformat()

    return ContractRunResult(
        run_id=route_run_id,
        status=_map_status(internal.status),  # type: ignore[arg-type]
        objective=objective,
        created_at=created_ts,
        duration_ms=None,
        nodes=nodes,
        edges=edges,
        strategies=contract_strategies,
    )


def make_partial_run_result(run_id: str, state: RunState) -> ContractRunResult:
    """
    Build a partial ``ContractRunResult`` for an in-progress or failed run
    that has no stored ``RunResult`` yet.

    Returns empty nodes/edges/strategies with the current status -- satisfies
    the contract schema (all array fields have empty-list defaults).
    """
    return ContractRunResult(
        run_id=run_id,
        status=_map_status(state.status),  # type: ignore[arg-type]
        objective=None,
        created_at=None,
        duration_ms=None,
        nodes=[],
        edges=[],
        strategies=[],
    )
