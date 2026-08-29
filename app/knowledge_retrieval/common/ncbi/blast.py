from __future__ import annotations

import logging
from typing import Any

import anyio
import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class NCBIBlastClient(BaseClient):
    BASE_URL = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"

    @property
    def source_name(self) -> str:
        return "ncbi_blast"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []

        if not context or "sequence" not in context:
            return records

        sequence = context["sequence"]

        for target in targets:
            try:
                put_params = {
                    "CMD": "Put",
                    "PROGRAM": "blastp",
                    "DATABASE": "nr",
                    "QUERY": sequence,
                    "FORMAT_TYPE": "JSON2",
                }

                resp = await self._http.post(self.BASE_URL, data=put_params)
                resp.raise_for_status()

                rid = None
                for line in resp.text.splitlines():
                    if line.startswith("    RID = "):
                        rid = line.split("=")[1].strip()
                        break

                if not rid:
                    continue

                max_poll_attempts = 20
                poll_interval = 10

                blast_results = None
                for _ in range(max_poll_attempts):
                    await anyio.sleep(poll_interval)

                    get_params = {
                        "CMD": "Get",
                        "FORMAT_OBJECT": "SearchInfo",
                        "RID": rid,
                    }

                    status_resp = await self._http.get(self.BASE_URL, params=get_params)
                    status_text = status_resp.text

                    if "Status=WAITING" in status_text:
                        continue

                    if "Status=FAILED" in status_text or "Status=UNKNOWN" in status_text:
                        break

                    if "Status=READY" in status_text:
                        res_params = {
                            "CMD": "Get",
                            "FORMAT_TYPE": "JSON2",
                            "RID": rid,
                        }
                        res = await self._http.get(self.BASE_URL, params=res_params)
                        blast_results = res.json()
                        break

                if not blast_results:
                    continue

                reports = blast_results.get("BlastOutput2", [])
                for report in reports:
                    search = report.get("report", {}).get("results", {}).get("search", {})
                    hits = search.get("hits", [])
                    for hit in hits:
                        hit_desc = hit.get("description", [{}])[0]
                        accession = hit_desc.get("accession", "")
                        title = hit_desc.get("title", "")
                        hsps = hit.get("hsps", [])
                        if hsps:
                            evalue = hsps[0].get("evalue", 1.0)
                            if evalue < 1e-3:
                                records.append(
                                    self._make_record(
                                        entity_a=target,
                                        relationship="gene_orthology",
                                        entity_b=title,
                                        source_id=accession,
                                        source_score=evalue,
                                        endpoint=self.BASE_URL,
                                        query_context={"sequence": sequence, "rid": rid},
                                        metadata=hit,
                                    )
                                )

            except httpx.HTTPError as e:
                logger.error(f"HTTP Error querying NCBI BLAST for {target}: {e}")
            except Exception as e:
                logger.error(f"Error querying NCBI BLAST for {target}: {e}")

        return records
