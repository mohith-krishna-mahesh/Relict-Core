from __future__ import annotations

import logging
from typing import Any
import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)

class EnsemblClient(BaseClient):
    BASE_URL = "https://rest.ensembl.org"

    @property
    def source_name(self) -> str:
        return "ensembl"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        species_name = species or "human"
        
        headers = {"Content-Type": "application/json"}
        
        for target in targets:
            try:
                # Lookup
                lookup_url = f"{self.BASE_URL}/lookup/symbol/{species_name}/{target}"
                lookup_res = await self._http.get(lookup_url, headers=headers)
                lookup_res.raise_for_status()
                gene_data = lookup_res.json()
                gene_id = gene_data.get("id")
                if not gene_id:
                    continue
                
                # Phenotypes
                pheno_url = f"{self.BASE_URL}/phenotype/gene/{species_name}/{gene_id}"
                pheno_res = await self._http.get(pheno_url, headers=headers)
                pheno_res.raise_for_status()
                for p in pheno_res.json():
                    phenotype = p.get("phenotype_description")
                    if phenotype:
                        records.append(
                            self._make_record(
                                entity_a=target,
                                relationship="gene_phenotype",
                                entity_b=phenotype,
                                source_id=gene_id,
                                source_score=1.0,
                                endpoint="/phenotype/gene",
                                query_context={"target": target},
                                metadata=p,
                            )
                        )
                        
                # Orthologs
                homo_url = f"{self.BASE_URL}/homology/symbol/{species_name}/{target}"
                homo_res = await self._http.get(homo_url, headers=headers)
                homo_res.raise_for_status()
                data = homo_res.json()
                if data and "data" in data and len(data["data"]) > 0:
                    homologies = data["data"][0].get("homologies", [])
                    for h in homologies:
                        ortholog = h.get("target", {}).get("id")
                        if ortholog:
                            records.append(
                                self._make_record(
                                    entity_a=target,
                                    relationship="gene_orthology",
                                    entity_b=ortholog,
                                    source_id=gene_id,
                                    source_score=1.0,
                                    endpoint="/homology/symbol",
                                    query_context={"target": target},
                                    metadata=h
                                )
                            )
            except httpx.HTTPError as e:
                logger.warning(f"Ensembl HTTP Error for {target}: {e}")
            except Exception as e:
                logger.warning(f"Ensembl Error for {target}: {e}")
                
        return records
