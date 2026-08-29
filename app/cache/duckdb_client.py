"""DuckDB client utilities for local bulk dataset querying."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Generator
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def get_duckdb_reader(db_path: str | Path) -> Generator[Any, None, None]:
    """Provide a safe, read-only DuckDB connection context that always closes cleanly."""
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"DuckDB database not found at {path}")

    import duckdb

    conn = duckdb.connect(str(path), read_only=True, config={"access_mode": "read_only"})
    try:
        yield conn
    finally:
        conn.close()
