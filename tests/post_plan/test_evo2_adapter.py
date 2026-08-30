"""
Unit tests for Evo2Adapter in Relict Core Sequence Risk Analysis.

All tests are deterministic and isolated using mocks (no direct GPU inference required).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.post_plan.guide_risk.evo2 import (
    Evo2Adapter,
    Evo2AnalysisResult,
    Evo2Config,
    Evo2RiskMetric,
    ProviderStatus,
)


def test_sequence_validation():
    """Test sequence validation rules for Evo 2."""
    adapter = Evo2Adapter(Evo2Config(max_sequence_length=100))

    # Empty sequence
    ok, err = adapter.validate_sequence("")
    assert not ok
    assert "empty" in err

    # Sequence too long
    ok, err = adapter.validate_sequence("A" * 150)
    assert not ok
    assert "exceeds maximum" in err

    # Invalid bases
    ok, err = adapter.validate_sequence("ATCGXYZ123")
    assert not ok
    assert "invalid nucleotide" in err

    # Valid sequence
    ok, err = adapter.validate_sequence("ATCGATCGATCG")
    assert ok
    assert err == ""


@pytest.mark.asyncio
async def test_successful_evo2_inference():
    """Test successful Evo 2 inference with mocked runner output."""
    adapter = Evo2Adapter()

    runner_stdout = (
        b'{"success": true, "raw_log_likelihood": -128.5, "mean_log_likelihood": -1.285, "len": 100}'
    )

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(runner_stdout, b""))

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
        result = await adapter.analyze_sequence(
            target_id="TYRP1_promoter",
            sequence="ATCG" * 25,
            species="Canis lupus",
            assembly="canFam3",
        )

        assert result.provider_status == ProviderStatus.SUCCESS
        assert result.target_id == "TYRP1_promoter"
        assert result.species == "Canis lupus"
        assert result.assembly == "canFam3"
        assert result.risk_metric is not None
        assert result.risk_metric.raw_log_likelihood == -128.5
        assert result.risk_metric.mean_log_likelihood == -1.285
        assert result.risk_metric.sequence_length == 100

        # Verify strict score semantics: no fabricated probability/biological score
        assert result.risk_metric.derived_metric is None
        assert result.risk_metric.interpretation == "NOT_YET_DEFINED"
        assert len(result.risk_metric.assumptions) > 0
        assert len(result.risk_metric.limitations) > 0


@pytest.mark.asyncio
async def test_model_unavailable_error():
    """Test handling when Evo 2 module or checkpoint is unavailable."""
    adapter = Evo2Adapter()

    runner_stdout = b'{"success": false, "error": "No module named \'evo2\'"}'

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(runner_stdout, b""))

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
        result = await adapter.analyze_sequence(
            target_id="TYRP1_promoter",
            sequence="ATCG" * 25,
            species="Canis lupus",
            assembly="canFam3",
        )

        assert result.provider_status == ProviderStatus.UNAVAILABLE
        assert result.risk_metric is None
        assert any("no module" in err.lower() for err in result.errors)


@pytest.mark.asyncio
async def test_cuda_runtime_error():
    """Test handling when Evo 2 encounters CUDA/GPU failure."""
    adapter = Evo2Adapter()

    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(
        return_value=(b"", b"RuntimeError: CUDA out of memory. Tried to allocate 4.00 GiB")
    )

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
        result = await adapter.analyze_sequence(
            target_id="TYRP1_promoter",
            sequence="ATCG" * 25,
            species="Canis lupus",
            assembly="canFam3",
        )

        assert result.provider_status == ProviderStatus.FAILED
        assert result.risk_metric is None
        assert any("cuda out of memory" in err.lower() for err in result.errors)


@pytest.mark.asyncio
async def test_timeout_handling():
    """Test timeout handling during model inference."""
    adapter = Evo2Adapter(Evo2Config(timeout_seconds=0.01))

    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
        mock_proc = MagicMock()
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
            result = await adapter.analyze_sequence(
                target_id="TYRP1_promoter",
                sequence="ATCG" * 25,
                species="Canis lupus",
                assembly="canFam3",
            )

            assert result.provider_status == ProviderStatus.FAILED
            assert result.risk_metric is None
            assert any("timed out" in err.lower() for err in result.errors)


@pytest.mark.asyncio
async def test_missing_assembly():
    """Test handling of missing assembly identifier."""
    adapter = Evo2Adapter()

    result = await adapter.analyze_sequence(
        target_id="TYRP1_promoter",
        sequence="ATCG" * 25,
        species="Canis lupus",
        assembly="",
    )

    assert result.provider_status == ProviderStatus.UNAVAILABLE
    assert any("assembly must be specified" in err.lower() for err in result.errors)


@pytest.mark.asyncio
async def test_malformed_runner_output():
    """Test graceful handling of non-JSON stdout from runner process."""
    adapter = Evo2Adapter()

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"Fatal crash: segmentation fault\n", b""))

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
        result = await adapter.analyze_sequence(
            target_id="TYRP1_promoter",
            sequence="ATCG" * 25,
            species="Canis lupus",
            assembly="canFam3",
        )

        assert result.provider_status == ProviderStatus.FAILED
        assert result.risk_metric is None
        assert any("malformed json" in err.lower() for err in result.errors)
