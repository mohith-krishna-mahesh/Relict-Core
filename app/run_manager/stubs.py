"""
Stub/mock implementations of the pipeline stage protocols for Phase 2A.

Each stub is fully deterministic and configurable via constructor flags,
allowing the orchestrator tests to exercise every defined failure path without
calling any external service or trained model.

Replace stubs one stage at a time in later phases; the orchestrator does not
need to change because it depends only on the Protocol interfaces in
``app.run_manager.stages``.
"""

from __future__ import annotations

from typing import Any

from app.models.evidence import EvidenceRecord
from app.models.graph import GraphEdge
from app.models.post_plan import PostPlanResult, PostPlanStatus
from app.models.requests import (
    AmbiguityStatus,
    ProjectContext,
    RetrievalContext,
    RunConfiguration,
    StructuredObjective,
)
from app.models.responses import RetrievalResult, SourceStatus, Strategy
from app.models.validation import ValidationResult


class StubObjectiveResolver:
    """
    Stub for Core Model Task 1.

    Parameters
    ----------
    clarification_required:
        Return ``ambiguity_status=CLARIFICATION_REQUIRED`` instead of CLEAR.
    raise_error:
        Raise ``RuntimeError`` to test unexpected-exception handling.
    """

    def __init__(
        self,
        *,
        clarification_required: bool = False,
        raise_error: bool = False,
    ) -> None:
        self._clarification_required = clarification_required
        self._raise_error = raise_error

    async def resolve(
        self,
        project: ProjectContext,
        run_config: RunConfiguration,
    ) -> StructuredObjective:
        if self._raise_error:
            raise RuntimeError("StubObjectiveResolver: simulated error")
        status = (
            AmbiguityStatus.CLARIFICATION_REQUIRED
            if self._clarification_required
            else AmbiguityStatus.CLEAR
        )
        return StructuredObjective(
            target_phenotypes=["coat pigmentation"],
            biological_processes=["melanogenesis"],
            desired_change="white coat",
            relevant_concepts=["melanin"],
            retrieval_targets=["TYRP1", "DCT", "MC1R"],
            ambiguity_status=status,
        )


class StubEvidenceRetriever:
    """
    Stub for Knowledge Retrieval.

    Parameters
    ----------
    return_empty:
        Return an empty list to trigger ``INSUFFICIENT_EVIDENCE``.
    raise_error:
        Raise ``RuntimeError`` to test unexpected-exception handling.
    failure_code:
        Explicit FailureCode to simulate stage failures.
    """

    def __init__(
        self,
        *,
        return_empty: bool = False,
        raise_error: bool = False,
        failure_code: Any = None,
    ) -> None:
        self._return_empty = return_empty
        self._raise_error = raise_error
        self._failure_code = failure_code

    async def retrieve(self, context: RetrievalContext) -> RetrievalResult:
        from app.models.responses import RetrievalResult

        if self._raise_error:
            raise RuntimeError("StubEvidenceRetriever: simulated error")
        if self._failure_code:
            return RetrievalResult(
                records=[],
                source_statuses=[],
                failure_code=self._failure_code,
            )
        if self._return_empty:
            return RetrievalResult(
                records=[],
                source_statuses=[],
                failure_code=None,
            )
        records = [
            EvidenceRecord(
                source="STRING",
                source_id="9606.ENSP00000000001",
                entity_a="TYRP1",
                entity_b="DCT",
                relationship="functional_association",
                source_score=0.91,
                provenance="https://string-db.org",
            ),
            EvidenceRecord(
                source="KEGG",
                source_id="hsa00230",
                entity_a="DCT",
                entity_b="MC1R",
                relationship="pathway_member",
                source_score=1.0,
                provenance="KEGG Release 112.0",
            ),
        ]
        statuses = [
            SourceStatus(source_name="STRING", success=True, record_count=1),
            SourceStatus(source_name="KEGG", success=True, record_count=1),
        ]
        return RetrievalResult(
            records=records,
            source_statuses=statuses,
            failure_code=None,
        )


