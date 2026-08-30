"""
Population Propagation Simulation Engine for Relict Core.

Implements deterministic mathematical population genetics simulations for evaluated alleles/edits
(architecture §2.5, §11, §12, §13, §14).

Supported Inheritance Models:
- Mendelian (Dominant, Recessive, Additive/Codominant)
- Gene Drive (Homing Endonuclease / CRISPR-Cas9 Cleavage and Homology-Directed Repair)

Explicit Boundary Constraints:
- Computational model only; exposes mathematical assumptions.
- Does NOT claim to be a comprehensive ecological forecast.
- Does NOT claim real-world biological certainty.
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class InheritanceModel(StrEnum):
    """Genetic inheritance model."""

    MENDELIAN_DOMINANT = "mendelian_dominant"
    MENDELIAN_RECESSIVE = "mendelian_recessive"
    MENDELIAN_ADDITIVE = "mendelian_additive"
    GENE_DRIVE_HOMING = "gene_drive_homing"


class PopulationParameters(BaseModel):
    """
    Input parameters for population genetics simulation.

    Validated strictly without silent clamping.
    """

    initial_frequency: float = Field(
        ge=0.0,
        le=1.0,
        description="Initial frequency of the engineered allele (0.0 to 1.0).",
    )
    population_size: int = Field(
        gt=0,
        description="Carrying capacity or population size (must be > 0).",
    )
    generations: int = Field(
        ge=0,
        default=50,
        description="Number of discrete generations to simulate.",
    )
    inheritance_model: InheritanceModel = Field(
        default=InheritanceModel.MENDELIAN_ADDITIVE,
        description="Mode of genetic inheritance.",
    )
    fitness_cost: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
        description="Fitness cost s in [0, 1] reducing homozygous/heterozygous viability.",
    )
    drive_efficiency: float = Field(
        ge=0.0,
        le=1.0,
        default=0.95,
        description="Homing/drive conversion efficiency c in [0, 1] for gene drive models.",
    )
    migration_rate: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
        description="Inward migration rate m of wild-type alleles per generation.",
    )
    target_threshold: float = Field(
        ge=0.0,
        le=1.0,
        default=0.80,
        description="Frequency threshold for calculating time_to_threshold.",
    )
    generation_time_years: float | None = Field(
        default=None,
        gt=0.0,
        description="Optional organism generation time in years.",
    )


class GenerationRecord(BaseModel):
    """Allele and genotype state at a specific generation."""

    generation: int
    allele_frequency: float
    genotype_frequencies: dict[str, float] = Field(default_factory=dict)


class DerivedMetrics(BaseModel):
    """Metrics derived from the frequency trajectory."""

    time_to_threshold: int | None = None
    final_frequency: float
    max_frequency: float
    persistence_generations: int
    population_penetration: float


class SimulationResult(BaseModel):
    """Complete structured output of population propagation simulation."""

    model: str
    parameters: PopulationParameters
    trajectory: list[GenerationRecord]
    derived_metrics: DerivedMetrics
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SensitivityAnalysisResult(BaseModel):
    """Comparative outcomes across varying parameter settings."""

    parameter_name: str
    tested_values: list[float]
    outcomes: list[dict[str, Any]]
    summary: str


class PopulationSimulator:
    """
    Deterministic population genetics simulation engine.
    """

    DEFAULT_ASSUMPTIONS: list[str] = [
        "Panmictic (random) mating within a single population structure unless migration is parameterized.",
        "Constant population carrying capacity across generations (deterministic recurrence).",
        "Discrete, non-overlapping generations.",
        "Selection acting at the diploid zygotic viability stage.",
    ]

    DEFAULT_LIMITATIONS: list[str] = [
        "Does not account for complex spatial ecology, microhabitats, or climate dynamics.",
        "Does not model emergence of drive-resistant target site mutations unless parameterized.",
        "Simulation outputs represent deterministic expectations under stated assumptions, not real-world guarantees.",
    ]

    def simulate(self, params: PopulationParameters) -> SimulationResult:
        """
        Run forward simulation over specified generations.
        """
        p = params.initial_frequency
        generations = params.generations
        s = params.fitness_cost
        c = params.drive_efficiency
        m = params.migration_rate
        threshold = params.target_threshold

        trajectory: list[GenerationRecord] = []
        time_to_thresh: int | None = None
        max_p = p
        persisting_gens = 0

        for gen in range(generations + 1):
            # Calculate genotype frequencies for the current allele frequency p
            # Let engineered allele be 'E', wild-type be 'W'
            q = 1.0 - p

            if params.inheritance_model == InheritanceModel.MENDELIAN_DOMINANT:
                # Fitness: EE: 1-s, EW: 1-s, WW: 1
                w_EE = 1.0 - s
                w_EW = 1.0 - s
                w_WW = 1.0
                mean_w = (p**2) * w_EE + 2 * p * q * w_EW + (q**2) * w_WW
                p_next = ((p**2) * w_EE + p * q * w_EW) / max(1e-12, mean_w) if mean_w > 0 else 0.0

            elif params.inheritance_model == InheritanceModel.MENDELIAN_RECESSIVE:
                # Fitness: EE: 1-s, EW: 1, WW: 1
                w_EE = 1.0 - s
                w_EW = 1.0
                w_WW = 1.0
                mean_w = (p**2) * w_EE + 2 * p * q * w_EW + (q**2) * w_WW
                p_next = ((p**2) * w_EE + p * q * w_EW) / max(1e-12, mean_w) if mean_w > 0 else 0.0

            elif params.inheritance_model == InheritanceModel.MENDELIAN_ADDITIVE:
                # Fitness: EE: 1-s, EW: 1 - s/2, WW: 1
                w_EE = 1.0 - s
                w_EW = 1.0 - (s / 2.0)
                w_WW = 1.0
                mean_w = (p**2) * w_EE + 2 * p * q * w_EW + (q**2) * w_WW
                p_next = ((p**2) * w_EE + p * q * w_EW) / max(1e-12, mean_w) if mean_w > 0 else 0.0

            elif params.inheritance_model == InheritanceModel.GENE_DRIVE_HOMING:
                # In homing gene drive, heterozygotes EW convert to EE with efficiency c
                # Before selection: EE: p^2 + 2*c*p*q, EW: 2*(1-c)*p*q, WW: q^2
                f_EE = p**2 + 2.0 * c * p * q
                f_EW = 2.0 * (1.0 - c) * p * q
                f_WW = q**2

                # Selection on genotypes (EE: 1-s, EW: 1-s/2, WW: 1)
                w_EE = 1.0 - s
                w_EW = 1.0 - (s / 2.0)
                w_WW = 1.0

                mean_w = f_EE * w_EE + f_EW * w_EW + f_WW * w_WW
                if mean_w > 0:
                    p_next = (f_EE * w_EE + 0.5 * f_EW * w_EW) / mean_w
                else:
                    p_next = 0.0

            else:
                p_next = p

            # Apply migration (influx of wild-type alleles at rate m)
            if m > 0.0:
                p_next = p_next * (1.0 - m)

            # Bound p_next
            p_next = max(0.0, min(1.0, p_next))

            # Record current generation
            genotype_dict = {
                "EE": round(p**2, 4),
                "EW": round(2 * p * q, 4),
                "WW": round(q**2, 4),
            }

            trajectory.append(
                GenerationRecord(
                    generation=gen,
                    allele_frequency=round(p, 6),
                    genotype_frequencies=genotype_dict,
                )
            )

            if p >= threshold and time_to_thresh is None:
                time_to_thresh = gen

            if p > max_p:
                max_p = p

            if p > 0.001:
                persisting_gens = gen

            # Advance to next generation
            p = p_next

        final_p = trajectory[-1].allele_frequency
        penetration = round(final_p, 4)

        metrics = DerivedMetrics(
            time_to_threshold=time_to_thresh,
            final_frequency=final_p,
            max_frequency=round(max_p, 6),
            persistence_generations=persisting_gens,
            population_penetration=penetration,
        )

        warnings: list[str] = []
        if final_p < 0.01 and params.initial_frequency > 0.0:
            warnings.append(
                "Allele declined to near zero; fitness costs or migration prevented establishment."
            )
        if params.fitness_cost > 0.5:
            warnings.append("High fitness cost (>0.5) strongly suppresses allele spread.")

        return SimulationResult(
            model=params.inheritance_model.value,
            parameters=params,
            trajectory=trajectory,
            derived_metrics=metrics,
            assumptions=list(self.DEFAULT_ASSUMPTIONS),
            limitations=list(self.DEFAULT_LIMITATIONS),
            warnings=warnings,
        )

    def analyze_sensitivity(
        self,
        base_params: PopulationParameters,
        parameter_name: str,
        tested_values: list[float],
    ) -> SensitivityAnalysisResult:
        """
        Evaluate sensitivity of population penetration across a list of parameter values.
        """
        valid_params = {"fitness_cost", "initial_frequency", "migration_rate", "drive_efficiency"}
        if parameter_name not in valid_params:
            raise ValueError(
                f"Sensitivity parameter '{parameter_name}' must be one of {valid_params}."
            )

        outcomes: list[dict[str, Any]] = []

        for val in tested_values:
            mod_params = base_params.model_copy(update={parameter_name: val})
            sim_res = self.simulate(mod_params)
            outcomes.append(
                {
                    parameter_name: val,
                    "final_frequency": sim_res.derived_metrics.final_frequency,
                    "time_to_threshold": sim_res.derived_metrics.time_to_threshold,
                    "max_frequency": sim_res.derived_metrics.max_frequency,
                }
            )

        summary = (
            f"Sensitivity analysis over {len(tested_values)} settings of '{parameter_name}'. "
            f"Final allele frequencies ranged from {min(o['final_frequency'] for o in outcomes)} "
            f"to {max(o['final_frequency'] for o in outcomes)}."
        )

        return SensitivityAnalysisResult(
            parameter_name=parameter_name,
            tested_values=tested_values,
            outcomes=outcomes,
            summary=summary,
        )
