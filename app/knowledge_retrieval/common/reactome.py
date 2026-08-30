from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class ReactomeClient(BaseClient):
    BASE_URL = "https://reactome.org/ContentService"

    @property
    def source_name(self) -> str:
        return "reactome"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        species_name = species or "Homo sapiens"

        for target in targets:
            try:
                # 1. Search Reactome entities with caching
                search_res = await self._get(
                    f"{self.BASE_URL}/search/query",
                    params={"query": target, "species": species_name},
                )
                search_data = self._safe_json(search_res)

                results = search_data.get("results", []) if isinstance(search_data, dict) else []
                entries = results[0].get("entries", []) if results else []

                # Limit to top 5 relevant entries to avoid hundreds of sequential requests
                top_entries = entries[:5]

                async def _fetch_pathways(st_id: str) -> list[dict[str, Any]]:
                    path_url = f"{self.BASE_URL}/data/pathways/low/entity/{st_id}"
                    try:
                        path_res = await self._get(path_url)
                        if path_res.status_code == 404:
                            return []
                        data = self._safe_json(path_res)
                        return data if isinstance(data, list) else []
                    except Exception:
                        return []

                # Fetch pathways for top entries concurrently
                st_ids = [e.get("stId") for e in top_entries if e.get("stId")]
                if st_ids:
                    pathway_lists = await asyncio.gather(*[_fetch_pathways(sid) for sid in st_ids])
                    for pathways in pathway_lists:
                        for pathway in pathways:
                            pathway_name = pathway.get("displayName")
                            pathway_id = pathway.get("stId")
                            if pathway_name:
                                records.append(
                                    self._make_record(
                                        entity_a=target,
                                        relationship="gene_pathway",
                                        entity_b=pathway_name,
                                        source_id=pathway_id,
                                        source_score=1.0,
                                        endpoint="/data/pathways/low/entity",
                                        query_context={"target": target},
                                        metadata={"pathway_id": pathway_id},
                                    )
                                )
            except httpx.HTTPError as e:
                logger.warning(f"Reactome HTTP Error for {target}: {e}")
            except Exception as e:
                logger.warning(f"Reactome Error for {target}: {e}")

        return records
