"""SQLite connection helper and persistent cache for Relict Core."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────────────────────
# Run Persistence Layer Helpers
# ───────────────────────────────────────────────────────────────────────────


def open_connection(path: Path) -> sqlite3.Connection:
    """Open a ``sqlite3.Connection`` to *path*, creating parent directories if needed.

    Returns the connection with WAL journal mode and foreign-key
    enforcement enabled.
    """
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the run-store tables if they do not already exist."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS run_states (
            run_id     TEXT PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS run_results (
            run_id      TEXT PRIMARY KEY,
            result_json TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );
        """
    )
    conn.commit()


def _utcnow_iso() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(tz=UTC).isoformat()


# ───────────────────────────────────────────────────────────────────────────
# Knowledge Retrieval SQLite Cache
# ───────────────────────────────────────────────────────────────────────────


def make_cache_key(source: str, endpoint: str, params: dict[str, Any] | None = None) -> str:
    """Generate a deterministic SHA-256 cache key from source, endpoint, and sorted parameters."""
    normalized_params: list[tuple[str, str]] = []
    if params:
        for k in sorted(params.keys()):
            val = params[k]
            if isinstance(val, (dict, list)):
                val_str = json.dumps(val, sort_keys=True)
            else:
                val_str = str(val)
            normalized_params.append((str(k), val_str))

    payload = f"{source}:{endpoint}:{json.dumps(normalized_params, sort_keys=True)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SQLiteCache:
    """Persistent SQLite-backed cache implementing CacheProtocol."""

    def __init__(self, db_path: str | Path, default_ttl: int = 86400) -> None:
        self.db_path = Path(db_path)
        self.default_ttl = default_ttl
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path), timeout=10.0)

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS response_cache (
                    cache_key TEXT PRIMARY KEY,
                    value BLOB NOT NULL,
                    source TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expires_at ON response_cache(expires_at)")
            conn.commit()

    async def get(self, key: str) -> bytes | None:
        """Retrieve cached value if present and not expired."""
        now = time.time()
        try:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT value FROM response_cache WHERE cache_key = ? AND expires_at > ?",
                    (key, now),
                )
                row = cur.fetchone()
                if row:
                    return bytes(row[0])
                return None
        except Exception as exc:
            logger.warning("SQLiteCache: get error for key %s: %s", key, exc)
            return None

    async def set(
        self,
        key: str,
        value: bytes,
        ttl: int | None = None,
        source: str = "",
    ) -> None:
        """Store value with expiration timestamp."""
        now = time.time()
        effective_ttl = ttl if ttl is not None else self.default_ttl
        expires_at = now + effective_ttl

        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO response_cache (cache_key, value, source, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        value=excluded.value,
                        source=excluded.source,
                        created_at=excluded.created_at,
                        expires_at=excluded.expires_at
                    """,
                    (key, value, source, now, expires_at),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("SQLiteCache: set error for key %s: %s", key, exc)

    async def purge_expired(self) -> int:
        """Purge all expired entries from cache."""
        now = time.time()
        try:
            with self._get_connection() as conn:
                cur = conn.execute("DELETE FROM response_cache WHERE expires_at <= ?", (now,))
                deleted = cur.rowcount
                conn.commit()
                return deleted
        except Exception as exc:
            logger.warning("SQLiteCache: purge error: %s", exc)
            return 0
