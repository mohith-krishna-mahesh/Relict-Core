from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class GBIFClient(BaseClient):
    BASE_URL = "https://api.gbif.org/v1"

    @property
    def source_name(self) -> str:
        return "gbif"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []

        queries = targets.copy()
        if species and species not in queries:
            queries.append(species)

        for query_term in queries:
            try:
                raw_resp = await self._get(
                    f"{self.BASE_URL}/species/match", params={"name": query_term}
                )
                match_data: dict[str, Any] = raw_resp.json()

                if match_data and match_data.get("matchType") != "NONE":
                    taxon_key = match_data.get("usageKey")
                    confidence = float(match_data.get("confidence", 0)) / 100.0
                    scientific_name = str(match_data.get("scientificName", query_term))

                    records.append(
                        self._make_record(
                            entity_a=query_term,
                            relationship="species_taxon",
                            entity_b=scientific_name,
                            source_id=str(taxon_key),
                            source_score=confidence,
                            endpoint=f"{self.BASE_URL}/species/match",
                            query_context={"query": query_term},
                            metadata=match_data,
                        )
                    )

                    if taxon_key:
                        occ_raw = await self._get(
                            f"{self.BASE_URL}/occurrence/search",
                            params={"taxonKey": taxon_key, "limit": 1},
                        )
                        occ_data: dict[str, Any] = occ_raw.json()
                        count = occ_data.get("count", 0)
                        if count > 0:
                            records.append(
                                self._make_record(
                                    entity_a=scientific_name,
                                    relationship="species_occurrence",
                                    entity_b=f"{count} occurrences",
                                    source_id=str(taxon_key),
                                    source_score=1.0,
                                    endpoint=f"{self.BASE_URL}/occurrence/search",
                                    query_context={"taxonKey": taxon_key},
                                    metadata={"count": count},
                                )
                            )
            except httpx.HTTPError as e:
                logger.error("HTTP Error querying GBIF for %s: %s", query_term, e)
            except Exception as e:
                logger.error("Error querying GBIF for %s: %s", query_term, e)

        return records
