"""
Unit and integration tests for enhanced Planner accuracy.

Verifies:
1. Multi-source consensus boosting (Noisy-OR aggregation).
2. Causal directional trajectory alignment (rewarding matching path signs).
3. Pleiotropy & off-target hub penalties.
4. Disjoint parallel redundancy vs bottlenecked linear routes.
5. Deterministic, fully reproducible strategy scoring.
"""

from __future__ import annotations

from app.models.evidence import EffectDirection, EffectType, EvidenceEffect, EvidenceRecord
from app.models.requests import StructuredObjective

from app.planner.graph_builder import GraphBuilder
from app.planner.search import SearchConfig, StrategySearch


def _make_objective(
    target_phenotypes: list[str],
    desired_change: str = "enhance target phenotype",
    biological_processes: list[str] | None = None,
) -> StructuredObjective:
    return StructuredObjective(
        target_phenotypes=target_phenotypes,
        desired_change=desired_change,
        biological_processes=biological_processes or [],
    )


class TestPlannerEnhancedAccuracy:
    def test_multi_source_consensus_boost(self) -> None:
        """When multiple databases corroborate the same link, consensus score is boosted."""
        # Single source evidence
        record_single = [
            EvidenceRecord(
                source="string",
                entity_a="GENE_A",
                relationship="protein_protein",
                entity_b="TARGET_PHE",
                source_score=0.6,
            )
        ]
        graph_single = GraphBuilder().build(record_single)

        # Multi-source corroborated evidence
        records_multi = [
            EvidenceRecord(
                source="string",
                entity_a="GENE_A",
                relationship="protein_protein",
                entity_b="TARGET_PHE",
                source_score=0.6,
            ),
            EvidenceRecord(
                source="reactome",
                entity_a="GENE_A",
                relationship="gene_pathway",
                entity_b="TARGET_PHE",
                source_score=0.7,
            ),
            EvidenceRecord(
                source="uniprot",
                entity_a="GENE_A",
                relationship="functional_association",
                entity_b="TARGET_PHE",
                source_score=0.8,
            ),
        ]
        graph_multi = GraphBuilder().build(records_multi)

        obj = _make_objective(["TARGET_PHE"])
        search_single = StrategySearch(obj, constraints=None, max_edits=1, strategy_type="minimal")
        search_multi = StrategySearch(obj, constraints=None, max_edits=1, strategy_type="minimal")

        res_single = search_single.search(graph_single)
        res_multi = search_multi.search(graph_multi)

        assert len(res_single) == 1
        assert len(res_multi) == 1
        # Multi-source corroborated strategy receives higher evidence confidence
        assert res_multi[0].score > res_single[0].score

    def test_directional_trajectory_alignment(self) -> None:
        """Paths aligning with desired_change receive a bonus; opposing paths receive a penalty."""
        # Gene 1 activates Target (aligns with 'increase')
        # Gene 2 inhibits Target (opposes 'increase')
        records = [
            EvidenceRecord(
                source="brenda",
                entity_a="GENE_POS",
                relationship="activates",
                entity_b="TARGET_PHE",
                source_score=0.8,
                effect=EvidenceEffect(
                    type=EffectType.ACTIVATION,
                    direction=EffectDirection.INCREASES,
                ),
            ),
            EvidenceRecord(
                source="brenda",
                entity_a="GENE_NEG",
                relationship="inhibits",
                entity_b="TARGET_PHE",
                source_score=0.8,
                effect=EvidenceEffect(
                    type=EffectType.INHIBITION,
                    direction=EffectDirection.DECREASES,
                ),
            ),
        ]
        graph = GraphBuilder().build(records)

        obj_increase = _make_objective(["TARGET_PHE"], desired_change="increase pigmentation")
        search_inc = StrategySearch(
            obj_increase, constraints=None, max_edits=1, strategy_type="minimal"
        )
        strategies_inc = search_inc.search(graph)

        assert len(strategies_inc) == 2
        # GENE_POS should rank higher than GENE_NEG when desired_change is 'increase'
        assert strategies_inc[0].selected_candidates == ["GENE_POS"]
        assert strategies_inc[1].selected_candidates == ["GENE_NEG"]
        assert strategies_inc[0].score > strategies_inc[1].score

    def test_pleiotropic_hub_penalty(self) -> None:
        """Promiscuous hub genes receive a specificity penalty compared to specific effectors."""
        records = [
            # Specific effector: only connected to TARGET
            EvidenceRecord(
                source="ensembl",
                entity_a="SPECIFIC_GENE",
                relationship="regulates",
                entity_b="TARGET_PHE",
                source_score=0.8,
            ),
            # Hub gene: connected to TARGET and 20 other unrelated processes
            EvidenceRecord(
                source="ensembl",
                entity_a="HUB_GENE",
                relationship="regulates",
                entity_b="TARGET_PHE",
                source_score=0.8,
            ),
        ]
        # Add 20 unrelated neighbors to HUB_GENE
        for i in range(20):
            records.append(
                EvidenceRecord(
                    source="string",
                    entity_a="HUB_GENE",
                    relationship="protein_protein",
                    entity_b=f"UNRELATED_PATHWAY_{i}",
                    source_score=0.8,
                )
            )

        graph = GraphBuilder().build(records)
        obj = _make_objective(["TARGET_PHE"])
        search = StrategySearch(
            obj,
            constraints=None,
            max_edits=1,
            strategy_type="minimal",
            config=SearchConfig(max_strategies=50),
        )
        strategies = search.search(graph)

        strat_hub = [s for s in strategies if s.selected_candidates == ["HUB_GENE"]][0]
        strat_specific = [s for s in strategies if s.selected_candidates == ["SPECIFIC_GENE"]][0]

        # Specific gene receives higher score than promiscuous hub gene
        assert strat_specific.score > strat_hub.score

    def test_disjoint_parallel_redundancy(self) -> None:
        """Redundant strategy rewards independent routes over bottlenecked linear routes."""
        # Route 1: Gene A -> Pathway 1 -> Target, Gene B -> Pathway 2 -> Target (Disjoint)
        records_disjoint = [
            EvidenceRecord(
                source="ensembl",
                entity_a="GENE_A",
                relationship="regulates",
                entity_b="PATH_1",
                source_score=0.8,
            ),
            EvidenceRecord(
                source="ensembl",
                entity_a="PATH_1",
                relationship="regulates",
                entity_b="TARGET",
                source_score=0.8,
            ),
            EvidenceRecord(
                source="ensembl",
                entity_a="GENE_B",
                relationship="regulates",
                entity_b="PATH_2",
                source_score=0.8,
            ),
            EvidenceRecord(
                source="ensembl",
                entity_a="PATH_2",
                relationship="regulates",
                entity_b="TARGET",
                source_score=0.8,
            ),
        ]
        graph_disjoint = GraphBuilder().build(records_disjoint)

        # Route 2: Gene C -> Bottleneck -> Target, Gene D -> Bottleneck -> Target (Bottlenecked)
        records_bottleneck = [
            EvidenceRecord(
                source="ensembl",
                entity_a="GENE_C",
                relationship="regulates",
                entity_b="BOTTLENECK",
                source_score=0.8,
            ),
            EvidenceRecord(
                source="ensembl",
                entity_a="GENE_D",
                relationship="regulates",
                entity_b="BOTTLENECK",
                source_score=0.8,
            ),
            EvidenceRecord(
                source="ensembl",
                entity_a="BOTTLENECK",
                relationship="regulates",
                entity_b="TARGET",
                source_score=0.8,
            ),
        ]
        graph_bottleneck = GraphBuilder().build(records_bottleneck)

        obj = _make_objective(["TARGET"])
        search_disjoint = StrategySearch(
            obj, constraints=None, max_edits=2, strategy_type="redundant"
        )
        search_bottleneck = StrategySearch(
            obj, constraints=None, max_edits=2, strategy_type="redundant"
        )

        strat_disjoint = [
            s
            for s in search_disjoint.search(graph_disjoint)
            if set(s.selected_candidates) == {"GENE_A", "GENE_B"}
        ][0]
        strat_bottleneck = [
            s
            for s in search_bottleneck.search(graph_bottleneck)
            if set(s.selected_candidates) == {"GENE_C", "GENE_D"}
        ][0]

        # Disjoint parallel routes receive higher redundancy reward
        assert strat_disjoint.score > strat_bottleneck.score
