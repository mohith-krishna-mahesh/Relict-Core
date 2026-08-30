from __future__ import annotations

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
                # Search
                search_res = await self._http.get(
                    f"{self.BASE_URL}/search/query",
                    params={"query": target, "species": species_name},
                )
                search_res.raise_for_status()
                search_data = self._safe_json(search_res)

                results = search_data.get("results", []) if isinstance(search_data, dict) else []
                entries = results[0].get("entries", []) if results else []

                for entry in entries:
                    st_id = entry.get("stId")
                    if not st_id:
                        continue

                    # Get pathways
                    path_url = f"{self.BASE_URL}/data/pathways/low/entity/{st_id}"
                    path_res = await self._http.get(path_url)
                    if path_res.status_code == 404:
                        continue
                    path_res.raise_for_status()
                    pathways = self._safe_json(path_res)

                    for pathway in pathways if isinstance(pathways, list) else []:
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
