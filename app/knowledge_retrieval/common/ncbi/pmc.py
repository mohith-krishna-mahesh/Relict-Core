from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class NCBIpmcClient(BaseClient):
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    @property
    def source_name(self) -> str:
        return "ncbi_pmc"

    def _get_params(self, **kwargs: Any) -> dict[str, Any]:
        params: dict[str, Any] = {"retmode": "json"}
        params.update(kwargs)
        if self.settings:
            if self.settings.ncbi_api_key:
                params["api_key"] = self.settings.ncbi_api_key
            if self.settings.ncbi_email:
                params["email"] = self.settings.ncbi_email
        return params

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []

        # Query PMC for top 2 specific targets
        for target in targets[:2]:
            try:
                term = target
                if species:
                    term = f"{target} AND {species}"

                search_params = self._get_params(db="pmc", term=term, retmax=3)
                search_raw = await self._get(f"{self.BASE_URL}/esearch.fcgi", params=search_params)
                search_resp = self._safe_json(search_raw)
                if not isinstance(search_resp, dict) or "esearchresult" not in search_resp:
                    continue

                id_list: list[str] = search_resp["esearchresult"].get("idlist", [])
                if not id_list:
                    continue

                # Batch summary request for all PMC IDs
                summary_params = self._get_params(db="pmc", id=",".join(id_list[:3]))
                summary_raw = await self._get(
                    f"{self.BASE_URL}/esummary.fcgi", params=summary_params
                )
                summary_resp = self._safe_json(summary_raw)
                if not isinstance(summary_resp, dict) or "result" not in summary_resp:
                    continue

                for pmcid in id_list[:3]:
                    doc_info = summary_resp["result"].get(pmcid, {})
                    if not doc_info:
                        continue

                    title = doc_info.get("title", "")
                    records.append(
                        self._make_record(
                            entity_a=target,
                            relationship="literature_association",
                            entity_b=title if title else f"PMC{pmcid}",
                            source_id=pmcid,
                            source_score=1.0,
                            endpoint=f"{self.BASE_URL}/esummary.fcgi",
                            query_context={"term": term},
                            metadata=doc_info,
                        )
                    )

            except httpx.HTTPError as e:
                logger.warning("HTTP Error querying NCBI PMC for %s: %s", target, e)
            except Exception as e:
                logger.warning("Error querying NCBI PMC for %s: %s", target, e)

        return records
