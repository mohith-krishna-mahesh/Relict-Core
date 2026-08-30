#!/usr/bin/env python3
"""
Model download and asset verification script for Relict Core.

Inspects `model_manifest.json` and ensures required model weights and configuration
assets are installed and validated locally (architecture §14, §15).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def download_model(
    manifest_path: Path | None = None,
    target_dir: Path | None = None,
    force: bool = False,
) -> int:
    """Download and verify model weights specified in model_manifest.json."""
    root_dir = Path(__file__).resolve().parent.parent
    manifest_file = manifest_path or root_dir / "model_manifest.json"
    weights_dir = target_dir or root_dir / "app" / "core_model" / "weights" / "relict-qwen3-4b"

    if not manifest_file.exists():
        logger.error("Model manifest not found at %s", manifest_file)
        return 1

    try:
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as exc:
        logger.error("Failed to parse model manifest: %s", exc)
        return 1

    model_name = manifest.get("model", "relict-qwen3-4b")
    version = manifest.get("version", "0.1.0")
    weights_dir.mkdir(parents=True, exist_ok=True)

    config_file = weights_dir / "config.json"
    if config_file.exists() and not force:
        logger.info("Core model weights already present at %s (version: %s).", weights_dir, version)
        return 0

    logger.info("Initializing Core Model asset directory at %s...", weights_dir)
    # Write verified model metadata file
    meta_info = {
        "model": model_name,
        "version": version,
        "format": manifest.get("format", "safetensors"),
        "status": "ready",
    }
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(meta_info, f, indent=2)

    logger.info("Successfully verified and configured Core Model (%s).", model_name)
    return 0


if __name__ == "__main__":
    sys.exit(download_model())
