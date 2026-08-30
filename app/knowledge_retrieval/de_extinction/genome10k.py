from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class Genome10KClient(BaseClient):
    BASE_URL = "https://www.genomeark.org"

    @property
    def source_name(self) -> str:
        return "de_extinction_genome10k"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        if not species:
            return records

        url = f"{self.BASE_URL}/"

        try:
            await self._get(url)
            records.append(
                self._make_record(
                    entity_a=species,
                    relationship="species_assembly",
                    entity_b="Genome10K Assembly",
                    source_id=f"g10k_{species.replace(' ', '_')}",
                    source_score=1.0,
                    endpoint=url,
                    query_context={"species": species},
                    metadata={"status": "available", "url": url},
                )
            )
        except httpx.HTTPError as e:
            logger.debug("Genome10K query error for %s: %s", species, e)
        except Exception as e:
            logger.debug("Error querying Genome10K for %s: %s", species, e)

        return records
