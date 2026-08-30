"""
Unit tests for Population Propagation simulation and sensitivity analysis.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.post_plan.population import (
    InheritanceModel,
    PopulationParameters,
    PopulationSimulator,
)


@pytest.fixture
def simulator() -> PopulationSimulator:
    return PopulationSimulator()


def test_mendelian_additive_simulation(simulator: PopulationSimulator):
    """Test standard Mendelian additive forward simulation."""
    params = PopulationParameters(
        initial_frequency=0.10,
        population_size=1000,
        generations=20,
        inheritance_model=InheritanceModel.MENDELIAN_ADDITIVE,
        fitness_cost=0.0,
    )

    res = simulator.simulate(params)

    assert res.model == "mendelian_additive"
    assert len(res.trajectory) == 21
    assert res.trajectory[0].generation == 0
    assert res.trajectory[0].allele_frequency == 0.10
    # With neutral selection, allele frequency remains constant (Hardy-Weinberg)
    assert pytest.approx(res.trajectory[-1].allele_frequency, abs=1e-4) == 0.10
    assert len(res.assumptions) > 0
    assert len(res.limitations) > 0


def test_gene_drive_simulation_threshold_reached(simulator: PopulationSimulator):
    """Test gene drive homing simulation reaching target threshold."""
    params = PopulationParameters(
        initial_frequency=0.05,
        population_size=5000,
        generations=20,
        inheritance_model=InheritanceModel.GENE_DRIVE_HOMING,
        fitness_cost=0.05,
        drive_efficiency=0.95,
        target_threshold=0.80,
    )

    res = simulator.simulate(params)

    assert res.derived_metrics.time_to_threshold is not None
    assert res.derived_metrics.time_to_threshold > 0
    assert res.derived_metrics.final_frequency >= 0.80


def test_threshold_never_reached(simulator: PopulationSimulator):
    """Test threshold not reached returns None for time_to_threshold."""
    params = PopulationParameters(
        initial_frequency=0.01,
        population_size=1000,
        generations=10,
        inheritance_model=InheritanceModel.MENDELIAN_DOMINANT,
        fitness_cost=0.30,  # Negative selection
        target_threshold=0.90,
    )

    res = simulator.simulate(params)

    assert res.derived_metrics.time_to_threshold is None
    assert res.derived_metrics.final_frequency < 0.01


def test_population_parameters_validation():
    """Test strict validation of population parameters."""
    # Invalid negative frequency
    with pytest.raises(ValidationError):
        PopulationParameters(initial_frequency=-0.1, population_size=100)

    # Invalid frequency > 1
    with pytest.raises(ValidationError):
        PopulationParameters(initial_frequency=1.5, population_size=100)

    # Invalid zero population size
    with pytest.raises(ValidationError):
        PopulationParameters(initial_frequency=0.1, population_size=0)

    # Invalid negative generations
    with pytest.raises(ValidationError):
        PopulationParameters(initial_frequency=0.1, population_size=100, generations=-5)


def test_sensitivity_analysis(simulator: PopulationSimulator):
    """Test sensitivity analysis across varying fitness costs."""
    base_params = PopulationParameters(
        initial_frequency=0.10,
        population_size=1000,
        generations=15,
        inheritance_model=InheritanceModel.GENE_DRIVE_HOMING,
        drive_efficiency=0.90,
    )

    sens_res = simulator.analyze_sensitivity(
        base_params=base_params,
        parameter_name="fitness_cost",
        tested_values=[0.0, 0.1, 0.3, 0.6],
    )

    assert sens_res.parameter_name == "fitness_cost"
    assert len(sens_res.outcomes) == 4
    # Final frequency should decrease as fitness cost increases
    final_freqs = [o["final_frequency"] for o in sens_res.outcomes]
    assert final_freqs[0] >= final_freqs[-1]
    assert "Sensitivity analysis" in sens_res.summary


def test_deterministic_repeatability(simulator: PopulationSimulator):
    """Test that simulation is strictly deterministic given identical parameters."""
    params = PopulationParameters(
        initial_frequency=0.08,
        population_size=2000,
        generations=25,
        inheritance_model=InheritanceModel.GENE_DRIVE_HOMING,
    )

    res1 = simulator.simulate(params)
    res2 = simulator.simulate(params)

    assert res1.derived_metrics.final_frequency == res2.derived_metrics.final_frequency
    assert res1.derived_metrics.time_to_threshold == res2.derived_metrics.time_to_threshold
    assert [g.allele_frequency for g in res1.trajectory] == [g.allele_frequency for g in res2.trajectory]
