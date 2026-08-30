"""
Root conftest.py — adds the project root to sys.path so that
``from app.models.*`` imports resolve correctly when running pytest
without installing the package.

This file is test infrastructure, not part of the application source.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root (directory containing this conftest.py) is on
# sys.path so that `import app.*` works regardless of how pytest is invoked.
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
