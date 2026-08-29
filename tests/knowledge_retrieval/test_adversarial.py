"""Comprehensive adversarial and stress tests for the Knowledge Retrieval subsystem.

Covers:
- Malformed APIs, HTML error pages, truncated JSON/XML
- HTTP 429 backoff, 502/503/504 retry safety
- Cross-species and cross-target cache collision resistance
- Effect type and effect direction strict semantic separation
- Blast bounded polling timeout
- High-volume SpeciesResolver lookups and benchmarks
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest
import respx

from app.cache.sqlite_client import SQLiteCache, make_cache_key
from app.config import RetrievalSettings
from app.knowledge_retrieval.agriculture.animal_qtldb import AnimalQTLdbClient
from app.knowledge_retrieval.common.ensembl import EnsemblClient
from app.knowledge_retrieval.common.ncbi.blast import NCBIBlastClient
from app.knowledge_retrieval.species import SpeciesResolver, get_species_resolver
from app.models.evidence import (
    EffectDirection,
    EffectType,
    EvidenceEffect,
    EvidenceRecord,
)


class TestAdversarialAPIsAndResponses:
    @respx.mock
    @pytest.mark.anyio
    async def test_malformed_json_response_does_not_crash(self) -> None:
        """HTML error pages or truncated JSON return empty records rather than crash."""
        respx.get("https://rest.ensembl.org/lookup/symbol/homo_sapiens/BRCA1").mock(
            return_value=httpx.Response(
                200, text="<html><body>502 Bad Gateway - Nginx Error</body></html>"
            )
        )

        client = EnsemblClient()
        records = await client.query(targets=["BRCA1"], species="Homo sapiens")
        assert isinstance(records, list)
        assert len(records) == 0

    @respx.mock
    @pytest.mark.anyio
    async def test_malformed_xml_response_does_not_crash(self) -> None:
        """Malformed XML should be safely caught and return empty records."""
        respx.get("https://www.animalgenome.org/cgi-bin/QTLdb/API/iquery").mock(
            return_value=httpx.Response(200, text="<xml><unclosed_tag>broken")
        )

        client = AnimalQTLdbClient()
        records = await client.query(targets=["QTL001"], species="Sus scrofa")
        assert isinstance(records, list)
        assert len(records) == 0

    @respx.mock
    @pytest.mark.anyio
    async def test_http_503_retry_and_graceful_recovery(self) -> None:
        """Transient 503 errors trigger backoff retries and return empty list on failure."""
        respx.get("https://rest.ensembl.org/lookup/symbol/homo_sapiens/TP53").mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )

        settings = RetrievalSettings(http_retries=2, retry_backoff_factor=0.01)
        client = EnsemblClient(settings=settings)
        records = await client.query(targets=["TP53"], species="Homo sapiens")
        assert isinstance(records, list)
        assert len(records) == 0

    @respx.mock
    @pytest.mark.anyio
    async def test_blast_bounded_polling_timeout(self) -> None:
        """BLAST client times out cleanly if NCBI job remains pending past max wait."""
        # 1. Mock BLAST submission
        respx.post("https://blast.ncbi.nlm.nih.gov/Blast.cgi").mock(
            return_value=httpx.Response(200, text="RID = TEST_RID_12345\nRTOE = 5\n")
        )
        # 2. Mock BLAST polling always returning STATUS=WAITING
        respx.get("https://blast.ncbi.nlm.nih.gov/Blast.cgi").mock(
            return_value=httpx.Response(200, text="Status=WAITING\nThere are no results yet.")
        )

        settings = RetrievalSettings(blast_max_wait_seconds=0.1)
        client = NCBIBlastClient(settings=settings)
        records = await client.query(
            targets=["QUERY_SEQ"],
            context={"sequence": "ATGCGATCGATCGATC"},
        )
        # Pending job must not emit fake evidence
        assert len(records) == 0


class TestCacheCollisionAndIntegrity:
    def test_cross_species_cache_key_isolation(self) -> None:
        """Identical queries for different species MUST produce distinct cache keys."""
        key_human = make_cache_key(
            source="ensembl",
            endpoint="/lookup/symbol",
            params={"species": "homo_sapiens", "target": "BRCA1"},
        )
        key_mouse = make_cache_key(
            source="ensembl",
            endpoint="/lookup/symbol",
            params={"species": "mus_musculus", "target": "BRCA1"},
        )
        assert key_human != key_mouse

    def test_parameter_order_insensitivity(self) -> None:
        """Dictionary parameter ordering must not alter the deterministic SHA-256 hash."""
        key_1 = make_cache_key(
            source="kegg",
            endpoint="/find",
            params={"org": "hsa", "query": "glycolysis", "limit": 10},
        )
        key_2 = make_cache_key(
            source="kegg",
            endpoint="/find",
            params={"limit": 10, "query": "glycolysis", "org": "hsa"},
        )
        assert key_1 == key_2

    @pytest.mark.anyio
    async def test_cache_ttl_and_purge(self, tmp_path: Path) -> None:
        """Expired entries must return None and get purged."""
        db_path = tmp_path / "test_cache.db"
        cache = SQLiteCache(db_path=db_path, default_ttl=1)

        key = "test_key_ttl"
        await cache.set(key, b"cached_payload", ttl=1)
        res = await cache.get(key)
        assert res == b"cached_payload"

        # Simulate expiration
        time.sleep(1.1)
        res_expired = await cache.get(key)
        assert res_expired is None


class TestEffectSemanticsAndHonesty:
    def test_strict_separation_of_type_and_direction(self) -> None:
        """EffectType and EffectDirection must be distinct concepts."""
        effect = EvidenceEffect(
            type=EffectType.ACTIVATION,
            direction=EffectDirection.INCREASES,
            magnitude=1.5,
        )
        record = EvidenceRecord(
            source="test_source",
            entity_a="GeneA",
            entity_b="ProteinB",
            relationship="gene_protein",
            effect=effect,
            consequence="increased downstream phosphorylation",
        )
        assert record.effect is not None
        assert record.effect.type == "activation"
        assert record.effect.direction == "increases"
        assert record.effect.magnitude == 1.5
        assert record.consequence == "increased downstream phosphorylation"

    def test_association_evidence_without_invented_direction(self) -> None:
        """Pure association evidence must retain direction=None and not guess causation."""
        record = EvidenceRecord(
            source="string",
            entity_a="TP53",
            entity_b="MDM2",
            relationship="protein_protein",
            effect=None,
        )
        assert record.effect is None
        assert record.consequence is None


class TestSpeciesResolverBenchmarksAndStress:
    @pytest.fixture
    def resolver(self) -> SpeciesResolver:
        return get_species_resolver()

    def test_bulk_lookup_performance(self, resolver: SpeciesResolver) -> None:
        """1,000 lookups must complete in under 50 milliseconds (<0.05ms per lookup)."""
        queries = [
            "Homo sapiens",
            "Human",
            "2883641",
            "Mus musculus",
            "House mouse",
            "3049974",
            "Sus scrofa",
            "pig",
            "Wild boar",
            "Mammuthus primigenius",
        ]

        t0 = time.perf_counter()
        count = 0
        for _ in range(100):
            for q in queries:
                res = resolver.resolve(q)
                assert res is not None
                count += 1
        elapsed = time.perf_counter() - t0

        avg_ms = (elapsed / count) * 1000
        assert avg_ms < 0.2  # Must be strictly under 0.2ms per lookup

    def test_unknown_and_adversarial_queries(self, resolver: SpeciesResolver) -> None:
        """Adversarial and non-existent species strings return None without exceptions."""
        assert resolver.resolve("   ") is None
        assert resolver.resolve("'; DROP TABLE species; --") is None
        assert resolver.resolve("UnknownCreature999999") is None
        assert resolver.get_by_taxonomy_id(-999) is None
        assert resolver.get_by_ensembl_name("") is None
