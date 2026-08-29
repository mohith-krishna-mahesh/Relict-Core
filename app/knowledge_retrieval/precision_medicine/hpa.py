from __future__ import annotations

import logging
from typing import Any

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class HPAClient(BaseClient):
    """Human Protein Atlas client.

    HPA provides per-gene JSON endpoints for protein expression,
    tissue localisation, and subcellular localisation data.

    Bulk data is also available via TSV/JSON downloads and can be
    ingested into DuckDB for large-scale queries.  This client
    supports the lightweight per-gene JSON endpoint for live
    retrieval.
    """

    GENE_URL = "https://www.proteinatlas.org/{ensembl_id}.json"

    @property
    def source_name(self) -> str:
        return "hpa"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        for target in targets:
            try:
                target_records = await self._query_gene(target)
                records.extend(target_records)
            except Exception:
                logger.warning("hpa: failed to query target %s", target, exc_info=True)
        return records

    async def _query_gene(self, ensembl_id: str) -> list[EvidenceRecord]:
        """Query HPA for a single gene by Ensembl ID."""
        url = self.GENE_URL.format(ensembl_id=ensembl_id)
        try:
            resp = await self._get(url)
        except Exception:
            logger.warning("hpa: could not fetch %s", url)
            return []

        try:
            data = self._safe_json(resp)
        except Exception:
            logger.warning("hpa: non-JSON response for %s", ensembl_id)
            return []

        records: list[EvidenceRecord] = []
        if not isinstance(data, dict):
            return []
        gene_name = data.get("Gene", ensembl_id)
        endpoint = f"/{ensembl_id}.json"

        # Tissue expression
        for tissue_entry in data.get("Tissue expression", []):
            tissue = tissue_entry.get("Tissue", "unknown")
            level = tissue_entry.get("Level", "")
            records.append(
                self._make_record(
                    entity_a=gene_name,
                    relationship="gene_expression",
                    entity_b=tissue,
                    source_id=ensembl_id,
                    endpoint=endpoint,
                    query_context={"ensembl_id": ensembl_id},
                    metadata={
                        "expression_level": level,
                        "reliability": tissue_entry.get("Reliability", ""),
                    },
                )
            )

        # Subcellular localisation
        for loc_entry in data.get("Subcellular location", []):
            location = loc_entry.get("Location", "unknown")
            records.append(
                self._make_record(
                    entity_a=gene_name,
                    relationship="protein_function",
                    entity_b=location,
                    source_id=ensembl_id,
                    endpoint=endpoint,
                    query_context={"ensembl_id": ensembl_id},
                    metadata={"subcellular_location": True},
                )
            )

        return records
