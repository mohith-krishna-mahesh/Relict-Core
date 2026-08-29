"""Tests for EvidenceRecord and RelationshipType."""

from __future__ import annotations

from app.models.evidence import EvidenceRecord, RelationshipType


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
        assert r.source_score is None
        assert r.provenance is None
        assert r.metadata == {}

    def test_create_full(self) -> None:
        r = EvidenceRecord(
            source="string",
            source_id="EDGE001",
            entity_a="BRCA1",
            entity_b="TP53",
            relationship="protein_protein",
            source_score=0.95,
            provenance="https://version-12-0.string-db.org",
            metadata={"combined_score": 950},
        )
        assert r.source_score == 0.95
        assert r.provenance == "https://version-12-0.string-db.org"
        assert r.metadata["combined_score"] == 950

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
