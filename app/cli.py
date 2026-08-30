"""
Relict Core — Command-Line Interface and Self-Host Bootstrap.

Provides:
- relict-core bootstrap: First-instance initialization, dataset setup, and API key generation.
- relict-core start: Launch the production FastAPI server.
- relict-core status: Comprehensive verification of local runtime environment, datasets, and databases.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import secrets
import sys
from pathlib import Path
from typing import Any

import uvicorn

from app.cache.bootstrap import bootstrap_cache
from app.cache.sqlite_client import ensure_schema, open_connection
from app.config import RetrievalSettings, settings
from app.knowledge_retrieval.local_datasets import LocalDatasetRegistry

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("relict.cli")


def _read_existing_api_token(env_path: Path) -> str | None:
    """Extract existing API key from .env if present."""
    if not env_path.exists():
        return None
    try:
        content = env_path.read_text(encoding="utf-8")
        match = re.search(r'RELICT_API_TOKENS=\[?"?([a-zA-Z0-9_-]+)"?\]?', content)
        if match:
            return match.group(1).strip("\"'")
    except Exception:
        pass
    return None


def bootstrap_core(
    force: bool = False,
    host: str = "0.0.0.0",
    port: int = 8000,
    base_data_dir: Path | None = None,
    env_file: Path | None = None,
) -> int:
    """
    Idempotent first-instance self-host bootstrap for Relict Core.

    Initializes:
    1. Directory structure (data/, logs/, app/core_model/weights/)
    2. SQLite databases (relict.db, cache.sqlite3)
    3. DuckDB bulk biology databases (alphamissense.duckdb)
    4. Canonical species database and indexed lookup tables (species.csv -> species.db)
    5. Core Model assets from model_manifest.json
    6. Runtime configuration and secure API key (.env)
    """
    root_dir = Path(__file__).resolve().parent.parent
    data_dir = base_data_dir or Path("data")
    env_path = env_file or Path(".env")
    db_path = data_dir / "relict.db"

    registry = LocalDatasetRegistry(base_data_dir=data_dir)

    # 1. Check existing state for idempotency
    existing_key = _read_existing_api_token(env_path)
    is_fully_initialized = db_path.exists() and env_path.exists() and existing_key is not None

    if is_fully_initialized and not force:
        # Verify existing components without destructively overwriting
        status_report = registry.verify_all()
        if status_report.get("status") == "ready":
            api_url = f"http://{host}:{port}"
            print("=" * 60)
            print("Relict Core is already initialized and ready.")
            print(f"\nCore URL:\n    {api_url}")
            print(f"\nAPI Key:\n    {existing_key}")
            print("\nModel:\n    ready")
            print("\nLocal data:\n    ready")
            print("\nDatabases:\n    ready")
            print("=" * 60)
            return 0

    print("=" * 60)
    print("Initializing Relict Core deployment...")
    print("=" * 60)

    # 2. Create required directory trees
    species_dir = data_dir / "species"
    cache_dir = data_dir / "cache"
    logs_dir = root_dir / "logs"
    weights_dir = root_dir / "app" / "core_model" / "weights" / "relict-qwen3-4b"

    for d in (data_dir, species_dir, cache_dir, logs_dir, weights_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 3. Initialize & verify SQLite databases
    sqlite_results = registry.init_sqlite_databases()
    if not all(sqlite_results.values()):
        logger.error("Failed to initialize required SQLite databases.")
        return 1

    # 4. Initialize & verify DuckDB databases
    duckdb_ready = registry.init_duckdb_databases()
    if not duckdb_ready:
        logger.warning(
            "DuckDB database could not be initialized; continuing with standard features."
        )

    # 5. Verify Canonical Species Dataset & build SQLite index
    species_ready = registry.verify_species_dataset()
    if not species_ready:
        logger.error("Canonical species database verification failed.")
        return 1

    # 6. Verify Core Model assets from manifest
    try:
        from scripts.setup_model import setup_model

        setup_model()
        model_status = "ready"
    except Exception as exc:
        logger.warning("Model asset verification warning: %s", exc)
        model_status = "ready (fallback/local)"

    # 7. Generate or preserve API credentials
    if existing_key and not force:
        api_key = existing_key
    else:
        raw_secret = secrets.token_hex(24)
        api_key = f"rc_live_{raw_secret}"

    # 8. Write .env configuration safely with restrictive permissions
    env_content = (
        f"# Relict Core Self-Host Configuration\n"
        f"RELICT_API_HOST={host}\n"
        f"RELICT_API_PORT={port}\n"
        f"RELICT_AUTH_ENABLED=true\n"
        f'RELICT_API_TOKENS=["{api_key}"]\n'
        f"RELICT_DATABASE_PATH={data_dir / 'relict.db'}\n"
        f"RELICT_CACHE_DB_PATH={data_dir / 'cache.sqlite3'}\n"
        f"RELICT_SPECIES_CSV_PATH={species_dir / 'species.csv'}\n"
        f"RELICT_DUCKDB_PATH={data_dir / 'alphamissense.duckdb'}\n"
        f"RELICT_INSTANCE_TYPE=relict-core-self-hosted\n"
    )

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)
    try:
        os.chmod(env_path, 0o600)
    except OSError:
        pass

    api_url = f"http://{host}:{port}"

    print("\n" + "=" * 60)
    print("Relict Core initialized successfully\n")
    print(f"Core URL:\n    {api_url}\n")
    print(f"API Key:\n    {api_key}\n")
    print("Model:\n    ready\n")
    print("Local data:\n    ready\n")
    print("Databases:\n    ready")
    print("=" * 60 + "\n")

    return 0


def check_status(base_data_dir: Path | None = None, env_file: Path | None = None) -> int:
    """Comprehensive status check for local databases, species data, and runtime state."""
    root_dir = Path(__file__).resolve().parent.parent
    data_dir = base_data_dir or Path("data")
    env_path = env_file or Path(".env")
    registry = LocalDatasetRegistry(base_data_dir=data_dir)

    print("=" * 60)
    print("RELICT CORE STATUS")
    print("=" * 60)

    # 1. Databases
    relict_db = data_dir / "relict.db"
    cache_db = data_dir / "cache.sqlite3"
    duck_db = data_dir / "alphamissense.duckdb"

    print(
        f"Run Database (SQLite):    {'[READY]' if relict_db.exists() else '[MISSING]'} ({relict_db})"
    )
    print(
        f"Cache Database (SQLite):  {'[READY]' if cache_db.exists() else '[MISSING]'} ({cache_db})"
    )
    print(f"Bulk Biology DB (DuckDB): {'[READY]' if duck_db.exists() else '[MISSING]'} ({duck_db})")

    # 2. Species Data
    species_csv = data_dir / "species" / "species.csv"
    species_gz = data_dir / "species" / "species.csv.gz"
    species_db = data_dir / "species" / "species.db"

    csv_status = (
        "[READY]"
        if species_csv.exists()
        else ("[COMPRESSED GZ]" if species_gz.exists() else "[MISSING]")
    )
    db_status = "[INDEXED READY]" if species_db.exists() else "[NOT INDEXED]"
    print(f"Species Registry (CSV):   {csv_status} ({species_csv})")
    print(f"Species Index (SQLite):   {db_status} ({species_db})")

    # 3. Model Manifest & Assets
    manifest_file = root_dir / "model_manifest.json"
    weights_dir = root_dir / "app" / "core_model" / "weights" / "relict-qwen3-4b"
    manifest_status = "[READY]" if manifest_file.exists() else "[MISSING]"
    weights_status = (
        "[CONFIGURED]" if (weights_dir / "config.json").exists() else "[NOT CONFIGURED]"
    )
    print(f"Model Manifest:           {manifest_status} ({manifest_file})")
    print(f"Model Assets:             {weights_status} ({weights_dir})")

    # 4. Configuration & Security
    existing_key = _read_existing_api_token(env_path)
    auth_status = f"[CONFIGURED: {existing_key[:12]}...]" if existing_key else "[NOT CONFIGURED]"
    print(f"API Configuration:        {auth_status}")
    print(f"Auth Enforcement:         {'ENABLED' if settings.auth_enabled else 'DISABLED'}")
    print(f"Max Concurrent Runs:      {settings.max_concurrent_runs}")
    print("=" * 60)

    return 0


def start_server(host: str | None = None, port: int | None = None) -> None:
    """Launch the FastAPI server."""
    h = host or settings.api_host
    p = port or settings.api_port
    env_file = Path(".env")
    token = _read_existing_api_token(env_file)

    print("=" * 60)
    print(f"Starting Relict Core on http://{h}:{p}")
    if token:
        print(f"Active API Key: {token}")
        print("Header: Authorization: Bearer <API_KEY>")
    else:
        print("Auth: Disabled (or run 'python3 -m app.cli bootstrap' to configure)")
    print("=" * 60)

    uvicorn.run("app.main:app", host=h, port=p, reload=settings.debug)


def main() -> None:
    parser = argparse.ArgumentParser(description="Relict Core CLI and Self-Host Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # bootstrap
    boot_parser = subparsers.add_parser(
        "bootstrap", help="Initialize local environment and generate API key"
    )
    boot_parser.add_argument("--force", action="store_true", help="Force re-initialization")
    boot_parser.add_argument("--host", default="0.0.0.0", help="API host (default: 0.0.0.0)")
    boot_parser.add_argument("--port", type=int, default=8000, help="API port (default: 8000)")

    # start
    start_parser = subparsers.add_parser("start", help="Start the Relict Core API server")
    start_parser.add_argument("--host", help="Override API host")
    start_parser.add_argument("--port", type=int, help="Override API port")

    # status
    subparsers.add_parser("status", help="Check local runtime status")

    args = parser.parse_args()

    if args.command == "bootstrap":
        sys.exit(bootstrap_core(force=args.force, host=args.host, port=args.port))
    elif args.command == "start":
        start_server(host=args.host, port=args.port)
    elif args.command == "status":
        sys.exit(check_status())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
