"""Comprehensive tests for SpeciesResolver and CanonicalSpecies models on canonical database."""

from __future__ import annotations

import pytest

from app.knowledge_retrieval.species import (
    SpeciesResolver,
    get_species_resolver,
)


class TestSpeciesResolver:
    @pytest.fixture
    def resolver(self) -> SpeciesResolver:
        return get_species_resolver()

    def test_loaded_species_count(self, resolver: SpeciesResolver) -> None:
        assert resolver.count() == 1_400_000

    def test_resolve_by_scientific_name(self, resolver: SpeciesResolver) -> None:
        human = resolver.resolve("Homo sapiens")
        assert human is not None
        assert human.scientific_name == "Homo sapiens"
        assert human.common_name == "Human"
        assert human.taxonomy_id == "2883641"
        assert human.ensembl_name == "homo_sapiens"

        mouse = resolver.resolve("Mus musculus")
        assert mouse is not None
        assert mouse.scientific_name == "Mus musculus"
        assert mouse.taxonomy_id == "3049974"
        assert mouse.ensembl_name == "mus_musculus"

    def test_resolve_by_common_name(self, resolver: SpeciesResolver) -> None:
        wolf = resolver.resolve("Wolf")
        assert wolf is not None
        assert "Canis lupus" in wolf.scientific_name or wolf.scientific_name == "Wolf"

        panda = resolver.resolve("Giant panda")
        assert panda is not None
        assert (
            panda.scientific_name == "Ailuropoda melanoleuca"
            or panda.scientific_name == "Giant panda"
        )

    def test_resolve_by_alias_and_tags(self, resolver: SpeciesResolver) -> None:
        pig = resolver.resolve("pig")
        assert pig is not None
        assert (
            "Sus scrofa" in pig.scientific_name
            or "pig" in pig.common_name.lower()
            or "pig" in pig.tags
        )

        boar = resolver.resolve("Wild boar")
        assert boar is not None
        assert "Sus scrofa" in boar.scientific_name or boar.scientific_name == "Wild boar"

        mammoth = resolver.resolve("Woolly mammoth")
        assert mammoth is not None
        assert mammoth.scientific_name == "Mammuthus primigenius"
        assert mammoth.is_extinct is True

    def test_resolve_by_taxonomy_id(self, resolver: SpeciesResolver) -> None:
        human = resolver.get_by_taxonomy_id(2883641)
        assert human is not None
        assert human.scientific_name == "Homo sapiens"

        mammoth = resolver.get_by_taxonomy_id("37349")
        assert mammoth is not None
        assert mammoth.scientific_name == "Mammuthus primigenius"

    def test_resolve_by_ensembl_name(self, resolver: SpeciesResolver) -> None:
        res = resolver.get_by_ensembl_name("danio_rerio")
        assert res is not None
        assert res.scientific_name == "Danio rerio"

    def test_case_and_whitespace_insensitivity(self, resolver: SpeciesResolver) -> None:
        assert resolver.resolve("  hOmO  SAPIENS  ") is not None
        assert resolver.resolve("mus_musculus") is not None
        assert resolver.resolve("Danio Rerio") is not None

    def test_resolve_unknown_species_returns_none(self, resolver: SpeciesResolver) -> None:
        assert resolver.resolve("Unknown alien species 123XYZ") is None
        assert resolver.resolve("9999999999999") is None
        assert resolver.resolve("") is None
        assert resolver.resolve(None) is None
