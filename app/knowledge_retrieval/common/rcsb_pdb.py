from __future__ import annotations

import asyncio
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
        candidate_genes = set(context.get("candidate_genes", [])) if context else set()

        # Only query RCSB PDB for clean gene symbols or short terms
        valid_targets = [
            t
            for t in targets
            if (t in candidate_genes or (t.isupper() and 2 <= len(t) <= 10) or len(t.split()) == 1)
            and len(t) <= 15
            and not any(c in t for c in [":", ";", "/", "\\", " "])
        ]

        for target in valid_targets[:3]:
            try:
                query_body = {
                    "query": {
                        "type": "terminal",
                        "service": "full_text",
                        "parameters": {"value": target},
                    },
                    "return_type": "entry",
                    "request_options": {"pager": {"start": 0, "rows": 3}},
                }

                raw_resp = await self._post(self.BASE_URL, json_data=query_body)
                resp = self._safe_json(raw_resp)
                if not isinstance(resp, dict) or "result_set" not in resp:
                    continue

                entries = resp.get("result_set", [])[:2]

                async def _fetch_entry(res: dict[str, Any]) -> tuple[str, float, str]:
                    entry_id = str(res["identifier"])
                    score = float(res.get("score", 1.0))
                    try:
                        data_raw = await self._get(f"{self.DATA_URL}/{entry_id}")
                        data_resp = self._safe_json(data_raw)
                        title = ""
                        if isinstance(data_resp, dict):
                            struct_info: dict[str, Any] = data_resp.get("struct", {})
                            title = struct_info.get("title", "")
                        return entry_id, score, title
                    except Exception:
                        return entry_id, score, ""

                results = await asyncio.gather(*[_fetch_entry(e) for e in entries])
                for entry_id, score, title in results:
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
                logger.debug("HTTP Error querying RCSB PDB for %s: %s", target, e)
            except Exception as e:
                logger.debug("Error querying RCSB PDB for %s: %s", target, e)

        return records
