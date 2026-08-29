from __future__ import annotations

import logging
from typing import Any
import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)

class KeggClient(BaseClient):
    BASE_URL = "https://rest.kegg.jp"

    @property
    def source_name(self) -> str:
        return "kegg"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        org = "hsa" if (species == "human" or not species) else species
        
        for target in targets:
            try:
                # Find gene
                find_res = await self._http.get(f"{self.BASE_URL}/find/{org}/{target}")
                find_res.raise_for_status()
                lines = find_res.text.strip().split("\n")
                
                gene_ids = []
                for line in lines:
                    if not line:
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 1:
                        gene_ids.append(parts[0])
                        
                for gene_id in gene_ids:
                    # Link pathway
                    link_res = await self._http.get(f"{self.BASE_URL}/link/pathway/{gene_id}")
                    link_res.raise_for_status()
                    link_lines = link_res.text.strip().split("\n")
                    
                    for link_line in link_lines:
                        if not link_line:
                            continue
                        link_parts = link_line.split("\t")
                        if len(link_parts) >= 2:
                            pathway_id = link_parts[1]
                            records.append(
                                self._make_record(
                                    entity_a=target,
                                    relationship="gene_pathway",
                                    entity_b=pathway_id,
                                    source_id=gene_id,
                                    source_score=1.0,
                                    endpoint=f"/link/pathway/{org}",
                                    query_context={"target": target},
                                    metadata={"pathway": pathway_id}
                                )
                            )
            except httpx.HTTPError as e:
                logger.warning(f"KEGG HTTP Error for {target}: {e}")
            except Exception as e:
                logger.warning(f"KEGG Error for {target}: {e}")
                
        return records
