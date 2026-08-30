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

        # GBIF is a species-level biodiversity database.
        # Only query for species name or valid binomial taxon names in targets.
        candidate_queries = []
        if species:
            candidate_queries.append(species)

        for t in targets:
            words = t.strip().split()
            if (
                len(words) == 2
                and words[0][0].isupper()
                and words[1].islower()
                and words[0].isalpha()
                and words[1].isalpha()
            ):
                candidate_queries.append(t.strip())

        for query_term in set(candidate_queries):
            try:
                raw_resp = await self._get(
                    f"{self.BASE_URL}/species/match", params={"name": query_term}
                )
                match_data = self._safe_json(raw_resp)
                if not isinstance(match_data, dict):
                    continue

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
                        occ_data = self._safe_json(occ_raw)
                        if isinstance(occ_data, dict):
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
                logger.debug("HTTP Error querying GBIF for %s: %s", query_term, e)
            except Exception as e:
                logger.debug("Error querying GBIF for %s: %s", query_term, e)

        return records
