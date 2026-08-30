"""Tests for AnimalQTLdbClient defensive XML handling."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.knowledge_retrieval.agriculture.animal_qtldb import AnimalQTLdbClient


class TestAnimalQTLdbClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_valid_xml_response(self) -> None:
        client = AnimalQTLdbClient()
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <QTLdb>
            <QTL id="12345">
                <trait>Milk yield</trait>
            </QTL>
        </QTLdb>"""

        respx.get("https://www.animalgenome.org/cgi-bin/QTLdb/API/iquery").mock(
            return_value=httpx.Response(200, text=xml_content)
        )

        records = await client.query(targets=["DGAT1"], species="Bos taurus")
        assert len(records) == 1
        assert records[0].entity_a == "DGAT1"
        assert records[0].relationship == "gene_qtl"
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_malformed_xml_handling(self) -> None:
        client = AnimalQTLdbClient()
        malformed_xml = "<QTLdb><broken unclosed tag"

        respx.get("https://www.animalgenome.org/cgi-bin/QTLdb/API/iquery").mock(
            return_value=httpx.Response(200, text=malformed_xml)
        )

        records = await client.query(targets=["DGAT1"], species="Bos taurus")
        assert records == []
        await client.close()
