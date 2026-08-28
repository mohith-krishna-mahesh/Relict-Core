"""Evidence Graph models: GraphNode and GraphEdge (architecture §3.6)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EntityType(StrEnum):
    """
    Known biological entity types represented as graph nodes.

    The architecture lists Gene, Protein, Pathway, Phenotype, Species as
    examples (§3.6).  ``OTHER`` accommodates entity types not yet enumerated.
    """

    GENE = "gene"
    PROTEIN = "protein"
    PATHWAY = "pathway"
    PHENOTYPE = "phenotype"
    SPECIES = "species"
    OTHER = "other"


class GraphNode(BaseModel):
    """
    A node in the Evidence Graph representing a biological entity.

    The full internal graph is constructed by ``planner/graph_builder.py``.
    Only the relevant subgraph is exposed to Shell (architecture §3.6).

    Fields
    ------
    node_id
        Stable identifier used to link GraphEdge source/target references.
    entity_type
        Biological entity category; see EntityType.
    name
        Human-readable display name (e.g. gene symbol, pathway name).
    metadata
        Optional source-specific annotations.
    """

    node_id: str
    entity_type: EntityType
    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """
    An edge in the Evidence Graph representing a source-backed relationship
    (architecture §3.6).

    Edge metadata exposed to Shell: relationship, source, source_score,
    provenance.  The internal Planner quantity ``planner_weight`` is NOT
    stored here; it lives solely inside the Planner's in-memory graph.

    Fields
    ------
    source_node_id
        ``node_id`` of the source (entity A) node.
    target_node_id
        ``node_id`` of the target (entity B) node.
    relationship
        Relationship type (e.g. ``"functional_association"``).
    source
        Database that supplied this relationship (e.g. ``"STRING"``).
    source_score
        Score from the originating source, if available.
    provenance
        Human-readable provenance reference.
    """

    source_node_id: str
    target_node_id: str
    relationship: str
    source: str
    source_score: float | None = None
    provenance: str | None = None
