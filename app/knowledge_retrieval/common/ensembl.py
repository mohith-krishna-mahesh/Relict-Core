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
                lookup_url = (
                    f"{self.BASE_URL}/lookup/symbol/"
                    f"{species_name}/{target}"
                )
                lookup_res = await self._get(lookup_url, headers=headers)
                gene_data = lookup_res.json()

                gene_id = gene_data.get("id")
                if not gene_id:
                    continue

                # Xrefs
                xrefs_url = f"{self.BASE_URL}/xrefs/id/{gene_id}"
                xrefs_res = await self._get(xrefs_url, headers=headers)

                for xref in xrefs_res.json():
                    description = xref.get("description")
                    if description:
                        records.append(
                            self._make_record(
                                entity_a=target,
                                relationship="gene_pathway",
                                entity_b=description,
                                source_id=gene_id,
                                source_score=1.0,
                                endpoint="/xrefs/id",
                                query_context={"target": target},
                                metadata=xref,
                            )
                        )

                # Phenotypes
                pheno_url = (
                    f"{self.BASE_URL}/phenotype/gene/"
                    f"{species_name}/{gene_id}"
                )
                pheno_res = await self._get(pheno_url, headers=headers)

                for phenotype_data in pheno_res.json():
                    phenotype = (
                        phenotype_data.get("phenotype_description")
                        or phenotype_data.get("phenotype")
                    )

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
                                metadata=phenotype_data,
                            )
                        )

                # Orthologs
                homo_url = (
                    f"{self.BASE_URL}/homology/symbol/"
                    f"{species_name}/{target}"
                )
                homo_res = await self._get(homo_url, headers=headers)

                data = homo_res.json()

                if data and "data" in data and data["data"]:
                    homologies = data["data"][0].get("homologies", [])

                    for homology in homologies:
                        ortholog = homology.get("target", {}).get("id")

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
                                    metadata=homology,
                                )
                            )

            except httpx.HTTPError as exc:
                logger.warning(
                    "Ensembl HTTP Error for %s: %s",
                    target,
                    exc,
                )
            except Exception as exc:
                logger.warning(
                    "Ensembl Error for %s: %s",
                    target,
                    exc,
                )

        return records
