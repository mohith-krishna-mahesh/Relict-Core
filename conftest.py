"""
Root conftest.py — adds the project root to sys.path and ensures clean settings isolation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the project root is on sys.path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.config import settings


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset global settings flags between tests to ensure test isolation."""
    monkeypatch.setattr(settings, "auth_enabled", False)
    monkeypatch.setattr(settings, "api_tokens", [])
