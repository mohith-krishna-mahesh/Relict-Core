"""Application-wide configuration for Relict Core."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RetrievalSettings(BaseSettings):
    """Configuration for the Knowledge Retrieval subsystem.

    Values are read from environment variables (prefixed ``RELICT_``).
    Provide sensible defaults for non-sensitive settings only.
    """

    model_config = SettingsConfigDict(
        env_prefix="RELICT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── HTTP defaults & resilience ───────────────────────────────
    http_timeout: float = 30.0
    user_agent: str = "RelictCore/0.1.0 (https://github.com/relict-core)"
    max_concurrency: int = 8
    http_retries: int = 3
    retry_backoff_factor: float = 0.5

    # ── Cache & TTL ───────────────────────────────────────────────
    cache_db_path: str = "data/cache.sqlite3"
    default_cache_ttl_seconds: int = 86400

    # ── Species Knowledge Base ────────────────────────────────────
    species_csv_path: str = "data/species/species.csv"

    # ── DuckDB (for local bulk data such as AlphaMissense) ────────
    duckdb_path: str = "data/alphamissense.duckdb"

    # ── NCBI & BLAST ──────────────────────────────────────────────
    ncbi_api_key: str | None = None
    ncbi_email: str | None = None
    blast_max_wait_seconds: float = 30.0

    # ── BRENDA ────────────────────────────────────────────────────
    brenda_email: str | None = None
    brenda_password: str | None = None

    # ── STRING ────────────────────────────────────────────────────
    string_caller_identity: str = "relict-core"

    # ── Minimum evidence threshold ────────────────────────────────
    min_evidence_records: int = 1


class Settings(BaseSettings):
    """
    Relict Core application settings.

    All values are environment-driven via the ``RELICT_`` prefix.
    A ``.env`` file at the project root is loaded automatically.
    Defaults are suitable for local development; production deployments
    must override them via environment variables.

    Environment variable mapping (case-insensitive):
        RELICT_API_HOST                     → api_host
        RELICT_API_PORT                     → api_port
        RELICT_DEBUG                        → debug
        RELICT_DATABASE_PATH                → database_path
        RELICT_MAX_CONCURRENT_RUNS          → max_concurrent_runs
        RELICT_RUN_TIMEOUT_SECONDS          → run_timeout_seconds
        RELICT_MODEL_CLIENT_URL             → model_client_url
        RELICT_MODEL_CLIENT_TIMEOUT_SECONDS → model_client_timeout_seconds
        RELICT_API_TOKENS                   → api_tokens (JSON list or space-separated)
        RELICT_AUTH_ENABLED                 → auth_enabled (default False)
        RELICT_INSTANCE_TYPE                → instance_type
    """

    model_config = SettingsConfigDict(
        env_prefix="RELICT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # API server
    # ------------------------------------------------------------------
    api_host: str = Field(
        default="0.0.0.0",
        description="Host address for the FastAPI server.",
    )
    api_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port for the FastAPI server.",
    )
    debug: bool = Field(
        default=False,
        description="Enable FastAPI debug / reload mode.  Never True in production.",
    )

    # ------------------------------------------------------------------
    # Persistence — Run Repository
    # ------------------------------------------------------------------
    database_path: Path = Field(
        default=Path("data/relict.db"),
        description=(
            "Filesystem path to the SQLite database used by the Run Repository "
            "to persist run state and artifacts."
        ),
    )

    # ------------------------------------------------------------------
    # Run Manager
    # ------------------------------------------------------------------
    max_concurrent_runs: int = Field(
        default=1,
        ge=1,
        description="Maximum number of pipeline runs that may execute concurrently.",
    )
    run_timeout_seconds: int = Field(
        default=3600,
        ge=1,
        description=(
            "Maximum wall-clock seconds allowed per run before the Run Manager marks it as FAILED."
        ),
    )

    # ------------------------------------------------------------------
    # Model client — placeholder (Core Model member will extend this)
    # ------------------------------------------------------------------
    model_client_url: str = Field(
        default="http://localhost:11434",
        description=(
            "Base URL of the model-serving backend "
            "(vLLM, Ollama, or llama.cpp-compatible endpoint)."
        ),
    )
    model_client_timeout_seconds: int = Field(
        default=120,
        ge=1,
        description="HTTP timeout in seconds for requests sent to the model client.",
    )

    # ------------------------------------------------------------------
    # Auth — bearer token validation
    # ------------------------------------------------------------------
    api_tokens: list[str] = Field(
        default_factory=list,
        description=(
            "List of valid bearer tokens accepted by the API. "
            "Set via RELICT_API_TOKENS as a JSON array or space-separated string. "
            "Empty list means no tokens are configured (all requests rejected when "
            "auth_enabled=True)."
        ),
    )
    auth_enabled: bool = Field(
        default=False,
        description=(
            "Enable bearer-token authentication on all /v1 endpoints. "
            "Defaults to False for local development and test environments. "
            "Must be True in production deployments."
        ),
    )

    # ------------------------------------------------------------------
    # Instance metadata
    # ------------------------------------------------------------------
    instance_type: str = Field(
        default="relict-core-standard",
        description=(
            "Human-readable deployment type label returned in POST /v1/auth/verify. "
            "Override via RELICT_INSTANCE_TYPE in production."
        ),
    )


settings = Settings()
