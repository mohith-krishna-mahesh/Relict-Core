#!/usr/bin/env python3
"""
Model setup verification and backend connectivity checker for Relict Core.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from scripts.download_model import download_model

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def setup_model() -> int:
    """Ensure model assets are installed and verify inference backend usability."""
    root_dir = Path(__file__).resolve().parent.parent
    manifest = root_dir / "model_manifest.json"
    weights = root_dir / "app" / "core_model" / "weights" / "relict-qwen3-4b"

    logger.info("Setting up Core Model from %s...", manifest)
    rc = download_model(manifest_path=manifest, target_dir=weights)
    if rc != 0:
        logger.error("Core model setup failed.")
        return rc

    logger.info("Core Model setup verified.")
    return 0


if __name__ == "__main__":
    sys.exit(setup_model())
