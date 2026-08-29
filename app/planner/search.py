from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

import networkx as nx

try:
    from app.planner.constraints import ConstraintEvaluator, ConstraintResult
    from app.planner.graph_builder import EvidenceGraph
except ImportError:
    from constraints import ConstraintEvaluator, ConstraintResult  # type: ignore[no-redef]
    from graph_builder import EvidenceGraph  # type: ignore[no-redef]

# =============================================================================
# Strategy model
# =============================================================================


@dataclass
class Strategy:
    """
    One feasible planner strategy.

    selected_candidates:
        The entities selected from the evidence graph.

    covered_targets:
        Objective concepts directly or indirectly connected to the selected
        candidates.

    edit_count:
        Number of selected candidates.

    score:
        Overall deterministic strategy score.

    supporting_edges:
        Evidence supporting the strategy.

    conflicting_edges:
        Evidence conflicting with the strategy or its constraints.

    uncertainty:
        A normalized qualitative evidence uncertainty estimate.

    rationale:
        Human-readable deterministic explanation of why this strategy
        was produced.
    """

    strategy_type: str

    selected_candidates: list[str]

    covered_targets: list[str]

    edit_count: int

    score: float

    supporting_edges: list[Any] = field(default_factory=list)

    conflicting_edges: list[Any] = field(default_factory=list)

    uncertainty: str = "unknown"

    uncertainty_score: float = 0.0

    rationale: str = ""


# =============================================================================
# Search configuration
# =============================================================================


@dataclass(frozen=True)
class SearchConfig:
    """
    Search behaviour configuration.

    max_strategies:
        Maximum number of feasible strategies returned.

    max_candidate_pool:
        Prevents combinatorial explosion when the graph contains many
        candidate entities.

    max_target_distance:
        Maximum graph distance used when determining whether a candidate
        can cover an objective target.

    Objective target nodes are distance 0.

    Directly connected nodes are distance 1.

    Example:

        GeneA -> Process -> Target

    GeneA has graph distance 2 from Target.
    """

    max_strategies: int = 10

    max_candidate_pool: int = 30

    max_target_distance: int = 2


# =============================================================================
# Search engine
# =============================================================================


