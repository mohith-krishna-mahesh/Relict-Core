"""
GET /v1/health

Returns a minimal liveness signal so that Shell and infrastructure tooling
can confirm that Core is running.  No authentication is required.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter()


class HealthResponse(BaseModel):
    """Response body for ``GET /v1/health``."""

    model_config = ConfigDict(extra="forbid")

    status: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check",
    description='Returns ``{"status": "ok"}`` when Core is running.',
    tags=["infrastructure"],
)
async def health() -> HealthResponse:
    """Return runtime health status based on local database accessibility."""
    from pathlib import Path
    from app.config import settings

    db_path = Path(settings.database_path)
    if not db_path.exists():
        return HealthResponse(status="degraded")

    return HealthResponse(status="ok")
