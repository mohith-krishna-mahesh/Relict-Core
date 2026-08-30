"""
CRISPOR Adapter for Relict Core Post-Plan Guide & Risk Analysis.

This module provides the Relict-side adapter for CRISPOR (http://crispor.org).
It isolates all CRISPOR-specific invocation, file parsing, score normalization,
and failure handling.

Architecture constraints (Relict Core architecture §2.5, §8):
- Model outputs are NOT biological evidence.
- The Planner remains responsible for candidate target loci; CRISPOR only evaluates
  downstream guide efficiency, specificity, and off-target risks for chosen loci.
- CRISPOR must NOT modify Planner strategy, override constraints, or insert edges.
- Failures (missing genome, execution failure, timeout, etc.) are captured as structured
  errors and must never fabricate guide sequences or scores.
"""

from __future__ import annotations

import asyncio
import csv
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ProviderStatus(StrEnum):
    """Execution status of the CRISPOR provider."""

    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class CrisporOfftarget(BaseModel):
    """
    Individual off-target locus identified by CRISPOR.

    Preserves source-native scores (MIT offtarget score, CFD offtarget score)
    without fabricating or reinterpreting them as calibrated probabilities.
    """

    offtarget_seq: str
    mismatch_pos: str = ""
    mismatch_count: int = 0
    mit_offtarget_score: float | None = None
    cfd_offtarget_score: float | None = None
    chrom: str
    start: int
    end: int
    strand: str
    locus_desc: str | None = None


class CrisporGuideCandidate(BaseModel):
    """
    Candidate guide RNA produced and scored by CRISPOR.

    Preserves all native specificity and efficiency scores:
    - mit_spec_score: MIT Specificity score (0-100)
    - cfd_spec_score: CFD Specificity score (0-100)
    - doench_16_score: Doench 2016 / Azimuth efficiency score
    - moreno_mateos_score: Moreno-Mateos / CRISPRscan efficiency score
    - ruleset3_score: Doench Rule Set 3 score
    - out_of_frame_score: Microhomology out-of-frame score
    - lindel_score: Lindel indel prediction score
    - graf_status: Graf et al. poly-T / self-cleavage flag
    """

    guide_id: str
    target_seq: str
    pam: str
    strand: str
    start_pos: int | None = None
    mit_spec_score: float | None = None
    cfd_spec_score: float | None = None
    offtarget_count: int = 0
    target_locus: str | None = None
    doench_16_score: float | None = None
    moreno_mateos_score: float | None = None
    ruleset3_score: float | None = None
    out_of_frame_score: float | None = None
    lindel_score: float | None = None
    graf_status: str | None = None
    offtargets: list[CrisporOfftarget] = Field(default_factory=list)


