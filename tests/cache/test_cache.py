"""Tests for SQLiteCache and cache key determinism."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cache.sqlite_client import SQLiteCache, make_cache_key


class TestSQLiteCache:
    def test_cache_key_determinism(self) -> None:
        key1 = make_cache_key("ensembl", "/lookup/symbol", {"species": "human", "symbol": "BRCA1"})
        key2 = make_cache_key("ensembl", "/lookup/symbol", {"symbol": "BRCA1", "species": "human"})
        assert key1 == key2

    def test_cache_key_different_params(self) -> None:
        key1 = make_cache_key("ensembl", "/lookup/symbol", {"species": "human", "symbol": "BRCA1"})
        key2 = make_cache_key("ensembl", "/lookup/symbol", {"species": "mouse", "symbol": "BRCA1"})
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, tmp_path: Path) -> None:
        db_file = tmp_path / "test_cache.sqlite3"
        cache = SQLiteCache(db_file, default_ttl=3600)

        key = "test_key_123"
        val = b"hello cached world"

        await cache.set(key, val, ttl=3600, source="test_src")
        retrieved = await cache.get(key)
        assert retrieved == val

    @pytest.mark.asyncio
    async def test_cache_expiration(self, tmp_path: Path) -> None:
        db_file = tmp_path / "test_cache.sqlite3"
        cache = SQLiteCache(db_file, default_ttl=1)

        key = "expiring_key"
        val = b"short lived value"

        # Set with -1 TTL (already expired)
        await cache.set(key, val, ttl=-10, source="test_src")
        retrieved = await cache.get(key)
        assert retrieved is None

        # Purge
        deleted = await cache.purge_expired()
        assert deleted >= 1
