"""EvidenceRecord: normalized evidence returned by Knowledge Retrieval."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RelationshipType(StrEnum):
    """Known biological relationship types.

    This is not exhaustive — sources may produce relationships
    outside this enumeration. The field on EvidenceRecord is a
    plain ``str`` so that novel relationship types are never
    silently dropped.
    """

    GENE_GENE = "gene_gene"
    GENE_PROTEIN = "gene_protein"
    GENE_PATHWAY = "gene_pathway"
    GENE_PHENOTYPE = "gene_phenotype"
    VARIANT_GENE = "variant_gene"
    PROTEIN_STRUCTURE = "protein_structure"
    PROTEIN_PROTEIN = "protein_protein"
    COMPOUND_PROTEIN = "compound_protein"
    ENZYME_REACTION = "enzyme_reaction"
    SPECIES_TAXON = "species_taxon"
    SPECIES_DIVERGENCE = "species_divergence"
    GENE_DISEASE = "gene_disease"
    GENE_EXPRESSION = "gene_expression"
    GENE_ORTHOLOGY = "gene_orthology"
    GENE_VARIANT = "gene_variant"
    PROTEIN_FUNCTION = "protein_function"
    GENE_QTL = "gene_qtl"
    COMPOUND_DISEASE = "compound_disease"
    VARIANT_PHENOTYPE = "variant_phenotype"
    VARIANT_PATHOGENICITY = "variant_pathogenicity"
    GENE_REACTION = "gene_reaction"
    PART_DESIGN = "part_design"
    SPECIES_OCCURRENCE = "species_occurrence"
    SPECIES_ASSEMBLY = "species_assembly"
    GENE_REGULATION = "gene_regulation"
    LITERATURE_ASSOCIATION = "literature_association"


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
    source_id: str | None = None
    entity_a: str
    entity_b: str | None = None
    relationship: str
    source_score: float | None = None
    provenance: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
