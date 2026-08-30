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

        # STRING requires clean gene/protein identifiers
        clean_targets = [
            t
            for t in targets
            if " " not in t and len(t) <= 15 and t.replace("-", "").replace("_", "").isalnum()
        ]
        if not clean_targets:
            return records

        caller_identity = getattr(self.settings, "string_caller_identity", "RelictCore")
        species_id = (context.get("species_tax_id") if context else None) or (
            species if species and str(species).isdigit() else "9606"
        )

        try:
            # 1. Map identifiers to STRING IDs
            data: dict[str, Any] = {
                "identifiers": "\r".join(clean_targets[:10]),
                "format": "json",
                "caller_identity": caller_identity,
            }

            if species_id:
                data["species"] = str(species_id)

            map_res = await self._post(f"{self.BASE_URL}/json/get_string_ids", data=data)
            mapped = self._safe_json(map_res)
            if not isinstance(mapped, list):
                return records

            string_ids = [m["stringId"] for m in mapped if isinstance(m, dict) and "stringId" in m]
            if not string_ids:
                return records

            # 2. Get interaction partners for top 5 mapped IDs
            partner_data: dict[str, Any] = {
                "identifiers": "%0d".join(string_ids[:5]),
                "required_score": "400",
                "caller_identity": caller_identity,
            }
            if species_id:
                partner_data["species"] = str(species_id)

            partner_res = await self._post(
                f"{self.BASE_URL}/json/interaction_partners", data=partner_data
            )
            partners = self._safe_json(partner_res)
            if not isinstance(partners, list):
                return records

            for p in partners:
                if not isinstance(p, dict):
                    continue
                p_a = p.get("preferredName_A")
                p_b = p.get("preferredName_B")
                score = float(p.get("score", 0.4))

                if p_a and p_b:
                    records.append(
                        self._make_record(
                            entity_a=p_a,
                            relationship="protein_protein",
                            entity_b=p_b,
                            source_id=f"string_{p_a}_{p_b}",
                            source_score=score,
                            endpoint=f"{self.BASE_URL}/json/interaction_partners",
                            query_context={"targets": clean_targets, "species": species},
                            metadata=p,
                        )
                    )
        except httpx.HTTPError as e:
            logger.warning("HTTP Error querying STRING DB: %s", e)
        except Exception as e:
            logger.warning("Error querying STRING DB: %s", e)

        return records
