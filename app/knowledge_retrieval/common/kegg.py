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
        # KEGG requires 3-4 letter organism code (e.g. hsa, ggo, mmu, dme, eco) or 'genes'
        org = "hsa"
        if context and context.get("species_kegg_code"):
            org = context["species_kegg_code"]
        elif species and len(species.split()) == 1 and len(species) <= 4:
            org = species.lower()

        # KEGG find only accepts clean single gene symbols (no phrases)
        valid_targets = [t for t in targets if " " not in t and len(t) <= 15 and t.isalnum()]

        for target in valid_targets[:5]:
            try:
                # Find gene using cached GET
                find_res = await self._get(f"{self.BASE_URL}/find/{org}/{target}")
                lines = find_res.text.strip().split("\n")

                gene_ids = []
                for line in lines:
                    if not line:
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 1:
                        gene_ids.append(parts[0])

                # Query top 2 gene IDs for pathways
                for gene_id in gene_ids[:2]:
                    link_res = await self._get(f"{self.BASE_URL}/link/pathway/{gene_id}")
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
                                    metadata={"pathway": pathway_id},
                                )
                            )
            except httpx.HTTPError as e:
                logger.debug("KEGG HTTP Error for %s: %s", target, e)
            except Exception as e:
                logger.debug("KEGG Error for %s: %s", target, e)

        return records
