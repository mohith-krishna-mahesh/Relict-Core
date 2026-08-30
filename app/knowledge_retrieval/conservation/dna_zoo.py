from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class DNAZooClient(BaseClient):
    BASE_URL = "https://www.dnazoo.org"

    @property
    def source_name(self) -> str:
        return "conservation_dna_zoo"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        if not species:
            return records

        url = f"{self.BASE_URL}/assemblies/{species.replace(' ', '_')}"

        try:
            await self._get(url)
            records.append(
                self._make_record(
                    entity_a=species,
                    relationship="species_assembly",
                    entity_b="DNA Zoo Assembly",
                    source_id=f"dnazoo_{species.replace(' ', '_')}",
                    source_score=1.0,
                    endpoint=url,
                    query_context={"species": species},
                    metadata={"status": "available", "url": url},
                )
            )
        except httpx.HTTPError as e:
            logger.debug("DNA Zoo assembly not found for %s: %s", species, e)
        except Exception as e:
            logger.debug("Error querying DNA Zoo for %s: %s", species, e)

        return records
