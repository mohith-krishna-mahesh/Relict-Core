from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class GnomadClient(BaseClient):
    BASE_URL = "https://gnomad.broadinstitute.org/api"

    @property
    def source_name(self) -> str:
        return "gnomad"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        candidate_genes = set(context.get("candidate_genes", [])) if context else set()

        # Only query gnomAD for clean human gene symbols
        clean_targets = [
            t
            for t in targets
            if (t in candidate_genes or (t.isupper() and 2 <= len(t) <= 10)) and " " not in t
        ]

        graphql_query = """
        query Gene($geneId: String!) {
            gene(gene_id: $geneId) {
                gene_id
                symbol
            }
        }
        """

        for target in clean_targets[:4]:
            json_data = {"query": graphql_query, "variables": {"geneId": target}}

            try:
                response = await self._post(self.BASE_URL, json_data=json_data)
                data = self._safe_json(response)

                if isinstance(data, dict) and isinstance(data.get("data"), dict):
                    data_obj = data["data"]
                    if data_obj.get("gene"):
                        records.append(
                            self._make_record(
                                entity_a=target,
                                relationship="gene_variant",
                                entity_b="gnomAD Variant",
                                source_id=f"gnomad_{target}",
                                source_score=1.0,
                                endpoint=self.BASE_URL,
                                query_context={"target": target, "species": species},
                                metadata={"allele_frequency": 0.0, "constraint": data_obj["gene"]},
                            )
                        )
            except httpx.HTTPError as e:
                logger.debug("gnomAD query error for %s: %s", target, e)
            except Exception as e:
                logger.debug("Unexpected error querying gnomAD for %s: %s", target, e)

        return records
