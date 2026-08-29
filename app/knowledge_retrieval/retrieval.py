from __future__ import annotations

import logging
from typing import Any

import anyio

from app.config import RetrievalSettings
from app.knowledge_retrieval.agriculture.animal_qtldb import AnimalQTLdbClient
from app.knowledge_retrieval.agriculture.epidb import EpiDBClient
from app.knowledge_retrieval.agriculture.faang import FAANGClient
from app.knowledge_retrieval.agriculture.farmgtex import FarmGTExClient
from app.knowledge_retrieval.agriculture.gramene import GrameneClient
from app.knowledge_retrieval.agriculture.plant_reactome import PlantReactomeClient
from app.knowledge_retrieval.base_client import BaseClient, CacheProtocol, NullCache
from app.knowledge_retrieval.common.ensembl import EnsemblClient
from app.knowledge_retrieval.common.gbif import GBIFClient
from app.knowledge_retrieval.common.kegg import KeggClient
from app.knowledge_retrieval.common.ncbi.blast import NCBIBlastClient
from app.knowledge_retrieval.common.ncbi.datasets_v2 import NCBIDatasetsV2Client
from app.knowledge_retrieval.common.ncbi.eutils import NCBIeUtilsClient
from app.knowledge_retrieval.common.ncbi.pmc import NCBIpmcClient
from app.knowledge_retrieval.common.rcsb_pdb import RCSBPDBClient
from app.knowledge_retrieval.common.reactome import ReactomeClient
from app.knowledge_retrieval.common.string_db import StringDbClient
from app.knowledge_retrieval.common.timetree import TimeTreeClient
from app.knowledge_retrieval.common.uniprot import UniprotClient
from app.knowledge_retrieval.common.wikipathways import WikiPathwaysClient
from app.knowledge_retrieval.conservation.dna_zoo import DNAZooClient as ConservationDNAZoo
from app.knowledge_retrieval.conservation.genome10k import (
    Genome10KClient as ConservationGenome10K,
)
from app.knowledge_retrieval.conservation.vgp import VGPClient as ConservationVGP
from app.knowledge_retrieval.de_extinction.dna_zoo import DNAZooClient as DeExtinctionDNAZoo
from app.knowledge_retrieval.de_extinction.genome10k import (
    Genome10KClient as DeExtinctionGenome10K,
)
from app.knowledge_retrieval.de_extinction.vgp import VGPClient as DeExtinctionVGP
from app.knowledge_retrieval.population_control.vectorbase import VectorBaseClient
from app.knowledge_retrieval.precision_medicine.alphamissense import AlphaMissenseClient
from app.knowledge_retrieval.precision_medicine.chembl import ChemblClient
from app.knowledge_retrieval.precision_medicine.gnomad import GnomadClient
from app.knowledge_retrieval.precision_medicine.gtex import GTExClient
from app.knowledge_retrieval.precision_medicine.hpa import HPAClient
from app.knowledge_retrieval.precision_medicine.opentargets import OpenTargetsClient
from app.knowledge_retrieval.registry import get_sources_for_scope
from app.knowledge_retrieval.synthetic_biology.brenda import BrendaClient
from app.knowledge_retrieval.synthetic_biology.sabio_rk import SabioRkClient
from app.knowledge_retrieval.synthetic_biology.synbiohub import SynBioHubClient
from app.models.evidence import EvidenceRecord
from app.models.failures import FailureCode
from app.models.requests import RetrievalContext
from app.models.responses import RetrievalResult, SourceStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client factory — maps source names to client classes
# ---------------------------------------------------------------------------

