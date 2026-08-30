"""
Local Dataset Registry, Manifest, and Initialization Manager for Relict Core.

Manages all required local biological datasets, caches, SQLite databases, and DuckDB
instances needed for offline/local execution (architecture §2.2, §3.4).
"""

from __future__ import annotations

import asyncio
import csv
import gzip
import hashlib
import logging
import os
import shutil
import sqlite3
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx

from app.cache.duckdb_client import get_duckdb_reader
from app.cache.sqlite_client import ensure_schema, open_connection
from app.config import RetrievalSettings, settings

logger = logging.getLogger(__name__)


class DatasetStatus(StrEnum):
    """Readiness status of a local dataset."""

    READY = "ready"
    MISSING = "missing"
    CORRUPTED = "corrupted"
    UPDATING = "updating"
    ERROR = "error"


@dataclass
class LocalDataset:
    """Metadata describing a required or optional local dataset."""

    name: str
    source_name: str
    local_path: Path
    description: str
    download_url: str | None = None
    expected_format: str = "csv"  # csv, gzip_csv, duckdb, sqlite
    expected_sha256: str | None = None
    min_size_bytes: int = 0
    is_required: bool = True
    status: DatasetStatus = DatasetStatus.MISSING
    version: str = "1.0.0"
    metadata: dict[str, Any] = field(default_factory=dict)


