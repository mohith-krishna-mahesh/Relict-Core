from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class AlphaMissenseClient(BaseClient):
    """AlphaMissense local-data client.

    AlphaMissense predictions are a bulk local dataset, NOT a live
    API.  This client queries pre-ingested data via DuckDB.

    If the local dataset has not been ingested, the client returns
    an empty result with a warning rather than fabricating evidence.
    """

    @property
    def source_name(self) -> str:
        return "alphamissense"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        db_path = self.settings.duckdb_path
        if not Path(db_path).exists():
            logger.warning(
                "alphamissense: local DuckDB not found at %s — "
                "returning empty results. Ingest AlphaMissense data first.",
                db_path,
            )
            return []

        try:
            import duckdb
        except ImportError:
            logger.warning("alphamissense: duckdb not installed")
            return []

        records: list[EvidenceRecord] = []
        try:
            con = duckdb.connect(db_path, read_only=True)
            try:
                # Check if the expected table exists
                tables = [
                    row[0]
                    for row in con.execute(
                        "SELECT table_name FROM information_schema.tables"
                    ).fetchall()
                ]
                if "alphamissense" not in tables:
                    logger.warning(
                        "alphamissense: table 'alphamissense' not found in %s",
                        db_path,
                    )
                    return []

                for target in targets:
                    target_records = self._query_gene(con, target)
                    records.extend(target_records)
            finally:
                con.close()
        except Exception:
            logger.warning(
                "alphamissense: DuckDB query failed",
                exc_info=True,
            )

        return records

    def _query_gene(self, con: Any, gene: str) -> list[EvidenceRecord]:
        """Query AlphaMissense predictions for a gene."""
        try:
            rows = con.execute(
                """
                SELECT
                    CHROM, POS, REF, ALT, genome,
                    uniprot_id, transcript_id,
                    protein_variant, am_pathogenicity, am_class
                FROM alphamissense
                WHERE uniprot_id = ? OR transcript_id = ? OR gene = ?
                LIMIT 500
                """,
                [gene, gene, gene],
            ).fetchall()
        except Exception:
            # Column names may differ — try a simpler query
            try:
                rows = con.execute(
                    "SELECT * FROM alphamissense WHERE gene = ? LIMIT 500",
                    [gene],
                ).fetchall()
            except Exception:
                logger.warning("alphamissense: query failed for gene %s", gene)
                return []

        records: list[EvidenceRecord] = []
        for row in rows:
            # Adapt to whichever column layout is present
            if len(row) >= 10:
                chrom, pos, ref, alt, genome = row[0], row[1], row[2], row[3], row[4]
                uniprot_id = row[5]
                protein_variant = row[7]
                am_pathogenicity = row[8]
                am_class = row[9]
            else:
                # Fallback for simpler schemas
                chrom = pos = ref = alt = genome = None
                uniprot_id = protein_variant = am_class = None
                am_pathogenicity = None

            variant_id = (
                f"chr{chrom}:{pos}:{ref}>{alt}" if chrom and pos else str(row)
            )
            records.append(
                self._make_record(
                    entity_a=variant_id,
                    relationship="variant_pathogenicity",
                    entity_b=gene,
                    source_id=variant_id,
                    source_score=(
                        float(am_pathogenicity) if am_pathogenicity is not None else None
                    ),
                    endpoint="local_duckdb",
                    query_context={"gene": gene},
                    metadata={
                        "genome": genome,
                        "uniprot_id": uniprot_id,
                        "protein_variant": protein_variant,
                        "am_class": am_class,
                    },
                )
            )
        return records
