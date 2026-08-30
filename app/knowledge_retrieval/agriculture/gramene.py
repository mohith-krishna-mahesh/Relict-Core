from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class GrameneClient(BaseClient):
    BASE_URL = "https://data.gramene.org"

    @property
    def source_name(self) -> str:
        return "gramene"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        clean_targets = [t for t in targets if " " not in t and len(t) <= 15][:3]

        for target in clean_targets:
            url = f"{self.BASE_URL}/genes"
            params = {"q": target}

            try:
                response = await self._get(url, params=params)
                data = self._safe_json(response)

                if isinstance(data, list) and data:
                    records.append(
                        self._make_record(
                            entity_a=target,
                            relationship="gene_pathway",
                            entity_b="Gramene Pathway",
                            source_id=f"gramene_{target}",
                            source_score=1.0,
                            endpoint=url,
                            query_context={"target": target, "species": species},
                            metadata={"results": len(data)},
                        )
                    )
            except httpx.HTTPError as e:
                logger.debug("Error querying Gramene for %s: %s", target, e)
            except Exception as e:
                logger.debug("Unexpected error querying Gramene for %s: %s", target, e)

        return records
