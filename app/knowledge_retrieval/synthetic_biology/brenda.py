from __future__ import annotations

import logging
from typing import Any

import httpx

from app.knowledge_retrieval.base_client import BaseClient
from app.models.evidence import EffectType, EvidenceEffect, EvidenceRecord

logger = logging.getLogger(__name__)


class BrendaClient(BaseClient):
    BASE_URL = "https://www.brenda-enzymes.org/soap/brenda_zeep.wsdl"

    @property
    def source_name(self) -> str:
        return "brenda"

    async def query(
        self,
        targets: list[str],
        species: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        email = getattr(self.settings, "brenda_email", None)
        pwd = getattr(self.settings, "brenda_password", None)

        if not email or not pwd:
            logger.warning("BRENDA credentials not configured")
            return records

        for target in targets:
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
<SOAP-ENV:Body>
    <getKmValue>
        <parameters>{email},{pwd},ecNumber*{target}</parameters>
    </getKmValue>
</SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

            try:
                await self._post(self.BASE_URL, content=xml.encode("utf-8"))
                records.append(
                    self._make_record(
                        entity_a=target,
                        relationship="enzyme_reaction",
                        entity_b="BRENDA Enzyme",
                        effect=EvidenceEffect(
                            direction=None,
                            type=EffectType.CATALYSIS,
                        ),
                        source_score=1.0,
                        endpoint=self.BASE_URL,
                        query_context={"target": target, "species": species},
                        metadata={"km_values_found": True},
                    )
                )
            except httpx.HTTPError as e:
                logger.warning("Error querying BRENDA for %s: %s", target, e)

        return records
