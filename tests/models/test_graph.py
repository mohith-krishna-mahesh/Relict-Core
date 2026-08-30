"""Tests for app.models.graph — EntityType, GraphNode, GraphEdge."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.graph import EntityType, GraphEdge, GraphNode


class TestEntityType:
    def test_known_values_present(self) -> None:
        values = {e.value for e in EntityType}
        for expected in ("gene", "protein", "pathway", "phenotype", "species", "other"):
            assert expected in values

    def test_invalid_entity_type_rejected(self) -> None:
        with pytest.raises((ValueError, ValidationError)):
            GraphNode(node_id="n1", entity_type="bacterium", name="X")  # type: ignore[arg-type]


class TestGraphNode:
    def test_minimal_valid_instance(self) -> None:
        node = GraphNode(node_id="gene:TYRP1", entity_type=EntityType.GENE, name="TYRP1")
        assert node.node_id == "gene:TYRP1"
        assert node.entity_type == EntityType.GENE
        assert node.name == "TYRP1"
        assert node.metadata == {}

    def test_with_metadata(self) -> None:
        node = GraphNode(
            node_id="pathway:ko00230",
            entity_type=EntityType.PATHWAY,
            name="Purine metabolism",
            metadata={"source": "KEGG", "organism": "hsa"},
        )
        assert node.metadata["source"] == "KEGG"

    def test_missing_node_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            GraphNode(entity_type=EntityType.GENE, name="X")  # type: ignore[call-arg]

    def test_missing_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            GraphNode(node_id="x", entity_type=EntityType.GENE)  # type: ignore[call-arg]

    def test_missing_entity_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            GraphNode(node_id="x", name="Y")  # type: ignore[call-arg]


class TestGraphEdge:
    def test_minimal_valid_instance(self) -> None:
        edge = GraphEdge(
            source_node_id="gene:TYRP1",
            target_node_id="gene:DCT",
            relationship="functional_association",
            source="STRING",
        )
        assert edge.source_node_id == "gene:TYRP1"
        assert edge.target_node_id == "gene:DCT"
        assert edge.relationship == "functional_association"
        assert edge.source == "STRING"
        assert edge.source_score is None
        assert edge.provenance is None

    def test_full_valid_instance(self) -> None:
        edge = GraphEdge(
            source_node_id="gene:TYRP1",
            target_node_id="pathway:pigmentation",
            relationship="pathway_member",
            source="KEGG",
            source_score=1.0,
            provenance="KEGG Release 112.0",
        )
        assert edge.source_score == 1.0
        assert edge.provenance == "KEGG Release 112.0"

    def test_missing_source_raises(self) -> None:
        with pytest.raises(ValidationError):
            GraphEdge(
                source_node_id="a",
                target_node_id="b",
                relationship="r",
            )  # type: ignore[call-arg]

    def test_missing_relationship_raises(self) -> None:
        with pytest.raises(ValidationError):
            GraphEdge(
                source_node_id="a",
                target_node_id="b",
                source="STRING",
            )  # type: ignore[call-arg]

    def test_wrong_score_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            GraphEdge(
                source_node_id="a",
                target_node_id="b",
                relationship="r",
                source="STRING",
                source_score="high",  # type: ignore[arg-type]
            )
