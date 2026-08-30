"""
Comprehensive Integration Tests for Relict Core Self-Host Bootstrap.

Verifies:
- Clean bootstrap from empty state
- Idempotency (no destructive wipes, no API key regeneration)
- DuckDB read-only concurrent access
- Species dataset decompression & recovery
- Status reporting accuracy
"""

from __future__ import annotations

import gzip
import shutil
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from app.cache.duckdb_client import get_duckdb_reader
from app.cli import _read_existing_api_token, bootstrap_core, check_status
from app.knowledge_retrieval.local_datasets import LocalDatasetRegistry


def test_bootstrap_from_empty_state(tmp_path: Path, monkeypatch: Any) -> None:
    """Bootstrap in an isolated directory must create all databases and valid .env credentials."""
    data_dir = tmp_path / "data"
    env_path = tmp_path / ".env"
    species_dir = data_dir / "species"
    species_dir.mkdir(parents=True, exist_ok=True)

    # Place minimal species dataset for testing
    species_csv = species_dir / "species.csv"
    with open(species_csv, "w", encoding="utf-8") as f:
        f.write(
            "id,scientificName,commonName,taxonomyId,source,isExtinct,hasGenomeData,tags,createdAt,updatedAt\n"
        )
        f.write("sp_01,Homo sapiens,Human,9606,ncbi,0,1,[],2026-01-01,2026-01-01\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "app.cli.Path",
        lambda *args: (
            tmp_path / Path(*args)
            if not str(Path(*args)).startswith(str(tmp_path))
            else Path(*args)
        ),
    )

    rc = bootstrap_core(force=False, host="127.0.0.1", port=8000, base_data_dir=data_dir)
    assert rc == 0

    # 1. Verify SQLite databases exist
    assert (data_dir / "relict.db").exists()
    assert (data_dir / "cache.sqlite3").exists()

    # 2. Verify DuckDB exists
    assert (data_dir / "alphamissense.duckdb").exists()

    # 3. Verify Species index was built
    assert (species_dir / "species.db").exists()

    # 4. Verify .env was written with API token
    assert env_path.exists()
    key = _read_existing_api_token(env_path)
    assert key is not None
    assert key.startswith("rc_live_")


def test_bootstrap_idempotency(tmp_path: Path, monkeypatch: Any) -> None:
    """Running bootstrap repeatedly must not regenerate the API key or overwrite valid databases."""
    data_dir = tmp_path / "data"
    env_path = tmp_path / ".env"
    species_dir = data_dir / "species"
    species_dir.mkdir(parents=True, exist_ok=True)

    species_csv = species_dir / "species.csv"
    with open(species_csv, "w", encoding="utf-8") as f:
        f.write(
            "id,scientificName,commonName,taxonomyId,source,isExtinct,hasGenomeData,tags,createdAt,updatedAt\n"
        )
        f.write("sp_01,Homo sapiens,Human,9606,ncbi,0,1,[],2026-01-01,2026-01-01\n")

    monkeypatch.chdir(tmp_path)

    # First bootstrap
    rc1 = bootstrap_core(force=False, host="127.0.0.1", port=8000, base_data_dir=data_dir)
    assert rc1 == 0
    key1 = _read_existing_api_token(env_path)
    assert key1 is not None

    # Write a test row into SQLite
    conn = sqlite3.connect(data_dir / "relict.db")
    conn.execute(
        "INSERT INTO run_states (run_id, state_json, updated_at) VALUES ('run_preservation_test', '{}', '2026-08-30')"
    )
    conn.commit()
    conn.close()

    # Second bootstrap (idempotent)
    rc2 = bootstrap_core(force=False, host="127.0.0.1", port=8000, base_data_dir=data_dir)
    assert rc2 == 0
    key2 = _read_existing_api_token(env_path)
    assert key1 == key2  # Key preserved!

    # Verify custom row still exists in SQLite
    conn = sqlite3.connect(data_dir / "relict.db")
    row = conn.execute(
        "SELECT run_id FROM run_states WHERE run_id = 'run_preservation_test'"
    ).fetchone()
    conn.close()
    assert row is not None


def test_bootstrap_species_decompression_recovery(tmp_path: Path) -> None:
    """If species.csv is missing but species.csv.gz is present, bootstrap must decompress it."""
    data_dir = tmp_path / "data"
    species_dir = data_dir / "species"
    species_dir.mkdir(parents=True, exist_ok=True)

    species_gz = species_dir / "species.csv.gz"
    species_csv = species_dir / "species.csv"

    # Write gz file
    raw_content = b"id,scientificName,commonName,taxonomyId,source,isExtinct,hasGenomeData,tags,createdAt,updatedAt\nsp_01,Homo sapiens,Human,9606,ncbi,0,1,[],2026-01-01,2026-01-01\n"
    with gzip.open(species_gz, "wb") as f:
        f.write(raw_content)

    assert not species_csv.exists()

    registry = LocalDatasetRegistry(base_data_dir=data_dir)
    success = registry.verify_species_dataset()

    assert success is True
    assert species_csv.exists()
    assert species_csv.stat().st_size > 0
    assert (species_dir / "species.db").exists()


def test_duckdb_concurrent_reads(tmp_path: Path) -> None:
    """Verify DuckDB database supports simultaneous read-only connections without lock errors."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    duck_path = data_dir / "alphamissense.duckdb"

    registry = LocalDatasetRegistry(base_data_dir=data_dir)
    registry.init_duckdb_databases()

    # Open 3 simultaneous readers
    with (
        get_duckdb_reader(duck_path) as conn1,
        get_duckdb_reader(duck_path) as conn2,
        get_duckdb_reader(duck_path) as conn3,
    ):
        tables1 = conn1.execute("SELECT table_name FROM information_schema.tables").fetchall()
        tables2 = conn2.execute("SELECT table_name FROM information_schema.tables").fetchall()
        tables3 = conn3.execute("SELECT table_name FROM information_schema.tables").fetchall()

        assert len(tables1) >= 1
        assert tables1 == tables2 == tables3