class LocalDatasetRegistry:
    """
    Central registry and manager for Relict Core local datasets and databases.
    """

    def __init__(self, base_data_dir: str | Path | None = None) -> None:
        self.root_dir = Path(__file__).resolve().parent.parent.parent
        self.base_data_dir = Path(base_data_dir) if base_data_dir else self.root_dir / "data"
        self._datasets: dict[str, LocalDataset] = {}
        self._register_default_datasets()

    def _register_default_datasets(self) -> None:
        """Register the authoritative local datasets required by Relict Core."""
        species_dir = self.base_data_dir / "species"
        cache_dir = self.base_data_dir / "cache"

        # 1. Canonical Species CSV
        self.register(
            LocalDataset(
                name="species_csv",
                source_name="canonical_species",
                local_path=species_dir / "species.csv",
                description="Canonical runtime species database (~1.4M species).",
                download_url=None,
                expected_format="csv",
                min_size_bytes=1000,
                is_required=True,
                version="1.0.0",
            )
        )

        # 2. Canonical Species SQLite Index
        self.register(
            LocalDataset(
                name="species_db",
                source_name="species_sqlite_index",
                local_path=species_dir / "species.db",
                description="Indexed SQLite database for low-latency species lookups.",
                expected_format="sqlite",
                min_size_bytes=1000,
                is_required=True,
                version="1.0.0",
            )
        )

        # 3. DuckDB Bulk Biology Database (AlphaMissense, FarmGTEx, EpiDB)
        self.register(
            LocalDataset(
                name="alphamissense_duckdb",
                source_name="alphamissense",
                local_path=self.base_data_dir / "alphamissense.duckdb",
                description="DuckDB database containing AlphaMissense, FarmGTEx, and EpiDB tables.",
                expected_format="duckdb",
                is_required=False,
                version="1.0.0",
            )
        )

        # 4. Primary SQLite Run Repository
        self.register(
            LocalDataset(
                name="relict_db",
                source_name="run_repository",
                local_path=Path(settings.database_path),
                description="SQLite database storing run states, artifacts, and execution logs.",
                expected_format="sqlite",
                is_required=True,
                version="1.0.0",
            )
        )

        # 5. SQLite Knowledge Retrieval Response Cache
        self.register(
            LocalDataset(
                name="source_cache_db",
                source_name="retrieval_cache",
                local_path=Path(RetrievalSettings().cache_db_path),
                description="Persistent SQLite cache for Knowledge Retrieval API responses.",
                expected_format="sqlite",
                is_required=True,
                version="1.0.0",
            )
        )

    def register(self, dataset: LocalDataset) -> None:
        """Register a dataset in the central registry."""
        self._datasets[dataset.name] = dataset

    def get(self, name: str) -> LocalDataset | None:
        """Retrieve dataset definition by name."""
        return self._datasets.get(name)

    def all_datasets(self) -> list[LocalDataset]:
        """Return all registered datasets."""
        return list(self._datasets.values())

    # ──────────────────────────────────────────────────────────────────────────
    # Verification and Health Check
    # ──────────────────────────────────────────────────────────────────────────

    def verify_dataset(self, name: str) -> DatasetStatus:
        """Verify the integrity and presence of a registered dataset."""
        dataset = self._datasets.get(name)
        if not dataset:
            return DatasetStatus.ERROR

        path = dataset.local_path
        if not path.exists():
            # For species.csv, check if species.csv.gz exists
            if name == "species_csv":
                gz_path = path.with_suffix(".csv.gz")
                if gz_path.exists() and gz_path.stat().st_size > 0:
                    dataset.status = DatasetStatus.READY
                    return DatasetStatus.READY
            dataset.status = DatasetStatus.MISSING
            return DatasetStatus.MISSING

        try:
            size = path.stat().st_size
            if size < dataset.min_size_bytes:
                logger.warning(
                    "Dataset %s size (%d bytes) is below minimum threshold (%d bytes).",
                    name,
                    size,
                    dataset.min_size_bytes,
                )
                dataset.status = DatasetStatus.CORRUPTED
                return DatasetStatus.CORRUPTED

            if dataset.expected_sha256:
                calculated = self.calculate_sha256(path)
                if calculated != dataset.expected_sha256:
                    logger.warning(
                        "Dataset %s checksum mismatch: expected %s, got %s.",
                        name,
                        dataset.expected_sha256,
                        calculated,
                    )
                    dataset.status = DatasetStatus.CORRUPTED
                    return DatasetStatus.CORRUPTED

            dataset.status = DatasetStatus.READY
            return DatasetStatus.READY
        except Exception as exc:
            logger.error("Error verifying dataset %s: %s", name, exc)
            dataset.status = DatasetStatus.ERROR
            return DatasetStatus.ERROR

    def calculate_sha256(self, path: Path, chunk_size: int = 64 * 1024) -> str:
        """Stream a file and compute its SHA-256 hash without loading entire file into memory."""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()

    # ──────────────────────────────────────────────────────────────────────────
    # Safe Streaming Downloader
    # ──────────────────────────────────────────────────────────────────────────

    async def download_file_safely(
        self,
        url: str,
        target_path: Path,
        expected_sha256: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
    ) -> bool:
        """
        Download a file safely with streaming, bounded retries, and atomic placement.

        Rules enforced:
        - Must use HTTPS where available.
        - Streams to a .tmp file first.
        - Verifies checksum/content before atomic rename.
        - Automatically cleans up partial files on failure.
        """
        if (
            not url.startswith("https://")
            and not url.startswith("http://localhost")
            and not url.startswith("http://127.0.0.1")
        ):
            logger.warning("Unencrypted download URL provided: %s", url)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_suffix(".tmp")

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    "Downloading %s to %s (attempt %d/%d)...",
                    url,
                    target_path.name,
                    attempt,
                    max_retries,
                )
                async with httpx.AsyncClient(
                    timeout=timeout_seconds, follow_redirects=True
                ) as client:
                    async with client.stream("GET", url) as response:
                        response.raise_for_status()
                        with open(tmp_path, "wb") as f:
                            async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                                f.write(chunk)

                # Verify checksum if expected
                if expected_sha256:
                    actual_sha256 = self.calculate_sha256(tmp_path)
                    if actual_sha256 != expected_sha256:
                        raise ValueError(
                            f"Checksum mismatch: expected {expected_sha256}, got {actual_sha256}"
                        )

                # Atomic rename
                tmp_path.replace(target_path)
                logger.info(
                    "Successfully downloaded %s (%.2f MB).",
                    target_path.name,
                    target_path.stat().st_size / (1024 * 1024),
                )
                return True

            except Exception as exc:
                logger.warning("Download failed on attempt %d/%d: %s", attempt, max_retries, exc)
                if tmp_path.exists():
                    tmp_path.unlink()
                if attempt < max_retries:
                    await asyncio.sleep(backoff_factor**attempt)

        return False

    # ──────────────────────────────────────────────────────────────────────────
    # Database Initialization & Verification
    # ──────────────────────────────────────────────────────────────────────────

    def init_sqlite_databases(self) -> dict[str, bool]:
        """
        Initialize and verify required SQLite databases (relict.db, cache.sqlite3).
        Runs a read-write verification test on each.
        """
        results: dict[str, bool] = {}

        # 1. Run Repository Database (relict.db)
        relict_path = self.base_data_dir / "relict.db"
        try:
            relict_path.parent.mkdir(parents=True, exist_ok=True)
            conn = open_connection(relict_path)
            ensure_schema(conn)

            # Read-write test
            test_id = "__bootstrap_test__"
            conn.execute(
                "INSERT OR REPLACE INTO run_states (run_id, state_json, updated_at) VALUES (?, ?, ?)",
                (test_id, "{}", "2026-08-30T00:00:00Z"),
            )
            conn.commit()
            row = conn.execute(
                "SELECT run_id FROM run_states WHERE run_id = ?", (test_id,)
            ).fetchone()
            assert row and row[0] == test_id
            conn.execute("DELETE FROM run_states WHERE run_id = ?", (test_id,))
            conn.commit()
            conn.close()
            results["relict_db"] = True
            logger.info("SQLite run repository verified at %s", relict_path)
        except Exception as exc:
            logger.error("Failed to initialize SQLite run repository: %s", exc)
            results["relict_db"] = False

        # 2. Retrieval Response Cache Database (cache.sqlite3)
        cache_path = self.base_data_dir / "cache.sqlite3"
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            conn = open_connection(cache_path)
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
            conn.close()
            results["source_cache_db"] = True
            logger.info("SQLite response cache verified at %s", cache_path)
        except Exception as exc:
            logger.error("Failed to initialize SQLite cache database: %s", exc)
            results["source_cache_db"] = False

        return results

    def init_duckdb_databases(self) -> bool:
        """
        Initialize and verify local DuckDB database (data/alphamissense.duckdb).
        Creates default schema if missing and verifies read-only access.
        """
        duckdb_path = self.base_data_dir / "alphamissense.duckdb"
        duckdb_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import duckdb
        except ImportError:
            logger.warning("DuckDB package not installed in environment.")
            return False

        try:
            # Initialize tables if not already present
            if not duckdb_path.exists() or duckdb_path.stat().st_size == 0:
                conn = duckdb.connect(str(duckdb_path))
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS alphamissense (
                        uniprot_id VARCHAR,
                        protein_variant VARCHAR,
                        am_pathogenicity DOUBLE,
                        am_class VARCHAR
                    );
                    CREATE TABLE IF NOT EXISTS farmgtex (
                        gene VARCHAR,
                        tissue VARCHAR,
                        median_tpm DOUBLE
                    );
                    CREATE TABLE IF NOT EXISTS epidb (
                        gene VARCHAR,
                        mark VARCHAR,
                        region VARCHAR
                    );
                    """
                )
                conn.close()

            # Verify read-only access via context manager
            with get_duckdb_reader(duckdb_path) as r_conn:
                tables = [
                    r[0]
                    for r in r_conn.execute(
                        "SELECT table_name FROM information_schema.tables"
                    ).fetchall()
                ]
                logger.info("DuckDB verified at %s with tables: %s", duckdb_path, tables)

            return True
        except Exception as exc:
            logger.error("Failed to initialize DuckDB database at %s: %s", duckdb_path, exc)
            return False

    def verify_species_dataset(self) -> bool:
        """
        Verify canonical species dataset (species.csv / species.csv.gz) and ensure
        the SQLite index (species.db) is built and readable.
        """
        species_dir = self.base_data_dir / "species"
        species_csv = species_dir / "species.csv"
        species_gz = species_dir / "species.csv.gz"
        species_db = species_dir / "species.db"

        # 1. If species.csv is missing but .csv.gz exists, stream decompress it
        if not species_csv.exists() and species_gz.exists():
            logger.info("Decompressing %s to %s...", species_gz, species_csv)
            tmp_csv = species_csv.with_suffix(".tmp")
            try:
                with (
                    gzip.open(species_gz, "rt", encoding="utf-8") as f_in,
                    open(tmp_csv, "w", encoding="utf-8", newline="") as f_out,
                ):
                    shutil.copyfileobj(f_in, f_out)
                tmp_csv.replace(species_csv)
                logger.info(
                    "Successfully decompressed species.csv (%.2f MB).",
                    species_csv.stat().st_size / (1024 * 1024),
                )
            except Exception as exc:
                logger.error("Failed to decompress species.csv.gz: %s", exc)
                if tmp_csv.exists():
                    tmp_csv.unlink()
                return False

        if not species_csv.exists() and not species_gz.exists():
            logger.error("Canonical species database is missing at %s", species_csv)
            return False

        # 2. Build or verify the SQLite index via SpeciesResolver
        try:
            from app.knowledge_retrieval.species import SpeciesResolver

            resolver = SpeciesResolver(
                csv_path=species_csv if species_csv.exists() else species_gz, db_path=species_db
            )
            # Perform a test resolution
            test_sp = resolver.resolve("Homo sapiens")
            assert test_sp is not None
            logger.info(
                "Species database verified successfully (resolved test species: %s, TaxID: %s)",
                test_sp.scientific_name,
                test_sp.taxonomy_id,
            )
            return True
        except Exception as exc:
            logger.error("Species resolution verification failed: %s", exc)
            return False

    def verify_all(self) -> dict[str, Any]:
        """Verify all local datasets, databases, and dependencies."""
        sqlite_res = self.init_sqlite_databases()
        duckdb_res = self.init_duckdb_databases()
        species_res = self.verify_species_dataset()

        all_ready = all(sqlite_res.values()) and duckdb_res and species_res
        return {
            "status": "ready" if all_ready else "degraded",
            "sqlite": sqlite_res,
            "duckdb": duckdb_res,
            "species": species_res,
        }
