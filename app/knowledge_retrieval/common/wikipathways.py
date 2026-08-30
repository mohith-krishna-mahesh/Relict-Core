from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class WikiPathwaysClient(BaseClient):
    BASE_URL = "https://sparql.wikipathways.org/sparql"

    @property
    def source_name(self) -> str:
        return "wikipathways"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        headers = {"Accept": "application/json"}

        # Only query WikiPathways for clean symbols or top 4 targets
        clean_targets = [t for t in targets if len(t.split()) <= 2 and len(t) <= 20][:4]

        for target in clean_targets:
            try:
                sparql_query = f"""
                PREFIX wp: <http://vocabularies.wikipathways.org/wp#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX dcterms: <http://purl.org/dc/terms/>
                PREFIX dc: <http://purl.org/dc/elements/1.1/>
                
                SELECT DISTINCT ?pathway ?pathwayTitle
                WHERE {{
                  ?gene a wp:GeneProduct ;
                        rdfs:label "{target}" ;
                        dcterms:isPartOf ?pathway .
                  ?pathway a wp:Pathway ;
                           dc:title ?pathwayTitle .
                }}
                LIMIT 10
                """

                res = await self._post(self.BASE_URL, data={"query": sparql_query}, headers=headers)
                data = self._safe_json(res)

                bindings = (
                    data.get("results", {}).get("bindings", []) if isinstance(data, dict) else []
                )
                for b in bindings:
                    pathway_title = b.get("pathwayTitle", {}).get("value")
                    pathway_uri = b.get("pathway", {}).get("value")
                    pathway_id = pathway_uri.split("/")[-1] if pathway_uri else ""

                    if pathway_title:
                        records.append(
                            self._make_record(
                                entity_a=target,
                                relationship="gene_pathway",
                                entity_b=pathway_title,
                                source_id=pathway_id,
                                source_score=1.0,
                                endpoint=self.BASE_URL,
                                query_context={"target": target},
                                metadata={"pathway_uri": pathway_uri},
                            )
                        )
            except httpx.HTTPError as e:
                logger.debug("WikiPathways HTTP Error for %s: %s", target, e)
            except Exception as e:
                logger.debug("WikiPathways Error for %s: %s", target, e)

        return records
