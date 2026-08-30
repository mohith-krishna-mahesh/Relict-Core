"""
Search endpoints.

GET /v1/search/species?q=<query>
    Prefix/substring species search backed by the SQLite-indexed
    ``SpeciesResolver``.  Returns ``list[Species]`` from the canonical
    knowledge base.  An unknown query returns an empty list, not an error.

GET /v1/search/genes?q=<query>&species=<species>
    Gene-symbol lookup backed by a live Ensembl REST API call.

    Known limitation (exact-match only)
    ------------------------------------
    The Ensembl REST API (v15+) does NOT provide a fuzzy or prefix gene-symbol
    search endpoint.  Both ``/lookup/symbol/{species}/{symbol}`` and
    ``/xrefs/symbol/{species}/{symbol}`` require an exact gene symbol.  This
    endpoint therefore performs exact-match lookup and returns either a single
    ``Gene`` or an empty list.  Callers should not expect autocomplete-style
    partial matching.

    This limitation is documented here and in the corresponding test to avoid
    silently mis-communicating the capability to Shell.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_bearer_token
from app.knowledge_retrieval.common.ensembl import EnsemblClient
from app.knowledge_retrieval.species import get_species_resolver
from app.models.data import Gene, Species

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Species search
# ---------------------------------------------------------------------------

_SPECIES_LIMIT = 20  # max results per query


@router.get(
    "/search/species",
    response_model=list[Species],
    summary="Search species",
    description=(
        "Prefix/substring search over the canonical species knowledge base. "
        "Matches against scientific name and common name (case-insensitive). "
        "Returns an empty list for unknown queries -- never an error response."
    ),
    tags=["search"],
)
async def search_species(
    q: str = Query(..., min_length=1, description="Species name prefix or substring."),
    _token: str = Depends(get_bearer_token),  # noqa: B008
) -> list[Species]:
    """Search the species knowledge base and return matching ``Species`` records."""
    resolver = get_species_resolver()
    try:
        results = resolver.search(q, limit=_SPECIES_LIMIT)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SpeciesResolver.search(%r) raised: %s", q, exc)
        results = []

    return [
        Species(name=cs.scientific_name, taxonomy_id=cs.taxonomy_id)
        for cs in results
    ]


# ---------------------------------------------------------------------------
# Gene search
# ---------------------------------------------------------------------------

_ENSEMBL_BASE = "https://rest.ensembl.org"
_ENSEMBL_TIMEOUT = 15.0


@router.get(
    "/search/genes",
    response_model=list[Gene],
    summary="Search genes",
    description=(
        "Exact-match gene symbol lookup via the Ensembl REST API. "
        "Returns a single Gene when the symbol is found, or an empty list. "
        "**Known limitation**: Ensembl REST does not expose a fuzzy/prefix gene-symbol "
        "search endpoint; only exact symbol matches are supported."
    ),
    tags=["search"],
)
async def search_genes(
    q: str = Query(..., min_length=1, description="Gene symbol (exact match)."),
    species: str = Query(..., min_length=1, description="Species name or taxonomy ID."),
    _token: str = Depends(get_bearer_token),  # noqa: B008
) -> list[Gene]:
    """
    Look up a gene symbol via Ensembl REST.

    KNOWN LIMITATION: exact-match only.  Ensembl REST /lookup/symbol and
    /xrefs/symbol both require the full, exact gene symbol.  There is no
    fuzzy or prefix search endpoint in the Ensembl REST API.
    """
    # Resolve species to Ensembl name
    resolver = get_species_resolver()
    canonical = resolver.resolve(species)
    if canonical is not None:
        ensembl_name = canonical.ensembl_name
    else:
        # Fall back to normalised name if species is unknown to our KB
        ensembl_name = species.strip().lower().replace(" ", "_")

    client = EnsemblClient()
    try:
        data = await client.lookup_symbol(ensembl_name, q)
        if not data:
            return []
            
        symbol = data.get("display_name") or data.get("id") or q
        description = data.get("description") or symbol
        return [Gene(symbol=symbol, name=description)]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ensembl gene lookup failed for %r / %r: %s", q, ensembl_name, exc)
        return []

