from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class NCBIDatasetsV2Client(BaseClient):
    BASE_URL = "https://api.ncbi.nlm.nih.gov/datasets/v2"

    @property
    def source_name(self) -> str:
        return "ncbi_datasets"

    def _get_headers(self) -> dict[str, str]:
        headers = {}
        if hasattr(self, "settings") and self.settings:
            if getattr(self.settings, "ncbi_api_key", None):
                headers["api-key"] = self.settings.ncbi_api_key
        return headers

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []

        taxon = species if species else "human"
        headers = self._get_headers()

        # Only query NCBI Datasets for clean gene symbols (no phrases)
        clean_targets = [t for t in targets if " " not in t and len(t) <= 15 and t.isalnum()][:3]

        for target in clean_targets:
            try:
                gene_resp = await self._get(
                    f"{self.BASE_URL}/gene/symbol/{target}/taxon/{taxon}", headers=headers
                )
                gene_data = self._safe_json(gene_resp)

                if not gene_data or not isinstance(gene_data, dict) or "reports" not in gene_data:
                    continue

                for report_wrapper in gene_data.get("reports", [])[:2]:
                    report = report_wrapper.get("gene", {})
                    gene_id = str(report.get("gene_id", ""))
                    if not gene_id:
                        continue

                    symbol = report.get("symbol", target)
                    description = report.get("description", "")

                    records.append(
                        self._make_record(
                            entity_a=target,
                            relationship="gene_annotation",
                            entity_b=description or symbol,
                            source_id=gene_id,
                            source_score=1.0,
                            endpoint=f"{self.BASE_URL}/gene/symbol",
                            query_context={"symbol": target, "taxon": taxon},
                            metadata=report,
                        )
                    )

                    try:
                        ortho_resp = await self._get(
                            f"{self.BASE_URL}/gene/id/{gene_id}/orthologs", headers=headers
                        )
                        ortho_data = self._safe_json(ortho_resp)

                        if isinstance(ortho_data, dict) and "reports" in ortho_data:
                            for ortho_wrapper in ortho_data.get("reports", [])[:3]:
                                ortho_gene = ortho_wrapper.get("gene", {})
                                ortho_symbol = ortho_gene.get("symbol")
                                ortho_taxname = ortho_gene.get("taxname", "ortholog")
                                if ortho_symbol:
                                    records.append(
                                        self._make_record(
                                            entity_a=target,
                                            relationship="gene_orthology",
                                            entity_b=f"{ortho_symbol} ({ortho_taxname})",
                                            source_id=str(ortho_gene.get("gene_id", "")),
                                            source_score=1.0,
                                            endpoint=f"{self.BASE_URL}/gene/id/orthologs",
                                            query_context={"gene_id": gene_id},
                                            metadata=ortho_gene,
                                        )
                                    )
                    except Exception as o_err:
                        logger.debug(
                            "NCBI Datasets ortholog query skipped for %s: %s", gene_id, o_err
                        )

            except httpx.HTTPError as e:
                logger.debug("HTTP Error querying NCBI Datasets for %s: %s", target, e)
            except Exception as e:
                logger.debug("Error querying NCBI Datasets for %s: %s", target, e)

        return records
