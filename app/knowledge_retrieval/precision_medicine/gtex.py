from __future__ import annotations

import logging
from typing import Any

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class GTExClient(BaseClient):
    """GTEx Portal client.

    Queries the GTEx REST API v2 for tissue-specific gene expression
    and eQTL associations.
    """

    BASE_URL = "https://gtexportal.org/api/v2"

    @property
    def source_name(self) -> str:
        return "gtex"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        for target in targets:
            try:
                records.extend(await self._query_expression(target))
                records.extend(await self._query_eqtl(target))
            except Exception:
                logger.warning("gtex: failed to query target %s", target, exc_info=True)
        return records

    async def _query_expression(self, gene_symbol: str) -> list[EvidenceRecord]:
        """Retrieve median gene expression across tissues."""
        url = f"{self.BASE_URL}/expression/medianGeneExpression"
        params = {"geneSymbol": gene_symbol, "datasetId": "gtex_v8"}
        try:
            resp = await self._get(url, params=params)
        except Exception:
            logger.warning("gtex: expression query failed for %s", gene_symbol)
            return []

        try:
            data = resp.json()
        except Exception:
            return []

        records: list[EvidenceRecord] = []
        if isinstance(data, list):
            items = data
        else:
            items = data.get("data", data.get("medianGeneExpression", []))
        if not isinstance(items, list):
            return []

        for item in items:
            tissue = item.get("tissueSiteDetailId", "unknown")
            median_tpm = item.get("median", item.get("medianTpm"))
            records.append(
                self._make_record(
                    entity_a=gene_symbol,
                    relationship="gene_expression",
                    entity_b=tissue,
                    source_id=item.get("gencodeId", gene_symbol),
                    source_score=float(median_tpm) if median_tpm is not None else None,
                    endpoint="/expression/medianGeneExpression",
                    query_context={"geneSymbol": gene_symbol},
                    metadata={
                        "tissue_site_detail_id": tissue,
                        "dataset_id": "gtex_v8",
                        "unit": "TPM",
                    },
                )
            )
        return records

    async def _query_eqtl(self, gene_symbol: str) -> list[EvidenceRecord]:
        """Retrieve significant single-tissue eQTL associations."""
        url = f"{self.BASE_URL}/association/singleTissueEqtl"
        params = {"geneSymbol": gene_symbol, "datasetId": "gtex_v8"}
        try:
            resp = await self._get(url, params=params)
        except Exception:
            logger.warning("gtex: eQTL query failed for %s", gene_symbol)
            return []

        try:
            data = resp.json()
        except Exception:
            return []

        records: list[EvidenceRecord] = []
        if isinstance(data, list):
            items = data
        else:
            items = data.get("data", data.get("singleTissueEqtl", []))
        if not isinstance(items, list):
            return []

        for item in items:
            variant_id = item.get("variantId", "unknown")
            tissue = item.get("tissueSiteDetailId", "unknown")
            pvalue = item.get("pValue", item.get("pvalue"))
            records.append(
                self._make_record(
                    entity_a=variant_id,
                    relationship="gene_regulation",
                    entity_b=gene_symbol,
                    source_id=variant_id,
                    source_score=float(pvalue) if pvalue is not None else None,
                    endpoint="/association/singleTissueEqtl",
                    query_context={"geneSymbol": gene_symbol},
                    metadata={
                        "tissue": tissue,
                        "nes": item.get("nes"),
                        "dataset_id": "gtex_v8",
                    },
                )
            )
        return records
