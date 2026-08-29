from __future__ import annotations

import abc
import logging
from typing import Any, Protocol, runtime_checkable

import httpx

from app.config import RetrievalSettings
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cache protocol — implemented by app/cache/ when wired up
# ---------------------------------------------------------------------------


@runtime_checkable
class CacheProtocol(Protocol):
    """Minimal async cache interface that Knowledge Retrieval programs against."""

    async def get(self, key: str) -> bytes | None: ...

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None: ...


class NullCache:
    """No-op cache for when no real cache is configured."""

    async def get(self, key: str) -> bytes | None:
        return None

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        pass


# ---------------------------------------------------------------------------
# Base client
# ---------------------------------------------------------------------------


class BaseClient(abc.ABC):
    """Abstract base for all Knowledge Retrieval source clients.

    Provides shared HTTP helpers, provenance construction, and a
    uniform ``query`` contract.
    """

    def __init__(
        self,
        settings: RetrievalSettings | None = None,
        cache: CacheProtocol | None = None,
    ) -> None:
        self.settings = settings or RetrievalSettings()
        self.cache: CacheProtocol = cache or NullCache()
        self._client: httpx.AsyncClient | None = None

    # ── HTTP client (lazy) ────────────────────────────────────────

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.http_timeout),
                headers={"User-Agent": self.settings.user_agent},
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    # ── Abstract contract ─────────────────────────────────────────

    @property
    @abc.abstractmethod
    def source_name(self) -> str:
        """Canonical name of this source (e.g. ``'ensembl'``)."""

    @abc.abstractmethod
    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        """Execute source-specific queries and return evidence."""

    # ── HTTP helpers ──────────────────────────────────────────────

    async def _get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Perform a GET request with error handling."""
        try:
            resp = await self._http.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError:
            logger.warning(
                "%s: HTTP %s from %s",
                self.source_name,
                resp.status_code,  # type: ignore[possibly-undefined]
                url,
            )
            raise
        except httpx.HTTPError as exc:
            logger.warning("%s: HTTP error for %s — %s", self.source_name, url, exc)
            raise

    async def _post(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        content: bytes | str | None = None,
        json_data: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Perform a POST request with error handling."""
        try:
            resp = await self._http.post(
                url, data=data, content=content, json=json_data, headers=headers
            )
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError:
            logger.warning(
                "%s: HTTP %s from %s",
                self.source_name,
                resp.status_code,  # type: ignore[possibly-undefined]
                url,
            )
            raise
        except httpx.HTTPError as exc:
            logger.warning("%s: HTTP error for %s — %s", self.source_name, url, exc)
            raise

    # ── Evidence construction helpers ─────────────────────────────

    def _make_provenance(
        self,
        endpoint: str | None = None,
        source_id: str | None = None,
        query_context: dict[str, Any] | None = None,
    ) -> str:
        parts = [self.source_name]
        if endpoint:
            parts.append(endpoint)
        if source_id:
            parts.append(f"id={source_id}")
        return ":".join(parts)

    def _make_record(
        self,
        entity_a: str,
        relationship: str,
        entity_b: str | None = None,
        source_id: str | None = None,
        source_score: float | None = None,
        endpoint: str | None = None,
        query_context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceRecord:
        return EvidenceRecord(
            source=self.source_name,
            source_id=source_id,
            entity_a=entity_a,
            entity_b=entity_b,
            relationship=relationship,
            source_score=source_score,
            provenance=self._make_provenance(
                endpoint=endpoint,
                source_id=source_id,
                query_context=query_context,
            ),
            metadata=metadata or {},
        )
