"""Tests for app.models.evidence — EvidenceRecord."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.evidence import EvidenceRecord


class TestEvidenceRecord:
    def test_no_planner_weight_field(self) -> None:
        """
        Architecture §3.5 explicitly states planner_weight is an internal
        Planner value, NOT part of EvidenceRecord.  This test enforces that.
        """
        assert "planner_weight" not in EvidenceRecord.model_fields

    def test_minimal_valid_instance(self) -> None:
        rec = EvidenceRecord(
            source="STRING",
            source_id="9606.ENSP00000000233",
            entity_a="GENE_A",
            entity_b="GENE_B",
            relationship="functional_association",
        )
        assert rec.source == "STRING"
        assert rec.entity_a == "GENE_A"
        assert rec.entity_b == "GENE_B"
        assert rec.relationship == "functional_association"
        assert rec.source_score is None
        assert rec.provenance is None
        assert rec.metadata == {}

    def test_full_valid_instance(self) -> None:
        rec = EvidenceRecord(
            source="STRING",
            source_id="9606.ENSP00000000233",
            entity_a="TYRP1",
            entity_b="DCT",
            relationship="functional_association",
            source_score=0.91,
            provenance="https://version-12-0.string-db.org",
            metadata={"combined_score": 0.91, "channel": "coexpression"},
        )
        assert rec.source_score == 0.91
        assert rec.metadata["channel"] == "coexpression"

    def test_missing_source_raises(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceRecord(
                source_id="x",
                entity_a="A",
                entity_b="B",
                relationship="r",
            )  # type: ignore[call-arg]

    def test_missing_entity_a_raises(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceRecord(
                source="STRING",
                source_id="x",
                entity_b="B",
                relationship="r",
            )  # type: ignore[call-arg]

    def test_wrong_source_score_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceRecord(
                source="STRING",
                source_id="x",
                entity_a="A",
                entity_b="B",
                relationship="r",
                source_score="not-a-float",  # type: ignore[arg-type]
            )

    def test_canonical_fields_exactly(self) -> None:
        """Verify the canonical field set matches revised evidence model."""
        expected_fields = {
            "source",
            "source_id",
            "entity_a",
            "entity_b",
            "relationship",
            "effect",
            "consequence",
            "source_score",
            "provenance",
            "metadata",
        }
        assert set(EvidenceRecord.model_fields.keys()) == expected_fields
