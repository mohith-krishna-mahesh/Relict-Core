"""Tests for retrieval orchestration."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from app.config import RetrievalSettings
from app.knowledge_retrieval.base_client import BaseClient
from app.knowledge_retrieval.retrieval import RetrievalOrchestrator
from app.models.evidence import EvidenceRecord
from app.models.failures import FailureCode
from app.models.requests import (
    ProjectContext,
    RetrievalContext,
    RunConfiguration,
    Scope,
    StrategyMode,
    StructuredObjective,
)


class DummyClient(BaseClient):
    @property
    def source_name(self) -> str:
        return "dummy_source"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        return [
            EvidenceRecord(
                source="dummy_source",
                entity_a=targets[0] if targets else "T1",
                relationship="gene_gene",
                provenance="dummy_source",
            )
        ]


@pytest.mark.asyncio
async def test_retrieve_empty_targets_returns_insufficient_evidence() -> None:
    orchestrator = RetrievalOrchestrator()
    ctx = RetrievalContext(
        project_context=ProjectContext(
            project_id="p1",
            species="human",
            scope=Scope.CONSERVATION,
            objective="test empty",
        ),
        run_configuration=RunConfiguration(
            max_edits=1,
            strategy=StrategyMode.MINIMAL,
        ),
        structured_objective=StructuredObjective(
            desired_change="test",
        ),
    )
    result = await orchestrator.retrieve(ctx)
    assert result.failure_code == FailureCode.INSUFFICIENT_EVIDENCE
    assert result.records == []


@pytest.mark.asyncio
async def test_retrieve_orchestrator_success(sample_context: RetrievalContext) -> None:
    orchestrator = RetrievalOrchestrator(
        settings=RetrievalSettings(min_evidence_records=1, max_concurrency=4)
    )

    with patch(
        "app.knowledge_retrieval.retrieval._CLIENT_REGISTRY",
        {"ensembl": DummyClient, "string": DummyClient},
    ):
        with patch(
            "app.knowledge_retrieval.retrieval.get_sources_for_scope",
            return_value=["ensembl", "string"],
        ):
            result = await orchestrator.retrieve(sample_context)

    assert result.failure_code is None
    assert len(result.records) > 0
    assert any(s.source_name == "ensembl" for s in result.source_statuses)
