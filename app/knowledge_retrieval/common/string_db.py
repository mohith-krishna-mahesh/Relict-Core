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
        candidate_genes = set(context.get("candidate_genes", [])) if context else set()

        # STRING requires clean gene/protein identifiers
        clean_targets = [
            t
            for t in targets
            if (t in candidate_genes or (t.isupper() and 2 <= len(t) <= 10) or len(t) <= 6)
            and " " not in t
            and t.replace("-", "").replace("_", "").isalnum()
        ]
        if not clean_targets:
            return records

        caller_identity = getattr(self.settings, "string_caller_identity", "RelictCore")
        tax_id = context.get("species_tax_id") if context else None
        species_id = (
            str(tax_id)
            if tax_id and str(tax_id).isdigit()
            else (species if species and str(species).isdigit() else "9606")
        )

        try:
            # 1. Map identifiers to STRING IDs
            data: dict[str, Any] = {
                "identifiers": "\r".join(clean_targets[:5]),
                "format": "json",
                "caller_identity": caller_identity,
                "species": str(species_id),
            }

            map_res = await self._post(f"{self.BASE_URL}/json/get_string_ids", data=data)
            mapped = self._safe_json(map_res)
            if not isinstance(mapped, list):
                return records

            string_ids = [m["stringId"] for m in mapped if isinstance(m, dict) and "stringId" in m]
            if not string_ids:
                return records

            # 2. Get interaction partners
            partners_data = {
                "identifiers": "\r".join(string_ids[:5]),
                "species": str(species_id),
                "limit": 5,
                "caller_identity": caller_identity,
            }

            net_res = await self._post(
                f"{self.BASE_URL}/json/interaction_partners", data=partners_data
            )
            interactions = self._safe_json(net_res)
            if isinstance(interactions, list):
                for inter in interactions:
                    if not isinstance(inter, dict):
                        continue
                    p_a = inter.get("preferredName_A")
                    p_b = inter.get("preferredName_B")
                    score = inter.get("score")
                    if p_a and p_b:
                        records.append(
                            self._make_record(
                                entity_a=p_a,
                                relationship="protein_protein",
                                entity_b=p_b,
                                source_id=f"string_{p_a}_{p_b}",
                                source_score=float(score) if score is not None else 1.0,
                                endpoint="/json/interaction_partners",
                                query_context={"identifiers": clean_targets, "species": species_id},
                                metadata=inter,
                            )
                        )

        except httpx.HTTPError as e:
            logger.debug("HTTP Error querying STRING DB: %s", e)
        except Exception as e:
            logger.debug("Error querying STRING DB: %s", e)

        return records
