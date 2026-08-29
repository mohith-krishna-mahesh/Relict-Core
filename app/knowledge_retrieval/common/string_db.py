from __future__ import annotations

import logging
from typing import Any
import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)

class StringDbClient(BaseClient):
    BASE_URL = "https://version-12-0.string-db.org/api"

    @property
    def source_name(self) -> str:
        return "string"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        if not targets:
            return records
            
        caller_identity = getattr(self.settings, "string_caller_identity", "RelictCore")
        species_id = "9606" if (species == "human" or not species) else None 

        try:
            # Map identifiers
            data = {
                "identifiers": "\r".join(targets),
                "format": "json",
                "caller_identity": caller_identity
            }
            if species_id:
                data["species"] = species_id
                
            map_res = await self._http.post(f"{self.BASE_URL}/json/get_string_ids", data=data)
            map_res.raise_for_status()
            mapped = map_res.json()
            
            string_ids = [m["stringId"] for m in mapped if "stringId" in m]
            if not string_ids:
                return records

            # Get network
            net_data = {
                "identifiers": "%0d".join(string_ids),
                "required_score": "400",
                "caller_identity": caller_identity
            }
            if species_id:
                net_data["species"] = species_id
                
            net_res = await self._http.post(f"{self.BASE_URL}/json/network", data=net_data)
            net_res.raise_for_status()
            network = net_res.json()
            
            for item in network:
                score = item.get("score", 0.0)
                if score >= 0.4:
                    records.append(
                        self._make_record(
                            entity_a=item.get("preferredName_A", ""),
                            relationship="protein_protein",
                            entity_b=item.get("preferredName_B", ""),
                            source_id=item.get("stringId_A", ""),
                            source_score=score,
                            endpoint="/json/network",
                            query_context={"targets": targets},
                            metadata=item
                        )
                    )
                    
        except httpx.HTTPError as e:
            logger.warning(f"STRING DB HTTP Error: {e}")
        except Exception as e:
            logger.warning(f"STRING DB Error: {e}")
            
        return records
