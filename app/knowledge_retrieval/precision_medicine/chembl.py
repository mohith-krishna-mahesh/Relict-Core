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
        candidate_genes = set(context.get("candidate_genes", [])) if context else set()

        clean_targets = [
            t
            for t in targets
            if (t in candidate_genes or (t.isupper() and 2 <= len(t) <= 10)) and " " not in t
        ]

        for target in clean_targets[:4]:
            url = f"{self.BASE_URL}/target/search.json"
            params = {"q": target}

            try:
                response = await self._get(url, params=params)
                data = self._safe_json(response)
                if not isinstance(data, dict):
                    continue

                targets_found = data.get("targets", [])
                for t in targets_found[:3]:
                    target_id = t.get("target_chembl_id")
                    if target_id:
                        records.append(
                            self._make_record(
                                entity_a=target,
                                relationship="compound_protein",
                                entity_b=target_id,
                                source_id=f"chembl_{target_id}",
                                source_score=1.0,
                                endpoint=url,
                                query_context={"target": target, "species": species},
                                metadata=t,
                            )
                        )
            except httpx.HTTPError as e:
                logger.debug("Error querying ChEMBL for %s: %s", target, e)
            except Exception as e:
                logger.debug("Unexpected error querying ChEMBL for %s: %s", target, e)

        return records
