"""Tests for cache integration behavior."""

from __future__ import annotations

import pytest

from app.knowledge_retrieval.base_client import NullCache
from tests.knowledge_retrieval.conftest import MockCache


@pytest.mark.asyncio
async def test_null_cache_operations() -> None:
    cache = NullCache()
    assert await cache.get("key") is None
    await cache.set("key", b"value")
    assert await cache.get("key") is None


@pytest.mark.asyncio
async def test_mock_cache_hit_and_miss(mock_cache: MockCache) -> None:
    # Miss
    assert await mock_cache.get("test_key") is None

    # Set
    await mock_cache.set("test_key", b'{"data": "cached"}')

    # Hit
    cached = await mock_cache.get("test_key")
    assert cached == b'{"data": "cached"}'
