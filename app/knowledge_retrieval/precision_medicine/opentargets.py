from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class OpenTargetsClient(BaseClient):
    BASE_URL = "https://api.platform.opentargets.org/api/v4/graphql"

    @property
    def source_name(self) -> str:
        return "opentargets"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        
        graphql_query = """
        query target($ensemblId: String!){
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
            }
        }
        """

        for target in targets:
            json_data = {
                "query": graphql_query,
                "variables": {"ensemblId": target}
            }

            try:
                response = await self._post(self.BASE_URL, json_data=json_data)
                data = response.json()
                
                if "data" in data and data["data"].get("target"):
                    records.append(
                        self._make_record(
                            entity_a=target,
                            relationship="gene_disease",
                            entity_b="OpenTargets Association",
                            source_id=f"opentargets_{target}",
                            source_score=1.0,
                            endpoint=self.BASE_URL,
                            query_context={"target": target, "species": species},
                            metadata=data["data"]["target"],
                        )
                    )
            except httpx.HTTPError as e:
                logger.warning(f"Error querying OpenTargets for {target}: {e}")

        return records
