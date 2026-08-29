from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import networkx as nx

# =============================================================================
# Graph models
# =============================================================================


@dataclass
class GraphNode:
    """
    One biological entity in the Planner evidence graph.

    `id` is the canonical identifier used internally by the graph.

    The graph builder does not invent entity types. If Retrieval provides
    type information in metadata, it is retained.
    """

    id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """
    One source-backed biological relationship.

    Every EvidenceRecord becomes one GraphEdge.

    Multiple GraphEdges may connect the same pair of nodes because different
    sources may provide different relationships or independent evidence.
    """

    source_node: str
    target_node: str

    relationship: str

    source: str | None = None
    source_id: str | None = None

    effect: Any | None = None

    source_score: float | None = None

    provenance: Any | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    consequence: Any | None = None


@dataclass
class EvidenceGraph:
    """
    Planner's internal graph representation.

    `nodes` and `edges` are explicit because the architecture defines the
    evidence graph as:

        GraphNode[]
        GraphEdge[]

    `networkx_graph` provides graph traversal/search functionality.
    """

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    networkx_graph: nx.MultiDiGraph


# =============================================================================
# Exceptions
# =============================================================================


class GraphBuilderError(ValueError):
    """Raised when an EvidenceRecord cannot be converted into a graph."""


# =============================================================================
# Helpers
# =============================================================================


def _get_field(
    record: Any,
    field_name: str,
    default: Any = None,
) -> Any:
    """
    Read a field from either:

        - dict
        - Pydantic model
        - dataclass
        - regular Python object
    """

    if isinstance(record, dict):
        return record.get(field_name, default)

    return getattr(record, field_name, default)


def _normalize_entity(entity: Any) -> str:
    """
    Convert an entity into a stable graph identifier.

    Entity normalization/resolution should already have happened upstream.
    The Planner must not invent aliases or biological identity mappings.
    """

    if entity is None:
        raise GraphBuilderError("EvidenceRecord has a missing entity.")

    entity_id = str(entity).strip()

    if not entity_id:
        raise GraphBuilderError("EvidenceRecord has an empty entity.")

    return entity_id


def _normalize_relationship(relationship: Any) -> str:
    """Validate a relationship."""

    if relationship is None:
        raise GraphBuilderError("EvidenceRecord has a missing relationship.")

    value = str(relationship).strip()

    if not value:
        raise GraphBuilderError("EvidenceRecord has an empty relationship.")

    return value


def _normalize_score(score: Any) -> float | None:
    """
    Convert source_score to float.

    source_score is preserved as source evidence metadata.

    IMPORTANT:
        It is NOT interpreted here as a probability or Planner score.
    """

    if score is None:
        return None

    try:
        return float(score)

    except (TypeError, ValueError) as exc:
        raise GraphBuilderError(f"Invalid source_score: {score!r}") from exc


def _normalize_metadata(metadata: Any) -> dict[str, Any]:
    """Ensure metadata is represented as a dictionary."""

    if metadata is None:
        return {}

    if isinstance(metadata, dict):
        return metadata

    # Don't discard unexpected metadata.
    return {"raw_metadata": metadata}


# =============================================================================
# GraphBuilder
# =============================================================================


class GraphBuilder:
    """
    Builds the Planner's evidence graph from EvidenceRecord objects.

    Uses a NetworkX MultiDiGraph.

    Why MultiDiGraph?

    Because this:

        GeneA --REGULATES--> PathwayX  [Source A]
        GeneA --REGULATES--> PathwayX  [Source B]

    represents TWO independent pieces of evidence.

    A normal DiGraph would collapse/overwrite edges between the same nodes.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []

        self._graph = nx.MultiDiGraph()

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def build(
        self,
        evidence_records: Iterable[Any],
    ) -> EvidenceGraph:
        """
        Build a fresh EvidenceGraph.

        Existing state is cleared before construction.
        """

        self.clear()

        for index, record in enumerate(evidence_records):
            self.add_record(
                record=record,
                record_index=index,
            )

        return EvidenceGraph(
            nodes=list(self._nodes.values()),
            edges=list(self._edges),
            networkx_graph=self._graph,
        )

    def add_record(
        self,
        record: Any,
        record_index: int | None = None,
    ) -> GraphEdge:
        """
        Convert one EvidenceRecord into:

            GraphNode(entity_a)
            GraphNode(entity_b)
            GraphEdge(entity_a -> entity_b)

        Returns the created GraphEdge.
        """

        entity_a = _normalize_entity(_get_field(record, "entity_a"))

        entity_b = _normalize_entity(_get_field(record, "entity_b"))

        relationship = _normalize_relationship(_get_field(record, "relationship"))

        source = _get_field(record, "source")
        source_id = _get_field(record, "source_id")

        effect = _get_field(record, "effect")

        source_score = _normalize_score(_get_field(record, "source_score"))

        provenance = _get_field(record, "provenance")

        metadata = _normalize_metadata(_get_field(record, "metadata", {}))

        consequence = _get_field(record, "consequence")

        # ---------------------------------------------------------------------
        # Create nodes
        # ---------------------------------------------------------------------

        self._add_node(entity_a)
        self._add_node(entity_b)

        # ---------------------------------------------------------------------
        # Create explicit GraphEdge
        # ---------------------------------------------------------------------

        edge = GraphEdge(
            source_node=entity_a,
            target_node=entity_b,
            relationship=relationship,
            source=source,
            source_id=source_id,
            effect=effect,
            source_score=source_score,
            provenance=provenance,
            metadata=metadata,
            consequence=consequence,
        )

        self._edges.append(edge)

        # ---------------------------------------------------------------------
        # Add equivalent edge to NetworkX
        # ---------------------------------------------------------------------

        self._graph.add_edge(
            entity_a,
            entity_b,
            relationship=relationship,
            source=source,
            source_id=source_id,
            effect=effect,
            source_score=source_score,
            provenance=provenance,
            metadata=metadata,
            consequence=consequence,
            evidence_index=record_index,
        )

        return edge

    def clear(self) -> None:
        """Clear all graph state."""

        self._nodes.clear()
        self._edges.clear()
        self._graph.clear()

    def summary(self) -> dict[str, int]:
        """Return simple graph statistics."""

        return {
            "node_count": len(self._nodes),
            "edge_count": len(self._edges),
        }

    # -------------------------------------------------------------------------
    # Node creation
    # -------------------------------------------------------------------------

    def _add_node(
        self,
        entity_id: str,
    ) -> None:
        """
        Add a node only if it does not already exist.

        One normalized biological entity corresponds to one GraphNode.
        """

        if entity_id in self._nodes:
            return

        node = GraphNode(
            id=entity_id,
        )

        self._nodes[entity_id] = node

        self._graph.add_node(
            entity_id,
            graph_node=node,
        )


# =============================================================================
# Convenience function
# =============================================================================


def build_evidence_graph(
    evidence_records: Iterable[Any],
) -> EvidenceGraph:
    """
    Convenience function for one-shot graph construction.
    """

    return GraphBuilder().build(evidence_records)
