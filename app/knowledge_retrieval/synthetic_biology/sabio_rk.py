from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class SabioRkClient(BaseClient):
    BASE_URL = "https://sabiork.h-its.org/sabioRestWebServices"

    @property
    def source_name(self) -> str:
        return "sabio_rk"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []

        for target in targets:
            url = f"{self.BASE_URL}/searchKineticLaws/entryIDs"

            try:
                response = await self._get(url, params={"q": target})

                records.append(
                    self._make_record(
                        entity_a=target,
                        relationship="enzyme_reaction",
                        entity_b="SABIO-RK Kinetic Law",
                        source_id=f"sabiork_{target}",
                        source_score=1.0,
                        endpoint=url,
                        query_context={"target": target, "species": species},
                        metadata={"results": response.text},
                    )
                )
            except httpx.HTTPError as e:
                logger.warning(f"Error querying SABIO-RK for {target}: {e}")

        return records
