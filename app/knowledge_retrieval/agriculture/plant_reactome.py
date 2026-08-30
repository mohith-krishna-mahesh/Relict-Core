from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class PlantReactomeClient(BaseClient):
    BASE_URL = "https://plantreactome.gramene.org/ContentService"

    @property
    def source_name(self) -> str:
        return "plant_reactome"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        clean_targets = [t for t in targets if " " not in t and len(t) <= 15][:3]

        for target in clean_targets:
            url = f"{self.BASE_URL}/data/query/{target}"

            try:
                response = await self._get(url)
                data = self._safe_json(response)
                if not isinstance(data, dict):
                    continue

                records.append(
                    self._make_record(
                        entity_a=target,
                        relationship="gene_pathway",
                        entity_b=data.get("displayName", "Pathway"),
                        source_id=f"reactome_{target}",
                        source_score=1.0,
                        endpoint=url,
                        query_context={"target": target, "species": species},
                        metadata={"type": data.get("className")},
                    )
                )
            except httpx.HTTPError as e:
                logger.debug("Error querying Plant Reactome for %s: %s", target, e)
            except Exception as e:
                logger.debug("Unexpected error querying Plant Reactome for %s: %s", target, e)

        return records
