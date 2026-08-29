from __future__ import annotations

import csv
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CanonicalSpecies(BaseModel):
    """Authoritative representation of a species from the canonical species registry."""

    id: str
    scientific_name: str
    common_name: str
    taxonomy_id: str
    ensembl_name: str
    source: str = "ncbi"
    is_extinct: bool = False
    has_genome_data: bool = True
    tags: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)

    @property
    def binomial(self) -> str:
        """Return the binomial/scientific name."""
        return self.scientific_name

    @property
    def tax_id(self) -> str:
        """Return the NCBI taxonomy ID as string."""
        return self.taxonomy_id


class SpeciesResolutionError(Exception):
    """Raised when a species cannot be resolved from the canonical knowledge base."""


class SpeciesResolver:
    """Memory-efficient, indexed Species Resolver for large-scale species datasets."""

    def __init__(
        self,
        csv_path: str | Path | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        root_dir = Path(__file__).resolve().parent.parent.parent
        if csv_path:
            self.csv_path = Path(csv_path)
        else:
            default_csv = root_dir / "data" / "species" / "species.csv"
            default_gz = root_dir / "data" / "species" / "species.csv.gz"
            self.csv_path = default_csv if default_csv.exists() else default_gz
        self.db_path = Path(db_path) if db_path else root_dir / "data" / "species" / "species.db"

        self._ensure_indexed_db()
        # Open persistent read-only connection
        self._conn = sqlite3.connect(
            f"file:{self.db_path}?mode=ro",
            uri=True,
            check_same_thread=False,
            timeout=10.0,
        )

    def _normalize(self, val: str | int | None) -> str:
        """Normalize query string for case-insensitive and whitespace-stripped lookup."""
        if val is None:
            return ""
        return " ".join(str(val).strip().lower().split())

    def _ensure_indexed_db(self) -> None:
        """Build indexed SQLite database from CSV if missing or outdated."""
        if self.db_path.exists() and self.db_path.stat().st_size > 0:
            return

        if not self.csv_path.exists():
            gz_fallback = self.csv_path.with_suffix(".csv.gz")
            if gz_fallback.exists():
                self.csv_path = gz_fallback
            else:
                logger.warning("Canonical species CSV not found at %s", self.csv_path)
                return

        logger.info("Building indexed species database at %s...", self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_db = self.db_path.with_suffix(".db.tmp")

        conn = sqlite3.connect(tmp_db)
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute("PRAGMA journal_mode = MEMORY")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS species (
                id TEXT PRIMARY KEY,
                scientific_name TEXT NOT NULL,
                common_name TEXT,
                taxonomy_id TEXT,
                ensembl_name TEXT,
                source TEXT,
                is_extinct INTEGER,
                has_genome_data INTEGER,
                tags TEXT,
                aliases TEXT
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS species_aliases (
                alias TEXT NOT NULL,
                species_id TEXT NOT NULL
            );
            """
        )

        import gzip

        open_fn = gzip.open if str(self.csv_path).endswith(".gz") else open
        with open_fn(self.csv_path, mode="rt", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            species_rows = []
            alias_rows = []

            for row in reader:
                sid = row.get("id", "").strip()
                sci = row.get("scientificName", "").strip()
                com = row.get("commonName", "").strip()
                tax = row.get("taxonomyId", "").strip()
                src = row.get("source", "ncbi").strip()
                ext_val = str(row.get("isExtinct", "")).strip().lower()
                ext = 1 if ext_val in ("true", "1", "yes") else 0
                gen_val = str(row.get("hasGenomeData", "")).strip().lower()
                gen = 1 if gen_val in ("true", "1", "yes") else 0
                tags_str = row.get("tags", "[]")
                ens = sci.lower().replace(" ", "_")

                species_rows.append((sid, sci, com, tax, ens, src, ext, gen, tags_str, ""))

                if com:
                    alias_rows.append((com.strip().lower(), sid))
                    if "/" in com:
                        for part in com.split("/"):
                            clean_p = part.strip().lower()
                            if clean_p:
                                alias_rows.append((clean_p, sid))

                if tags_str and tags_str != "[]":
                    clean_tags = tags_str.strip("[]{}").replace("'", "").split(",")
                    for t in clean_tags:
                        t_clean = t.strip().lower()
                        if t_clean:
                            alias_rows.append((t_clean, sid))

                if len(species_rows) >= 50000:
                    conn.executemany(
                        "INSERT OR REPLACE INTO species VALUES (?,?,?,?,?,?,?,?,?,?)",
                        species_rows,
                    )
                    conn.executemany("INSERT INTO species_aliases VALUES (?,?)", alias_rows)
                    species_rows.clear()
                    alias_rows.clear()

            if species_rows:
                conn.executemany(
                    "INSERT OR REPLACE INTO species VALUES (?,?,?,?,?,?,?,?,?,?)",
                    species_rows,
                )
                conn.executemany("INSERT INTO species_aliases VALUES (?,?)", alias_rows)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_sci_lower ON species(lower(scientific_name));")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_com_lower ON species(lower(common_name));")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tax ON species(taxonomy_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ens ON species(ensembl_name);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alias ON species_aliases(alias);")
        conn.commit()
        conn.close()

        tmp_db.replace(self.db_path)
        logger.info("Species database index complete.")

    def _row_to_model(self, row: tuple[Any, ...]) -> CanonicalSpecies:
        """Convert a database tuple into a CanonicalSpecies model."""
        (
            sid,
            sci,
            com,
            tax,
            ens,
            src,
            ext,
            gen,
            tags_str,
            _aliases_str,
        ) = row

        tags: list[str] = []
        if tags_str and tags_str != "[]":
            try:
                parsed = json.loads(tags_str)
                if isinstance(parsed, list):
                    tags = [str(t).strip() for t in parsed if str(t).strip()]
            except Exception:
                try:
                    parsed = json.loads(tags_str.replace("'", '"'))
                    if isinstance(parsed, list):
                        tags = [str(t).strip() for t in parsed if str(t).strip()]
                except Exception:
                    clean = tags_str.strip("[]{}'\"")
                    tags = [t.strip().strip("'\"") for t in clean.split(",") if t.strip()]

        aliases: list[str] = list(tags)
        if com and "/" in com:
            for part in com.split("/"):
                clean_p = part.strip()
                if clean_p and clean_p.lower() != com.lower():
                    aliases.append(clean_p)

        return CanonicalSpecies(
            id=sid,
            scientific_name=sci,
            common_name=com or "",
            taxonomy_id=str(tax or ""),
            ensembl_name=ens or sci.lower().replace(" ", "_"),
            source=src or "ncbi",
            is_extinct=bool(ext),
            has_genome_data=bool(gen),
            tags=tags,
            aliases=aliases,
        )

    def resolve(self, query: str | int | None) -> CanonicalSpecies | None:
        """Resolve a species query (scientific name, common name, alias, or tax ID)."""
        if query is None:
            return None

        norm = self._normalize(query)
        if not norm:
            return None

        cur = self._conn.cursor()

        # 1. Direct scientific match (case-insensitive)
        cur.execute(
            "SELECT id, scientific_name, common_name, taxonomy_id, ensembl_name, "
            "source, is_extinct, has_genome_data, tags, aliases "
            "FROM species WHERE lower(scientific_name) = ? LIMIT 1",
            (norm,),
        )
        row = cur.fetchone()
        if row:
            return self._row_to_model(row)

        # 2. Common name match (case-insensitive)
        cur.execute(
            "SELECT id, scientific_name, common_name, taxonomy_id, ensembl_name, "
            "source, is_extinct, has_genome_data, tags, aliases "
            "FROM species WHERE lower(common_name) = ? LIMIT 1",
            (norm,),
        )
        row = cur.fetchone()
        if row:
            return self._row_to_model(row)

        # 3. Taxonomy ID match
        cur.execute(
            "SELECT id, scientific_name, common_name, taxonomy_id, ensembl_name, "
            "source, is_extinct, has_genome_data, tags, aliases "
            "FROM species WHERE taxonomy_id = ? LIMIT 1",
            (norm,),
        )
        row = cur.fetchone()
        if row:
            return self._row_to_model(row)

        # 4. Ensembl name match
        norm_ens = norm.replace(" ", "_")
        cur.execute(
            "SELECT id, scientific_name, common_name, taxonomy_id, ensembl_name, "
            "source, is_extinct, has_genome_data, tags, aliases "
            "FROM species WHERE ensembl_name = ? LIMIT 1",
            (norm_ens,),
        )
        row = cur.fetchone()
        if row:
            return self._row_to_model(row)

        # 5. Alias / Tag index lookup
        cur.execute(
            "SELECT s.id, s.scientific_name, s.common_name, s.taxonomy_id, "
            "s.ensembl_name, s.source, s.is_extinct, s.has_genome_data, "
            "s.tags, s.aliases FROM species s "
            "JOIN species_aliases a ON s.id = a.species_id "
            "WHERE a.alias = ? LIMIT 1",
            (norm,),
        )
        row = cur.fetchone()
        if row:
            return self._row_to_model(row)

        return None

    def get_by_taxonomy_id(self, tax_id: int | str) -> CanonicalSpecies | None:
        """Get canonical species by NCBI taxonomy ID."""
        norm = self._normalize(tax_id)
        if not norm:
            return None
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, scientific_name, common_name, taxonomy_id, ensembl_name, "
            "source, is_extinct, has_genome_data, tags, aliases "
            "FROM species WHERE taxonomy_id = ? LIMIT 1",
            (norm,),
        )
        row = cur.fetchone()
        return self._row_to_model(row) if row else None

    def get_by_ensembl_name(self, ensembl_name: str) -> CanonicalSpecies | None:
        """Get canonical species by Ensembl species name."""
        norm = self._normalize(ensembl_name).replace(" ", "_")
        if not norm:
            return None
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, scientific_name, common_name, taxonomy_id, ensembl_name, "
            "source, is_extinct, has_genome_data, tags, aliases "
            "FROM species WHERE ensembl_name = ? LIMIT 1",
            (norm,),
        )
        row = cur.fetchone()
        return self._row_to_model(row) if row else None

    def get_by_binomial(self, scientific_name: str) -> CanonicalSpecies | None:
        """Get canonical species by binomial/scientific name."""
        norm = self._normalize(scientific_name)
        if not norm:
            return None
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, scientific_name, common_name, taxonomy_id, ensembl_name, "
            "source, is_extinct, has_genome_data, tags, aliases "
            "FROM species WHERE lower(scientific_name) = ? LIMIT 1",
            (norm,),
        )
        row = cur.fetchone()
        return self._row_to_model(row) if row else None

    def all_species(self, limit: int | None = None) -> list[CanonicalSpecies]:
        """Return canonical species from database (optionally limited)."""
        cur = self._conn.cursor()
        if limit:
            cur.execute(
                "SELECT id, scientific_name, common_name, taxonomy_id, "
                "ensembl_name, source, is_extinct, has_genome_data, tags, aliases "
                "FROM species LIMIT ?",
                (limit,),
            )
        else:
            cur.execute(
                "SELECT id, scientific_name, common_name, taxonomy_id, "
                "ensembl_name, source, is_extinct, has_genome_data, tags, aliases "
                "FROM species"
            )
        return [self._row_to_model(r) for r in cur.fetchall()]

    def count(self) -> int:
        """Return the exact count of species in the database."""
        cur = self._conn.cursor()
        cur.execute("SELECT count(*) FROM species")
        res = cur.fetchone()
        return res[0] if res else 0


# Global singleton instance for project-wide use
_global_resolver: SpeciesResolver | None = None


def get_species_resolver() -> SpeciesResolver:
    """Return the global shared SpeciesResolver instance."""
    global _global_resolver
    if _global_resolver is None:
        _global_resolver = SpeciesResolver()
    return _global_resolver
