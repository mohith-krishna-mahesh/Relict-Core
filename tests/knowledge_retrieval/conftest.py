"""Shared fixtures for Knowledge Retrieval tests."""

from __future__ import annotations

from typing import Any

import pytest

from app.config import RetrievalSettings
from app.models.evidence import EvidenceRecord
from app.models.requests import (
    AmbiguityStatus,
    ProjectContext,
    RetrievalContext,
    RunConfiguration,
    Scope,
    StrategyMode,
    StructuredObjective,
)


@pytest.fixture
def settings() -> RetrievalSettings:
    return RetrievalSettings(
        http_timeout=5.0,
        cache_db_path=":memory:",
        ncbi_api_key=None,
        ncbi_email=None,
    )


@pytest.fixture
def sample_context() -> RetrievalContext:
    return RetrievalContext(
        project_context=ProjectContext(
            project_id="test-project-001",
            species="homo_sapiens",
            scope=Scope.PRECISION_MEDICINE,
            objective="Investigate BRCA1 role in DNA repair",
        ),
        run_configuration=RunConfiguration(
            candidate_genes=["BRCA1", "TP53"],
            max_edits=2,
            constraints=["preserve fertility"],
            strategy=StrategyMode.MINIMAL,
        ),
        structured_objective=StructuredObjective(
            target_phenotypes=["cancer susceptibility"],
            biological_processes=["DNA repair", "homologous recombination"],
            desired_change="enhance DNA repair",
            relevant_concepts=["tumor suppressor"],
            retrieval_targets=["BRCA1", "TP53", "RAD51"],
            ambiguity_status=AmbiguityStatus.CLEAR,
        ),
    )


@pytest.fixture
def sample_record() -> EvidenceRecord:
    return EvidenceRecord(
        source="test_source",
        source_id="TEST001",
        entity_a="BRCA1",
        entity_b="TP53",
        relationship="protein_protein",
        source_score=0.95,
        provenance="test_source:/test/endpoint",
        metadata={"confidence": "high"},
    )


class MockCache:
    """In-memory mock cache for testing."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self._store.get(key)

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        self._store[key] = value


@pytest.fixture
def mock_cache() -> MockCache:
    return MockCache()


def make_record(
    source: str = "test",
    source_id: str = "ID1",
    entity_a: str = "GENE_A",
    entity_b: str | None = "GENE_B",
    relationship: str = "protein_protein",
    source_score: float | None = 0.9,
    **kwargs: Any,
) -> EvidenceRecord:
    """Helper to quickly build EvidenceRecord instances for tests."""
    return EvidenceRecord(
        source=source,
        source_id=source_id,
        entity_a=entity_a,
        entity_b=entity_b,
        relationship=relationship,
        source_score=source_score,
        provenance=f"https://example.com/{source}",
        metadata=kwargs,
    )
