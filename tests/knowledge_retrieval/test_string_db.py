"""Tests for StringDbClient using mocked HTTP responses."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from app.knowledge_retrieval.common.string_db import StringDbClient


@pytest.mark.asyncio
async def test_string_db_query_success() -> None:
    client = StringDbClient()

    string_ids_resp = [
        {
            "queryIndex": 0,
            "queryItem": "BRCA1",
            "stringId": "9606.ENSP00000350283",
            "preferredName": "BRCA1",
        }
    ]

    partners_resp = [
        {
            "stringId_A": "9606.ENSP00000350283",
            "stringId_B": "9606.ENSP00000269305",
            "preferredName_A": "BRCA1",
            "preferredName_B": "TP53",
            "score": 0.985,
        }
    ]

    async def mock_post(url: str, *args, **kwargs) -> httpx.Response:
        req = httpx.Request("POST", url)
        if "get_string_ids" in url:
            return httpx.Response(200, json=string_ids_resp, request=req)
        elif "interaction_partners" in url:
            return httpx.Response(200, json=partners_resp, request=req)
        return httpx.Response(404, request=req)

    with patch.object(client, "_post", side_effect=mock_post):
        records = await client.query(targets=["BRCA1"], species="9606")

    assert len(records) > 0
    record = records[0]
    assert record.source == "string"
    assert record.entity_a == "BRCA1"
    assert record.entity_b == "TP53"
    assert record.relationship == "protein_protein"
    assert record.source_score == 0.985
    await client.close()
