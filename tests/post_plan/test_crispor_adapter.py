"""
Unit tests for CRISPORAdapter in Relict Core.

All tests are deterministic and isolated using mocks (no direct CRISPOR subprocess calls).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.post_plan.guide_risk.crispor import (
    CRISPORAdapter,
    CrisporAnalysisResult,
    CrisporConfig,
    CrisporGuideCandidate,
    CrisporOfftarget,
    ProviderStatus,
    parse_crispor_tsv_outputs,
)

SAMPLE_GUIDES_TSV = """#seqId\tguideId\ttargetSeq\tmitSpecScore\tcfdSpecScore\tofftargetCount\ttargetGenomeGeneLocus\tDoench '16-Score\tMoreno-Mateos-Score\tDoench-RuleSet3-Score\tOut-of-Frame-Score\tLindel-Score\tGrafEtAlStatus
testSeq\t41forw\tTACATAAACATATTGGCTTGTGG\t68\t98\t6\texon:YAL069W/YAL068W-A\t58\t38\t4\t69\t90\ttt
testSeq\t137forw\tAGAATATTTCGTACTTACACAGG\t54\t100\t6\tintergenic:YAL069W/YAL068W-A-PAU8\t56\t19\t-23\t63\t66\tGrafOK
testSeq\t80rev\tTCAAGCAAATTGCAATATTGAGG\t43\t94\t13\tintergenic:YAL069W/YAL068W-A-PAU8\t52\t31\t-89\t73\t84\tGrafOK
"""

SAMPLE_OFFS_TSV = """seqId\tguideId\tguideSeq\tofftargetSeq\tmismatchPos\tmismatchCount\tmitOfftargetScore\tcfdOfftargetScore\tchrom\tstart\tend\tstrand\tlocusDesc
testSeq\t41forw\tTACATAAACATATTGGCTTGTGG\tTACATAAACATATTGACTTGTGG\t...............*....\t1\t17.2\t1.0\tchrIV\t1524618\t1524640\t-\texon:YDR543C
testSeq\t41forw\tTACATAAACATATTGGCTTGTGG\tTACATAAACATATTGACTTGAAG\t...............*....\t1\t3.44\t0.259\tchrXV\t1083915\t1083937\t-\tintergenic:PAU21-YOR394C-A
testSeq\t137forw\tAGAATATTTCGTACTTACACAGG\tAGAATATTTCGTACTTACACAGA\t....................\t0\t20.0\t0.069\tchrV\t569498\t569520\t-\tintergenic:YER188W-YER188C-A
"""


@pytest.fixture
def mock_crispor_output_dir(tmp_path: Path) -> tuple[Path, Path]:
    """Create mock TSV output files."""
    guides_file = tmp_path / "guides.tsv"
    offs_file = tmp_path / "offtargets.tsv"
    guides_file.write_text(SAMPLE_GUIDES_TSV, encoding="utf-8")
    offs_file.write_text(SAMPLE_OFFS_TSV, encoding="utf-8")
    return guides_file, offs_file


def test_parse_crispor_tsv_outputs(mock_crispor_output_dir: tuple[Path, Path]):
    """Test parsing of valid CRISPOR TSV outputs."""
    guides_file, offs_file = mock_crispor_output_dir
    candidates = parse_crispor_tsv_outputs(guides_file, offs_file)

    assert len(candidates) == 3
    # Check first guide
    g1 = candidates[0]
    assert g1.guide_id == "41forw"
    assert g1.target_seq == "TACATAAACATATTGGCTTGTGG"
    assert g1.strand == "+"
    assert g1.start_pos == 41
    assert g1.mit_spec_score == 68.0
    assert g1.cfd_spec_score == 98.0
    assert g1.offtarget_count == 6
    assert g1.target_locus == "exon:YAL069W/YAL068W-A"
    assert g1.doench_16_score == 58.0
    assert g1.moreno_mateos_score == 38.0
    assert g1.ruleset3_score == 4.0
    assert g1.out_of_frame_score == 69.0
    assert g1.lindel_score == 90.0
    assert g1.graf_status == "tt"
    assert len(g1.offtargets) == 2

    # Check reverse strand guide
    g3 = candidates[2]
    assert g3.guide_id == "80rev"
    assert g3.strand == "-"
    assert g3.start_pos == 80
    assert g3.ruleset3_score == -89.0
    assert len(g3.offtargets) == 0


def test_sequence_validation():
    """Test input sequence validation edge cases."""
    adapter = CRISPORAdapter()

    # Empty sequence
    ok, err = adapter.validate_sequence("")
    assert not ok
    assert "empty" in err

    # Too short sequence (<23bp)
    ok, err = adapter.validate_sequence("ATCGATCG")
    assert not ok
    assert "too short" in err

    # Invalid characters
    ok, err = adapter.validate_sequence("ATCGATCGATCGATCGATCGXYZ123")
    assert not ok
    assert "invalid nucleotide" in err

    # Valid sequence
    ok, err = adapter.validate_sequence("ATTCTACTTTTCAACAATAATACATAAACATATTGGCTTGTGGTAGCAACACT")
    assert ok
    assert err == ""


@pytest.mark.asyncio
async def test_successful_crispor_analysis(mock_crispor_output_dir: tuple[Path, Path]):
    """Test full analysis flow with mocked successful subprocess execution."""
    guides_file, offs_file = mock_crispor_output_dir
    adapter = CRISPORAdapter(CrisporConfig(use_wsl=False))

    async def mock_communicate():
        return b"CRISPOR completed\n", b""

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = mock_communicate

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)), \
         patch("app.post_plan.guide_risk.crispor.parse_crispor_tsv_outputs", return_value=parse_crispor_tsv_outputs(guides_file, offs_file)):

        result = await adapter.analyze_target(
            target_identifier="testGene",
            sequence="ATTCTACTTTTCAACAATAATACATAAACATATTGGCTTGTGGTAGCAACACT",
            genome="sacCer3",
            pam="NGG",
        )

        assert result.provider_status == ProviderStatus.SUCCESS
        assert result.target_identifier == "testGene"
        assert result.genome == "sacCer3"
        assert result.pam == "NGG"
        assert len(result.guide_candidates) == 3
        assert len(result.errors) == 0


@pytest.mark.asyncio
async def test_executable_missing():
    """Test failure when CRISPOR binary / python runtime cannot be found."""
    adapter = CRISPORAdapter(CrisporConfig(use_wsl=False))

    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("No such file or directory: 'crispor.py'")):
        result = await adapter.analyze_target(
            target_identifier="testGene",
            sequence="ATTCTACTTTTCAACAATAATACATAAACATATTGGCTTGTGGTAGCAACACT",
            genome="sacCer3",
        )

        assert result.provider_status == ProviderStatus.UNAVAILABLE
        assert len(result.guide_candidates) == 0
        assert any("not found" in err.lower() for err in result.errors)


@pytest.mark.asyncio
async def test_subprocess_failure():
    """Test failure handling when CRISPOR exits with non-zero code."""
    adapter = CRISPORAdapter(CrisporConfig(use_wsl=False))

    async def mock_communicate():
        return b"", b"Error: genome hg38.2bit not found in /genomes/hg38\n"

    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate = mock_communicate

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
        result = await adapter.analyze_target(
            target_identifier="testGene",
            sequence="ATTCTACTTTTCAACAATAATACATAAACATATTGGCTTGTGGTAGCAACACT",
            genome="hg38",
        )

        assert result.provider_status == ProviderStatus.FAILED
        assert len(result.guide_candidates) == 0
        assert any("process execution failed" in err.lower() for err in result.errors)


@pytest.mark.asyncio
async def test_timeout_handling():
    """Test timeout handling when CRISPOR execution exceeds time limit."""
    adapter = CRISPORAdapter(CrisporConfig(timeout_seconds=0.01, use_wsl=False))

    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
        mock_proc = MagicMock()
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
            result = await adapter.analyze_target(
                target_identifier="testGene",
                sequence="ATTCTACTTTTCAACAATAATACATAAACATATTGGCTTGTGGTAGCAACACT",
                genome="sacCer3",
            )

            assert result.provider_status == ProviderStatus.FAILED
            assert len(result.guide_candidates) == 0
            assert any("timed out" in err.lower() for err in result.errors)


@pytest.mark.asyncio
async def test_empty_unsupported_genome():
    """Test handling of missing or unsupported genome assembly."""
    adapter = CRISPORAdapter()

    result = await adapter.analyze_target(
        target_identifier="testGene",
        sequence="ATTCTACTTTTCAACAATAATACATAAACATATTGGCTTGTGGTAGCAACACT",
        genome="",
    )

    assert result.provider_status == ProviderStatus.UNAVAILABLE
    assert any("genome assembly must be explicitly specified" in err.lower() for err in result.errors)


@pytest.mark.asyncio
async def test_malformed_tsv_output(tmp_path: Path):
    """Test graceful handling when CRISPOR produces empty or malformed TSV output."""
    empty_tsv = tmp_path / "empty.tsv"
    empty_tsv.write_text("", encoding="utf-8")

    candidates = parse_crispor_tsv_outputs(empty_tsv)
    assert candidates == []

    # Non-existent file
    candidates_missing = parse_crispor_tsv_outputs(tmp_path / "nonexistent.tsv")
    assert candidates_missing == []
