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
        species_id = (context.get("species_tax_id") if context else None) or (
            species if species and species.isdigit() else "9606"
        )

        try:
            # 1. Map identifiers to STRING IDs
            data: dict[str, Any] = {
                "identifiers": "\r".join(targets),
                "format": "json",
                "caller_identity": caller_identity,
            }

            if species_id:
                data["species"] = species_id

            map_res = await self._post(f"{self.BASE_URL}/json/get_string_ids", data=data)
            mapped = self._safe_json(map_res)
            if not isinstance(mapped, list):
                return records

            string_ids = [m["stringId"] for m in mapped if isinstance(m, dict) and "stringId" in m]
            if not string_ids:
                return records

            # 2. Get interaction partners
            partner_data: dict[str, Any] = {
                "identifiers": "%0d".join(string_ids),
                "required_score": "400",
                "caller_identity": caller_identity,
            }

            if species_id:
                partner_data["species"] = species_id

            partner_res = await self._post(
                f"{self.BASE_URL}/json/interaction_partners", data=partner_data
            )
            interactions = self._safe_json(partner_res)

            if not isinstance(interactions, list):
                # Fallback to /json/network
                net_res = await self._post(f"{self.BASE_URL}/json/network", data=partner_data)
                interactions = self._safe_json(net_res)

            if isinstance(interactions, list):
                for item in interactions:
                    if not isinstance(item, dict):
                        continue
                    score = float(item.get("score", 0.0))
                    name_a = item.get("preferredName_A", "")
                    name_b = item.get("preferredName_B", "")
                    if score >= 0.4 and name_a:
                        records.append(
                            self._make_record(
                                entity_a=name_a,
                                relationship="protein_protein",
                                entity_b=name_b or None,
                                source_id=item.get("stringId_A", ""),
                                source_score=score,
                                endpoint="/json/interaction_partners",
                                query_context={"targets": targets, "species": species_id},
                                metadata=item,
                            )
                        )

        except httpx.HTTPError as e:
            logger.warning("STRING DB HTTP Error: %s", e)
        except Exception as e:
            logger.warning("STRING DB Error: %s", e)

        return records