class StubStrategicPlanner:
    """
    Stub for the Planner.

    Parameters
    ----------
    return_empty:
        Return an empty list to trigger ``NO_FEASIBLE_PLAN``.
    raise_error:
        Raise ``RuntimeError`` to test unexpected-exception handling.
    """

    def __init__(
        self,
        *,
        return_empty: bool = False,
        raise_error: bool = False,
    ) -> None:
        self._return_empty = return_empty
        self._raise_error = raise_error

    async def plan(
        self,
        context: RetrievalContext,
        evidence: list[EvidenceRecord],
    ) -> list[Strategy]:
        if self._raise_error:
            raise RuntimeError("StubStrategicPlanner: simulated error")
        if self._return_empty:
            return []
        edge = GraphEdge(
            source_node_id="gene:TYRP1",
            target_node_id="gene:DCT",
            relationship="functional_association",
            source="STRING",
            source_score=0.91,
        )
        return [
            Strategy(
                strategy_type=context.run_configuration.strategy,
                selected_candidates=["TYRP1", "DCT"],
                covered_targets=["coat pigmentation"],
                edit_count=2,
                score=0.92,
                supporting_edges=[edge],
                conflicting_edges=[],
                rationale="Stub: two-gene pigmentation strategy.",
            )
        ]


class StubStrategyValidator:
    """
    Stub for the Plan Validator.

    Parameters
    ----------
    return_valid:
        If ``False``, return ``valid=False`` to trigger ``VALIDATION_FAILED``.
    raise_error:
        Raise ``RuntimeError`` to test unexpected-exception handling.
    """

    def __init__(
        self,
        *,
        return_valid: bool = True,
        raise_error: bool = False,
    ) -> None:
        self._return_valid = return_valid
        self._raise_error = raise_error

    async def validate(
        self,
        strategy: Strategy,
        run_config: RunConfiguration,
    ) -> ValidationResult:
        if self._raise_error:
            raise RuntimeError("StubStrategyValidator: simulated error")
        if not self._return_valid:
            return ValidationResult(
                valid=False,
                checks=["edit_budget", "target_coverage"],
                violations=["edit_budget: strategy exceeds max_edits"],
                warnings=[],
            )
        return ValidationResult(
            valid=True,
            checks=["edit_budget", "target_coverage", "constraints", "species_consistency"],
            violations=[],
            warnings=[],
        )


class StubPostPlanAnalyzer:
    """
    Stub for Post-Plan Analysis.

    Parameters
    ----------
    return_status:
        Terminal status: ``"complete"``, ``"partial"``, or ``"failed"``.
    raise_error:
        Raise ``RuntimeError`` to test unexpected-exception handling.
    """

    def __init__(
        self,
        *,
        return_status: str = "complete",
        raise_error: bool = False,
    ) -> None:
        self._return_status = return_status
        self._raise_error = raise_error

    async def analyze(
        self,
        strategy: Strategy,
        evidence: list[EvidenceRecord],
        run_config: RunConfiguration,
    ) -> PostPlanResult:
        if self._raise_error:
            raise RuntimeError("StubPostPlanAnalyzer: simulated error")
        status_map: dict[str, PostPlanStatus] = {
            "complete": PostPlanStatus.COMPLETE,
            "partial": PostPlanStatus.PARTIAL,
            "failed": PostPlanStatus.FAILED,
        }
        status = status_map.get(self._return_status, PostPlanStatus.COMPLETE)
        return PostPlanResult(
            status=status,
            node_explanations={
                "gene:TYRP1": "Stub: pigmentation-associated gene.",
                "gene:DCT": "Stub: involved in melanin synthesis.",
            },
            strategy_explanation=("Stub: strategy targets coat pigmentation via TYRP1 and DCT."),
        )
