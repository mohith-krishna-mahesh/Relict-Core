from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)

REACTOME_SUPPORTED_SPECIES: set[str] = {
    "Homo sapiens",
    "Mus musculus",
    "Rattus norvegicus",
    "Danio rerio",
    "Drosophila melanogaster",
    "Caenorhabditis elegans",
    "Saccharomyces cerevisiae",
    "Sus scrofa",
    "Gallus gallus",
    "Oryza sativa",
    "Arabidopsis thaliana",
    "Canis lupus familiaris",
    "Bos taurus",
}


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
        candidate_genes = set(context.get("candidate_genes", [])) if context else set()

        # Reactome is indexed primarily for model organisms; fallback to Homo sapiens for primates/mammals
        species_name = "Homo sapiens"
        if species and species in REACTOME_SUPPORTED_SPECIES:
            species_name = species

        # Only query Reactome for clean gene symbols or top candidates
        clean_targets = [
            t
            for t in targets
            if (t in candidate_genes or (t.isupper() and 2 <= len(t) <= 10) or len(t.split()) <= 2)
            and len(t) <= 25
        ][:3]

        for target in clean_targets:
            try:
                # 1. Search Reactome entities with caching
                search_res = await self._get(
                    f"{self.BASE_URL}/search/query",
                    params={"query": target, "species": species_name},
                )
                search_data = self._safe_json(search_res)

                results = search_data.get("results", []) if isinstance(search_data, dict) else []
                entries = results[0].get("entries", []) if results else []

                # Limit to top 3 relevant entries
                top_entries = entries[:3]

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
                logger.debug("Reactome HTTP Error for %s: %s", target, e)
            except Exception as e:
                logger.debug("Reactome Error for %s: %s", target, e)

        return records
