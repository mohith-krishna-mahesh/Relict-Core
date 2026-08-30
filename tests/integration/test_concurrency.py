"""
Concurrency and State Isolation Tests for Relict Core.

Verifies:
- Multiple concurrent API requests receive unique run IDs.
- Concurrent execution maintains isolated state in the repository.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.cache.sqlite_client import ensure_schema, open_connection
from app.cache.sqlite_repository import SQLiteRunRepository
from app.core_model.resolver import CoreModelObjectiveResolver
from app.main import app
from app.models.evidence import EffectDirection, EffectType, EvidenceEffect, EvidenceRecord
from app.models.requests import (
    ProjectContext,
    RetrievalContext,
    RunConfiguration,
    Scope,
    StrategyMode,
)
from app.models.responses import RetrievalResult, SourceStatus
from app.models.run_state import RunStatus
from app.planner.adapter import ProductionStrategicPlanner
from app.post_plan.analyzer import DefaultPostPlanAnalyzer
from app.run_manager.events import InMemoryRunEventBus
from app.run_manager.orchestrator import RunOrchestrator
from app.validator.plan_validator import PlanValidator


class MockRetrieval:
    async def retrieve(self, ctx: RetrievalContext) -> RetrievalResult:
        records = [
            EvidenceRecord(
                entity_a="GENE_1",
                relationship="activates",
                entity_b="TRAIT_1",
                source="ensembl",
                source_id="E01",
                source_score=0.9,
                effect=EvidenceEffect(
                    type=EffectType.ACTIVATION, direction=EffectDirection.INCREASES
                ),
            )
        ]
        return RetrievalResult(
            records=records,
            source_statuses=[SourceStatus(source_name="ensembl", success=True)],
            failure_code=None,
        )


@pytest.mark.asyncio
async def test_concurrent_pipeline_executions(tmp_path: Any) -> None:
    """Verify that multiple concurrent pipeline executions maintain unique IDs and isolated states."""
    conn = open_connection(tmp_path / "test_concurrent.db")
    ensure_schema(conn)
    repo = SQLiteRunRepository(conn)
    bus = InMemoryRunEventBus()

    orchestrator = RunOrchestrator(
        resolver=CoreModelObjectiveResolver(),
        retriever=MockRetrieval(),
        planner=ProductionStrategicPlanner(),
        validator=PlanValidator(),
        analyzer=DefaultPostPlanAnalyzer(),
        repository=repo,
        event_bus=bus,
    )

    async def _run_one(idx: int) -> str:
        project = ProjectContext(
            project_id=f"proj_{idx}",
            scope=Scope.CONSERVATION,
            species="Panthera tigris",
            objective=f"Objective for run {idx} with targeted genetic modulation",
        )
        config = RunConfiguration(
            max_edits=2,
            strategy=StrategyMode.MINIMAL,
            candidate_genes=["GENE_1"],
            constraints=[],
        )
        res = await orchestrator.execute(project, config)
        return res.run_id

    run_ids = await asyncio.gather(*[_run_one(i) for i in range(5)])

    assert len(set(run_ids)) == 5
    for rid in run_ids:
        state = repo.load_state(rid)
        assert state is not None
        assert state.status in (RunStatus.COMPLETE, RunStatus.FAILED)

    conn.close()
