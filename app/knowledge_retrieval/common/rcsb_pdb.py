from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class RCSBPDBClient(BaseClient):
    BASE_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
    DATA_URL = "https://data.rcsb.org/rest/v1/core/entry"

    @property
    def source_name(self) -> str:
        return "rcsb_pdb"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        for target in targets:
            try:
                query_body = {
                    "query": {
                        "type": "terminal",
                        "service": "text",
                        "parameters": {"value": target},
                    },
                    "return_type": "entry",
                    "request_options": {"pager": {"start": 0, "rows": 5}},
                }

                raw_resp = await self._post(self.BASE_URL, json_data=query_body)
                resp = self._safe_json(raw_resp)
                if not isinstance(resp, dict):
                    continue
                if not resp or "result_set" not in resp:
                    continue

                for result in resp.get("result_set", []):
                    entry_id = str(result["identifier"])
                    score = float(result.get("score", 1.0))

                    data_raw = await self._get(f"{self.DATA_URL}/{entry_id}")
                    data_resp = self._safe_json(data_raw)
                    if not isinstance(data_resp, dict):
                        continue
                    if data_resp:
                        struct_info: dict[str, Any] = data_resp.get("struct", {})
                        title = struct_info.get("title", "")
                        records.append(
                            self._make_record(
                                entity_a=target,
                                relationship="protein_structure",
                                entity_b=entry_id,
                                source_id=entry_id,
                                source_score=score,
                                endpoint=self.BASE_URL,
                                query_context={"target": target, "species": species},
                                metadata={"title": title},
                            )
                        )
            except httpx.HTTPError as e:
                logger.error("HTTP Error querying RCSB PDB for %s: %s", target, e)
            except Exception as e:
                logger.error("Error querying RCSB PDB for %s: %s", target, e)

        return records