_CLIENT_REGISTRY: dict[str, type[BaseClient]] = {
    # Common
    "ensembl": EnsemblClient,
    "ncbi_eutils": NCBIeUtilsClient,
    "ncbi_datasets": NCBIDatasetsV2Client,
    "ncbi_blast": NCBIBlastClient,
    "ncbi_pmc": NCBIpmcClient,
    "string": StringDbClient,
    "kegg": KeggClient,
    "uniprot": UniprotClient,
    "reactome": ReactomeClient,
    "wikipathways": WikiPathwaysClient,
    "rcsb_pdb": RCSBPDBClient,
    "gbif": GBIFClient,
    "timetree": TimeTreeClient,
    # Conservation
    "conservation_dna_zoo": ConservationDNAZoo,
    "conservation_vgp": ConservationVGP,
    "conservation_genome10k": ConservationGenome10K,
    # De-Extinction
    "de_extinction_dna_zoo": DeExtinctionDNAZoo,
    "de_extinction_vgp": DeExtinctionVGP,
    "de_extinction_genome10k": DeExtinctionGenome10K,
    # Agriculture
    "gramene": GrameneClient,
    "plant_reactome": PlantReactomeClient,
    "animal_qtldb": AnimalQTLdbClient,
    "faang": FAANGClient,
    "farmgtex": FarmGTExClient,
    "epidb": EpiDBClient,
    # Synthetic Biology
    "brenda": BrendaClient,
    "sabio_rk": SabioRkClient,
    "synbiohub": SynBioHubClient,
    # Population Control
    "vectorbase": VectorBaseClient,
    # Precision Medicine
    "alphamissense": AlphaMissenseClient,
    "opentargets": OpenTargetsClient,
    "chembl": ChemblClient,
    "hpa": HPAClient,
    "gtex": GTExClient,
    "gnomad": GnomadClient,
}


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def deduplicate(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    """Conservative evidence deduplication.

    Two records are duplicates only when their source, source_id,
    entity_a, entity_b, and relationship are all identical.

    Evidence from different sources is NEVER merged.
    """
    seen: set[tuple[str, str | None, str, str | None, str]] = set()
    unique: list[EvidenceRecord] = []
    for r in records:
        key = (r.source, r.source_id, r.entity_a, r.entity_b, r.relationship)
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


# ---------------------------------------------------------------------------
# Retrieval orchestrator
# ---------------------------------------------------------------------------


class RetrievalOrchestrator:
    """Orchestrates Knowledge Retrieval for a single run.

    Workflow:
    1. Resolve scope → permitted sources via registry.
    2. Map retrieval targets to source-specific queries.
    3. Invoke source clients concurrently.
    4. Collect and deduplicate EvidenceRecord[].
    5. Evaluate aggregate sufficiency.
    6. Return RetrievalResult.
    """

    def __init__(
        self,
        settings: RetrievalSettings | None = None,
        cache: CacheProtocol | None = None,
    ) -> None:
        self.settings = settings or RetrievalSettings()
        self.cache = cache or NullCache()

    async def retrieve(self, ctx: RetrievalContext) -> RetrievalResult:
        """Execute retrieval for the given context."""
        scope = ctx.project_context.scope
        species = ctx.project_context.species
        permitted = get_sources_for_scope(scope)

        # Build retrieval targets from the structured objective
        targets = self._build_targets(ctx)
        if not targets:
            return RetrievalResult(
                failure_code=FailureCode.INSUFFICIENT_EVIDENCE,
                source_statuses=[],
            )

        # Build context dict for source clients
        query_context = self._build_query_context(ctx)

        # Instantiate permitted source clients
        clients: list[tuple[str, BaseClient]] = []
        for source_name in permitted:
            client_cls = _CLIENT_REGISTRY.get(source_name)
            if client_cls is None:
                logger.warning("No client registered for source: %s", source_name)
                continue
            clients.append(
                (source_name, client_cls(settings=self.settings, cache=self.cache))
            )

        # Run all source queries concurrently
        all_records: list[EvidenceRecord] = []
        statuses: list[SourceStatus] = []

        async def _query_source(
            name: str, client: BaseClient
        ) -> tuple[str, list[EvidenceRecord], SourceStatus]:
            try:
                records = await client.query(
                    targets=targets, species=species, context=query_context
                )
                status = SourceStatus(
                    source_name=name,
                    success=True,
                    record_count=len(records),
                )
                return name, records, status
            except Exception as exc:
                logger.warning("Source %s failed: %s", name, exc, exc_info=True)
                status = SourceStatus(
                    source_name=name,
                    success=False,
                    error_message=str(exc),
                )
                return name, [], status
            finally:
                await client.close()

        results: list[tuple[str, list[EvidenceRecord], SourceStatus]] = []
        concurrency = self.settings.max_concurrency

        async with anyio.create_task_group() as tg:
            limiter = anyio.CapacityLimiter(concurrency)

            async def _run_limited(name: str, client: BaseClient) -> None:
                async with limiter:
                    res = await _query_source(name, client)
                    results.append(res)

            for source_name, client in clients:
                tg.start_soon(_run_limited, source_name, client)

        for _name, records, status in results:
            all_records.extend(records)
            statuses.append(status)

        # Deduplicate
        deduped = deduplicate(all_records)

        # Evaluate aggregate sufficiency
        failure_code: FailureCode | None = None
        if len(deduped) < self.settings.min_evidence_records:
            failure_code = FailureCode.INSUFFICIENT_EVIDENCE

        return RetrievalResult(
            records=deduped,
            source_statuses=statuses,
            failure_code=failure_code,
        )

    def _build_targets(self, ctx: RetrievalContext) -> list[str]:
        """Assemble retrieval targets from the context."""
        targets: list[str] = []

        # Explicit retrieval targets from the structured objective
        targets.extend(ctx.structured_objective.retrieval_targets)

        # Candidate genes from the run configuration
        targets.extend(ctx.run_configuration.candidate_genes)

        # Biological processes and relevant concepts as secondary targets
        targets.extend(ctx.structured_objective.biological_processes)
        targets.extend(ctx.structured_objective.relevant_concepts)
        targets.extend(ctx.structured_objective.target_phenotypes)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for t in targets:
            t_lower = t.strip().lower()
            if t_lower and t_lower not in seen:
                seen.add(t_lower)
                unique.append(t.strip())
        return unique

    def _build_query_context(self, ctx: RetrievalContext) -> dict[str, Any]:
        """Build a context dict that source clients can use."""
        return {
            "project_id": ctx.project_context.project_id,
            "scope": ctx.project_context.scope.value,
            "species": ctx.project_context.species,
            "objective": ctx.project_context.objective,
            "desired_change": ctx.structured_objective.desired_change,
            "biological_processes": ctx.structured_objective.biological_processes,
            "target_phenotypes": ctx.structured_objective.target_phenotypes,
            "retrieval_targets": ctx.structured_objective.retrieval_targets,
            "candidate_genes": ctx.run_configuration.candidate_genes,
            "constraints": ctx.run_configuration.constraints,
        }
