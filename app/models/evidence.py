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


class EffectType(StrEnum):
    """Mechanistic and functional effect classifications."""

    ACTIVATION = "activation"
    INHIBITION = "inhibition"
    PRODUCTION = "production"
    REGULATION = "regulation"
    EXPRESSION = "expression"
    CATALYSIS = "catalysis"
    REQUIREMENT = "requirement"
    LOSS_OF_FUNCTION = "loss_of_function"
    GAIN_OF_FUNCTION = "gain_of_function"
    ASSOCIATION = "association"
    PERTURBATION = "perturbation"
    UNKNOWN = "unknown"


class EffectDirection(StrEnum):
    """Directional trajectory of an effect."""

    INCREASES = "increases"
    DECREASES = "decreases"
    NO_CHANGE = "no_change"
    UNKNOWN = "unknown"


class EvidenceEffect(BaseModel):
    """Directional and functional effect details of an evidence relationship."""

    direction: str | None = None
    type: str | None = None
    magnitude: float | None = None


class EvidenceRecord(BaseModel):
    """Normalized representation of a single piece of biological evidence.

    Knowledge Retrieval returns EvidenceRecord instances wrapped in a
    RetrievalResult.

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
        Relationship type as reported by the source (e.g. ``"catalytic"``, ``"association"``).
    effect
        Optional directional, mechanistic, or functional effect.
    consequence
        Optional explicit biological perturbation consequence if reported by source.
    source_score
        Score supplied by the originating source where available.
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
    effect: EvidenceEffect | None = None
    consequence: str | None = None
    source_score: float | None = None
    provenance: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
