"""Tests for app.models.validation — ValidationResult."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.validation import ValidationResult


class TestValidationResult:
    def test_minimal_passing_result(self) -> None:
        result = ValidationResult(valid=True)
        assert result.valid is True
        assert result.checks == []
        assert result.violations == []
        assert result.warnings == []

    def test_full_passing_result(self) -> None:
        result = ValidationResult(
            valid=True,
            checks=["edit_budget", "target_coverage", "constraints"],
            violations=[],
            warnings=["Strategy may have unknown relationship between candidate A and B."],
        )
        assert result.valid is True
        assert len(result.checks) == 3
        assert len(result.warnings) == 1

    def test_failing_result_with_violations(self) -> None:
        result = ValidationResult(
            valid=False,
            checks=["edit_budget", "target_coverage"],
            violations=["edit_budget: 5 edits requested, max_edits=3"],
            warnings=[],
        )
        assert result.valid is False
        assert "edit_budget: 5 edits requested, max_edits=3" in result.violations

    def test_missing_valid_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            ValidationResult(checks=["x"])  # type: ignore[call-arg]

    def test_wrong_valid_type_raises(self) -> None:
        # Pydantic v2 coerces string "yes"/"no" to bool via standard Python
        # truthiness rules, so we use a list — an unconvertible type — to
        # ensure ValidationError is actually raised.
        with pytest.raises(ValidationError):
            ValidationResult(valid=["not", "a", "bool"])  # type: ignore[arg-type]

    def test_wrong_violations_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            ValidationResult(valid=False, violations="not a list")  # type: ignore[arg-type]
