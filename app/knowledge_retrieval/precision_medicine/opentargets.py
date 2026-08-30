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
        candidate_genes = set(context.get("candidate_genes", [])) if context else set()

        clean_targets = [
            t
            for t in targets
            if (t in candidate_genes or (t.isupper() and 2 <= len(t) <= 10)) and " " not in t
        ]

        graphql_query = """
        query target($ensemblId: String!){
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
            }
        }
        """

        for target in clean_targets[:4]:
            json_data = {"query": graphql_query, "variables": {"ensemblId": target}}

            try:
                response = await self._post(self.BASE_URL, json_data=json_data)
                data = self._safe_json(response)

                if isinstance(data, dict) and isinstance(data.get("data"), dict):
                    data_obj = data["data"]
                    if data_obj.get("target"):
                        records.append(
                            self._make_record(
                                entity_a=target,
                                relationship="gene_disease",
                                entity_b="OpenTargets Association",
                                source_id=f"opentargets_{target}",
                                source_score=1.0,
                                endpoint=self.BASE_URL,
                                query_context={"target": target, "species": species},
                                metadata=data_obj["target"],
                            )
                        )
            except httpx.HTTPError as e:
                logger.debug("Error querying OpenTargets for %s: %s", target, e)
            except Exception as e:
                logger.debug("Unexpected error querying OpenTargets for %s: %s", target, e)

        return records
