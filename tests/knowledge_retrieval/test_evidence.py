"""Tests for EvidenceRecord, RelationshipType, EffectType, and EffectDirection."""

from __future__ import annotations

from app.models.evidence import (
    EffectDirection,
    EffectType,
    EvidenceEffect,
    EvidenceRecord,
    RelationshipType,
)


class TestEvidenceRecord:
    def test_create_minimal(self) -> None:
        r = EvidenceRecord(
            source="test",
            entity_a="BRCA1",
            relationship="gene_gene",
        )
        assert r.source == "test"
        assert r.entity_a == "BRCA1"
        assert r.entity_b is None
        assert r.effect is None
        assert r.consequence is None
        assert r.source_score is None
        assert r.provenance is None
        assert r.metadata == {}

    def test_create_full_with_effect_and_consequence(self) -> None:
        effect = EvidenceEffect(
            direction=EffectDirection.DECREASES,
            type=EffectType.INHIBITION,
            magnitude=0.85,
        )
        r = EvidenceRecord(
            source="string",
            source_id="EDGE001",
            entity_a="BRCA1",
            entity_b="TP53",
            relationship="protein_protein",
            effect=effect,
            consequence="decreased cell proliferation",
            source_score=0.95,
            provenance="https://version-12-0.string-db.org",
            metadata={"combined_score": 950},
        )
        assert r.source_score == 0.95
        assert r.provenance == "https://version-12-0.string-db.org"
        assert r.metadata["combined_score"] == 950
        assert r.effect is not None
        assert r.effect.direction == "decreases"
        assert r.effect.type == "inhibition"
        assert r.effect.magnitude == 0.85
        assert r.consequence == "decreased cell proliferation"

    def test_relationship_accepts_any_string(self) -> None:
        """relationship is a free str, not constrained to RelationshipType."""
        r = EvidenceRecord(
            source="test",
            entity_a="X",
            relationship="novel_relationship_type",
        )
        assert r.relationship == "novel_relationship_type"

    def test_known_relationship_types(self) -> None:
        assert RelationshipType.GENE_GENE == "gene_gene"
        assert RelationshipType.PROTEIN_PROTEIN == "protein_protein"
        assert RelationshipType.VARIANT_PATHOGENICITY == "variant_pathogenicity"
        assert RelationshipType.ENZYME_REACTION == "enzyme_reaction"

    def test_known_effect_types_and_directions(self) -> None:
        assert EffectType.ACTIVATION == "activation"
        assert EffectType.INHIBITION == "inhibition"
        assert EffectType.PRODUCTION == "production"
        assert EffectType.CATALYSIS == "catalysis"
        assert EffectType.REGULATION == "regulation"
        assert EffectType.LOSS_OF_FUNCTION == "loss_of_function"
        assert EffectType.GAIN_OF_FUNCTION == "gain_of_function"

        assert EffectDirection.INCREASES == "increases"
        assert EffectDirection.DECREASES == "decreases"
        assert EffectDirection.NO_CHANGE == "no_change"
        assert EffectDirection.UNKNOWN == "unknown"

    def test_source_score_not_modified(self) -> None:
        """source_score must be preserved as-is — no probability conversion."""
        r = EvidenceRecord(
            source="string",
            entity_a="A",
            relationship="protein_protein",
            source_score=950.0,
        )
        assert r.source_score == 950.0

    def test_metadata_allows_arbitrary_keys(self) -> None:
        r = EvidenceRecord(
            source="test",
            entity_a="A",
            relationship="gene_gene",
            metadata={"custom_key": [1, 2, 3], "nested": {"a": "b"}},
        )
        assert r.metadata["custom_key"] == [1, 2, 3]
        assert r.metadata["nested"]["a"] == "b"

    def test_entity_b_optional(self) -> None:
        r = EvidenceRecord(
            source="test",
            entity_a="species_x",
            relationship="species_taxon",
        )
        assert r.entity_b is None
