#!/usr/bin/env python3
"""Export species table from Neon PostgreSQL database to canonical CSV.

Usage:
    DATABASE_URL="postgresql://..." python scripts/export_species.py
"""

from __future__ import annotations

import csv
import logging
import os
import sys
from pathlib import Path

import psycopg2

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def export_species(database_url: str | None = None, output_path: Path | None = None) -> int:
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        logger.error("DATABASE_URL environment variable is required.")
        return 1

    default_csv = Path(__file__).resolve().parent.parent / "data" / "species" / "species.csv"
    out_file = output_path or default_csv
    tmp_file = out_file.with_suffix(".csv.tmp")
    out_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Connecting to Neon database...")
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor(name="export_species_cursor")
        cur.itersize = 50000

        # Query all rows from species table
        headers = [
            "id",
            "scientificName",
            "commonName",
            "taxonomyId",
            "source",
            "isExtinct",
            "hasGenomeData",
            "tags",
            "createdAt",
            "updatedAt",
        ]
        select_sql = (
            'SELECT id, "scientificName", "commonName", "taxonomyId", source, '
            '"isExtinct", "hasGenomeData", tags, "createdAt", "updatedAt" '
            'FROM "public"."Species"'
        )
        cur.execute(select_sql)

        logger.info("Streaming species rows to %s in 50k chunks...", out_file)
        total_written = 0
        with open(tmp_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            while True:
                rows = cur.fetchmany(50000)
                if not rows:
                    break
                writer.writerows(rows)
                total_written += len(rows)

        tmp_file.replace(out_file)
        cur.close()
        conn.close()
        size_mb = out_file.stat().st_size / (1024 * 1024)
        logger.info(
            "Successfully exported %d rows to %s (%.2f MB).", total_written, out_file, size_mb
        )
        return 0
    except Exception as exc:
        logger.error("Failed to export species data: %s", exc)
        if tmp_file.exists():
            tmp_file.unlink()
        return 1


if __name__ == "__main__":
    sys.exit(export_species())
