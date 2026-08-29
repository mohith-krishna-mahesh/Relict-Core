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
    description="Returns ``{\"status\": \"ok\"}`` when Core is running.",
    tags=["infrastructure"],
)
async def health() -> HealthResponse:
    """Return a static liveness response."""
    return HealthResponse(status="ok")
