from __future__ import annotations

from app.models.requests import Scope

# ---------------------------------------------------------------------------
# Source registry — data-driven scope → source mapping
# ---------------------------------------------------------------------------

# Common sources are always included regardless of the selected scope.
_COMMON_SOURCES: list[str] = [
    "ensembl",
    "ncbi_eutils",
    "ncbi_datasets",
    "ncbi_blast",
    "ncbi_pmc",
    "string",
    "kegg",
    "uniprot",
    "reactome",
    "wikipathways",
    "rcsb_pdb",
    "gbif",
    "timetree",
]

_SCOPE_SOURCES: dict[Scope, list[str]] = {
    Scope.CONSERVATION: [
        "conservation_dna_zoo",
        "conservation_vgp",
        "conservation_genome10k",
    ],
    Scope.DE_EXTINCTION: [
        "de_extinction_dna_zoo",
        "de_extinction_vgp",
        "de_extinction_genome10k",
    ],
    Scope.AGRICULTURE: [
        "gramene",
        "plant_reactome",
        "animal_qtldb",
        "faang",
        "farmgtex",
        "epidb",
    ],
    Scope.SYNTHETIC_BIOLOGY: [
        "brenda",
        "sabio_rk",
        "synbiohub",
    ],
    Scope.POPULATION_CONTROL: [
        "vectorbase",
    ],
    Scope.PRECISION_MEDICINE: [
        "alphamissense",
        "opentargets",
        "chembl",
        "hpa",
        "gtex",
        "gnomad",
    ],
}


def get_sources_for_scope(scope: Scope) -> list[str]:
    """Return the list of permitted source names for a given scope.

    COMMON sources are always included. The scope-specific sources
    are appended after.
    """
    scope_specific = _SCOPE_SOURCES.get(scope, [])
    return list(_COMMON_SOURCES) + list(scope_specific)


def all_scopes() -> list[Scope]:
    """Return all available scopes."""
    return list(Scope)


def all_sources() -> list[str]:
    """Return all registered source names (deduplicated)."""
    seen: set[str] = set()
    result: list[str] = []
    for s in _COMMON_SOURCES:
        if s not in seen:
            seen.add(s)
            result.append(s)
    for sources in _SCOPE_SOURCES.values():
        for s in sources:
            if s not in seen:
                seen.add(s)
                result.append(s)
    return result
