"""Tests for app.models.failures — FailureCode and FailureDetail."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.failures import FailureCode, FailureDetail

# ---------------------------------------------------------------------------
# FailureCode enum
# ---------------------------------------------------------------------------


class TestFailureCodeEnum:
    def test_failure_code_has_exactly_five_values(self) -> None:
        """Architecture §3.12 mandates exactly five failure codes."""
        expected = {
            "CLARIFICATION_REQUIRED",
            "INSUFFICIENT_EVIDENCE",
            "NO_FEASIBLE_PLAN",
            "VALIDATION_FAILED",
            "PARTIAL_ANALYSIS",
        }
        actual = {fc.value for fc in FailureCode}
        assert actual == expected, f"Unexpected values: {actual ^ expected}"
        assert len(FailureCode) == 5

    def test_failure_code_values_are_strings(self) -> None:
        """FailureCode uses StrEnum, so members should compare equal to strings."""
        assert FailureCode.CLARIFICATION_REQUIRED == "CLARIFICATION_REQUIRED"
        assert FailureCode.INSUFFICIENT_EVIDENCE == "INSUFFICIENT_EVIDENCE"
        assert FailureCode.NO_FEASIBLE_PLAN == "NO_FEASIBLE_PLAN"
        assert FailureCode.VALIDATION_FAILED == "VALIDATION_FAILED"
        assert FailureCode.PARTIAL_ANALYSIS == "PARTIAL_ANALYSIS"

    def test_failure_code_is_serialisable_as_string(self) -> None:
        fd = FailureDetail(code=FailureCode.VALIDATION_FAILED, message="bad strategy")
        dumped = fd.model_dump()
        assert dumped["code"] == "VALIDATION_FAILED"

    def test_failure_code_rejects_unknown_value(self) -> None:
        with pytest.raises((ValueError, ValidationError)):
            FailureDetail(code="UNKNOWN_CODE", message="x")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# FailureDetail model
# ---------------------------------------------------------------------------


class TestFailureDetail:
    def test_minimal_valid_instance(self) -> None:
        fd = FailureDetail(
            code=FailureCode.INSUFFICIENT_EVIDENCE,
            message="Not enough evidence for planning.",
        )
        assert fd.code == FailureCode.INSUFFICIENT_EVIDENCE
        assert fd.message == "Not enough evidence for planning."
        assert fd.stage is None

    def test_full_valid_instance(self) -> None:
        fd = FailureDetail(
            code=FailureCode.NO_FEASIBLE_PLAN,
            message="No strategy satisfies all constraints.",
            stage="planner",
        )
        assert fd.stage == "planner"

    def test_missing_required_code_raises(self) -> None:
        with pytest.raises(ValidationError):
            FailureDetail(message="missing code")  # type: ignore[call-arg]

    def test_missing_required_message_raises(self) -> None:
        with pytest.raises(ValidationError):
            FailureDetail(code=FailureCode.PARTIAL_ANALYSIS)  # type: ignore[call-arg]

    def test_wrong_code_type_raises(self) -> None:
        with pytest.raises((ValueError, ValidationError)):
            FailureDetail(code=42, message="wrong type")  # type: ignore[arg-type]
