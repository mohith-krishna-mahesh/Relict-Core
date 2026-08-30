"""Cache bootstrap and initialization helpers."""

from __future__ import annotations

import logging
from pathlib import Path

from app.cache.sqlite_client import SQLiteCache
from app.config import RetrievalSettings

logger = logging.getLogger(__name__)


def bootstrap_cache(settings: RetrievalSettings | None = None) -> SQLiteCache:
    """Initialize cache directory and return a configured SQLiteCache instance."""
    cfg = settings or RetrievalSettings()
    cache_path = Path(cfg.cache_db_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Initializing SQLite cache at %s (default TTL: %ds)",
        cache_path,
        cfg.default_cache_ttl_seconds,
    )
    return SQLiteCache(db_path=cache_path, default_ttl=cfg.default_cache_ttl_seconds)
