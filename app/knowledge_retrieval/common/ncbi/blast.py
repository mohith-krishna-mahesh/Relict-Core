from __future__ import annotations

import logging
import time
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
        max_wait = getattr(self.settings, "blast_max_wait_seconds", 30.0)

        for target in targets:
            try:
                put_params = {
                    "CMD": "Put",
                    "PROGRAM": "blastp",
                    "DATABASE": "nr",
                    "QUERY": sequence,
                    "FORMAT_TYPE": "JSON2",
                }

                resp = await self._post(self.BASE_URL, data=put_params)

                rid: str | None = None
                for line in resp.text.splitlines():
                    if "RID = " in line:
                        parts = line.split("=")
                        if len(parts) > 1:
                            rid = parts[1].strip()
                            break

                if not rid:
                    continue

                poll_interval = 5.0
                start_time = time.time()
                blast_results: dict[str, Any] | None = None

                while (time.time() - start_time) < max_wait:
                    await anyio.sleep(poll_interval)

                    get_params = {
                        "CMD": "Get",
                        "FORMAT_OBJECT": "SearchInfo",
                        "RID": rid,
                    }

                    status_resp = await self._get(self.BASE_URL, params=get_params)
                    status_text = status_resp.text

                    if "Status=WAITING" in status_text:
                        continue

                    if "Status=FAILED" in status_text or "Status=UNKNOWN" in status_text:
                        logger.warning("NCBI BLAST job %s failed or unknown status.", rid)
                        break

                    if "Status=READY" in status_text:
                        res_params = {
                            "CMD": "Get",
                            "FORMAT_TYPE": "JSON2",
                            "RID": rid,
                        }
                        res = await self._get(self.BASE_URL, params=res_params)
                        blast_results = self._safe_json(res)
                        break

                if not blast_results:
                    logger.info(
                        "NCBI BLAST for target %s (RID %s) did not finish within %.1fs budget.",
                        target,
                        rid,
                        max_wait,
                    )
                    continue

                reports = blast_results.get("BlastOutput2", [])
                for report in reports:
                    search = report.get("report", {}).get("results", {}).get("search", {})
                    hits = search.get("hits", [])
                    for hit in hits:
                        descriptions = hit.get("description", [])
                        hit_desc = descriptions[0] if descriptions else {}
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
                                        source_score=float(evalue),
                                        endpoint=self.BASE_URL,
                                        query_context={"sequence": sequence, "rid": rid},
                                        metadata=hit,
                                    )
                                )

            except httpx.HTTPError as e:
                logger.error("HTTP Error querying NCBI BLAST for %s: %s", target, e)
            except Exception as e:
                logger.error("Error querying NCBI BLAST for %s: %s", target, e)

        return records
