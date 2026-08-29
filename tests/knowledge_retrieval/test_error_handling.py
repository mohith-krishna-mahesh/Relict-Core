"""Tests for error handling in source clients and orchestrator."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from app.config import RetrievalSettings
from app.knowledge_retrieval.base_client import BaseClient
from app.knowledge_retrieval.common.ensembl import EnsemblClient
from app.knowledge_retrieval.retrieval import RetrievalOrchestrator
from app.models.evidence import EvidenceRecord
from app.models.requests import RetrievalContext


@pytest.mark.asyncio
async def test_client_handles_http_error_gracefully() -> None:
    client = EnsemblClient()

    async def mock_error_get(url: str, *args, **kwargs) -> httpx.Response:
        req = httpx.Request("GET", url)
        raise httpx.ConnectError("Connection failed", request=req)

    with patch.object(client, "_get", side_effect=mock_error_get):
        records = await client.query(targets=["BRCA1"], species="human")

    # Should not throw exception, but return empty records
    assert records == []
    await client.close()


@pytest.mark.asyncio
async def test_orchestrator_handles_single_source_failure(
    sample_context: RetrievalContext,
) -> None:
    class FailingClient(BaseClient):
        @property
        def source_name(self) -> str:
            return "failing_source"

        async def query(self, targets, species=None, context=None) -> list[EvidenceRecord]:
            raise RuntimeError("Database connection timed out")

    class WorkingClient(BaseClient):
        @property
        def source_name(self) -> str:
            return "working_source"

        async def query(self, targets, species=None, context=None) -> list[EvidenceRecord]:
            return [
                self._make_record(
                    entity_a="BRCA1",
                    relationship="gene_gene",
                    entity_b="TP53",
                )
            ]

    orchestrator = RetrievalOrchestrator(
        settings=RetrievalSettings(min_evidence_records=1, max_concurrency=2)
    )

    with patch(
        "app.knowledge_retrieval.retrieval._CLIENT_REGISTRY",
        {"failing_source": FailingClient, "working_source": WorkingClient},
    ):
        with patch(
            "app.knowledge_retrieval.retrieval.get_sources_for_scope",
            return_value=["failing_source", "working_source"],
        ):
            result = await orchestrator.retrieve(sample_context)

    assert result.failure_code is None
    assert len(result.records) == 1
    assert any(s.source_name == "failing_source" and not s.success for s in result.source_statuses)
    assert any(s.source_name == "working_source" and s.success for s in result.source_statuses)
