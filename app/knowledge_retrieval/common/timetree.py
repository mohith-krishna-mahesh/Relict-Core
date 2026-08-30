from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class TimeTreeClient(BaseClient):
    BASE_URL = "https://timetree.org/api"

    @property
    def source_name(self) -> str:
        return "timetree"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []

        if not species or not targets:
            return records

        # TimeTree only accepts pairwise species comparisons (e.g. "Pan troglodytes" vs "Gorilla gorilla")
        # Filter out gene symbols, pathways, and single-word keywords
        candidate_taxa = []
        if context and context.get("related_species"):
            candidate_taxa.append(context["related_species"])

        for target in targets:
            words = target.strip().split()
            # Valid binomial species name has exactly 2 words, begins with uppercase letter, and has no digits/punctuation
            if (
                len(words) == 2
                and words[0][0].isupper()
                and words[1].islower()
                and words[0].isalpha()
                and words[1].isalpha()
                and target.lower() != species.lower()
            ):
                candidate_taxa.append(target)

        for taxon in set(candidate_taxa):
            try:
                raw_resp = await self._get(f"{self.BASE_URL}/pairwise/{taxon}/{species}")
                resp = self._safe_json(raw_resp)
                if isinstance(resp, dict) and "time" in resp:
                    est_time = resp.get("time")
                    try:
                        score = float(est_time) if est_time is not None else 0.0
                    except (ValueError, TypeError):
                        score = 0.0

                    records.append(
                        self._make_record(
                            entity_a=taxon,
                            relationship="species_divergence",
                            entity_b=species,
                            source_id=f"{taxon}_{species}",
                            source_score=score,
                            endpoint=f"{self.BASE_URL}/pairwise",
                            query_context={"taxon_a": taxon, "taxon_b": species},
                            metadata=resp,
                        )
                    )
            except httpx.HTTPError as e:
                logger.debug("HTTP Error querying TimeTree for %s vs %s: %s", taxon, species, e)
            except Exception as e:
                logger.debug("Error querying TimeTree for %s vs %s: %s", taxon, species, e)

        return records
