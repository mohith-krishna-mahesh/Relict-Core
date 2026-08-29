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

        for target in targets:
            try:
                # Use _http to pass headers directly
                gene_resp = await self._http.get(
                    f"{self.BASE_URL}/gene/symbol/{target}/taxon/{taxon}", headers=headers
                )
                gene_resp.raise_for_status()
                gene_data = gene_resp.json()

                if not gene_data or "reports" not in gene_data:
                    continue

                for report_wrapper in gene_data.get("reports", []):
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

                    ortho_resp = await self._http.get(
                        f"{self.BASE_URL}/gene/id/{gene_id}/orthologs", headers=headers
                    )
                    ortho_resp.raise_for_status()
                    ortho_data = ortho_resp.json()

                    if ortho_data and "reports" in ortho_data:
                        for ortho_wrapper in ortho_data.get("reports", []):
                            ortho = ortho_wrapper.get("gene", {})
                            ortho_id = str(ortho.get("gene_id", ""))
                            ortho_sym = ortho.get("symbol", "")
                            if ortho_id:
                                records.append(
                                    self._make_record(
                                        entity_a=symbol,
                                        relationship="gene_orthology",
                                        entity_b=ortho_sym,
                                        source_id=ortho_id,
                                        source_score=1.0,
                                        endpoint=f"{self.BASE_URL}/gene/id/orthologs",
                                        query_context={"gene_id": gene_id},
                                        metadata=ortho,
                                    )
                                )

            except httpx.HTTPError as e:
                logger.error(f"HTTP Error querying NCBI Datasets for {target}: {e}")
            except Exception as e:
                logger.error(f"Error querying NCBI Datasets for {target}: {e}")

        return records
