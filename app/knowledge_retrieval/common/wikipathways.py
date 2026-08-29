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
        
        for target in targets:
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
                LIMIT 50
                """
                
                res = await self._http.post(
                    self.BASE_URL,
                    data={"query": sparql_query},
                    headers=headers
                )
                res.raise_for_status()
                data = res.json()
                
                bindings = data.get("results", {}).get("bindings", [])
                for b in bindings:
                    pathway_title = b.get("pathwayTitle", {}).get("value")
                    pathway_uri = b.get("pathway", {}).get("value")
                    
                    if pathway_title:
                        records.append(
                            self._make_record(
                                entity_a=target,
                                relationship="gene_pathway",
                                entity_b=pathway_title,
                                source_id=pathway_uri,
                                source_score=1.0,
                                endpoint="sparql",
                                query_context={"target": target},
                                metadata={"pathway_uri": pathway_uri}
                            )
                        )
            except httpx.HTTPError as e:
                logger.warning(f"WikiPathways HTTP Error for {target}: {e}")
            except Exception as e:
                logger.warning(f"WikiPathways Error for {target}: {e}")
                
        return records
