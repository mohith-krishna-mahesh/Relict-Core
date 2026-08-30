"""
Relict Core — FastAPI application entry point.

Lifecycle
---------
On startup (``lifespan``):
  1. Open a SQLite connection at ``settings.database_path`` and create the
     run-store schema if it doesn't already exist.
  2. Build the ``SQLiteRunRepository`` singleton backed by that connection.
  3. Build the ``InMemoryRunEventBus`` singleton (Phase 2C).
  4. Wire the five pipeline stubs into a ``RunOrchestrator``, injecting both
     the repository and the event bus.
  5. Store the connection, repository, event bus, and orchestrator on
     ``app.state`` so route dependencies can retrieve them.

On shutdown:
  Close the SQLite connection cleanly.

Router mounting
---------------
All routes are registered under the ``/v1`` prefix:
  POST /v1/auth/verify
  GET  /v1/search/species
  GET  /v1/search/genes
  GET  /v1/health
  GET  /v1/system
  POST /v1/runs
  GET  /v1/runs/{run_id}
  GET  /v1/runs/{run_id}/stream   <- Phase 2C
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.cache.sqlite_client import ensure_schema, open_connection
from app.cache.sqlite_repository import SQLiteRunRepository
from app.config import settings
from app.core_model.resolver import CoreModelObjectiveResolver
from app.knowledge_retrieval.retrieval import RetrievalOrchestrator
from app.planner.adapter import ProductionStrategicPlanner
from app.post_plan.analyzer import DefaultPostPlanAnalyzer
from app.routes import auth, health, runs, search, system
from app.routes import stream as stream_routes
from app.run_manager.events import InMemoryRunEventBus
from app.run_manager.orchestrator import RunOrchestrator
from app.validator.plan_validator import PlanValidator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan: open the SQLite store and build the orchestrator
    with full production pipeline stages.
    """
    db_conn = open_connection(settings.database_path)
    ensure_schema(db_conn)

    repository = SQLiteRunRepository(db_conn)
    event_bus = InMemoryRunEventBus()

    # Wire real production stage implementations
    resolver = CoreModelObjectiveResolver()
    retriever = RetrievalOrchestrator()
    planner = ProductionStrategicPlanner()
    validator = PlanValidator()
    analyzer = DefaultPostPlanAnalyzer()

    orchestrator = RunOrchestrator(
        resolver=resolver,
        retriever=retriever,
        planner=planner,
        validator=validator,
        analyzer=analyzer,
        repository=repository,
        event_bus=event_bus,
    )

    app.state.db_conn = db_conn
    app.state.repository = repository
    app.state.event_bus = event_bus
    app.state.orchestrator = orchestrator

    yield

    # Shutdown: close the SQLite connection cleanly.
    db_conn.close()


app = FastAPI(
    title="Relict Core",
    description=(
        "Evidence-grounded biological strategy engine. "
        "Converts a natural-language biological objective into an "
        "evidence-backed, constrained strategy and performs downstream "
        "guide/risk analysis, population analysis, and explanation."
    ),
    version="0.1.0",
    contact={
        "name": "Relict Core",
        "url": "https://github.com/mohith-krishna-mahesh/Relict-Core",
    },
    license_info={"name": "AGPL-3.0-only"},
    lifespan=lifespan,
)

app.include_router(health.router, prefix="/v1")
app.include_router(system.router, prefix="/v1")
app.include_router(auth.router, prefix="/v1")
app.include_router(search.router, prefix="/v1")
app.include_router(runs.router, prefix="/v1")
app.include_router(stream_routes.router, prefix="/v1")
