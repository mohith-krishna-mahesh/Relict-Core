"""
Production Strategic Planner Adapter for Relict Core.

Implements the StrategicPlanner protocol (app.run_manager.stages.StrategicPlanner)
connecting EvidenceGraph construction, deterministic constraint filtering, and
StrategySearch to produce ranked candidate Strategy response models.
"""

from __future__ import annotations

import logging
from typing import Any

from app.models.evidence import EvidenceRecord
from app.models.graph import GraphEdge
from app.models.requests import RetrievalContext, StrategyMode
from app.models.responses import Strategy as ResponseStrategy
from app.planner.graph_builder import EvidenceGraph, build_evidence_graph
from app.planner.search import StrategySearch

logger = logging.getLogger(__name__)


def _to_graph_edge(e: Any) -> GraphEdge:
    """Safely convert graph/planner edge representations into GraphEdge models."""
    if isinstance(e, GraphEdge):
        return e
    if isinstance(e, dict):
        src = (
            e.get("source_node_id")
            or e.get("source_node")
            or e.get("_source_node")
            or e.get("source")
            or ""
        )
        tgt = (
            e.get("target_node_id")
            or e.get("target_node")
            or e.get("_target_node")
            or e.get("target")
            or ""
        )
        return GraphEdge(
            source_node_id=str(src),
            target_node_id=str(tgt),
            relationship=str(e.get("relationship", "associated_with")),
            source=str(e.get("source", "evidence")),
            source_score=float(e["source_score"]) if e.get("source_score") is not None else None,
            provenance=str(e.get("provenance")) if e.get("provenance") is not None else None,
        )
    src = getattr(e, "source_node_id", getattr(e, "source_node", getattr(e, "_source_node", "")))
    tgt = getattr(e, "target_node_id", getattr(e, "target_node", getattr(e, "_target_node", "")))
    rel = getattr(e, "relationship", "associated_with")
    src_db = getattr(e, "source", "evidence") or "evidence"
    score = getattr(e, "source_score", None)
    prov = getattr(e, "provenance", None)
    return GraphEdge(
        source_node_id=str(src),
        target_node_id=str(tgt),
        relationship=str(rel),
        source=str(src_db),
        source_score=float(score) if score is not None else None,
        provenance=str(prov) if prov is not None else None,
    )


def _convert_strategy(s: Any) -> ResponseStrategy:
    """Convert an internal planner Strategy dataclass into a ResponseStrategy model."""
    raw_mode = getattr(s, "strategy_type", "minimal")
    try:
        mode = StrategyMode(str(raw_mode).lower())
    except ValueError:
        mode = StrategyMode.MINIMAL

    supp = [_to_graph_edge(e) for e in getattr(s, "supporting_edges", [])]
    conf = [_to_graph_edge(e) for e in getattr(s, "conflicting_edges", [])]
    candidates = list(getattr(s, "selected_candidates", []))
    targets = list(getattr(s, "covered_targets", []))

    return ResponseStrategy(
        strategy_type=mode,
        selected_candidates=candidates,
        covered_targets=targets,
        edit_count=int(getattr(s, "edit_count", len(candidates))),
        score=float(getattr(s, "score", 0.0)),
        supporting_edges=supp,
        conflicting_edges=conf,
        rationale=str(getattr(s, "rationale", "")),
    )


class ProductionStrategicPlanner:
    """
    Production Strategic Planner satisfying app.run_manager.stages.StrategicPlanner.
    """

    def __init__(self) -> None:
        pass

    async def plan(
        self,
        context: RetrievalContext,
        evidence: list[EvidenceRecord],
    ) -> list[ResponseStrategy]:
        """
        Build the EvidenceGraph and perform deterministic strategy search.

        Parameters
        ----------
        context:
            Complete retrieval and run context.
        evidence:
            Normalized EvidenceRecord objects from Knowledge Retrieval.

        Returns
        -------
        list[ResponseStrategy]
            Ranked list of feasible strategies, or empty list if no feasible plan.
        """
        if not evidence:
            return []

        # 1. Build EvidenceGraph
        graph = build_evidence_graph(evidence)
        candidate_genes = list(context.run_configuration.candidate_genes)
        if candidate_genes:
            for g in candidate_genes:
                if g in graph.networkx_graph.nodes:
                    graph.networkx_graph.nodes[g]["entity_type"] = "gene"
                    graph.networkx_graph.nodes[g]["type"] = "gene"

        # 2. Configure StrategySearch
        max_edits = max(1, context.run_configuration.max_edits)
        strat_mode = getattr(
            context.run_configuration,
            "strategy",
            getattr(context.run_configuration, "strategy_mode", StrategyMode.MINIMAL),
        )
        strategy_type = (
            strat_mode.value.lower() if hasattr(strat_mode, "value") else str(strat_mode).lower()
        )
        constraints = list(context.run_configuration.constraints)

        try:
            search_engine = StrategySearch(
                objective=context.structured_objective,
                constraints=constraints,
                max_edits=max_edits,
                strategy_type=strategy_type,
            )
            raw_strategies = search_engine.search(graph)
        except Exception as exc:
            logger.warning("Strategy search encountered an error: %s", exc)
            return []

        # 3. Convert to response strategy models
        results = [_convert_strategy(s) for s in raw_strategies]

        # Enforce candidate_genes filter if specified
        if candidate_genes:
            allowed = set(candidate_genes)
            results = [s for s in results if all(c in allowed for c in s.selected_candidates)]

        return results
