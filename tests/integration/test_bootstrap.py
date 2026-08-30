"""
Self-Host Bootstrap & CLI Tests for Relict Core.

Verifies:
1. Fresh bootstrap creates directories, databases, and generates API credentials.
2. Idempotency prevents destructive overwrite of existing setup.
3. Authenticated request using generated API key succeeds against /v1/auth/verify.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.cli import bootstrap_core, check_status
from app.config import settings
from app.main import app


def test_bootstrap_flow(tmp_path: Any, monkeypatch: Any) -> None:
    """Test full bootstrap lifecycle in an isolated temporary directory."""
    data_dir = tmp_path / "data"
    species_dir = data_dir / "species"
    species_dir.mkdir(parents=True, exist_ok=True)
    species_csv = species_dir / "species.csv"
    with open(species_csv, "w", encoding="utf-8") as f:
        f.write(
            "id,scientificName,commonName,taxonomyId,source,isExtinct,hasGenomeData,tags,createdAt,updatedAt\n"
        )
        f.write("sp_01,Homo sapiens,Human,9606,ncbi,0,1,[],2026-01-01,2026-01-01\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "database_path", data_dir / "relict.db")

    # 1. Fresh bootstrap
    ret = bootstrap_core(force=False, host="127.0.0.1", port=8000, base_data_dir=data_dir)
    assert ret == 0

    assert (tmp_path / "data").exists()
    assert (tmp_path / "data" / "relict.db").exists()
    assert (tmp_path / ".env").exists()

    # Read generated .env
    with open(tmp_path / ".env", encoding="utf-8") as f:
        env_text = f.read()

    assert "RELICT_AUTH_ENABLED=true" in env_text
    assert "RELICT_API_TOKENS=" in env_text
    assert "rc_live_" in env_text

    # Extract generated token
    token = None
    for line in env_text.splitlines():
        if line.startswith("RELICT_API_TOKENS="):
            # Parse token from line
            token = line.split('["')[1].split('"]')[0]

    assert token is not None and token.startswith("rc_live_")

    # 2. Idempotency test (second run should detect existing setup)
    ret_second = bootstrap_core(force=False, base_data_dir=data_dir)
    assert ret_second == 0

    # 3. Status check
    ret_status = check_status(base_data_dir=data_dir)
    assert ret_status == 0

    # 4. Authenticated request against API using the generated token
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_tokens", [token])

    client = TestClient(app)

    # Missing header -> 401
    resp_unauth = client.post("/v1/auth/verify")
    assert resp_unauth.status_code == 401

    # Invalid header -> 401
    resp_bad = client.post("/v1/auth/verify", headers={"Authorization": "Bearer invalid_key"})
    assert resp_bad.status_code == 401

    # Valid header -> 200
    resp_ok = client.post("/v1/auth/verify", headers={"Authorization": f"Bearer {token}"})
    assert resp_ok.status_code == 200
    data = resp_ok.json()
    assert data["status"] == "verified"
    assert "core_version" in data
