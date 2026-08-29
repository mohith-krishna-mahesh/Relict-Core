from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class EpiDBClient(BaseClient):
    @property
    def source_name(self) -> str:
        return "epidb"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        duckdb_path = getattr(self.settings, "duckdb_path", None)

        if not duckdb_path or not Path(duckdb_path).exists():
            logger.info(
                "EpiDB: local DuckDB not found at %s — returning empty results.",
                duckdb_path,
            )
            return records

        try:
            import duckdb
        except ImportError:
            logger.warning("EpiDB: duckdb package not installed.")
            return records

        try:
            conn = duckdb.connect(
                duckdb_path,
                read_only=True,
                config={"access_mode": "read_only"},
            )
            try:
                table_query = "SELECT table_name FROM information_schema.tables"
                tables = [r[0] for r in conn.execute(table_query).fetchall()]
                if "epidb" in tables:
                    for target in targets:
                        rows = conn.execute(
                            "SELECT mark, region FROM epidb WHERE gene = ? LIMIT 100", [target]
                        ).fetchall()
                        for mark, region in rows:
                            records.append(
                                self._make_record(
                                    entity_a=target,
                                    relationship="gene_regulation",
                                    entity_b=str(mark),
                                    source_id=f"epidb_{target}_{region}",
                                    source_score=1.0,
                                    endpoint="local:duckdb",
                                    query_context={"target": target, "species": species},
                                    metadata={"region": region, "epigenetic_mark": mark},
                                )
                            )
            finally:
                conn.close()
        except Exception as e:
            logger.warning("Error querying local EpiDB duckdb: %s", e)

        return records
