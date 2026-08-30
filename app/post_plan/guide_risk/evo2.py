"""
Evo 2 Adapter for Relict Core Post-Plan Sequence & Regulatory Risk Analysis.

This module provides the Relict-side adapter for Evo 2 (Arc Institute genomic foundation model).
It isolates model loading, sequence evaluation, raw score normalization, and failure handling.

Architecture constraints (Relict Core architecture §2.5, §8):
- Model outputs are NOT biological evidence.
- Evo 2 belongs strictly to Post-Plan Analysis; it does NOT select candidate targets or modify Planner strategies.
- Evo 2 raw outputs (such as log-likelihoods / perplexities) must NEVER be automatically conflated with
  clinical risk or probability of real-world biological efficacy without explicit calibration.
- Raw model outputs, derived metrics, and interpretations are strictly separated.
- If Evo 2 is unavailable (e.g. missing GPU/VRAM, uninstalled runtime), returns structured UNAVAILABLE
  status allowing Post-Plan Analysis to gracefully report PARTIAL_ANALYSIS.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ProviderStatus(StrEnum):
    """Execution status of the Evo 2 provider."""

    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class Evo2RiskMetric(BaseModel):
    """
    Normalized sequence risk and likelihood metrics produced by Evo 2.

    Strict semantic separation:
    - raw_log_likelihood: Raw model sequence log-likelihood
    - mean_log_likelihood: Per-nucleotide average log-likelihood
    - sequence_length: Number of evaluated nucleotides
    - derived_metric: Derived numeric score (if calibrated, otherwise None)
    - interpretation: Qualitative biological interpretation (marked 'NOT_YET_DEFINED' by default)
    - assumptions: Explicit model assumptions (e.g. context window limits, zero-shot distribution)
    - limitations: Known limitations (e.g. genomic foundation priors do not guarantee in-vivo efficacy)
    """

    raw_log_likelihood: float | None = None
    mean_log_likelihood: float | None = None
    sequence_length: int = 0
    derived_metric: float | None = None
    interpretation: str = "NOT_YET_DEFINED"
    assumptions: list[str] = Field(
        default_factory=lambda: [
            "Evaluated under zero-shot autoregressive genomic prior.",
            "Local sequence context evaluated up to model maximum context length.",
        ]
    )
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Genomic language model log-likelihood reflects sequence probability under training distribution, not experimental editing efficiency or clinical safety.",
            "In-vivo biological outcomes require empirical validation.",
        ]
    )


class Evo2AnalysisResult(BaseModel):
    """
    Normalized result of Evo 2 sequence risk analysis for a target locus.

    Attached to PostPlanResult.guide_risk under the 'evo2' key.
    """

    provider: str = "Evo2"
    provider_status: ProviderStatus
    model_name: str = "arcinstitute/evo2_1b_base"
    target_id: str
    species: str
    assembly: str
    risk_metric: Evo2RiskMetric | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


@dataclass
class Evo2Config:
    """Configuration settings for the Evo 2 adapter."""

    model_name: str = "arcinstitute/evo2_1b_base"
    python_executable: str = "C:/Users/walki/evo2-env/Scripts/python.exe"
    device: str = "cuda"  # 'cuda' or 'cpu'
    max_sequence_length: int = 8192
    timeout_seconds: float = 60.0
    lazy_load: bool = True


class Evo2Adapter:
    """
    Adapter for running Evo 2 sequence and regulatory risk analysis.

    Isolation:
    - Operates downstream of validated Planner strategies.
    - Never modifies input project or strategy models.
    - Encapsulates GPU/CUDA availability checks, model invocation, and timeout management.
    """

    def __init__(self, config: Evo2Config | None = None) -> None:
        self.config = config or Evo2Config()

    def validate_sequence(self, sequence: str) -> tuple[bool, str]:
        """Validate input nucleotide sequence."""
        cleaned = sequence.strip().upper()
        if not cleaned:
            return False, "Input sequence cannot be empty."
        if len(cleaned) > self.config.max_sequence_length:
            return (
                False,
                f"Sequence length ({len(cleaned)}bp) exceeds maximum supported length ({self.config.max_sequence_length}bp).",
            )
        valid_bases = set("ACGTUNRYKMSWBDHV")
        invalid = set(cleaned) - valid_bases
        if invalid:
            return False, f"Sequence contains invalid nucleotide characters: {', '.join(sorted(invalid))}"
        return True, ""

    async def analyze_sequence(
        self,
        target_id: str,
        sequence: str,
        species: str,
        assembly: str,
    ) -> Evo2AnalysisResult:
        """
        Evaluate sequence risk and likelihood metrics using Evo 2.

        Parameters
        ----------
        target_id:
            Gene or locus identifier.
        sequence:
            Target genomic DNA sequence.
        species:
            Authoritative species from ProjectContext.
        assembly:
            Genome assembly identifier.
        """
        # 1. Validate sequence
        is_valid, validation_err = self.validate_sequence(sequence)
        if not is_valid:
            return Evo2AnalysisResult(
                provider_status=ProviderStatus.FAILED,
                model_name=self.config.model_name,
                target_id=target_id,
                species=species,
                assembly=assembly,
                risk_metric=None,
                warnings=[],
                errors=[f"Sequence validation failed: {validation_err}"],
                provenance={"adapter": "Evo2Adapter"},
            )

        # 2. Check assembly/species
        if not assembly:
            return Evo2AnalysisResult(
                provider_status=ProviderStatus.UNAVAILABLE,
                model_name=self.config.model_name,
                target_id=target_id,
                species=species,
                assembly=assembly,
                risk_metric=None,
                warnings=[],
                errors=["Assembly must be specified."],
                provenance={"adapter": "Evo2Adapter"},
            )

        # 3. Execute inference via worker process or async executor to prevent event-loop blocking
        try:
            # We invoke the dedicated Evo 2 runner script in evo2-env
            runner_code = (
                "import sys, json\n"
                "try:\n"
                "    import torch\n"
                "    from evo2 import Evo2\n"
                "    seq = sys.argv[1]\n"
                "    model = Evo2(sys.argv[2])\n"
                "    with torch.no_grad():\n"
                "        logits, _ = model(seq)\n"
                "        # Calculate log-likelihood\n"
                "        log_p = -float(torch.nn.functional.cross_entropy(logits[:-1], model.tokenizer.tokenize(seq)[1:], reduction='sum'))\n"
                "        mean_log_p = log_p / max(1, len(seq))\n"
                "    print(json.dumps({'success': True, 'raw_log_likelihood': log_p, 'mean_log_likelihood': mean_log_p, 'len': len(seq)}))\n"
                "except Exception as e:\n"
                "    print(json.dumps({'success': False, 'error': str(e)}))\n"
            )

            cmd = [
                self.config.python_executable,
                "-c",
                runner_code,
                sequence.strip().upper(),
                self.config.model_name,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout_seconds,
            )
            stdout_str = stdout_b.decode("utf-8", errors="replace").strip()
            stderr_str = stderr_b.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0:
                err_msg = stderr_str or stdout_str or f"Process exited with code {proc.returncode}"
                return Evo2AnalysisResult(
                    provider_status=ProviderStatus.FAILED,
                    model_name=self.config.model_name,
                    target_id=target_id,
                    species=species,
                    assembly=assembly,
                    risk_metric=None,
                    warnings=[],
                    errors=[f"Evo 2 inference process failed: {err_msg}"],
                    provenance={"adapter": "Evo2Adapter", "return_code": proc.returncode},
                )

            import json

            try:
                payload = json.loads(stdout_str)
            except Exception:
                payload = {"success": False, "error": f"Malformed JSON from Evo 2 runner: {stdout_str}"}

            if not payload.get("success"):
                err_text = payload.get("error", "Unknown inference error")
                status = ProviderStatus.UNAVAILABLE if "not found" in err_text.lower() or "no module" in err_text.lower() else ProviderStatus.FAILED
                return Evo2AnalysisResult(
                    provider_status=status,
                    model_name=self.config.model_name,
                    target_id=target_id,
                    species=species,
                    assembly=assembly,
                    risk_metric=None,
                    warnings=[],
                    errors=[f"Evo 2 inference error: {err_text}"],
                    provenance={"adapter": "Evo2Adapter"},
                )

            metric = Evo2RiskMetric(
                raw_log_likelihood=payload.get("raw_log_likelihood"),
                mean_log_likelihood=payload.get("mean_log_likelihood"),
                sequence_length=payload.get("len", len(sequence)),
                derived_metric=None,  # Intentionally separated: no uncalibrated biological risk metric
                interpretation="NOT_YET_DEFINED",
            )

            return Evo2AnalysisResult(
                provider_status=ProviderStatus.SUCCESS,
                model_name=self.config.model_name,
                target_id=target_id,
                species=species,
                assembly=assembly,
                risk_metric=metric,
                warnings=[],
                errors=[],
                provenance={
                    "adapter": "Evo2Adapter",
                    "model": self.config.model_name,
                    "device": self.config.device,
                },
            )

        except asyncio.TimeoutError:
            logger.error("Evo 2 inference timed out after %s seconds", self.config.timeout_seconds)
            return Evo2AnalysisResult(
                provider_status=ProviderStatus.FAILED,
                model_name=self.config.model_name,
                target_id=target_id,
                species=species,
                assembly=assembly,
                risk_metric=None,
                warnings=[],
                errors=[f"Evo 2 inference timed out after {self.config.timeout_seconds}s."],
                provenance={"adapter": "Evo2Adapter", "timeout": True},
            )
        except FileNotFoundError as e:
            logger.error("Evo 2 runtime environment or executable not found: %s", e)
            return Evo2AnalysisResult(
                provider_status=ProviderStatus.UNAVAILABLE,
                model_name=self.config.model_name,
                target_id=target_id,
                species=species,
                assembly=assembly,
                risk_metric=None,
                warnings=[],
                errors=[f"Evo 2 runtime environment not found: {e}"],
                provenance={"adapter": "Evo2Adapter"},
            )
        except Exception as e:
            logger.exception("Unexpected error executing Evo 2: %s", e)
            return Evo2AnalysisResult(
                provider_status=ProviderStatus.FAILED,
                model_name=self.config.model_name,
                target_id=target_id,
                species=species,
                assembly=assembly,
                risk_metric=None,
                warnings=[],
                errors=[f"Unexpected error during Evo 2 analysis: {e}"],
                provenance={"adapter": "Evo2Adapter"},
            )
