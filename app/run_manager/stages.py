"""
Protocol interfaces for pipeline stage implementations.

These define the contracts the ``RunOrchestrator`` expects from each stage.
Real implementations (Core Model, Knowledge Retrieval, Planner, Validator,
Post-Plan Analysis) are injected when ready.  Stub classes satisfy the same
interface for Phase 2A testing.

Python's structural subtyping means any class that supplies the required
``async`` method with the correct signature automatically satisfies the
corresponding protocol — no explicit inheritance needed.
"""

from __future__ import annotations

from typing import Protocol

from app.models.evidence import EvidenceRecord
from app.models.post_plan import PostPlanResult
from app.models.requests import (
    ProjectContext,
    RetrievalContext,
    RunConfiguration,
    StructuredObjective,
)
from app.models.responses import RetrievalResult, Strategy
from app.models.validation import ValidationResult


class ObjectiveResolver(Protocol):
    """Core Model Task 1 — interprets the natural-language objective."""

    async def resolve(
        self,
        project: ProjectContext,
        run_config: RunConfiguration,
    ) -> StructuredObjective: ...


class EvidenceRetriever(Protocol):
    """Knowledge Retrieval — returns source-backed ``RetrievalResult``."""

    async def retrieve(self, context: RetrievalContext) -> RetrievalResult: ...


class StrategicPlanner(Protocol):
    """Planner — builds the evidence graph and returns ranked ``Strategy`` list."""

    async def plan(
        self,
        context: RetrievalContext,
        evidence: list[EvidenceRecord],
    ) -> list[Strategy]: ...


class StrategyValidator(Protocol):
    """Plan Validator — deterministically checks a candidate ``Strategy``."""

    async def validate(
        self,
        strategy: Strategy,
        run_config: RunConfiguration,
    ) -> ValidationResult: ...


class PostPlanAnalyzer(Protocol):
    """Post-Plan Analysis — guide/risk, population propagation, explanation."""

    async def analyze(
        self,
        strategy: Strategy,
        evidence: list[EvidenceRecord],
        run_config: RunConfiguration,
    ) -> PostPlanResult: ...
