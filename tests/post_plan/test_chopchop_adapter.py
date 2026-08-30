"""
Unit tests for CHOPCHOPAdapter in Relict Core.

All tests are deterministic and isolated using mocks (no direct CHOPCHOP subprocess calls).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.post_plan.guide_risk.chopchop import (
    CHOPCHOPAdapter,
    ChopchopAnalysisResult,
    ChopchopConfig,
    ChopchopGuideCandidate,
    ProviderStatus,
    parse_chopchop_output,
)

SAMPLE_CHOPCHOP_ALL_OUTPUT = """
Rank\tTarget sequence\tGenomic location\tStrand\tGC content (%)\tSelf-complementarity\tMM0\tMM1\tMM2\tMM3\tXU_2015\tDOENCH_2014\tDOENCH_2016\tMORENO_MATEOS_2015\tCHARI_2015\tG_20\tALKAN_2018\tZHANG_2019
1\tTACATAAACATATTGGCTTGTGG\tchrIV:1524618\t+\t40.0\t0\t1\t0\t2\t4\t0.75\t0.65\t58.2\t38.1\t0.0\t1.0\t-12.4\t0.82
2\tAGAATATTTCGTACTTACACAGG\tchrIV:1524700\t+\t35.0\t1\t1\t1\t0\t5\t0.60\t0.50\t56.0\t19.4\t0.0\t0.0\t-10.1\t0.70
3\tTCAAGCAAATTGCAATATTGAGG\tchrIV:1524850\t-\t30.0\t0\t1\t0\t3\t10\t0.45\t0.40\t52.1\t31.0\t0.0\t1.0\t-8.5\t0.55
"""

SAMPLE_CHOPCHOP_STANDARD_OUTPUT = """
Rank\tTarget sequence\tGenomic location\tStrand\tGC content (%)\tSelf-complementarity\tMM0\tMM1\tMM2\tMM3\tEfficiency
1\tTACATAAACATATTGGCTTGTGG\tchrIV:1524618\t+\t40.0\t0\t1\t0\t2\t4\t58.2
2\tAGAATATTTCGTACTTACACAGG\tchrIV:1524700\t+\t35.0\t1\t1\t1\t0\t5\t56.0
"""


def test_parse_chopchop_all_output():
    """Test parsing of CHOPCHOP ALL scores tabular output."""
    candidates = parse_chopchop_output(SAMPLE_CHOPCHOP_ALL_OUTPUT)
    assert len(candidates) == 3

    # First candidate
    c1 = candidates[0]
    assert c1.rank == 1
    assert c1.target_seq == "TACATAAACATATTGGCTTGTGG"
    assert c1.genomic_location == "chrIV:1524618"
    assert c1.strand == "+"
    assert c1.gc_content == 40.0
    assert c1.self_complementarity == 0.0
    assert c1.mm0 == 1
    assert c1.mm1 == 0
    assert c1.mm2 == 2
    assert c1.mm3 == 4
    assert c1.efficiency_score == 58.2
    assert c1.scores["DOENCH_2016"] == 58.2
    assert c1.scores["MORENO_MATEOS_2015"] == 38.1
    assert c1.scores["ALKAN_2018"] == -12.4

    # Reverse strand candidate
    c3 = candidates[2]
    assert c3.rank == 3
    assert c3.strand == "-"
    assert c3.mm3 == 10
    assert c3.scores["XU_2015"] == 0.45


def test_parse_chopchop_standard_output():
    """Test parsing of CHOPCHOP standard efficiency output."""
    candidates = parse_chopchop_output(SAMPLE_CHOPCHOP_STANDARD_OUTPUT)
    assert len(candidates) == 2
    assert candidates[0].efficiency_score == 58.2
    assert candidates[1].efficiency_score == 56.0


def test_parse_chopchop_malformed_output():
    """Test graceful handling of empty or corrupted output."""
    assert parse_chopchop_output("") == []
    assert parse_chopchop_output("No candidates found") == []
    assert parse_chopchop_output("Rank\tTarget sequence\tGenomic location\tStrand\n") == []


def test_validate_target():
    """Test target validation."""
    adapter = CHOPCHOPAdapter()

    ok, err = adapter.validate_target("")
    assert not ok
    assert "empty" in err

    ok, err = adapter.validate_target("TYRP1")
    assert ok
    assert err == ""

    ok, err = adapter.validate_target("chr4:1000-2000")
    assert ok
    assert err == ""


@pytest.mark.asyncio
async def test_successful_chopchop_analysis():
    """Test full analysis flow with mocked successful subprocess execution."""
    adapter = CHOPCHOPAdapter(ChopchopConfig(use_wsl=False))

    async def mock_communicate():
        return SAMPLE_CHOPCHOP_ALL_OUTPUT.encode("utf-8"), b""

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = mock_communicate

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
        result = await adapter.analyze_target(
            target="TYRP1",
            species="Canis lupus",
            genome="canFam3",
            pam="NGG",
        )

        assert result.provider_status == ProviderStatus.SUCCESS
        assert result.target == "TYRP1"
        assert result.species == "Canis lupus"
        assert result.genome == "canFam3"
        assert len(result.guide_candidates) == 3
        assert len(result.errors) == 0
        assert result.provenance["guide_count"] == 3


@pytest.mark.asyncio
async def test_executable_missing():
    """Test handling when CHOPCHOP script / python executable is not found."""
    adapter = CHOPCHOPAdapter(ChopchopConfig(use_wsl=False))

    with patch(
        "asyncio.create_subprocess_exec", side_effect=FileNotFoundError("chopchop.py not found")
    ):
        result = await adapter.analyze_target(
            target="TYRP1",
            species="Canis lupus",
            genome="canFam3",
        )

        assert result.provider_status == ProviderStatus.UNAVAILABLE
        assert len(result.guide_candidates) == 0
        assert any("not found" in err.lower() for err in result.errors)


@pytest.mark.asyncio
async def test_subprocess_failure():
    """Test handling when CHOPCHOP exits with a non-zero code."""
    adapter = CHOPCHOPAdapter(ChopchopConfig(use_wsl=False))

    async def mock_communicate():
        return b"", b"Error: Gene table for canFam3 not found in genePred_folder\n"

    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate = mock_communicate

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
        result = await adapter.analyze_target(
            target="TYRP1",
            species="Canis lupus",
            genome="canFam3",
        )

        assert result.provider_status == ProviderStatus.FAILED
        assert len(result.guide_candidates) == 0
        assert any("execution failed" in err.lower() for err in result.errors)


@pytest.mark.asyncio
async def test_timeout_handling():
    """Test timeout handling when CHOPCHOP execution exceeds timeout limit."""
    adapter = CHOPCHOPAdapter(ChopchopConfig(timeout_seconds=0.01, use_wsl=False))

    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
        mock_proc = MagicMock()
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
            result = await adapter.analyze_target(
                target="TYRP1",
                species="Canis lupus",
                genome="canFam3",
            )

            assert result.provider_status == ProviderStatus.FAILED
            assert len(result.guide_candidates) == 0
            assert any("timed out" in err.lower() for err in result.errors)


@pytest.mark.asyncio
async def test_missing_genome():
    """Test handling when genome assembly is empty."""
    adapter = CHOPCHOPAdapter()

    result = await adapter.analyze_target(
        target="TYRP1",
        species="Canis lupus",
        genome="",
    )

    assert result.provider_status == ProviderStatus.UNAVAILABLE
    assert any(
        "genome assembly must be explicitly specified" in err.lower() for err in result.errors
    )
