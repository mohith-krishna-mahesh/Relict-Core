from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class UniprotClient(BaseClient):
    BASE_URL = "https://rest.uniprot.org"

    @property
    def source_name(self) -> str:
        return "uniprot"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        org_name = species or "human"

        for target in targets:
            try:
                search_url = f"{self.BASE_URL}/uniprotkb/search"
                params = {"query": f"gene:{target} AND organism_name:{org_name}", "format": "json"}
                search_res = await self._http.get(search_url, params=params)
                search_res.raise_for_status()
                data = self._safe_json(search_res)

                results = data.get("results", []) if isinstance(data, dict) else []
                for result in results:
                    accession = result.get("primaryAccession")
                    if not accession:
                        continue

                    records.append(
                        self._make_record(
                            entity_a=target,
                            relationship="gene_protein",
                            entity_b=accession,
                            source_id=accession,
                            source_score=1.0,
                            endpoint="/uniprotkb/search",
                            query_context={"target": target},
                            metadata={},
                        )
                    )

                    comments = result.get("comments", [])
                    for comment in comments:
                        if comment.get("commentType") == "FUNCTION":
                            texts = comment.get("texts", [])
                            for text_obj in texts:
                                func_val = text_obj.get("value")
                                if func_val:
                                    records.append(
                                        self._make_record(
                                            entity_a=accession,
                                            relationship="protein_function",
                                            entity_b=func_val[:200],
                                            source_id=accession,
                                            source_score=1.0,
                                            endpoint="/uniprotkb/search",
                                            query_context={"target": target},
                                            metadata={"full_function": func_val},
                                        )
                                    )

            except httpx.HTTPError as e:
                logger.warning(f"UniProt HTTP Error for {target}: {e}")
            except Exception as e:
                logger.warning(f"UniProt Error for {target}: {e}")

        return records
