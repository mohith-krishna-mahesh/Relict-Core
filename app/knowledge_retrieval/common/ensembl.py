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
        species_name = (context.get("species_ensembl_name") if context else None) or (
            species.lower().replace(" ", "_") if species else "homo_sapiens"
        )

        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        for target in targets:
            # Ensembl symbol lookup expects single clean gene symbols (no spaces or multi-word phrases)
            if (
                " " in target
                or len(target) > 20
                or not target.replace("-", "").replace("_", "").replace(";", "").isalnum()
            ):
                continue

            try:
                # 1. Gene Symbol Lookup
                lookup_url = f"{self.BASE_URL}/lookup/symbol/{species_name}/{target}"
                lookup_res = await self._get(lookup_url, headers=headers)
                gene_data = self._safe_json(lookup_res)
                if not gene_data or not isinstance(gene_data, dict):
                    continue
                gene_id = gene_data.get("id")
                if not gene_id:
                    continue

                # 2. Phenotypes
                try:
                    pheno_url = f"{self.BASE_URL}/phenotype/gene/{species_name}/{gene_id}"
                    pheno_res = await self._get(pheno_url, headers=headers)
                    pheno_data = self._safe_json(pheno_res)
                    if isinstance(pheno_data, list):
                        for p in pheno_data:
                            phenotype = p.get("phenotype_description") or p.get("phenotype")
                            if phenotype:
                                records.append(
                                    self._make_record(
                                        entity_a=target,
                                        relationship="gene_phenotype",
                                        entity_b=str(phenotype),
                                        source_id=gene_id,
                                        source_score=1.0,
                                        endpoint="/phenotype/gene",
                                        query_context={"target": target, "species": species_name},
                                        metadata=p,
                                    )
                                )
                except Exception as p_err:
                    logger.debug("Ensembl phenotype query skipped for %s: %s", target, p_err)

                # 3. Cross references
                try:
                    xref_url = f"{self.BASE_URL}/xrefs/id/{gene_id}"
                    xref_res = await self._get(xref_url, headers=headers)
                    xref_data = self._safe_json(xref_res)
                    if isinstance(xref_data, list):
                        for x in xref_data:
                            dbname = x.get("dbname")
                            primary_id = x.get("primary_id")
                            if dbname == "GO" or "pathway" in str(dbname).lower():
                                desc = x.get("description") or primary_id
                                records.append(
                                    self._make_record(
                                        entity_a=target,
                                        relationship="gene_pathway",
                                        entity_b=str(desc),
                                        source_id=str(primary_id),
                                        source_score=1.0,
                                        endpoint="/xrefs/id",
                                        query_context={"target": target, "species": species_name},
                                        metadata=x,
                                    )
                                )
                except Exception as x_err:
                    logger.debug("Ensembl xrefs query skipped for %s: %s", target, x_err)

                # 4. Orthologs / Homologies
                try:
                    homo_url = f"{self.BASE_URL}/homology/symbol/{species_name}/{target}"
                    homo_res = await self._get(homo_url, headers=headers)
                    data = self._safe_json(homo_res)
                    if isinstance(data, dict) and "data" in data and len(data["data"]) > 0:
                        homologies = data["data"][0].get("homologies", [])
                        for h in homologies:
                            ortholog = h.get("target", {}).get("id")
                            if ortholog:
                                records.append(
                                    self._make_record(
                                        entity_a=target,
                                        relationship="gene_orthology",
                                        entity_b=str(ortholog),
                                        source_id=gene_id,
                                        source_score=1.0,
                                        endpoint="/homology/symbol",
                                        query_context={"target": target, "species": species_name},
                                        metadata=h,
                                    )
                                )
                except Exception as h_err:
                    logger.debug("Ensembl homology query skipped for %s: %s", target, h_err)

            except httpx.HTTPError as e:
                logger.warning("Ensembl HTTP Error for %s: %s", target, e)
            except Exception as e:
                logger.warning("Ensembl Error for %s: %s", target, e)

        return records

    async def lookup_symbol(self, species_ensembl_name: str, symbol: str) -> dict | None:
        """
        Look up a gene symbol via Ensembl REST API (exact match only).
        Returns the parsed JSON dictionary, or None on failure (e.g. 404).
        """
        url = f"{self.BASE_URL}/lookup/symbol/{species_ensembl_name}/{symbol}"
        headers = {"Accept": "application/json"}
        try:
            res = await self._get(url, headers=headers)
            data = self._safe_json(res)
            if isinstance(data, dict):
                return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                logger.warning(
                    "Ensembl lookup error for %s in %s: %s", symbol, species_ensembl_name, e
                )
        except Exception as e:
            logger.warning("Ensembl lookup error for %s in %s: %s", symbol, species_ensembl_name, e)
        return None
