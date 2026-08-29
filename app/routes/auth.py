"""
Auth endpoints.

POST /v1/auth/verify
    Validates the caller's bearer token and returns a ``VerifyResponse``
    containing the Core version, instance type, and a minimal token identity.

    Token validation is performed by the shared ``get_bearer_token`` dependency
    (``app.dependencies``).  If we reach the handler, the token is valid.

    Identity model (minimal -- flagged design decision)
    ---------------------------------------------------
    No per-token identity store exists.  All valid tokens receive the same
    static scopes: ``["runs:write", "runs:read", "search:read"]``.  A product
    decision is required before implementing per-token user/org mapping.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import settings
from app.dependencies import get_bearer_token
from app.models.contract import TokenIdentity, VerifyResponse

# Version constant mirrors app/main.py FastAPI(version=...).  Kept in sync
# manually -- if the main app version changes, update this too.
# (We avoid importing app.main here to prevent a circular import.)
_CORE_VERSION = "0.1.0"

router = APIRouter()


@router.post(
    "/auth/verify",
    response_model=VerifyResponse,
    summary="Verify bearer token",
    description=(
        "Validates the ``Authorization: Bearer <token>`` header and returns "
        "Core version, instance type, and the identity associated with the token. "
        "HTTP 401 is returned when the token is missing or invalid."
    ),
    tags=["auth"],
)
async def verify_token(
    _token: str = Depends(get_bearer_token),  # noqa: B008
) -> VerifyResponse:
    """Validate the bearer token and return a ``VerifyResponse``."""
    return VerifyResponse(
        status="verified",
        core_version=_CORE_VERSION,
        instance_type=settings.instance_type,
        identity=TokenIdentity(
            # Minimal identity -- flagged design decision (no per-token identity store).
            user_or_org="api-token",
            scopes=["runs:write", "runs:read", "search:read"],
        ),
    )
