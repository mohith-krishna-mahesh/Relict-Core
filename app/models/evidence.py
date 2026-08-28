"""EvidenceRecord: normalized evidence returned by Knowledge Retrieval."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvidenceRecord(BaseModel):
    """
    Normalized representation of a single piece of evidence returned by
    the Knowledge Retrieval stage (architecture §3.5).

    Every field maps directly to the canonical spec.  No ``planner_weight``
    field is present here: that value is an internal Planner quantity derived
    from source_score, lives on the Planner's internal graph edge, and is
    never part of the shared evidence contract.

    Fields
    ------
    source
        Name of the originating database (e.g. ``"STRING"``, ``"KEGG"``).
    source_id
        Database-native identifier for the record.
    entity_a
        Primary biological entity involved in the relationship.
    entity_b
        Secondary biological entity involved in the relationship.
    relationship
        Relationship type as reported by the source
        (e.g. ``"functional_association"``).
    source_score
        Score supplied by the originating source where available.
        Not automatically a calibrated probability.
    provenance
        Human-readable provenance string (e.g. publication DOI, URL, version).
    metadata
        Source-specific extra fields that do not fit the canonical columns.
    """

    source: str
    source_id: str
    entity_a: str
    entity_b: str
    relationship: str
    source_score: float | None = None
    provenance: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
