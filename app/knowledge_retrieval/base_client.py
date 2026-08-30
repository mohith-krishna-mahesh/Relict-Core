from __future__ import annotations

import abc
import json
import logging
from typing import Any, Protocol, runtime_checkable

import anyio
import httpx

from app.config import RetrievalSettings
from app.models.evidence import EvidenceEffect, EvidenceRecord

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

    Provides shared HTTP helpers, safe JSON parsing, retry with exponential
    backoff, provenance construction, and a uniform ``query`` contract.
    """

    TRANSIENT_STATUS_CODES: tuple[int, ...] = (429, 502, 503, 504)

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

    # ── HTTP helpers with retry / backoff ─────────────────────────

    def _safe_json(self, response: httpx.Response | None) -> Any | None:
        """Safely parse JSON response body with informative error logging on failure."""
        if response is None:
            return None
        try:
            return response.json()
        except (json.JSONDecodeError, httpx.DecodingError, ValueError) as exc:
            logger.warning(
                "%s: Failed to decode JSON from %s (status %s): %s",
                self.source_name,
                getattr(response, "url", "unknown"),
                getattr(response, "status_code", "unknown"),
                exc,
            )
            return None

    async def _get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Perform a GET request with retry and exponential backoff for transient errors."""
        max_retries = max(0, self.settings.http_retries)
        backoff = max(0.1, self.settings.retry_backoff_factor)

        for attempt in range(max_retries + 1):
            try:
                resp = await self._http.get(url, params=params, headers=headers)
                if resp.status_code in self.TRANSIENT_STATUS_CODES and attempt < max_retries:
                    delay = backoff * (2**attempt)
                    logger.warning(
                        "%s: HTTP %s from %s — retrying in %.2fs (attempt %d/%d)",
                        self.source_name,
                        resp.status_code,
                        url,
                        delay,
                        attempt + 1,
                        max_retries,
                    )
                    await anyio.sleep(delay)
                    continue

                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as exc:
                is_transient = exc.response.status_code in self.TRANSIENT_STATUS_CODES
                if is_transient and attempt < max_retries:
                    delay = backoff * (2**attempt)
                    await anyio.sleep(delay)
                    continue
                logger.warning(
                    "%s: HTTP %s from %s",
                    self.source_name,
                    exc.response.status_code,
                    url,
                )
                raise
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                if attempt < max_retries:
                    delay = backoff * (2**attempt)
                    logger.warning(
                        "%s: Network error (%s) for %s — retrying in %.2fs",
                        self.source_name,
                        exc,
                        url,
                        delay,
                    )
                    await anyio.sleep(delay)
                    continue
                logger.warning("%s: HTTP transport error for %s — %s", self.source_name, url, exc)
                raise

        raise httpx.HTTPError(f"{self.source_name}: Max retries exceeded for {url}")

    async def _post(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        content: bytes | str | None = None,
        json_data: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Perform a POST request with retry and error handling."""
        max_retries = max(0, self.settings.http_retries)
        backoff = max(0.1, self.settings.retry_backoff_factor)

        for attempt in range(max_retries + 1):
            try:
                resp = await self._http.post(
                    url, data=data, content=content, json=json_data, headers=headers
                )
                if resp.status_code in self.TRANSIENT_STATUS_CODES and attempt < max_retries:
                    delay = backoff * (2**attempt)
                    await anyio.sleep(delay)
                    continue

                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as exc:
                is_transient = exc.response.status_code in self.TRANSIENT_STATUS_CODES
                if is_transient and attempt < max_retries:
                    delay = backoff * (2**attempt)
                    await anyio.sleep(delay)
                    continue
                logger.warning(
                    "%s: HTTP %s from %s",
                    self.source_name,
                    exc.response.status_code,
                    url,
                )
                raise
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                if attempt < max_retries:
                    delay = backoff * (2**attempt)
                    await anyio.sleep(delay)
                    continue
                logger.warning("%s: HTTP transport error for %s — %s", self.source_name, url, exc)
                raise

        raise httpx.HTTPError(f"{self.source_name}: Max retries exceeded for {url}")

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
        effect: EvidenceEffect | None = None,
        consequence: str | None = None,
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
            effect=effect,
            consequence=consequence,
            source_score=source_score,
            provenance=self._make_provenance(
                endpoint=endpoint,
                source_id=source_id,
                query_context=query_context,
            ),
            metadata=metadata or {},
        )
