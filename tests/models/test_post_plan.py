"""Tests for app.models.post_plan — PostPlanStatus and PostPlanResult."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.post_plan import PostPlanResult, PostPlanStatus


class TestPostPlanStatus:
    def test_has_exactly_three_values(self) -> None:
        values = {s.value for s in PostPlanStatus}
        assert values == {"complete", "partial", "failed"}

    def test_string_equality(self) -> None:
        assert PostPlanStatus.COMPLETE == "complete"
        assert PostPlanStatus.PARTIAL == "partial"
        assert PostPlanStatus.FAILED == "failed"


class TestPostPlanResult:
    def test_minimal_complete_result(self) -> None:
        result = PostPlanResult(status=PostPlanStatus.COMPLETE)
        assert result.status == PostPlanStatus.COMPLETE
        assert result.guide_risk is None
        assert result.population_analysis is None
        assert result.node_explanations is None
        assert result.edge_explanations is None
        assert result.strategy_explanation is None

    def test_partial_result_with_some_outputs(self) -> None:
        """Partial status is valid with some outputs present and some absent."""
        result = PostPlanResult(
            status=PostPlanStatus.PARTIAL,
            node_explanations={"gene:TYRP1": "Pigmentation-associated gene."},
            strategy_explanation="Strategy targets the pigmentation pathway via TYRP1.",
        )
        assert result.status == PostPlanStatus.PARTIAL
        assert result.guide_risk is None  # unavailable → partial
        assert result.node_explanations is not None

    def test_full_complete_result(self) -> None:
        result = PostPlanResult(
            status=PostPlanStatus.COMPLETE,
            guide_risk={"guides": [{"sequence": "ATCG", "score": 0.95}]},
            population_analysis={"generations": 50, "penetration": 0.8},
            node_explanations={"gene:TYRP1": "Involved in melanin synthesis."},
            edge_explanations={"gene:TYRP1->gene:DCT": "Functional association via STRING."},
            strategy_explanation="Selected strategy targets coat pigmentation via TYRP1 and DCT.",
        )
        assert result.status == PostPlanStatus.COMPLETE
        assert result.guide_risk is not None
        assert result.population_analysis is not None

    def test_missing_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            PostPlanResult()  # type: ignore[call-arg]

    def test_invalid_status_value_raises(self) -> None:
        with pytest.raises((ValueError, ValidationError)):
            PostPlanResult(status="pending")  # type: ignore[arg-type]

    def test_wrong_node_explanations_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            PostPlanResult(
                status=PostPlanStatus.COMPLETE,
                node_explanations="should be a dict",  # type: ignore[arg-type]
            )
