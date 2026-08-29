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

        for target in targets:
            if target.lower() == species.lower():
                continue

            try:
                raw_resp = await self._get(f"{self.BASE_URL}/pairwise/{target}/{species}")
                resp = self._safe_json(raw_resp)
                if isinstance(resp, dict) and "time" in resp:
                    est_time = resp.get("time")
                    try:
                        score = float(est_time) if est_time is not None else 0.0
                    except (ValueError, TypeError):
                        score = 0.0

                    records.append(
                        self._make_record(
                            entity_a=target,
                            relationship="species_divergence",
                            entity_b=species,
                            source_id=f"{target}_{species}",
                            source_score=score,
                            endpoint=f"{self.BASE_URL}/pairwise",
                            query_context={"taxon_a": target, "taxon_b": species},
                            metadata=resp,
                        )
                    )
            except httpx.HTTPError as e:
                logger.error("HTTP Error querying TimeTree for %s vs %s: %s", target, species, e)
            except Exception as e:
                logger.error("Error querying TimeTree for %s vs %s: %s", target, species, e)

        return records
