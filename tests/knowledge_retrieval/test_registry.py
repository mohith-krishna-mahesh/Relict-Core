"""Tests for scope-to-source mapping and source registry."""

from __future__ import annotations

from app.knowledge_retrieval.registry import (
    all_scopes,
    all_sources,
    get_sources_for_scope,
)
from app.models.requests import Scope


def test_all_scopes_covers_all_enum_values() -> None:
    scopes = all_scopes()
    assert set(scopes) == set(Scope)


def test_common_sources_included_in_all_scopes() -> None:
    for scope in Scope:
        sources = get_sources_for_scope(scope)
        assert "ensembl" in sources
        assert "string" in sources
        assert "kegg" in sources
        assert "uniprot" in sources
        assert "ncbi_eutils" in sources
        assert "ncbi_datasets" in sources
        assert "ncbi_blast" in sources
        assert "ncbi_pmc" in sources
        assert "reactome" in sources
        assert "wikipathways" in sources
        assert "rcsb_pdb" in sources
        assert "gbif" in sources
        assert "timetree" in sources


def test_agriculture_scope_includes_agriculture_sources() -> None:
    sources = get_sources_for_scope(Scope.AGRICULTURE)
    assert "gramene" in sources
    assert "plant_reactome" in sources
    assert "animal_qtldb" in sources
    assert "faang" in sources
    assert "farmgtex" in sources
    assert "epidb" in sources


def test_synthetic_biology_scope_includes_synbio_sources() -> None:
    sources = get_sources_for_scope(Scope.SYNTHETIC_BIOLOGY)
    assert "brenda" in sources
    assert "sabio_rk" in sources
    assert "synbiohub" in sources


def test_precision_medicine_scope_includes_medicine_sources() -> None:
    sources = get_sources_for_scope(Scope.PRECISION_MEDICINE)
    assert "alphamissense" in sources
    assert "opentargets" in sources
    assert "chembl" in sources
    assert "hpa" in sources
    assert "gtex" in sources
    assert "gnomad" in sources


def test_all_sources_non_empty_and_unique() -> None:
    sources = all_sources()
    assert len(sources) > 20
    assert len(sources) == len(set(sources))
