"""Application-wide configuration for Relict Core (Member 5 scope)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Relict Core application settings.

    All values are environment-driven via the ``RELICT_`` prefix.
    A ``.env`` file at the project root is loaded automatically.
    Defaults are suitable for local development; production deployments
    must override them via environment variables.

    Only settings owned by Member 5 (API server, Run Manager, persistence,
    model client URL placeholder) are defined here.  Pipeline-stage
    configuration for Knowledge Retrieval, Planner, Validator, and Post-Plan
    Analysis will be added by their respective owners.

    Environment variable mapping (case-insensitive):
        RELICT_API_HOST                 → api_host
        RELICT_API_PORT                 → api_port
        RELICT_DEBUG                    → debug
        RELICT_DATABASE_PATH            → database_path
        RELICT_MAX_CONCURRENT_RUNS      → max_concurrent_runs
        RELICT_RUN_TIMEOUT_SECONDS      → run_timeout_seconds
        RELICT_MODEL_CLIENT_URL         → model_client_url
        RELICT_MODEL_CLIENT_TIMEOUT_SECONDS → model_client_timeout_seconds
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
            "Maximum wall-clock seconds allowed per run before the Run Manager "
            "marks it as FAILED."
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


settings = Settings()
