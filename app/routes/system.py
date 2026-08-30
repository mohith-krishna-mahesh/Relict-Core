"""
GET /v1/system

Returns a snapshot of the runtime configuration values that are safe to
expose to Shell: the application version, debug flag, and key Run Manager
limits.  Internal values (database path, model client URL) are not exposed.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.config import settings

router = APIRouter()

# Application version is sourced from a single place (pyproject.toml) to
# avoid version skew.  For Phase 2B the string is set here as a constant;
# Phase 3 can wire in importlib.metadata if desired.
_VERSION = "0.1.0"


class SystemResponse(BaseModel):
    """Response body for ``GET /v1/system``."""

    model_config = ConfigDict(extra="forbid")

    version: str
    debug: bool
    max_concurrent_runs: int
    run_timeout_seconds: int


@router.get(
    "/system",
    response_model=SystemResponse,
    summary="Runtime system information",
    description=(
        "Returns the Core version and key Run Manager limits. "
        "Internal credentials and paths are not exposed."
    ),
    tags=["infrastructure"],
)
async def system_info() -> SystemResponse:
    """Return current runtime configuration snapshot."""
    return SystemResponse(
        version=_VERSION,
        debug=settings.debug,
        max_concurrent_runs=settings.max_concurrent_runs,
        run_timeout_seconds=settings.run_timeout_seconds,
    )
