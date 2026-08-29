from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class FAANGClient(BaseClient):
    BASE_URL = "https://data.faang.org/api"

    @property
    def source_name(self) -> str:
        return "faang"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []

        for target in targets:
            url = f"{self.BASE_URL}/dataset/_search/"
            params = {"q": target}

            try:
                response = await self._get(url, params=params)
                data = response.json()
                
                hits = data.get("hits", {}).get("hits", [])
                for hit in hits:
                    records.append(
                        self._make_record(
                            entity_a=target,
                            relationship="gene_regulation",
                            entity_b=hit.get("_id", "FAANG Dataset"),
                            source_id=f"faang_{hit.get('_id')}",
                            source_score=hit.get("_score", 1.0),
                            endpoint=url,
                            query_context={"target": target, "species": species},
                            metadata=hit.get("_source", {}),
                        )
                    )
            except httpx.HTTPError as e:
                logger.warning(f"Error querying FAANG for {target}: {e}")

        return records
