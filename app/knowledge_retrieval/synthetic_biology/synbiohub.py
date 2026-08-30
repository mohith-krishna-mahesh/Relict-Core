from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class SynBioHubClient(BaseClient):
    BASE_URL = "https://api.synbiohub.org"

    @property
    def source_name(self) -> str:
        return "synbiohub"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        clean_targets = [t for t in targets if " " not in t and len(t) <= 15][:3]

        for target in clean_targets:
            url = f"{self.BASE_URL}/search/"
            params = {"q": target}

            try:
                await self._get(url, params=params)
                records.append(
                    self._make_record(
                        entity_a=target,
                        relationship="part_design",
                        entity_b="SynBioHub Design",
                        source_id=f"synbiohub_{target}",
                        source_score=1.0,
                        endpoint=url,
                        query_context={"target": target, "species": species},
                        metadata={},
                    )
                )
            except httpx.HTTPError as e:
                logger.debug("Error querying SynBioHub for %s: %s", target, e)
            except Exception as e:
                logger.debug("Unexpected error querying SynBioHub for %s: %s", target, e)

        return records
