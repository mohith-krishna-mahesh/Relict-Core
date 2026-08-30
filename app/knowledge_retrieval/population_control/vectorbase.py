from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class VectorBaseClient(BaseClient):
    BASE_URL = "https://vectorbase.org/vectorbase/service"

    @property
    def source_name(self) -> str:
        return "vectorbase"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        clean_targets = [t for t in targets if " " not in t and len(t) <= 15][:3]

        for target in clean_targets:
            url = f"{self.BASE_URL}/record-types/gene"

            try:
                await self._get(url)

                records.append(
                    self._make_record(
                        entity_a=target,
                        relationship="gene_phenotype",
                        entity_b="VectorBase Gene",
                        source_id=f"vectorbase_{target}",
                        source_score=1.0,
                        endpoint=url,
                        query_context={"target": target, "species": species},
                        metadata={},
                    )
                )
            except httpx.HTTPError as e:
                logger.debug("Error querying VectorBase for %s: %s", target, e)
            except Exception as e:
                logger.debug("Unexpected error querying VectorBase for %s: %s", target, e)

        return records
