"""Tests for RetrievalContext, ProjectContext, and StructuredObjective models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.requests import (
    AmbiguityStatus,
    ProjectContext,
    RetrievalContext,
    RunConfiguration,
    Scope,
    StrategyMode,
    StructuredObjective,
)


class TestProjectContext:
    def test_valid_project_context(self) -> None:
        pc = ProjectContext(
            project_id="proj-123",
            species="Arabidopsis thaliana",
            scope=Scope.AGRICULTURE,
            objective="Improve drought tolerance",
        )
        assert pc.project_id == "proj-123"
        assert pc.species == "Arabidopsis thaliana"
        assert pc.scope == Scope.AGRICULTURE
        assert pc.objective == "Improve drought tolerance"

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            ProjectContext.model_validate({"project_id": "p1"})


class TestStructuredObjective:
    def test_structured_objective_defaults(self) -> None:
        obj = StructuredObjective(desired_change="upregulate")
        assert obj.target_phenotypes == []
        assert obj.biological_processes == []
        assert obj.desired_change == "upregulate"
        assert obj.relevant_concepts == []
        assert obj.retrieval_targets == []
        assert obj.ambiguity_status == AmbiguityStatus.CLEAR

    def test_structured_objective_with_values(self) -> None:
        obj = StructuredObjective(
            target_phenotypes=["drought resistance"],
            biological_processes=["abscisic acid response"],
            desired_change="upregulate",
            relevant_concepts=["transcription factors"],
            retrieval_targets=["ABA1", "NCED3"],
            ambiguity_status=AmbiguityStatus.CLARIFICATION_REQUIRED,
        )
        assert len(obj.retrieval_targets) == 2
        assert obj.ambiguity_status == AmbiguityStatus.CLARIFICATION_REQUIRED


class TestRetrievalContext:
    def test_valid_retrieval_context(self) -> None:
        ctx = RetrievalContext(
            project_context=ProjectContext(
                project_id="p1",
                species="Mus musculus",
                scope=Scope.CONSERVATION,
                objective="Study p53 regulation",
            ),
            run_configuration=RunConfiguration(
                candidate_genes=["Trp53"],
                max_edits=2,
                constraints=["preserve fertility"],
                strategy=StrategyMode.MINIMAL,
            ),
            structured_objective=StructuredObjective(
                desired_change="knockout",
                retrieval_targets=["Trp53", "Mdm2"],
            ),
        )
        assert ctx.project_context.species == "Mus musculus"
        assert ctx.run_configuration.max_edits == 2
        assert ctx.structured_objective.retrieval_targets == ["Trp53", "Mdm2"]
