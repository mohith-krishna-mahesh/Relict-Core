"""Tests for normalization boundary."""

from __future__ import annotations

import pytest

from app.knowledge_retrieval.normalize import (
    NormalizationError,
    normalize_record,
    normalize_records,
)


def test_normalize_valid_dict() -> None:
    raw = {
        "source": "ensembl",
        "entity_a": "ENSG00000139618",
        "entity_b": "BRCA2",
        "relationship": "gene_gene",
        "source_score": 0.99,
        "metadata": {"gene_type": "protein_coding"},
    }
    rec = normalize_record(raw)
    assert rec.source == "ensembl"
    assert rec.entity_a == "ENSG00000139618"
    assert rec.entity_b == "BRCA2"
    assert rec.relationship == "gene_gene"
    assert rec.source_score == 0.99
    assert rec.metadata["gene_type"] == "protein_coding"


def test_normalize_with_source_override() -> None:
    raw = {
        "entity_a": "GENE1",
        "relationship": "protein_function",
    }
    rec = normalize_record(raw, source="uniprot")
    assert rec.source == "uniprot"
    assert rec.entity_a == "GENE1"


def test_normalize_missing_source_raises() -> None:
    raw = {
        "entity_a": "GENE1",
        "relationship": "protein_function",
    }
    with pytest.raises(NormalizationError):
        normalize_record(raw)


def test_normalize_missing_entity_a_raises() -> None:
    raw = {
        "source": "ensembl",
        "relationship": "gene_gene",
    }
    with pytest.raises(NormalizationError):
        normalize_record(raw)


def test_normalize_missing_relationship_raises() -> None:
    raw = {
        "source": "ensembl",
        "entity_a": "GENE1",
    }
    with pytest.raises(NormalizationError):
        normalize_record(raw)


def test_normalize_batch_skips_malformed() -> None:
    raws = [
        {"source": "src1", "entity_a": "A", "relationship": "rel1"},
        {"source": "src2"},  # Missing entity_a & relationship
        {"source": "src3", "entity_a": "B", "relationship": "rel2"},
    ]
    records = normalize_records(raws)
    assert len(records) == 2
    assert records[0].entity_a == "A"
    assert records[1].entity_a == "B"
