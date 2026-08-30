"""
CHOPCHOP Adapter for Relict Core Post-Plan Guide & Risk Analysis.

This module provides the Relict-side adapter for CHOPCHOP (https://chopchop.cbu.uib.no/).
It isolates all CHOPCHOP-specific execution, tabular output parsing, score normalization,
and error handling.

Architecture constraints (Relict Core architecture §2.5, §8):
- Model outputs are NOT biological evidence.
- The Planner remains responsible for candidate target loci; CHOPCHOP only evaluates
  downstream guide efficiency, off-target counts (MM0..MM3), and self-complementarity.
- CHOPCHOP must NOT modify Planner strategy, override constraints, or insert edges.
- Failures (missing genome, execution failure, timeout, etc.) are captured as structured
  errors and must never fabricate guide sequences or scores.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ProviderStatus(StrEnum):
    """Execution status of the CHOPCHOP provider."""

    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class ChopchopGuideCandidate(BaseModel):
    """
    Candidate guide RNA produced and scored by CHOPCHOP.

    Preserves all native CHOPCHOP metrics:
    - rank: Candidate rank according to CHOPCHOP ranking criteria
    - target_seq: Full target sequence (guide + PAM)
    - genomic_location: Genomic coordinate string (e.g. 'chrIV:1524618')
    - strand: Genomic strand ('+' or '-')
    - gc_content: GC percentage
    - self_complementarity: Self-complementarity score
    - mm0: Number of off-targets with 0 mismatches
    - mm1: Number of off-targets with 1 mismatch
    - mm2: Number of off-targets with 2 mismatches
    - mm3: Number of off-targets with 3 mismatches
    - efficiency_score: Primary efficiency score
    - scores: Mapping of individual model scores (XU_2015, DOENCH_2016, etc.)
    """

    rank: int
    target_seq: str
    genomic_location: str = ""
    strand: str = "+"
    gc_content: float | None = None
    self_complementarity: float | None = None
    mm0: int = 0
    mm1: int = 0
    mm2: int = 0
    mm3: int = 0
    efficiency_score: float | None = None
    scores: dict[str, float] = Field(default_factory=dict)


class ChopchopAnalysisResult(BaseModel):
    """
    Normalized result of CHOPCHOP guide & risk analysis for a target locus.

    Attached to PostPlanResult.guide_risk under the 'chopchop' key.
    """

    provider: str = "CHOPCHOP"
    provider_status: ProviderStatus
    target: str
    species: str
    genome: str
    pam: str
    guide_candidates: list[ChopchopGuideCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


@dataclass
class ChopchopConfig:
    """Configuration settings for the CHOPCHOP adapter."""

    script_path: str = "/mnt/c/Users/walki/chopchop/chopchop.py"
    python_executable: str = "/mnt/c/Users/walki/crisporWebsite/venv/bin/python"
    config_json_path: str = "/mnt/c/Users/walki/chopchop/config.json"
    default_pam: str = "NGG"
    default_guide_length: int = 20
    default_max_mismatches: int = 3
    timeout_seconds: float = 120.0
    use_wsl: bool = True


def _parse_float(val: str | None) -> float | None:
    """Safely parse float values, returning None on invalid/missing strings."""
    if not val:
        return None
    val = val.strip()
    if val in ("", "None", "NA", "na", "-", "null"):
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _parse_int(val: str | None, default: int = 0) -> int:
    """Safely parse integer values."""
    if not val:
        return default
    val = val.strip()
    try:
        return int(float(val))
    except ValueError:
        return default


def parse_chopchop_output(stdout_text: str) -> list[ChopchopGuideCandidate]:
    """
    Parse CHOPCHOP standard tabular output into normalized ChopchopGuideCandidate objects.

    Handles standard headers:
    - Standard: Rank, Target sequence, Genomic location, Strand, GC content (%), Self-complementarity, MM0, MM1, MM2, MM3, Efficiency
    - ALL scores: ... XU_2015, DOENCH_2014, DOENCH_2016, MORENO_MATEOS_2015, CHARI_2015, G_20, ALKAN_2018, ZHANG_2019
    """
    lines = [line.strip() for line in stdout_text.splitlines() if line.strip()]
    if not lines:
        return []

    header_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("Rank\t") or "Target sequence" in line:
            header_idx = i
            break

    if header_idx == -1:
        return []

    headers = [h.strip() for h in lines[header_idx].split("\t")]
    candidates: list[ChopchopGuideCandidate] = []

    for line in lines[header_idx + 1 :]:
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("\t")]
        if len(parts) < 4:
            continue

        row = dict(zip(headers, parts))

        rank_val = _parse_int(row.get("Rank"), len(candidates) + 1)
        target_seq = row.get("Target sequence", "").strip()
        location = row.get("Genomic location", "").strip()
        strand = row.get("Strand", "+").strip()
        gc = _parse_float(row.get("GC content (%)"))
        self_comp = _parse_float(row.get("Self-complementarity"))

        mm0 = _parse_int(row.get("MM0"), 0)
        mm1 = _parse_int(row.get("MM1"), 0)
        mm2 = _parse_int(row.get("MM2"), 0)
        mm3 = _parse_int(row.get("MM3"), 0)

        # Collect scores
        scores: dict[str, float] = {}
        eff = _parse_float(row.get("Efficiency"))

        known_score_keys = [
            "XU_2015",
            "DOENCH_2014",
            "DOENCH_2016",
            "MORENO_MATEOS_2015",
            "CHARI_2015",
            "G_20",
            "ALKAN_2018",
            "ZHANG_2019",
        ]
        for k in known_score_keys:
            if k in row:
                parsed_sc = _parse_float(row[k])
                if parsed_sc is not None:
                    scores[k] = parsed_sc

        # If DOENCH_2016 or primary efficiency exists, preserve it
        if eff is None and "DOENCH_2016" in scores:
            eff = scores["DOENCH_2016"]

        candidate = ChopchopGuideCandidate(
            rank=rank_val,
            target_seq=target_seq,
            genomic_location=location,
            strand=strand,
            gc_content=gc,
            self_complementarity=self_comp,
            mm0=mm0,
            mm1=mm1,
            mm2=mm2,
            mm3=mm3,
            efficiency_score=eff,
            scores=scores,
        )
        candidates.append(candidate)

    return candidates


class CHOPCHOPAdapter:
    """
    Adapter for invoking CHOPCHOP and producing normalized guide & risk analysis.

    Isolation:
    - Never modifies input project or strategy models.
    - Captures all subprocess exceptions, timeouts, missing genomes, and parsing errors.
    - Returns structured ChopchopAnalysisResult with ProviderStatus.
    """

    def __init__(self, config: ChopchopConfig | None = None) -> None:
        self.config = config or ChopchopConfig()

    def validate_target(self, target: str) -> tuple[bool, str]:
        """Validate input gene symbol or genomic coordinate string."""
        cleaned = target.strip()
        if not cleaned:
            return False, "Target identifier/region cannot be empty."
        return True, ""

    async def analyze_target(
        self,
        target: str,
        species: str,
        genome: str,
        pam: str | None = None,
        guide_length: int | None = None,
        max_mismatches: int | None = None,
        scoring_method: str = "ALL",
    ) -> ChopchopAnalysisResult:
        """
        Execute CHOPCHOP guide & risk evaluation for a target gene or region.

        Parameters
        ----------
        target:
            Gene symbol (e.g. 'TYRP1') or genomic coordinate ('chr1:1000-2000').
        species:
            Authoritative species name from ProjectContext.
        genome:
            Explicitly resolved genome assembly identifier (e.g. 'hg38', 'mm10', 'sacCer3').
        pam:
            PAM motif (default 'NGG').
        guide_length:
            Length of the guide RNA (default 20).
        max_mismatches:
            Maximum off-target mismatches (default 3).
        scoring_method:
            Scoring mode (default 'ALL').
        """
        active_pam = pam or self.config.default_pam
        active_glen = guide_length or self.config.default_guide_length
        active_mm = max_mismatches or self.config.default_max_mismatches

        # 1. Validate target
        is_valid, validation_err = self.validate_target(target)
        if not is_valid:
            return ChopchopAnalysisResult(
                provider_status=ProviderStatus.FAILED,
                target=target,
                species=species,
                genome=genome,
                pam=active_pam,
                guide_candidates=[],
                warnings=[],
                errors=[f"Target validation failed: {validation_err}"],
                provenance={"adapter": "CHOPCHOPAdapter"},
            )

        # 2. Check genome assembly
        if not genome or genome.strip() == "":
            return ChopchopAnalysisResult(
                provider_status=ProviderStatus.UNAVAILABLE,
                target=target,
                species=species,
                genome=genome,
                pam=active_pam,
                guide_candidates=[],
                warnings=[],
                errors=["Genome assembly must be explicitly specified for CHOPCHOP."],
                provenance={"adapter": "CHOPCHOPAdapter"},
            )

        # 3. Build command
        if self.config.use_wsl and os.name == "nt":
            cmd = [
                "wsl",
                "--",
                self.config.python_executable,
                self.config.script_path,
                "-G",
                genome,
                "-M",
                active_pam,
                "-g",
                str(active_glen),
                "--maxMismatches",
                str(active_mm),
                "--scoringMethod",
                scoring_method,
                "-Target",
                target,
            ]
        else:
            cmd = [
                self.config.python_executable,
                self.config.script_path,
                "-G",
                genome,
                "-M",
                active_pam,
                "-g",
                str(active_glen),
                "--maxMismatches",
                str(active_mm),
                "--scoringMethod",
                scoring_method,
                "-Target",
                target,
            ]

        try:
            # Run subprocess asynchronously
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout_seconds,
            )
            stdout_str = stdout_b.decode("utf-8", errors="replace")
            stderr_str = stderr_b.decode("utf-8", errors="replace")

            if proc.returncode != 0:
                err_msg = stderr_str.strip() or stdout_str.strip() or f"Process exited with code {proc.returncode}"
                logger.warning("CHOPCHOP execution failed: %s", err_msg)
                return ChopchopAnalysisResult(
                    provider_status=ProviderStatus.FAILED,
                    target=target,
                    species=species,
                    genome=genome,
                    pam=active_pam,
                    guide_candidates=[],
                    warnings=[],
                    errors=[f"CHOPCHOP execution failed: {err_msg}"],
                    provenance={
                        "adapter": "CHOPCHOPAdapter",
                        "return_code": proc.returncode,
                        "command": " ".join(cmd),
                    },
                )

            # Parse outputs
            candidates = parse_chopchop_output(stdout_str)

            warnings: list[str] = []
            if not candidates:
                warnings.append(f"CHOPCHOP completed successfully but no guide candidates were found for target '{target}'.")

            return ChopchopAnalysisResult(
                provider_status=ProviderStatus.SUCCESS,
                target=target,
                species=species,
                genome=genome,
                pam=active_pam,
                guide_candidates=candidates,
                warnings=warnings,
                errors=[],
                provenance={
                    "adapter": "CHOPCHOPAdapter",
                    "species": species,
                    "genome": genome,
                    "pam": active_pam,
                    "guide_count": len(candidates),
                },
            )

        except asyncio.TimeoutError:
            logger.error("CHOPCHOP execution timed out after %s seconds", self.config.timeout_seconds)
            return ChopchopAnalysisResult(
                provider_status=ProviderStatus.FAILED,
                target=target,
                species=species,
                genome=genome,
                pam=active_pam,
                guide_candidates=[],
                warnings=[],
                errors=[f"CHOPCHOP execution timed out after {self.config.timeout_seconds}s."],
                provenance={"adapter": "CHOPCHOPAdapter", "timeout": True},
            )
        except FileNotFoundError as e:
            logger.error("CHOPCHOP binary or runtime not found: %s", e)
            return ChopchopAnalysisResult(
                provider_status=ProviderStatus.UNAVAILABLE,
                target=target,
                species=species,
                genome=genome,
                pam=active_pam,
                guide_candidates=[],
                warnings=[],
                errors=[f"CHOPCHOP executable or runtime not found: {e}"],
                provenance={"adapter": "CHOPCHOPAdapter"},
            )
        except Exception as e:
            logger.exception("Unexpected error executing CHOPCHOP: %s", e)
            return ChopchopAnalysisResult(
                provider_status=ProviderStatus.FAILED,
                target=target,
                species=species,
                genome=genome,
                pam=active_pam,
                guide_candidates=[],
                warnings=[],
                errors=[f"Unexpected error during CHOPCHOP execution: {e}"],
                provenance={"adapter": "CHOPCHOPAdapter"},
            )
