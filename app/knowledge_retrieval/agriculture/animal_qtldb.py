from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


class AnimalQTLdbClient(BaseClient):
    BASE_URL = "https://www.animalgenome.org/cgi-bin/QTLdb/API"

    @property
    def source_name(self) -> str:
        return "animal_qtldb"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []

        for target in targets:
            url = f"{self.BASE_URL}/iquery"
            params = {"q": target, "s": "QTL"}

            try:
                response = await self._get(url, params=params)
                try:
                    root = ET.fromstring(response.text)
                    count = len(root.findall(".//QTL"))
                    if count > 0:
                        records.append(
                            self._make_record(
                                entity_a=target,
                                relationship="gene_qtl",
                                entity_b="AnimalQTL",
                                source_id=f"qtldb_{target}",
                                source_score=1.0,
                                endpoint=url,
                                query_context={"target": target, "species": species},
                                metadata={"count": count},
                            )
                        )
                except ET.ParseError:
                    logger.warning(f"Failed to parse XML from AnimalQTLdb for {target}")

            except httpx.HTTPError as e:
                logger.warning(f"Error querying AnimalQTLdb for {target}: {e}")

        return records
