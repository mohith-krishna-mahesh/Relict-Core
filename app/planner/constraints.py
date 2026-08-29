from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


# =============================================================================
# Constraint definitions
# =============================================================================


class ConstraintType(str, Enum):
    PRESERVE_FERTILITY = "preserve_fertility"
    MAXIMIZE_GENETIC_DIVERSITY = "maximize_genetic_diversity"


@dataclass
class ConstraintResult:
    """
    Result of evaluating one or more constraints.

    valid:
        Whether the candidate selection is allowed to continue.

    score_adjustment:
        A value search.py can add to its strategy score.

        Positive = evidence supports a constraint.
        Negative = evidence conflicts with a constraint.

    violations:
        Hard constraint violations.

    supporting_edges:
        Evidence edges that support the constraint.

    conflicting_edges:
        Evidence edges that conflict with the constraint.
    """

    valid: bool

    score_adjustment: float = 0.0

    violations: list[str] = field(default_factory=list)

    supporting_edges: list[Any] = field(default_factory=list)

    conflicting_edges: list[Any] = field(default_factory=list)


# =============================================================================
# ConstraintEvaluator
# =============================================================================


class ConstraintEvaluator:
    """
    Evaluates Planner constraints against graph evidence.

    Parameters
    ----------
    constraints:
        Active constraints.

    fertility_is_hard_constraint:
        If True, a strategy with evidence indicating fertility harm is invalid.

    diversity_is_hard_constraint:
        If True, a strategy with evidence indicating decreased genetic
        diversity is invalid.

        Normally this should remain False because "maximize" is naturally
        an optimization objective rather than a strict yes/no requirement.
    """

    def __init__(
        self,
        constraints: Iterable[str | ConstraintType] | None = None,
        *,
        fertility_is_hard_constraint: bool = True,
        diversity_is_hard_constraint: bool = False,
    ) -> None:
        self.constraints = self._normalize_constraints(constraints)

        self.fertility_is_hard_constraint = fertility_is_hard_constraint

        self.diversity_is_hard_constraint = diversity_is_hard_constraint

    # =========================================================================
    # Public API
    # =========================================================================

    def evaluate(
        self,
        selected_candidates: Iterable[Any],
        graph: Any,
    ) -> ConstraintResult:
        """
        Evaluate all active constraints.

        Parameters
        ----------
        selected_candidates:
            CandidateAction objects, genes, entity IDs, or other objects
            representing the current strategy selection.

        graph:
            The NetworkX graph from EvidenceGraph.networkx_graph.

        Returns
        -------
        ConstraintResult
        """

        selected_entities = self._extract_candidate_entities(
            selected_candidates
        )

        if not self.constraints:
            return ConstraintResult(valid=True)

        result = ConstraintResult(valid=True)

        relevant_edges = self._get_relevant_edges(
            selected_entities,
            graph,
        )

        # ---------------------------------------------------------------------
        # Preserve fertility
        # ---------------------------------------------------------------------

        if ConstraintType.PRESERVE_FERTILITY in self.constraints:

            fertility_result = self._evaluate_fertility(
                relevant_edges
            )

            result.score_adjustment += (
                fertility_result.score_adjustment
            )

            result.supporting_edges.extend(
                fertility_result.supporting_edges
            )

            result.conflicting_edges.extend(
                fertility_result.conflicting_edges
            )

            result.violations.extend(
                fertility_result.violations
            )

            if not fertility_result.valid:
                result.valid = False

        # ---------------------------------------------------------------------
        # Maximize genetic diversity
        # ---------------------------------------------------------------------

        if ConstraintType.MAXIMIZE_GENETIC_DIVERSITY in self.constraints:

            diversity_result = self._evaluate_genetic_diversity(
                relevant_edges
            )

            result.score_adjustment += (
                diversity_result.score_adjustment
            )

            result.supporting_edges.extend(
                diversity_result.supporting_edges
            )

            result.conflicting_edges.extend(
                diversity_result.conflicting_edges
            )

            result.violations.extend(
                diversity_result.violations
            )

            if not diversity_result.valid:
                result.valid = False

        return result

    def is_valid(
        self,
        selected_candidates: Iterable[Any],
        graph: Any,
    ) -> bool:
        """
        Convenience method.

        Returns True only if the candidate selection satisfies all
        active hard constraints.
        """

        return self.evaluate(
            selected_candidates,
            graph,
        ).valid

    # =========================================================================
    # Fertility
    # =========================================================================

    def _evaluate_fertility(
        self,
        edges: list[dict[str, Any]],
    ) -> ConstraintResult:
        """
        Evaluate evidence relating selected candidates to fertility.

        Logic:

            evidence supports fertility
                -> positive score

            evidence harms/reduces fertility
                -> negative score

                -> invalid if fertility_is_hard_constraint=True

        The evaluator only acts on explicit evidence semantics.
        """

        result = ConstraintResult(valid=True)

        for edge in edges:

            semantic_text = self._edge_semantic_text(edge)

            if not self._mentions_fertility(semantic_text):
                continue

            score = self._edge_score(edge)

            if self._indicates_negative_effect(
                semantic_text
            ):
                result.conflicting_edges.append(edge)

                result.score_adjustment -= score

                if self.fertility_is_hard_constraint:

                    result.valid = False

                    result.violations.append(
                        "Selected candidate has evidence indicating "
                        "a negative effect on fertility."
                    )

            elif self._indicates_positive_effect(
                semantic_text
            ):
                result.supporting_edges.append(edge)

                result.score_adjustment += score

        return result

    # =========================================================================
    # Genetic diversity
    # =========================================================================

    def _evaluate_genetic_diversity(
        self,
        edges: list[dict[str, Any]],
    ) -> ConstraintResult:
        """
        Evaluate evidence relating selected candidates to genetic diversity.

        Logic:

            increases/preserves diversity
                -> positive score

            reduces diversity
                -> negative score

                -> optionally invalid if diversity_is_hard_constraint=True

        Normally "maximize genetic diversity" should be treated as a
        scoring preference rather than a hard rejection rule.
        """

        result = ConstraintResult(valid=True)

        for edge in edges:

            semantic_text = self._edge_semantic_text(edge)

            if not self._mentions_genetic_diversity(
                semantic_text
            ):
                continue

            score = self._edge_score(edge)

            if self._indicates_negative_effect(
                semantic_text
            ):
                result.conflicting_edges.append(edge)

                result.score_adjustment -= score

                if self.diversity_is_hard_constraint:

                    result.valid = False

                    result.violations.append(
                        "Selected candidate has evidence indicating "
                        "reduced genetic diversity."
                    )

            elif self._indicates_positive_effect(
                semantic_text
            ):
                result.supporting_edges.append(edge)

                result.score_adjustment += score

        return result

    # =========================================================================
    # Graph traversal
    # =========================================================================

    def _get_relevant_edges(
        self,
        selected_entities: set[str],
        graph: Any,
    ) -> list[dict[str, Any]]:
        """
        Return graph edges directly connected to selected entities.

        Each returned edge contains:

            source
            target
            relationship
            source_score
            effect
            consequence
            provenance
            metadata

        This works with NetworkX MultiDiGraph.
        """

        relevant_edges: list[dict[str, Any]] = []

        seen_edges: set[tuple[Any, Any, Any]] = set()

        for entity in selected_entities:

            if entity not in graph:
                continue

            # Outgoing edges.
            for source, target, key, data in graph.out_edges(
                entity,
                keys=True,
                data=True,
            ):

                edge_id = (source, target, key)

                if edge_id in seen_edges:
                    continue

                seen_edges.add(edge_id)

                relevant_edges.append(
                    self._edge_to_dict(
                        source,
                        target,
                        key,
                        data,
                    )
                )

            # Incoming edges.
            for source, target, key, data in graph.in_edges(
                entity,
                keys=True,
                data=True,
            ):

                edge_id = (source, target, key)

                if edge_id in seen_edges:
                    continue

                seen_edges.add(edge_id)

                relevant_edges.append(
                    self._edge_to_dict(
                        source,
                        target,
                        key,
                        data,
                    )
                )

        return relevant_edges

    @staticmethod
    def _edge_to_dict(
        source: Any,
        target: Any,
        key: Any,
        data: dict[str, Any],
    ) -> dict[str, Any]:

        return {
            "source_node": source,
            "target_node": target,
            "edge_key": key,
            **data,
        }

    # =========================================================================
    # Candidate extraction
    # =========================================================================

    def _extract_candidate_entities(
        self,
        selected_candidates: Iterable[Any],
    ) -> set[str]:
        """
        Extract graph entity IDs from selected candidates.

        Supports:

            "GENE_A"

            {"entity": "GENE_A"}

            {"gene": "GENE_A"}

            CandidateAction(
                entity="GENE_A"
            )

        This is intentionally flexible because search.py may eventually
        pass CandidateAction objects rather than plain gene strings.
        """

        entities: set[str] = set()

        for candidate in selected_candidates:

            if candidate is None:
                continue

            if isinstance(candidate, str):
                entities.add(candidate)
                continue

            if isinstance(candidate, dict):

                entity = (
                    candidate.get("entity")
                    or candidate.get("gene")
                    or candidate.get("entity_id")
                    or candidate.get("target")
                )

                if entity is not None:
                    entities.add(str(entity))

                continue

            for field_name in (
                "entity",
                "gene",
                "entity_id",
                "target",
            ):

                value = getattr(
                    candidate,
                    field_name,
                    None,
                )

                if value is not None:
                    entities.add(str(value))
                    break

        return entities

    # =========================================================================
    # Evidence semantics
    # =========================================================================

    def _edge_semantic_text(
        self,
        edge: dict[str, Any],
    ) -> str:
        """
        Combine evidence fields into searchable normalized text.

        We inspect:

            source/target entities
            relationship
            effect
            consequence
            metadata

        This is NOT inferring biology.

        It simply allows constraints.py to recognize explicit semantic
        information already supplied in the EvidenceRecord.
        """

        values = [
            edge.get("source_node"),
            edge.get("target_node"),
            edge.get("relationship"),
            edge.get("effect"),
            edge.get("consequence"),
            edge.get("metadata"),
        ]

        text = " ".join(
            self._stringify(value)
            for value in values
            if value is not None
        )

        return text.lower()

    @staticmethod
    def _stringify(value: Any) -> str:

        if isinstance(value, dict):

            return " ".join(
                f"{key} {ConstraintEvaluator._stringify(item)}"
                for key, item in value.items()
            )

        if isinstance(value, (list, tuple, set)):

            return " ".join(
                ConstraintEvaluator._stringify(item)
                for item in value
            )

        return str(value)

    # =========================================================================
    # Semantic checks
    # =========================================================================

    @staticmethod
    def _mentions_fertility(
        text: str,
    ) -> bool:

        fertility_terms = (
            "fertility",
            "fecundity",
            "reproductive success",
            "reproduction",
            "sterility",
            "infertility",
        )

        return any(
            term in text
            for term in fertility_terms
        )

    @staticmethod
    def _mentions_genetic_diversity(
        text: str,
    ) -> bool:

        diversity_terms = (
            "genetic diversity",
            "genetic variation",
            "genetic variability",
            "heterozygosity",
            "allelic diversity",
            "allele diversity",
        )

        return any(
            term in text
            for term in diversity_terms
        )

    @staticmethod
    def _indicates_negative_effect(
        text: str,
    ) -> bool:

        negative_terms = (
            "decrease",
            "decreases",
            "decreased",
            "reduce",
            "reduces",
            "reduced",
            "impair",
            "impairs",
            "impaired",
            "harm",
            "harms",
            "negative effect",
            "loss",
            "loss_of_function",
            "loss of function",
            "infertility",
            "sterility",
        )

        return any(
            term in text
            for term in negative_terms
        )

    @staticmethod
    def _indicates_positive_effect(
        text: str,
    ) -> bool:

        positive_terms = (
            "increase",
            "increases",
            "increased",
            "enhance",
            "enhances",
            "enhanced",
            "preserve",
            "preserves",
            "preserved",
            "maintain",
            "maintains",
            "maintained",
            "positive effect",
            "improve",
            "improves",
            "improved",
        )

        return any(
            term in text
            for term in positive_terms
        )

    # =========================================================================
    # Scoring
    # =========================================================================

    @staticmethod
    def _edge_score(
        edge: dict[str, Any],
    ) -> float:
        """
        Return the evidence score for an edge.

        Missing scores default to 1.0.

        This does NOT normalize scores because the graph builder should
        preserve source_score semantics from upstream.
        """

        score = edge.get("source_score")

        if score is None:
            return 1.0

        try:
            return float(score)

        except (TypeError, ValueError):
            return 1.0

    # =========================================================================
    # Constraint normalization
    # =========================================================================

    @staticmethod
    def _normalize_constraints(
        constraints: Iterable[str | ConstraintType] | None,
    ) -> set[ConstraintType]:

        if constraints is None:
            return set()

        normalized: set[ConstraintType] = set()

        aliases = {
            "preserve fertility":
                ConstraintType.PRESERVE_FERTILITY,

            "preserve_fertility":
                ConstraintType.PRESERVE_FERTILITY,

            "maximize genetic diversity":
                ConstraintType.MAXIMIZE_GENETIC_DIVERSITY,

            "maximize_genetic_diversity":
                ConstraintType.MAXIMIZE_GENETIC_DIVERSITY,
        }

        for constraint in constraints:

            if isinstance(constraint, ConstraintType):
                normalized.add(constraint)
                continue

            value = str(constraint).strip().lower()

            if value not in aliases:
                raise ValueError(
                    f"Unsupported constraint: {constraint!r}"
                )

            normalized.add(aliases[value])

        return normalized


# =============================================================================
# Convenience function
# =============================================================================


def evaluate_constraints(
    selected_candidates: Iterable[Any],
    graph: Any,
    constraints: Iterable[str | ConstraintType] | None,
) -> ConstraintResult:
    """
    Convenience function for one-shot constraint evaluation.
    """

    evaluator = ConstraintEvaluator(constraints)

    return evaluator.evaluate(
        selected_candidates,
        graph,
    )