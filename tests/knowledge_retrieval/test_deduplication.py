"""Tests for conservative evidence deduplication."""

from __future__ import annotations

from app.knowledge_retrieval.retrieval import deduplicate
from app.models.evidence import EvidenceRecord


def test_deduplicate_identical_records() -> None:
    rec1 = EvidenceRecord(
        source="ensembl",
        source_id="ID1",
        entity_a="BRCA1",
        entity_b="TP53",
        relationship="gene_gene",
        provenance="ensembl",
    )
    rec2 = EvidenceRecord(
        source="ensembl",
        source_id="ID1",
        entity_a="BRCA1",
        entity_b="TP53",
        relationship="gene_gene",
        provenance="ensembl",
    )
    res = deduplicate([rec1, rec2])
    assert len(res) == 1


def test_does_not_merge_across_different_sources() -> None:
    rec1 = EvidenceRecord(
        source="ensembl",
        source_id="ID1",
        entity_a="BRCA1",
        entity_b="TP53",
        relationship="gene_gene",
        provenance="ensembl",
    )
    rec2 = EvidenceRecord(
        source="string",
        source_id="ID1",
        entity_a="BRCA1",
        entity_b="TP53",
        relationship="gene_gene",
        provenance="string",
    )
    res = deduplicate([rec1, rec2])
    assert len(res) == 2


def test_distinguishes_different_relationships() -> None:
    rec1 = EvidenceRecord(
        source="ensembl",
        source_id="ID1",
        entity_a="BRCA1",
        entity_b="TP53",
        relationship="gene_gene",
        provenance="ensembl",
    )
    rec2 = EvidenceRecord(
        source="ensembl",
        source_id="ID1",
        entity_a="BRCA1",
        entity_b="TP53",
        relationship="protein_protein",
        provenance="ensembl",
    )
    res = deduplicate([rec1, rec2])
    assert len(res) == 2
