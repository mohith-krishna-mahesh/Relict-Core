from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class VGPClient(BaseClient):
    BASE_URL = "https://genomeark.github.io/genomeark-all"

    @property
    def source_name(self) -> str:
        return "conservation_vgp"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []

        for target in targets:
            query_species = species or target
            url = f"{self.BASE_URL}/genomeark.json"

            try:
                response = await self._get(url)
                data = response.json()
                if query_species in str(data):
                    records.append(
                        self._make_record(
                            entity_a=query_species,
                            relationship="species_assembly",
                            entity_b="VGP Assembly",
                            source_id=f"vgp_{query_species.replace(' ', '_')}",
                            source_score=1.0,
                            endpoint=url,
                            query_context={"target": target, "species": species},
                            metadata={"status": "available", "url": url},
                        )
                    )
            except httpx.HTTPError as e:
                logger.warning(f"Error querying VGP for {query_species}: {e}")

        return records
