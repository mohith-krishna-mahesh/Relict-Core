from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class ChemblClient(BaseClient):
    BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"

    @property
    def source_name(self) -> str:
        return "chembl"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []

        for target in targets:
            url = f"{self.BASE_URL}/target/search.json"
            params = {"q": target}

            try:
                response = await self._get(url, params=params)
                data = response.json()
                
                targets_found = data.get("targets", [])
                for t in targets_found:
                    records.append(
                        self._make_record(
                            entity_a=target,
                            relationship="compound_protein",
                            entity_b=t.get("target_chembl_id"),
                            source_id=f"chembl_{t.get('target_chembl_id')}",
                            source_score=1.0,
                            endpoint=url,
                            query_context={"target": target, "species": species},
                            metadata=t,
                        )
                    )
            except httpx.HTTPError as e:
                logger.warning(f"Error querying ChEMBL for {target}: {e}")

        return records
