"""
Unit tests for GuideRiskProvider in Relict Core Post-Plan Analysis.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.models.post_plan import PostPlanStatus
from app.post_plan.guide_risk import (
    CHOPCHOPAdapter,
    CRISPORAdapter,
    ChopchopAnalysisResult,
    CrisporAnalysisResult,
    Evo2Adapter,
    Evo2AnalysisResult,
    Evo2RiskMetric,
    GuideRiskProvider,
)
from app.post_plan.guide_risk.chopchop import ProviderStatus as ChopchopStatus
from app.post_plan.guide_risk.crispor import ProviderStatus as CrisporStatus
from app.post_plan.guide_risk.evo2 import ProviderStatus as Evo2Status


@pytest.mark.asyncio
async def test_guide_risk_provider_all_success():
    """Test when CRISPOR, CHOPCHOP, and Evo 2 all succeed."""
    mock_crispor = AsyncMock(spec=CRISPORAdapter)
    mock_crispor.analyze_target.return_value = CrisporAnalysisResult(
        provider_status=CrisporStatus.SUCCESS,
        target_identifier="TYRP1",
        genome="canFam3",
        pam="NGG",
        guide_candidates=[],
        warnings=[],
        errors=[],
        provenance={},
    )

    mock_chopchop = AsyncMock(spec=CHOPCHOPAdapter)
    mock_chopchop.analyze_target.return_value = ChopchopAnalysisResult(
        provider_status=ChopchopStatus.SUCCESS,
        target="TYRP1",
        species="Canis lupus",
        genome="canFam3",
        pam="NGG",
        guide_candidates=[],
        warnings=[],
        errors=[],
        provenance={},
    )

    mock_evo2 = AsyncMock(spec=Evo2Adapter)
    mock_evo2.analyze_sequence.return_value = Evo2AnalysisResult(
        provider_status=Evo2Status.SUCCESS,
        target_id="TYRP1",
        species="Canis lupus",
        assembly="canFam3",
        risk_metric=Evo2RiskMetric(
            raw_log_likelihood=-128.0,
            mean_log_likelihood=-1.28,
            sequence_length=100,
        ),
        warnings=[],
        errors=[],
        provenance={},
    )

    provider = GuideRiskProvider(
        crispor_adapter=mock_crispor,
        chopchop_adapter=mock_chopchop,
        evo2_adapter=mock_evo2,
    )

    results, status = await provider.evaluate_target(
        target_identifier="TYRP1",
        species="Canis lupus",
        genome="canFam3",
        sequence="ATTCTACTTTTCAACAATAATACATAAACATATTGGCTTGTGGTAGCAACACT",
        pam="NGG",
        include_evo2=True,
    )

    assert status == PostPlanStatus.COMPLETE
    assert "crispor" in results
    assert "chopchop" in results
    assert "evo2" in results
    assert results["evo2"]["risk_metric"]["raw_log_likelihood"] == -128.0


@pytest.mark.asyncio
async def test_guide_risk_provider_partial_analysis():
    """Test partial analysis when CHOPCHOP is unavailable but CRISPOR succeeds."""
    mock_crispor = AsyncMock(spec=CRISPORAdapter)
    mock_crispor.analyze_target.return_value = CrisporAnalysisResult(
        provider_status=CrisporStatus.SUCCESS,
        target_identifier="TYRP1",
        genome="canFam3",
        pam="NGG",
        guide_candidates=[],
        warnings=[],
        errors=[],
        provenance={},
    )

    mock_chopchop = AsyncMock(spec=CHOPCHOPAdapter)
    mock_chopchop.analyze_target.return_value = ChopchopAnalysisResult(
        provider_status=ChopchopStatus.UNAVAILABLE,
        target="TYRP1",
        species="Canis lupus",
        genome="canFam3",
        pam="NGG",
        guide_candidates=[],
        warnings=[],
        errors=["CHOPCHOP not installed or executable missing."],
        provenance={},
    )

    provider = GuideRiskProvider(
        crispor_adapter=mock_crispor,
        chopchop_adapter=mock_chopchop,
    )

    results, status = await provider.evaluate_target(
        target_identifier="TYRP1",
        species="Canis lupus",
        genome="canFam3",
        sequence="ATTCTACTTTTCAACAATAATACATAAACATATTGGCTTGTGGTAGCAACACT",
        pam="NGG",
    )

    assert status == PostPlanStatus.PARTIAL
    assert results["crispor"]["provider_status"] == "success"
    assert results["chopchop"]["provider_status"] == "unavailable"


@pytest.mark.asyncio
async def test_guide_risk_provider_both_failed():
    """Test failure status when all providers fail or are unavailable."""
    mock_crispor = AsyncMock(spec=CRISPORAdapter)
    mock_crispor.analyze_target.return_value = CrisporAnalysisResult(
        provider_status=CrisporStatus.FAILED,
        target_identifier="TYRP1",
        genome="canFam3",
        pam="NGG",
        guide_candidates=[],
        warnings=[],
        errors=["CRISPOR error."],
        provenance={},
    )

    mock_chopchop = AsyncMock(spec=CHOPCHOPAdapter)
    mock_chopchop.analyze_target.return_value = ChopchopAnalysisResult(
        provider_status=ChopchopStatus.FAILED,
        target="TYRP1",
        species="Canis lupus",
        genome="canFam3",
        pam="NGG",
        guide_candidates=[],
        warnings=[],
        errors=["CHOPCHOP error."],
        provenance={},
    )

    provider = GuideRiskProvider(
        crispor_adapter=mock_crispor,
        chopchop_adapter=mock_chopchop,
    )

    results, status = await provider.evaluate_target(
        target_identifier="TYRP1",
        species="Canis lupus",
        genome="canFam3",
        sequence="ATTCTACTTTTCAACAATAATACATAAACATATTGGCTTGTGGTAGCAACACT",
        pam="NGG",
    )

    assert status == PostPlanStatus.FAILED
