from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class NCBIeUtilsClient(BaseClient):
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    @property
    def source_name(self) -> str:
        return "ncbi_eutils"

    def _get_params(self, **kwargs: Any) -> dict[str, Any]:
        params: dict[str, Any] = {"retmode": "json"}
        params.update(kwargs)
        if self.settings:
            if self.settings.ncbi_api_key:
                params["api_key"] = self.settings.ncbi_api_key
            if self.settings.ncbi_email:
                params["email"] = self.settings.ncbi_email
        return params

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []

        for target in targets:
            try:
                term = target
                if species:
                    term = f"{target}[Gene] AND {species}[Organism]"

                search_params = self._get_params(db="gene", term=term, retmax=5)
                search_raw = await self._get(
                    f"{self.BASE_URL}/esearch.fcgi", params=search_params
                )
                search_resp: dict[str, Any] = search_raw.json()

                if not search_resp or "esearchresult" not in search_resp:
                    continue

                id_list: list[str] = search_resp["esearchresult"].get("idlist", [])
                if not id_list:
                    continue

                summary_params = self._get_params(db="gene", id=",".join(id_list))
                summary_raw = await self._get(
                    f"{self.BASE_URL}/esummary.fcgi", params=summary_params
                )
                summary_resp: dict[str, Any] = summary_raw.json()

                if not summary_resp or "result" not in summary_resp:
                    continue

                for gene_id in id_list:
                    gene_info = summary_resp["result"].get(gene_id, {})
                    if not gene_info:
                        continue

                    name = gene_info.get("name", target)
                    description = gene_info.get("description", "")

                    records.append(
                        self._make_record(
                            entity_a=target,
                            relationship="gene_gene",
                            entity_b=name,
                            source_id=gene_id,
                            source_score=1.0,
                            endpoint=f"{self.BASE_URL}/esummary.fcgi",
                            query_context={"term": term},
                            metadata=gene_info,
                        )
                    )

                    if description:
                        records.append(
                            self._make_record(
                                entity_a=name,
                                relationship="gene_phenotype",
                                entity_b=description,
                                source_id=gene_id,
                                source_score=1.0,
                                endpoint=f"{self.BASE_URL}/esummary.fcgi",
                                query_context={"term": term},
                                metadata={"description": description},
                            )
                        )

            except httpx.HTTPError as e:
                logger.error("HTTP Error querying NCBI eUtils for %s: %s", target, e)
            except Exception as e:
                logger.error("Error querying NCBI eUtils for %s: %s", target, e)

        return records
