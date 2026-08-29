from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from app.knowledge_retrieval.common.ensembl import EnsemblClient


@pytest.mark.asyncio
async def test_ensembl_query_success() -> None:
    client = EnsemblClient()

    lookup_data = {
        "id": "ENSG00000139618",
        "display_name": "BRCA2",
        "biotype": "protein_coding",
    }
    xrefs_data = [
        {"primary_id": "P51587", "dbname": "UniProtKB/Swiss-Prot"},
        {"primary_id": "GO:0006281", "dbname": "GO", "description": "DNA repair"},
    ]
    phenotype_data = [{"phenotype": "Breast cancer susceptibility", "source": "ClinVar"}]
    homology_data = {
        "data": [
            {
                "homologies": [
                    {
                        "target": {
                            "id": "ENSMUSG00000041147",
                            "species": "mus_musculus",
                            "protein_id": "ENSMUSP00000040778",
                        },
                        "type": "ortholog_one2one",
                    }
                ]
            }
        ]
    }

    async def mock_get(url: str, *args, **kwargs) -> httpx.Response:
        req = httpx.Request("GET", url)
        if "/lookup/symbol/" in url:
            return httpx.Response(200, json=lookup_data, request=req)
        elif "/xrefs/id/" in url:
            return httpx.Response(200, json=xrefs_data, request=req)
        elif "/phenotype/gene/" in url:
            return httpx.Response(200, json=phenotype_data, request=req)
        elif "/homology/symbol/" in url:
            return httpx.Response(200, json=homology_data, request=req)
        return httpx.Response(404, request=req)

    with patch.object(client, "_get", side_effect=mock_get):
        records = await client.query(targets=["BRCA2"], species="homo_sapiens")

    assert len(records) > 0
    relationships = {r.relationship for r in records}
    expected = {"gene_pathway", "gene_phenotype", "gene_orthology"}
    assert bool(relationships & expected)
    await client.close()
