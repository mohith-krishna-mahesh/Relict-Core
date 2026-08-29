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

        caller_identity = getattr(
            self.settings,
            "string_caller_identity",
            "RelictCore",
        )

        species_id = "9606" if (species == "human" or not species) else species

        try:
            # Map identifiers to STRING IDs.
            data = {
                "identifiers": "\r".join(targets),
                "format": "json",
                "caller_identity": caller_identity,
            }

            if species_id:
                data["species"] = species_id

            map_res = await self._post(
                f"{self.BASE_URL}/json/get_string_ids",
                data=data,
            )

            mapped = map_res.json()

            string_ids = [
                item["stringId"]
                for item in mapped
                if "stringId" in item
            ]

            if not string_ids:
                return records

            # Retrieve interaction partners.
            partner_data = {
                "identifiers": "%0d".join(string_ids),
                "required_score": "400",
                "caller_identity": caller_identity,
            }

            if species_id:
                partner_data["species"] = species_id

            partner_res = await self._post(
                f"{self.BASE_URL}/json/interaction_partners",
                data=partner_data,
            )

            partners = partner_res.json()

            for item in partners:
                score = float(item.get("score", 0.0))

                if score < 0.4:
                    continue

                records.append(
                    self._make_record(
                        entity_a=item.get("preferredName_A", ""),
                        relationship="protein_protein",
                        entity_b=item.get("preferredName_B", ""),
                        source_id=item.get("stringId_A", ""),
                        source_score=score,
                        endpoint="/json/interaction_partners",
                        query_context={
                            "targets": targets,
                            "species": species,
                        },
                        metadata=item,
                    )
                )

        except httpx.HTTPError as exc:
            logger.warning("STRING DB HTTP Error: %s", exc)
        except Exception as exc:
            logger.warning("STRING DB Error: %s", exc)

        return records
