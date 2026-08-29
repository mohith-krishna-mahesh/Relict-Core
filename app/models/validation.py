"""ValidationResult: output contract of the Plan Validator stage."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    """
    Records the deterministic checks performed by the Plan Validator
    and their outcomes (architecture §3.8).

    A strategy with ``valid=False`` does not proceed to Post-Plan Analysis.

    Fields
    ------
    valid
        True if the strategy passed all validator checks.
    checks
        Names or descriptions of every check that was performed,
        in execution order.
    violations
        Checks that failed (subset of ``checks``).  Non-empty implies
        ``valid=False``.
    warnings
        Non-fatal observations recorded during validation.
    """

    valid: bool
    checks: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