class StrategySearch:
    """
    Deterministic strategy search over an EvidenceGraph.

    The search process is:

        1. Extract objective concepts.
        2. Locate corresponding graph nodes.
        3. Identify candidate entities near those targets.
        4. Rank candidates by evidence relevance.
        5. Generate combinations up to max_edits.
        6. Evaluate each combination.
        7. Reject combinations violating hard constraints.
        8. Score feasible strategies.
        9. Return multiple strategies ranked by score.

    The implementation intentionally keeps search deterministic.
    """

    def __init__(
        self,
        objective: Any,
        constraints: Iterable[Any] | None,
        max_edits: int,
        strategy_type: str,
        config: SearchConfig | None = None,
    ) -> None:

        if max_edits < 1:
            raise ValueError("max_edits must be at least 1.")

        strategy_type = str(strategy_type).strip().lower()

        if strategy_type not in {
            "minimal",
            "redundant",
        }:
            raise ValueError("strategy_type must be either 'minimal' or 'redundant'.")

        self.objective = objective

        self.max_edits = max_edits

        self.strategy_type = strategy_type

        self.config = config or SearchConfig()

        self.constraint_evaluator = ConstraintEvaluator(constraints)

    # =========================================================================
    # Public API
    # =========================================================================

    def search(
        self,
        evidence_graph: EvidenceGraph,
    ) -> list[Strategy]:
        """
        Generate multiple feasible strategies.

        Returns
        -------
        list[Strategy]

        Sorted from highest score to lowest score.
        """

        graph = evidence_graph.networkx_graph

        if graph.number_of_nodes() == 0:
            return []

        objective_terms = self._extract_objective_terms()

        if not objective_terms:
            return []

        target_nodes = self._find_target_nodes(
            graph=graph,
            objective_terms=objective_terms,
        )

        if not target_nodes:
            return []

        candidate_nodes = self._identify_candidates(
            graph=graph,
            target_nodes=target_nodes,
        )

        if not candidate_nodes:
            return []

        candidate_nodes = self._limit_candidate_pool(
            graph=graph,
            candidates=candidate_nodes,
            target_nodes=target_nodes,
        )

        strategies: list[Strategy] = []

        # ---------------------------------------------------------------------
        # Generate candidate combinations.
        #
        # For max_edits = 3:
        #
        # [A]
        # [B]
        # [C]
        #
        # [A, B]
        # [A, C]
        # [B, C]
        #
        # [A, B, C]
        # ---------------------------------------------------------------------

        maximum_size = min(
            self.max_edits,
            len(candidate_nodes),
        )

        for edit_count in range(
            1,
            maximum_size + 1,
        ):
            for combination in combinations(
                candidate_nodes,
                edit_count,
            ):
                strategy = self._evaluate_combination(
                    graph=graph,
                    selected_candidates=list(combination),
                    target_nodes=target_nodes,
                    objective_terms=objective_terms,
                )

                if strategy is None:
                    continue

                strategies.append(strategy)

        strategies = self._deduplicate_strategies(strategies)

        strategies.sort(
            key=self._strategy_sort_key,
            reverse=True,
        )

        return strategies[: self.config.max_strategies]

    # =========================================================================
    # Objective extraction
    # =========================================================================

    def _extract_objective_terms(
        self,
    ) -> set[str]:
        """
        Extract all graph-relevant concepts from StructuredObjective.

        Expected fields:

            target_phenotypes
            biological_processes
            relevant_concepts
            desired_change

        desired_change is included separately in scoring and rationale.

        The actual target nodes are primarily derived from:

            target_phenotypes
            biological_processes
            relevant_concepts
        """

        terms: set[str] = set()

        for field_name in (
            "target_phenotypes",
            "biological_processes",
            "relevant_concepts",
        ):
            value = self._get_field(
                self.objective,
                field_name,
                [],
            )

            terms.update(self._normalize_terms(value))

        return terms

    def _get_desired_change(
        self,
    ) -> str | None:

        value = self._get_field(
            self.objective,
            "desired_change",
            None,
        )

        if value is None:
            return None

        value = str(value).strip()

        return value or None

    # =========================================================================
    # Target identification
    # =========================================================================

    def _find_target_nodes(
        self,
        graph: nx.MultiDiGraph,
        objective_terms: set[str],
    ) -> set[str]:
        """
        Find graph nodes matching objective concepts.

        Matching is deterministic and case-insensitive.

        Exact matches are preferred.

        A limited substring match is also supported because an objective
        concept may be represented with slightly more context in the graph.
        """

        targets: set[str] = set()

        normalized_terms = {term.lower() for term in objective_terms}

        for node in graph.nodes:
            node_text = str(node).strip().lower()

            if node_text in normalized_terms:
                targets.add(str(node))
                continue

            for term in normalized_terms:
                if not term:
                    continue

                if term in node_text:
                    targets.add(str(node))
                    break

        return targets

    # =========================================================================
    # Candidate identification
    # =========================================================================

    def _identify_candidates(
        self,
        graph: nx.MultiDiGraph,
        target_nodes: set[str],
    ) -> set[str]:
        """
        Identify entities that can participate in a strategy.

        Candidate selection is based on graph proximity.

        A node is considered a candidate when:

            - it is not itself an objective target
            - it lies within max_target_distance of a target

        If node metadata explicitly identifies entity type as a gene,
        those nodes are preferred.

        This avoids guessing entity type from the entity name.
        """

        distances = self._distances_to_targets(
            graph=graph,
            target_nodes=target_nodes,
        )

        nearby_nodes = {
            node
            for node, distance in distances.items()
            if (node not in target_nodes and distance <= self.config.max_target_distance)
        }

        typed_gene_candidates = {
            node
            for node in nearby_nodes
            if self._is_gene_node(
                graph,
                node,
            )
        }

        # If explicit gene typing exists, use it.
        if typed_gene_candidates:
            return typed_gene_candidates

        # Otherwise, graph_builder.py has no reliable node type information.
        #
        # In that case we return relevant nearby entities and leave biological
        # interpretation to the evidence available to Search.
        return nearby_nodes

    def _is_gene_node(
        self,
        graph: nx.MultiDiGraph,
        node: str,
    ) -> bool:
        """
        Determine whether upstream metadata explicitly identifies a node
        as a gene.

        No name-based biological guessing is performed.
        """

        data = graph.nodes[node]

        values: list[Any] = []

        values.append(data.get("entity_type"))

        values.append(data.get("type"))

        graph_node = data.get("graph_node")

        if graph_node is not None:
            values.append(
                getattr(
                    graph_node,
                    "entity_type",
                    None,
                )
            )

            metadata = getattr(
                graph_node,
                "metadata",
                {},
            )

            if isinstance(metadata, dict):
                values.extend(
                    [
                        metadata.get("entity_type"),
                        metadata.get("type"),
                    ]
                )

        for value in values:
            if value is None:
                continue

            if str(value).strip().lower() == "gene":
                return True

        return False

    # =========================================================================
    # Candidate pool limiting
    # =========================================================================

    def _limit_candidate_pool(
        self,
        graph: nx.MultiDiGraph,
        candidates: set[str],
        target_nodes: set[str],
    ) -> list[str]:
        """
        Rank candidate entities before exhaustive combination generation.

        This protects search from exploding when many graph nodes exist.
        """

        scored_candidates = []

        for candidate in candidates:
            relevance = self._candidate_relevance_score(
                graph=graph,
                candidate=candidate,
                target_nodes=target_nodes,
            )

            scored_candidates.append(
                (
                    relevance,
                    candidate,
                )
            )

        scored_candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
            ),
            reverse=True,
        )

        return [candidate for _, candidate in scored_candidates[: self.config.max_candidate_pool]]

    def _candidate_relevance_score(
        self,
        graph: nx.MultiDiGraph,
        candidate: str,
        target_nodes: set[str],
    ) -> float:
        """
        Estimate deterministic candidate relevance.

        Score components:

            evidence strength
            proximity to objective targets
            number of targets reachable
        """

        score = 0.0

        for target in target_nodes:
            distance = self._shortest_distance(
                graph,
                candidate,
                target,
            )

            if distance is None:
                continue

            if distance > self.config.max_target_distance:
                continue

            # Closer targets receive more relevance.
            proximity = 1.0 / (distance + 1)

            score += proximity

        # Add evidence strength from directly connected edges.
        for _, _, _, edge_data in self._incident_edges(
            graph,
            candidate,
        ):
            score += self._edge_score(edge_data)

        return score

    # =========================================================================
    # Combination evaluation
    # =========================================================================

    def _evaluate_combination(
        self,
        graph: nx.MultiDiGraph,
        selected_candidates: list[str],
        target_nodes: set[str],
        objective_terms: set[str],
    ) -> Strategy | None:
        """
        Evaluate one candidate combination.

        Returns None when the combination is infeasible.
        """

        # ---------------------------------------------------------------------
        # Evaluate constraints.
        # ---------------------------------------------------------------------

        constraint_result = self.constraint_evaluator.evaluate(
            selected_candidates=selected_candidates,
            graph=graph,
        )

        # Hard constraint violation.
        if not constraint_result.valid:
            return None

        # ---------------------------------------------------------------------
        # Determine target coverage.
        # ---------------------------------------------------------------------

        covered_targets = self._calculate_coverage(
            graph=graph,
            selected_candidates=selected_candidates,
            target_nodes=target_nodes,
        )

        # A strategy that reaches no objective target is not useful.
        if not covered_targets:
            return None

        # ---------------------------------------------------------------------
        # Collect evidence.
        # ---------------------------------------------------------------------

        supporting_edges = self._collect_supporting_edges(
            graph=graph,
            selected_candidates=selected_candidates,
            covered_targets=covered_targets,
        )

        conflicting_edges = list(constraint_result.conflicting_edges)

        # ---------------------------------------------------------------------
        # Score strategy.
        # ---------------------------------------------------------------------

        score = self._score_strategy(
            graph=graph,
            selected_candidates=selected_candidates,
            target_nodes=target_nodes,
            covered_targets=covered_targets,
            supporting_edges=supporting_edges,
            constraint_result=constraint_result,
        )

        # ---------------------------------------------------------------------
        # Uncertainty.
        # ---------------------------------------------------------------------

        uncertainty_score = self._calculate_uncertainty(
            supporting_edges=supporting_edges,
            conflicting_edges=conflicting_edges,
            constraint_result=constraint_result,
        )

        uncertainty = self._uncertainty_label(uncertainty_score)

        rationale = self._build_rationale(
            selected_candidates=selected_candidates,
            covered_targets=covered_targets,
            target_nodes=target_nodes,
            uncertainty=uncertainty,
        )

        return Strategy(
            strategy_type=self.strategy_type,
            selected_candidates=selected_candidates,
            covered_targets=sorted(covered_targets),
            edit_count=len(selected_candidates),
            score=score,
            supporting_edges=supporting_edges,
            conflicting_edges=conflicting_edges,
            uncertainty=uncertainty,
            uncertainty_score=uncertainty_score,
            rationale=rationale,
        )

    # =========================================================================
    # Coverage
    # =========================================================================

    def _calculate_coverage(
        self,
        graph: nx.MultiDiGraph,
        selected_candidates: list[str],
        target_nodes: set[str],
    ) -> set[str]:
        """
        Determine which objective targets are reachable from the selected
        candidate set.

        A target is covered when at least one candidate is connected to it
        within max_target_distance.
        """

        covered: set[str] = set()

        for target in target_nodes:
            for candidate in selected_candidates:
                distance = self._shortest_distance(
                    graph,
                    candidate,
                    target,
                )

                if distance is not None and distance <= self.config.max_target_distance:
                    covered.add(target)
                    break

        return covered

    # =========================================================================
    # Evidence collection
    # =========================================================================

    def _collect_supporting_edges(
        self,
        graph: nx.MultiDiGraph,
        selected_candidates: list[str],
        covered_targets: set[str],
    ) -> list[dict[str, Any]]:
        """
        Collect edges participating in candidate-to-target support.

        Direct candidate edges are always included.

        If a candidate reaches a target through an intermediate node,
        edges along one shortest path are included.
        """

        supporting: list[dict[str, Any]] = []

        seen: set[tuple[Any, Any, Any]] = set()

        for candidate in selected_candidates:
            for target in covered_targets:
                path = self._shortest_path(
                    graph,
                    candidate,
                    target,
                )

                if path is None:
                    continue

                if len(path) - 1 > self.config.max_target_distance:
                    continue

                for source, target_node in zip(
                    path,
                    path[1:],
                    strict=False,
                ):
                    edge_data = self._best_edge_between(
                        graph,
                        source,
                        target_node,
                    )

                    if edge_data is None:
                        continue

                    edge_key = (
                        source,
                        target_node,
                        edge_data.get("_edge_key"),
                    )

                    if edge_key in seen:
                        continue

                    seen.add(edge_key)

                    supporting.append(edge_data)

        return supporting

    # =========================================================================
    # Strategy scoring
    # =========================================================================

    def _score_strategy(
        self,
        graph: nx.MultiDiGraph,
        selected_candidates: list[str],
        target_nodes: set[str],
        covered_targets: set[str],
        supporting_edges: list[dict[str, Any]],
        constraint_result: ConstraintResult,
    ) -> float:
        """
        Calculate deterministic strategy score.

        Components:
            1. Objective coverage
            2. Evidence strength (with multi-source consensus)
            3. Constraint adjustment
            4. Directional trajectory alignment
            5. Pleiotropy & specificity adjustment
            6. Strategy-type preference (with disjoint path redundancy)
        """

        # ---------------------------------------------------------------------
        # 1. Coverage
        # ---------------------------------------------------------------------

        coverage_ratio = len(covered_targets) / len(target_nodes)
        coverage_score = coverage_ratio * 100.0

        # ---------------------------------------------------------------------
        # 2. Evidence strength
        # ---------------------------------------------------------------------

        if supporting_edges:
            evidence_score = sum(self._edge_score(edge) for edge in supporting_edges) / len(
                supporting_edges
            )
            evidence_score *= 25.0
        else:
            evidence_score = 0.0

        # ---------------------------------------------------------------------
        # 3. Constraint score
        # ---------------------------------------------------------------------

        constraint_score = constraint_result.score_adjustment * 10.0

        # ---------------------------------------------------------------------
        # 4. Directional trajectory alignment
        # ---------------------------------------------------------------------

        directional_score = self._evaluate_directional_alignment(
            supporting_edges=supporting_edges,
            desired_change=self._get_desired_change(),
        )

        # ---------------------------------------------------------------------
        # 5. Pleiotropy & Off-target specificity penalty
        # ---------------------------------------------------------------------

        pleiotropy_penalty = self._calculate_pleiotropy_penalty(
            graph=graph,
            selected_candidates=selected_candidates,
            target_nodes=target_nodes,
        )

        # ---------------------------------------------------------------------
        # 6. Strategy preference & Redundancy
        # ---------------------------------------------------------------------

        strategy_adjustment = 0.0

        if self.strategy_type == "minimal":
            # Fewer edits are preferred.
            strategy_adjustment -= len(selected_candidates) * 5.0

        elif self.strategy_type == "redundant":
            # Reward independent, parallel biological routes over single linear bottlenecks.
            strategy_adjustment += self._calculate_redundancy_adjustment(
                graph=graph,
                selected_candidates=selected_candidates,
                covered_targets=covered_targets,
            )

        return (
            coverage_score
            + evidence_score
            + constraint_score
            + directional_score
            - pleiotropy_penalty
            + strategy_adjustment
        )

    def _evaluate_directional_alignment(
        self,
        supporting_edges: list[dict[str, Any]],
        desired_change: str | None,
    ) -> float:
        """
        Evaluate directional alignment between candidate intervention paths
        and objective desired_change.

        Returns:
          +5.0 if directional evidence supports the desired change trajectory
          -10.0 if directional evidence directly opposes the desired change trajectory
          0.0 if neutral or purely associative
        """
        if not desired_change or not supporting_edges:
            return 0.0

        desired_lower = desired_change.lower()
        target_sign = 0
        if any(
            w in desired_lower
            for w in (
                "increase",
                "enhance",
                "higher",
                "up",
                "production",
                "elevate",
                "activate",
                "boost",
            )
        ):
            target_sign = 1
        elif any(
            w in desired_lower
            for w in (
                "decrease",
                "reduce",
                "lower",
                "down",
                "inhibit",
                "suppress",
                "silence",
                "knockout",
                "loss",
                "abolish",
            )
        ):
            target_sign = -1

        if target_sign == 0:
            return 0.0

        path_signs: list[int] = []
        for edge in supporting_edges:
            effect = edge.get("effect")
            if effect is None:
                continue

            eff_type = getattr(effect, "type", None) or (
                effect.get("type") if isinstance(effect, dict) else None
            )
            eff_dir = getattr(effect, "direction", None) or (
                effect.get("direction") if isinstance(effect, dict) else None
            )

            edge_sign = 0
            if eff_dir:
                dir_str = str(getattr(eff_dir, "value", eff_dir)).lower()
                if dir_str == "increases":
                    edge_sign = 1
                elif dir_str == "decreases":
                    edge_sign = -1

            if edge_sign == 0 and eff_type:
                type_str = str(getattr(eff_type, "value", eff_type)).lower()
                if type_str in ("activation", "production", "expression", "gain_of_function"):
                    edge_sign = 1
                elif type_str in ("inhibition", "loss_of_function"):
                    edge_sign = -1

            if edge_sign != 0:
                path_signs.append(edge_sign)

        if not path_signs:
            return 0.0

        net_path_sign = 1
        for s in path_signs:
            net_path_sign *= s

        if net_path_sign == target_sign:
            return 5.0
        elif net_path_sign == -target_sign:
            return -10.0
        return 0.0

    def _calculate_pleiotropy_penalty(
        self,
        graph: nx.MultiDiGraph,
        selected_candidates: list[str],
        target_nodes: set[str],
    ) -> float:
        """
        Calculate specificity penalty for candidate genes that are hyper-connected promiscuous hubs.
        """
        penalty = 0.0
        for cand in selected_candidates:
            if cand in graph:
                neighbors = set(graph.predecessors(cand)) | set(graph.successors(cand))
                non_target_neighbors = neighbors - target_nodes
                if len(non_target_neighbors) > 15:
                    penalty += min(5.0, (len(non_target_neighbors) - 15) * 0.2)
        return min(penalty, 10.0)

    def _calculate_redundancy_adjustment(
        self,
        graph: nx.MultiDiGraph,
        selected_candidates: list[str],
        covered_targets: set[str],
    ) -> float:
        """
        Calculate redundancy score for multiple candidate edits.
        Rewards candidates that reach targets via independent/disjoint intermediate paths.
        """
        if len(selected_candidates) <= 1:
            return 0.0

        intermediate_sets: list[set[str]] = []
        for cand in selected_candidates:
            cand_intermediates: set[str] = set()
            for tgt in covered_targets:
                path = self._shortest_path(graph, cand, tgt)
                if path and len(path) > 2:
                    cand_intermediates.update(path[1:-1])
            intermediate_sets.append(cand_intermediates)

        is_disjoint = True
        for i in range(len(intermediate_sets)):
            for j in range(i + 1, len(intermediate_sets)):
                if (
                    intermediate_sets[i]
                    and intermediate_sets[j]
                    and (intermediate_sets[i] & intermediate_sets[j])
                ):
                    is_disjoint = False
                    break

        if is_disjoint:
            return len(selected_candidates) * 4.0
        else:
            return len(selected_candidates) * 2.0

    # =========================================================================
    # Uncertainty
    # =========================================================================

    def _calculate_uncertainty(
        self,
        supporting_edges: list[dict[str, Any]],
        conflicting_edges: list[Any],
        constraint_result: ConstraintResult,
    ) -> float:
        """
        Produce a deterministic evidence uncertainty score.

        Higher score = greater uncertainty.

        Uncertainty increases when:

            - supporting evidence is weak
            - conflicting evidence exists
            - constraint penalties exist

        The uncertainty score is not a biological probability.
        It is a planner evidence uncertainty/conflict indicator.
        """

        uncertainty_score = 0.0

        # Weak evidence increases uncertainty.
        if supporting_edges:
            average_evidence = sum(self._edge_score(edge) for edge in supporting_edges) / len(
                supporting_edges
            )

            # Assuming source_score is normally normalized to 0..1.
            evidence_uncertainty = max(
                0.0,
                1.0 - average_evidence,
            )

            uncertainty_score += evidence_uncertainty * 50.0

        else:
            uncertainty_score += 50.0

        # Conflicting evidence.
        uncertainty_score += len(conflicting_edges) * 15.0

        # Negative constraint adjustments.
        if constraint_result.score_adjustment < 0:
            uncertainty_score += abs(constraint_result.score_adjustment) * 10.0

        return min(
            uncertainty_score,
            100.0,
        )

    @staticmethod
    def _uncertainty_label(
        uncertainty_score: float,
    ) -> str:

        if uncertainty_score < 25:
            return "low"

        if uncertainty_score < 50:
            return "moderate"

        if uncertainty_score < 75:
            return "high"

        return "very_high"

    # =========================================================================
    # Rationale
    # =========================================================================

    def _build_rationale(
        self,
        selected_candidates: list[str],
        covered_targets: set[str],
        target_nodes: set[str],
        uncertainty: str,
    ) -> str:
        """
        Build a deterministic rationale.

        No LLM generation is used here.
        """

        coverage_ratio = len(covered_targets) / len(target_nodes)

        desired_change = self._get_desired_change()

        parts = [
            (f"Selected {len(selected_candidates)} candidate(s)"),
            (
                f"covering {len(covered_targets)} of "
                f"{len(target_nodes)} objective target(s) "
                f"({coverage_ratio:.0%} coverage)"
            ),
        ]

        if desired_change:
            parts.append(f"for desired change '{desired_change}'")

        parts.append(f"with {uncertainty} evidence uncertainty")

        if self.strategy_type == "minimal":
            parts.append("using a minimal-edit preference")

        elif self.strategy_type == "redundant":
            parts.append("using a redundancy preference")

        return ", ".join(parts) + "."

    # =========================================================================
    # Graph utilities
    # =========================================================================

    def _distances_to_targets(
        self,
        graph: nx.MultiDiGraph,
        target_nodes: set[str],
    ) -> dict[str, int]:
        """
        Calculate shortest undirected distances from objective targets.

        Undirected traversal is used for relevance discovery because
        EvidenceRecord direction does not necessarily mean causal direction.

        The actual edge relationships remain preserved and available for
        later scoring/interpretation.
        """

        undirected = graph.to_undirected()

        distances: dict[str, int] = {}

        for target in target_nodes:
            lengths = nx.single_source_shortest_path_length(
                undirected,
                target,
                cutoff=self.config.max_target_distance,
            )

            for node, distance in lengths.items():
                if node not in distances or distance < distances[node]:
                    distances[node] = distance

        return distances

    def _shortest_distance(
        self,
        graph: nx.MultiDiGraph,
        source: str,
        target: str,
    ) -> int | None:

        undirected = graph.to_undirected()

        try:
            return int(
                nx.shortest_path_length(
                    undirected,
                    source=source,
                    target=target,
                )
            )

        except (
            nx.NetworkXNoPath,
            nx.NodeNotFound,
        ):
            return None

    def _shortest_path(
        self,
        graph: nx.MultiDiGraph,
        source: str,
        target: str,
    ) -> list[str] | None:

        undirected = graph.to_undirected()

        try:
            return nx.shortest_path(
                undirected,
                source=source,
                target=target,
            )

        except (
            nx.NetworkXNoPath,
            nx.NodeNotFound,
        ):
            return None

    def _incident_edges(
        self,
        graph: nx.MultiDiGraph,
        node: str,
    ) -> list[
        tuple[
            Any,
            Any,
            Any,
            dict[str, Any],
        ]
    ]:
        """
        Return all incoming and outgoing edges for a node.
        """

        edges = []

        edges.extend(
            graph.out_edges(
                node,
                keys=True,
                data=True,
            )
        )

        edges.extend(
            graph.in_edges(
                node,
                keys=True,
                data=True,
            )
        )

        return edges

    def _best_edge_between(
        self,
        graph: nx.MultiDiGraph,
        source: str,
        target: str,
    ) -> dict[str, Any] | None:
        """
        Select the strongest evidence edge between two nodes.

        Multiple evidence edges can exist because this is a MultiDiGraph.

        We preserve all evidence in the graph, but for constructing a
        representative supporting path we select the highest source_score.
        """

        candidates: list[dict[str, Any]] = []

        # Forward direction.
        edge_bundle = graph.get_edge_data(
            source,
            target,
            default={},
        )

        for key, data in edge_bundle.items():
            edge = dict(data)

            edge["_edge_key"] = key

            edge["_source_node"] = source
            edge["_target_node"] = target

            candidates.append(edge)

        # The shortest path is generated on an undirected graph.
        # Therefore evidence may exist only in the reverse direction.
        if not candidates:
            reverse_bundle = graph.get_edge_data(
                target,
                source,
                default={},
            )

            for key, data in reverse_bundle.items():
                edge = dict(data)

                edge["_edge_key"] = key

                edge["_source_node"] = target
                edge["_target_node"] = source

                candidates.append(edge)

        if not candidates:
            return None

        best = max(
            candidates,
            key=self._edge_score,
        )

        # If multiple independent source edges connect this pair, compute Noisy-OR consensus
        if len(candidates) > 1:
            prob_failure = 1.0
            for c in candidates:
                s = self._raw_score(c)
                prob_failure *= 1.0 - 0.7 * s
            consensus_score = max(self._raw_score(best), min(1.0, 1.0 - prob_failure))
            best = dict(best)
            best["_consensus_score"] = consensus_score
            best["_corroborating_sources_count"] = len(candidates)

        return best

    # =========================================================================
    # Evidence utilities
    # =========================================================================

    @staticmethod
    def _raw_score(edge: dict[str, Any]) -> float:
        value = edge.get("source_score")
        if value is None:
            return 0.5
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(score, 1.0))

    @classmethod
    def _edge_score(
        cls,
        edge: dict[str, Any],
    ) -> float:
        """
        Read source evidence score or multi-source consensus score.
        Missing/invalid scores are treated as 0.5 neutral confidence.
        """
        if "_consensus_score" in edge:
            return float(edge["_consensus_score"])
        return cls._raw_score(edge)

    # =========================================================================
    # Deduplication / ranking
    # =========================================================================

    @staticmethod
    def _deduplicate_strategies(
        strategies: list[Strategy],
    ) -> list[Strategy]:
        """
        Keep only the highest-scoring instance of each candidate set.
        """

        unique: dict[
            tuple[str, ...],
            Strategy,
        ] = {}

        for strategy in strategies:
            key = tuple(sorted(strategy.selected_candidates))

            existing = unique.get(key)

            if existing is None or strategy.score > existing.score:
                unique[key] = strategy

        return list(unique.values())

    @staticmethod
    def _strategy_sort_key(
        strategy: Strategy,
    ) -> tuple[float, float, int]:

        # Higher score is better.
        #
        # Lower uncertainty is preferred when scores are equal.
        #
        # Fewer edits break final ties.
        return (
            strategy.score,
            -strategy.uncertainty_score,
            -strategy.edit_count,
        )

    # =========================================================================
    # Generic object helpers
    # =========================================================================

    @staticmethod
    def _get_field(
        obj: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:

        if isinstance(obj, dict):
            return obj.get(
                field_name,
                default,
            )

        return getattr(
            obj,
            field_name,
            default,
        )

    @staticmethod
    def _normalize_terms(
        value: Any,
    ) -> set[str]:

        if value is None:
            return set()

        if isinstance(
            value,
            str,
        ):
            value = [value]

        try:
            return {str(item).strip() for item in value if str(item).strip()}

        except TypeError:
            return {str(value).strip()}


# =============================================================================
# Convenience function
# =============================================================================


def search_strategies(
    evidence_graph: EvidenceGraph,
    objective: Any,
    constraints: Iterable[Any] | None,
    max_edits: int,
    strategy_type: str,
    config: SearchConfig | None = None,
) -> list[Strategy]:

    search_engine = StrategySearch(
        objective=objective,
        constraints=constraints,
        max_edits=max_edits,
        strategy_type=strategy_type,
        config=config,
    )

    return search_engine.search(evidence_graph)