class CrisporAnalysisResult(BaseModel):
    """
    Normalized result of CRISPOR guide & risk analysis for a target locus.

    Attached to PostPlanResult.guide_risk under the 'crispor' key.
    """

    provider: str = "CRISPOR"
    provider_status: ProviderStatus
    target_identifier: str
    genome: str
    pam: str
    guide_candidates: list[CrisporGuideCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


@dataclass
class CrisporConfig:
    """Configuration settings for the CRISPOR adapter."""

    crispor_script_path: str = "/mnt/c/Users/walki/crisporWebsite/crispor.py"
    python_executable: str = "/mnt/c/Users/walki/crisporWebsite/venv/bin/python"
    genome_dir: str = "/mnt/c/Users/walki/crisporWebsite/genomes"
    default_pam: str = "NGG"
    max_mismatches: int = 4
    timeout_seconds: float = 120.0
    use_wsl: bool = True


def _parse_float(val: str | None) -> float | None:
    """Safely parse float values, returning None on invalid/missing strings."""
    if not val:
        return None
    val = val.strip()
    if val in ("", "None", "NA", "na", "-", "NotEnoughFlankSeq"):
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


def parse_crispor_tsv_outputs(
    guides_tsv_path: Path | str,
    offs_tsv_path: Path | str | None = None,
    default_pam: str = "NGG",
) -> list[CrisporGuideCandidate]:
    """
    Parse CRISPOR TSV output files into normalized CrisporGuideCandidate objects.

    Parameters
    ----------
    guides_tsv_path:
        Path to the primary guides TSV file produced by crispor.py.
    offs_tsv_path:
        Optional path to the off-targets TSV file produced by crispor.py (-o).
    default_pam:
        Fallback PAM string.
    """
    guides_path = Path(guides_tsv_path)
    if not guides_path.exists() or guides_path.stat().st_size == 0:
        return []

    # Map guideId -> list of offtargets
    offtargets_by_guide: dict[str, list[CrisporOfftarget]] = {}
    if offs_tsv_path:
        offs_path = Path(offs_tsv_path)
        if offs_path.exists() and offs_path.stat().st_size > 0:
            with open(offs_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f, delimiter="\t")
                header = next(reader, None)
                if header:
                    for row in reader:
                        if not row or len(row) < 12:
                            continue
                        # Standard CRISPOR offtarget columns:
                        # 0: seqId, 1: guideId, 2: guideSeq, 3: offtargetSeq,
                        # 4: mismatchPos, 5: mismatchCount, 6: mitOfftargetScore,
                        # 7: cfdOfftargetScore, 8: chrom, 9: start, 10: end,
                        # 11: strand, 12: locusDesc (optional)
                        gid = row[1].strip()
                        ot = CrisporOfftarget(
                            offtarget_seq=row[3].strip(),
                            mismatch_pos=row[4].strip() if len(row) > 4 else "",
                            mismatch_count=_parse_int(row[5]) if len(row) > 5 else 0,
                            mit_offtarget_score=_parse_float(row[6]) if len(row) > 6 else None,
                            cfd_offtarget_score=_parse_float(row[7]) if len(row) > 7 else None,
                            chrom=row[8].strip() if len(row) > 8 else "",
                            start=_parse_int(row[9]) if len(row) > 9 else 0,
                            end=_parse_int(row[10]) if len(row) > 10 else 0,
                            strand=row[11].strip() if len(row) > 11 else "+",
                            locus_desc=row[12].strip() if len(row) > 12 else None,
                        )
                        offtargets_by_guide.setdefault(gid, []).append(ot)

    candidates: list[CrisporGuideCandidate] = []
    with open(guides_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter="\t")
        header = None
        for row in reader:
            if not row:
                continue
            if row[0].startswith("#"):
                header = [h.strip().lstrip("#") for h in row]
                continue
            if header is None:
                # No comment header found; assume standard columns
                header = [
                    "seqId",
                    "guideId",
                    "targetSeq",
                    "mitSpecScore",
                    "cfdSpecScore",
                    "offtargetCount",
                    "targetGenomeGeneLocus",
                    "Doench '16-Score",
                    "Moreno-Mateos-Score",
                    "Doench-RuleSet3-Score",
                    "Out-of-Frame-Score",
                    "Lindel-Score",
                    "GrafEtAlStatus",
                ]

            row_dict = dict(zip(header, row))
            gid = row_dict.get("guideId", "").strip()
            if not gid:
                continue

            # Determine strand and pos from guideId (e.g. '41forw', '80rev')
            strand = "+"
            start_pos = None
            if "forw" in gid:
                strand = "+"
                try:
                    start_pos = int(gid.replace("forw", ""))
                except ValueError:
                    pass
            elif "rev" in gid:
                strand = "-"
                try:
                    start_pos = int(gid.replace("rev", ""))
                except ValueError:
                    pass

            target_seq = row_dict.get("targetSeq", "").strip()
            pam = default_pam
            if len(target_seq) >= 23:
                # If 23bp with NGG at 3' end
                pam = target_seq[-3:]

            candidate = CrisporGuideCandidate(
                guide_id=gid,
                target_seq=target_seq,
                pam=pam,
                strand=strand,
                start_pos=start_pos,
                mit_spec_score=_parse_float(row_dict.get("mitSpecScore")),
                cfd_spec_score=_parse_float(row_dict.get("cfdSpecScore")),
                offtarget_count=_parse_int(row_dict.get("offtargetCount"), 0),
                target_locus=row_dict.get("targetGenomeGeneLocus"),
                doench_16_score=_parse_float(row_dict.get("Doench '16-Score")),
                moreno_mateos_score=_parse_float(row_dict.get("Moreno-Mateos-Score")),
                ruleset3_score=_parse_float(row_dict.get("Doench-RuleSet3-Score")),
                out_of_frame_score=_parse_float(row_dict.get("Out-of-Frame-Score")),
                lindel_score=_parse_float(row_dict.get("Lindel-Score")),
                graf_status=row_dict.get("GrafEtAlStatus"),
                offtargets=offtargets_by_guide.get(gid, []),
            )
            candidates.append(candidate)

    return candidates


class CRISPORAdapter:
    """
    Adapter for invoking CRISPOR and producing normalized guide & risk analysis.

    Isolation:
    - Never modifies input project or strategy models.
    - Captures all subprocess exceptions, timeouts, missing genomes, and parsing errors.
    - Returns structured CrisporAnalysisResult with ProviderStatus.
    """

    def __init__(self, config: CrisporConfig | None = None) -> None:
        self.config = config or CrisporConfig()

    def validate_sequence(self, sequence: str) -> tuple[bool, str]:
        """Validate input DNA sequence before passing to CRISPOR."""
        cleaned = sequence.strip().upper()
        if not cleaned:
            return False, "Target sequence cannot be empty."
        if len(cleaned) < 23:
            return False, f"Target sequence length ({len(cleaned)}bp) is too short for CRISPOR (min 23bp)."
        valid_bases = set("ACGTUNRYKMSWBDHV")
        invalid = set(cleaned) - valid_bases
        if invalid:
            return False, f"Target sequence contains invalid nucleotide characters: {', '.join(sorted(invalid))}"
        return True, ""

    async def analyze_target(
        self,
        target_identifier: str,
        sequence: str,
        genome: str,
        pam: str | None = None,
        max_mismatches: int | None = None,
    ) -> CrisporAnalysisResult:
        """
        Execute CRISPOR guide & risk evaluation for a target sequence.

        Parameters
        ----------
        target_identifier:
            Locus or gene identifier from Planner / ProjectContext.
        sequence:
            Genomic DNA sequence string for the target region.
        genome:
            Explicitly resolved genome assembly identifier (e.g. 'sacCer3', 'hg38', 'mm10').
        pam:
            PAM motif (default configured or 'NGG').
        max_mismatches:
            Maximum off-target mismatches to evaluate (default 4).
        """
        active_pam = pam or self.config.default_pam
        active_mm = max_mismatches or self.config.max_mismatches

        # 1. Validate sequence input
        is_valid, validation_err = self.validate_sequence(sequence)
        if not is_valid:
            return CrisporAnalysisResult(
                provider_status=ProviderStatus.FAILED,
                target_identifier=target_identifier,
                genome=genome,
                pam=active_pam,
                guide_candidates=[],
                warnings=[],
                errors=[f"Input sequence validation failed: {validation_err}"],
                provenance={"adapter": "CRISPORAdapter"},
            )

        # 2. Check genome assembly presence
        if not genome or genome.strip() == "":
            return CrisporAnalysisResult(
                provider_status=ProviderStatus.UNAVAILABLE,
                target_identifier=target_identifier,
                genome=genome,
                pam=active_pam,
                guide_candidates=[],
                warnings=[],
                errors=["Genome assembly must be explicitly specified."],
                provenance={"adapter": "CRISPORAdapter"},
            )

        # 3. Create temporary files for execution
        with tempfile.TemporaryDirectory(prefix="relict_crispor_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            fa_path = tmp_path / "input.fa"
            guides_out = tmp_path / "guides.tsv"
            offs_out = tmp_path / "offtargets.tsv"

            # Write FASTA input
            with open(fa_path, "w", encoding="utf-8") as f:
                f.write(f">{target_identifier}\n{sequence.strip().upper()}\n")

            # Build command
            # Convert paths to WSL if on Windows and use_wsl is True
            if self.config.use_wsl and os.name == "nt":
                # Convert Windows paths to WSL paths
                def to_wsl_path(p: Path) -> str:
                    s = str(p.resolve()).replace("\\", "/")
                    if len(s) >= 2 and s[1] == ":":
                        drive = s[0].lower()
                        return f"/mnt/{drive}{s[2:]}"
                    return s

                wsl_fa = to_wsl_path(fa_path)
                wsl_guides = to_wsl_path(guides_out)
                wsl_offs = to_wsl_path(offs_out)

                cmd = [
                    "wsl",
                    "--",
                    self.config.python_executable,
                    self.config.crispor_script_path,
                    "-g",
                    self.config.genome_dir,
                    "-p",
                    active_pam,
                    "--mm",
                    str(active_mm),
                    genome,
                    wsl_fa,
                    wsl_guides,
                    "-o",
                    wsl_offs,
                ]
            else:
                cmd = [
                    self.config.python_executable,
                    self.config.crispor_script_path,
                    "-g",
                    self.config.genome_dir,
                    "-p",
                    active_pam,
                    "--mm",
                    str(active_mm),
                    genome,
                    str(fa_path),
                    str(guides_out),
                    "-o",
                    str(offs_out),
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
                    logger.warning("CRISPOR execution failed: %s", err_msg)
                    return CrisporAnalysisResult(
                        provider_status=ProviderStatus.FAILED,
                        target_identifier=target_identifier,
                        genome=genome,
                        pam=active_pam,
                        guide_candidates=[],
                        warnings=[],
                        errors=[f"CRISPOR process execution failed: {err_msg}"],
                        provenance={
                            "adapter": "CRISPORAdapter",
                            "return_code": proc.returncode,
                            "command": " ".join(cmd),
                        },
                    )

                # Parse outputs
                candidates = parse_crispor_tsv_outputs(
                    guides_tsv_path=guides_out,
                    offs_tsv_path=offs_out,
                    default_pam=active_pam,
                )

                warnings: list[str] = []
                if not candidates:
                    warnings.append(f"CRISPOR completed successfully but no guide candidates with PAM '{active_pam}' were found in target sequence.")

                return CrisporAnalysisResult(
                    provider_status=ProviderStatus.SUCCESS,
                    target_identifier=target_identifier,
                    genome=genome,
                    pam=active_pam,
                    guide_candidates=candidates,
                    warnings=warnings,
                    errors=[],
                    provenance={
                        "adapter": "CRISPORAdapter",
                        "genome": genome,
                        "pam": active_pam,
                        "guide_count": len(candidates),
                    },
                )

            except asyncio.TimeoutError:
                logger.error("CRISPOR execution timed out after %s seconds", self.config.timeout_seconds)
                return CrisporAnalysisResult(
                    provider_status=ProviderStatus.FAILED,
                    target_identifier=target_identifier,
                    genome=genome,
                    pam=active_pam,
                    guide_candidates=[],
                    warnings=[],
                    errors=[f"CRISPOR execution timed out after {self.config.timeout_seconds}s."],
                    provenance={"adapter": "CRISPORAdapter", "timeout": True},
                )
            except FileNotFoundError as e:
                logger.error("CRISPOR binary/executable not found: %s", e)
                return CrisporAnalysisResult(
                    provider_status=ProviderStatus.UNAVAILABLE,
                    target_identifier=target_identifier,
                    genome=genome,
                    pam=active_pam,
                    guide_candidates=[],
                    warnings=[],
                    errors=[f"CRISPOR executable or runtime not found: {e}"],
                    provenance={"adapter": "CRISPORAdapter"},
                )
            except Exception as e:
                logger.exception("Unexpected error during CRISPOR execution: %s", e)
                return CrisporAnalysisResult(
                    provider_status=ProviderStatus.FAILED,
                    target_identifier=target_identifier,
                    genome=genome,
                    pam=active_pam,
                    guide_candidates=[],
                    warnings=[],
                    errors=[f"Unexpected error executing CRISPOR: {e}"],
                    provenance={"adapter": "CRISPORAdapter"},
                )
