"""
End-to-End Pipeline Integration Tests for Relict Core.

Validates the full request-to-result path:
    HTTP request
        ↓
    Authentication
        ↓
    Run creation
        ↓
    Objective resolution (Core Model Task 1)
        ↓
    Knowledge retrieval
        ↓
    Evidence Graph & Deterministic Planning
        ↓
    Validation
        ↓
    Post-Plan Analysis (Guide/Risk, Population, Explanation Task 2)
        ↓
    RunResult persistence & API response
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.cache.sqlite_client import ensure_schema, open_connection
from app.cache.sqlite_repository import SQLiteRunRepository
from app.config import settings
from app.core_model.resolver import CoreModelObjectiveResolver
from app.knowledge_retrieval.retrieval import KnowledgeRetrievalEngine
from app.main import app
from app.models.evidence import EffectDirection, EffectType, EvidenceEffect, EvidenceRecord
from app.models.requests import (
    ProjectContext,
    RetrievalContext,
    RunConfiguration,
    Scope,
    StrategyMode,
    StructuredObjective,
)
from app.models.responses import RetrievalResult, SourceStatus
from app.models.run_state import RunStatus
from app.planner.adapter import ProductionStrategicPlanner
from app.post_plan.analyzer import DefaultPostPlanAnalyzer
from app.run_manager.events import InMemoryRunEventBus
from app.run_manager.orchestrator import RunOrchestrator
from app.validator.plan_validator import PlanValidator


class MockRetrievalEngine:
    """Mock retrieval providing realistic source-backed evidence records."""

    async def retrieve(self, context: RetrievalContext) -> RetrievalResult:
        records = [
            EvidenceRecord(
                entity_a="UCP1",
                relationship="increases_expression_of",
                entity_b="thermogenesis",
                source="uniprot",
                source_id="UP001",
                source_score=0.95,
                effect=EvidenceEffect(
                    type=EffectType.EXPRESSION, direction=EffectDirection.INCREASES
                ),
                metadata={"species": "Mammuthus primigenius"},
            ),
            EvidenceRecord(
                entity_a="TRPV3",
                relationship="regulates",
                entity_b="cold_tolerance",
                source="ensembl",
                source_id="ENS002",
                source_score=0.90,
                effect=EvidenceEffect(
                    type=EffectType.REGULATION, direction=EffectDirection.INCREASES
                ),
                metadata={"species": "Mammuthus primigenius"},
            ),
            EvidenceRecord(
                entity_a="HBB",
                relationship="regulates",
                entity_b="oxygen_affinity",
                source="ncbi_datasets",
                source_id="NCBI003",
                source_score=0.92,
                effect=EvidenceEffect(
                    type=EffectType.REGULATION, direction=EffectDirection.INCREASES
                ),
                metadata={"species": "Mammuthus primigenius"},
            ),
        ]
        statuses = [
            SourceStatus(source_name="uniprot", success=True, record_count=1),
            SourceStatus(source_name="ensembl", success=True, record_count=1),
            SourceStatus(source_name="ncbi_datasets", success=True, record_count=1),
        ]
        return RetrievalResult(records=records, source_statuses=statuses, failure_code=None)


@pytest.mark.asyncio
async def test_full_pipeline_orchestration(tmp_path: Any) -> None:
    """Test full pipeline execution through RunOrchestrator directly."""
    db_file = tmp_path / "test_relict.db"
    conn = open_connection(db_file)
    ensure_schema(conn)
    repo = SQLiteRunRepository(conn)
    bus = InMemoryRunEventBus()

    orchestrator = RunOrchestrator(
        resolver=CoreModelObjectiveResolver(),
        retriever=MockRetrievalEngine(),
        planner=ProductionStrategicPlanner(),
        validator=PlanValidator(),
        analyzer=DefaultPostPlanAnalyzer(),
        repository=repo,
        event_bus=bus,
    )

    project = ProjectContext(
        project_id="proj_mammoth_01",
        scope=Scope.DE_EXTINCTION,
        species="Mammuthus primigenius",
        objective="Reconstitute subzero non-shivering thermogenesis and cold tolerance via UCP1 and TRPV3",
    )
    config = RunConfiguration(
        max_edits=3,
        strategy=StrategyMode.MINIMAL,
        candidate_genes=["UCP1", "TRPV3", "HBB"],
        constraints=[],
    )

    result = await orchestrator.execute(project, config)

    # Validate end-to-end result
    if result.status != RunStatus.COMPLETE:
        print(f"DEBUG FAILURE: status={result.status}, failure={result.failure}")
    assert result.status == RunStatus.COMPLETE
    assert result.structured_objective is not None
    assert result.structured_objective.ambiguity_status.value.upper() == "CLEAR"
    assert len(result.strategies) >= 1
    assert result.post_plan is not None
    assert result.post_plan.status.value in ("complete", "partial")

    conn.close()


def test_api_end_to_end_http_request(tmp_path: Any, monkeypatch: Any) -> None:
    """Test full HTTP API request cycle with async dispatch and result polling."""
    from app.dependencies import get_orchestrator, get_repository

    db_file = tmp_path / "test_api_relict.db"
    conn = open_connection(db_file)
    ensure_schema(conn)
    repo = SQLiteRunRepository(conn)
    bus = InMemoryRunEventBus()

    test_orchestrator = RunOrchestrator(
        resolver=CoreModelObjectiveResolver(),
        retriever=MockRetrievalEngine(),
        planner=ProductionStrategicPlanner(),
        validator=PlanValidator(),
        analyzer=DefaultPostPlanAnalyzer(),
        repository=repo,
        event_bus=bus,
    )

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_orchestrator] = lambda: test_orchestrator
    monkeypatch.setattr(settings, "max_concurrent_runs", 10)

    test_token = "rc_live_test_integration_token_123"
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_tokens", [test_token])
    headers = {"Authorization": f"Bearer {test_token}"}

    try:
        with TestClient(app) as client:
            payload = {
                "species": "Mammuthus primigenius",
                "research_objective": "Introduce precise mutations to UCP1 and TRPV3 to restore cold adaptation phenotypes",
                "candidate_genes": ["UCP1", "TRPV3"],
                "constraints": {
                    "max_edits": 2,
                    "preserve_fertility": False,
                    "maximize_diversity": False,
                },
                "presets": ["minimal"],
            }

            resp = client.post("/v1/runs", json=payload, headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert "run_id" in data
            run_id = data["run_id"]

            # Poll run status
            import time

            result_data = None
            for i in range(50):
                time.sleep(0.1)
                get_resp = client.get(f"/v1/runs/{run_id}", headers=headers)
                assert get_resp.status_code == 200
                res = get_resp.json()
                status_val = res.get("status")
                if status_val in ("COMPLETE", "FAILED", "complete", "failed"):
                    result_data = res
                    break

            assert result_data is not None, f"Last response: {res}"
            assert result_data["run_id"] == run_id
            assert result_data["status"].lower() == "complete"
    finally:
        app.dependency_overrides.pop(get_repository, None)
        app.dependency_overrides.pop(get_orchestrator, None)
        conn.close()
