"""Tests for app.models.requests — enums, pipeline contracts, CreateRunRequest."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.requests import (
    AmbiguityStatus,
    CreateRunRequest,
    ProjectContext,
    RetrievalContext,
    RunConfiguration,
    Scope,
    StrategyMode,
    StructuredObjective,
)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestStrategyMode:
    def test_values(self) -> None:
        assert {s.value for s in StrategyMode} == {"minimal", "redundant"}

    def test_invalid_strategy_raises(self) -> None:
        with pytest.raises((ValueError, ValidationError)):
            RunConfiguration(max_edits=3, strategy="maximal")  # type: ignore[arg-type]


class TestScope:
    def test_all_scopes_present(self) -> None:
        expected = {
            "conservation",
            "de-extinction",
            "agriculture",
            "synthetic-biology",
            "population-control",
            "precision-medicine",
        }
        assert {s.value for s in Scope} == expected

    def test_invalid_scope_raises(self) -> None:
        with pytest.raises((ValueError, ValidationError)):
            ProjectContext(
                project_id="p1",
                species="X",
                scope="unknown",  # type: ignore
                objective="y",
            )


class TestAmbiguityStatus:
    def test_values(self) -> None:
        assert {a.value for a in AmbiguityStatus} == {"clear", "CLARIFICATION_REQUIRED"}

    def test_clarification_required_value(self) -> None:
        assert AmbiguityStatus.CLARIFICATION_REQUIRED == "CLARIFICATION_REQUIRED"

    def test_structured_objective_defaults_to_clear(self) -> None:
        obj = StructuredObjective(desired_change="white coat")
        assert obj.ambiguity_status == AmbiguityStatus.CLEAR

    def test_structured_objective_accepts_clarification_required(self) -> None:
        obj = StructuredObjective(
            desired_change="unclear",
            ambiguity_status=AmbiguityStatus.CLARIFICATION_REQUIRED,
        )
        assert obj.ambiguity_status == AmbiguityStatus.CLARIFICATION_REQUIRED


# ---------------------------------------------------------------------------
# ProjectContext
# ---------------------------------------------------------------------------


class TestProjectContext:
    def test_valid_instance(self) -> None:
        ctx = ProjectContext(
            project_id="proj-001",
            species="Canis lupus",
            scope=Scope.DE_EXTINCTION,
            objective="Make the coat white.",
        )
        assert ctx.species == "Canis lupus"
        assert ctx.scope == Scope.DE_EXTINCTION

    def test_missing_species_raises(self) -> None:
        with pytest.raises(ValidationError):
            ProjectContext(  # type: ignore[call-arg]
                project_id="p", scope=Scope.CONSERVATION, objective="x"
            )

    def test_invalid_scope_string_raises(self) -> None:
        with pytest.raises((ValueError, ValidationError)):
            ProjectContext(
                project_id="p",
                species="X",
                scope="invalid",  # type: ignore
                objective="y",
            )


# ---------------------------------------------------------------------------
# RunConfiguration
# ---------------------------------------------------------------------------


class TestRunConfiguration:
    def test_valid_minimal_instance(self) -> None:
        cfg = RunConfiguration(max_edits=3, strategy=StrategyMode.MINIMAL)
        assert cfg.max_edits == 3
        assert cfg.strategy == StrategyMode.MINIMAL
        assert cfg.candidate_genes == []
        assert cfg.constraints == []

    def test_max_edits_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            RunConfiguration(max_edits=0, strategy=StrategyMode.MINIMAL)

    def test_max_edits_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            RunConfiguration(max_edits=-1, strategy=StrategyMode.MINIMAL)

    def test_missing_strategy_raises(self) -> None:
        with pytest.raises(ValidationError):
            RunConfiguration(max_edits=3)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# StructuredObjective
# ---------------------------------------------------------------------------


class TestStructuredObjective:
    def test_minimal_valid_instance(self) -> None:
        obj = StructuredObjective(desired_change="white coat pigmentation")
        assert obj.desired_change == "white coat pigmentation"
        assert obj.ambiguity_status == AmbiguityStatus.CLEAR
        assert obj.target_phenotypes == []
        assert obj.retrieval_targets == []

    def test_missing_desired_change_raises(self) -> None:
        with pytest.raises(ValidationError):
            StructuredObjective()  # type: ignore[call-arg]

    def test_full_valid_instance(self) -> None:
        obj = StructuredObjective(
            target_phenotypes=["coat pigmentation"],
            biological_processes=["melanogenesis"],
            desired_change="white coat",
            relevant_concepts=["melanin", "pigment"],
            retrieval_targets=["TYRP1", "DCT", "MC1R"],
            ambiguity_status=AmbiguityStatus.CLEAR,
        )
        assert "TYRP1" in obj.retrieval_targets


# ---------------------------------------------------------------------------
# RetrievalContext
# ---------------------------------------------------------------------------


class TestRetrievalContext:
    def test_valid_instance(self) -> None:
        ctx = RetrievalContext(
            project_context=ProjectContext(
                project_id="p",
                species="Canis lupus",
                scope=Scope.DE_EXTINCTION,
                objective="White coat",
            ),
            run_configuration=RunConfiguration(max_edits=3, strategy=StrategyMode.MINIMAL),
            structured_objective=StructuredObjective(desired_change="white coat"),
        )
        assert ctx.project_context.species == "Canis lupus"

    def test_missing_project_context_raises(self) -> None:
        with pytest.raises(ValidationError):
            RetrievalContext(  # type: ignore[call-arg]
                run_configuration=RunConfiguration(max_edits=3, strategy=StrategyMode.MINIMAL),
                structured_objective=StructuredObjective(desired_change="x"),
            )


# ---------------------------------------------------------------------------
# CreateRunRequest (API body)
# ---------------------------------------------------------------------------


class TestCreateRunRequest:
    def test_valid_instance(self) -> None:
        req = CreateRunRequest.model_validate(
            {
                "project": {"species": "Canis lupus", "scope": "de-extinction"},
                "run": {
                    "objective": "Make the wolf's coat white.",
                    "candidate_genes": [],
                    "constraints": ["preserve fertility"],
                    "max_edits": 3,
                    "strategy": "minimal",
                },
            }
        )
        assert req.project.species == "Canis lupus"
        assert req.run.strategy == StrategyMode.MINIMAL
        assert req.run.constraints == ["preserve fertility"]

    def test_invalid_scope_in_project_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateRunRequest.model_validate(
                {
                    "project": {"species": "X", "scope": "invalid_scope"},
                    "run": {"objective": "y", "max_edits": 1, "strategy": "minimal"},
                }
            )

    def test_missing_project_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateRunRequest.model_validate(
                {"run": {"objective": "x", "max_edits": 1, "strategy": "minimal"}}
            )
