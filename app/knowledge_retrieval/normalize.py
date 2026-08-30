from __future__ import annotations

import logging
from typing import Any

from app.models.evidence import EvidenceEffect, EvidenceRecord

logger = logging.getLogger(__name__)


class NormalizationError(Exception):
    """Raised when a raw evidence dict cannot be normalized into an EvidenceRecord."""


def normalize_record(
    raw: dict[str, Any],
    *,
    source: str | None = None,
) -> EvidenceRecord:
    """Convert a raw dict into a validated ``EvidenceRecord``.

    Raises ``NormalizationError`` if required fields are missing or
    the data is fundamentally malformed.

    Parameters
    ----------
    raw:
        Dictionary that should contain at minimum ``entity_a`` and
        ``relationship``. All other fields have defaults.
    source:
        Override for the ``source`` field; if not provided the raw
        dict must contain ``"source"``.
    """
    try:
        effective_source = source or raw.get("source")
        if not effective_source:
            raise NormalizationError("Missing 'source' in evidence data.")

        entity_a = raw.get("entity_a")
        if not entity_a:
            raise NormalizationError("Missing 'entity_a' in evidence data.")

        relationship = raw.get("relationship")
        if not relationship:
            raise NormalizationError("Missing 'relationship' in evidence data.")

        provenance = raw.get("provenance")
        if provenance is not None and not isinstance(provenance, str):
            provenance = str(provenance)

        # Parse effect if present
        effect_obj: EvidenceEffect | None = None
        raw_effect = raw.get("effect")
        if isinstance(raw_effect, dict):
            effect_obj = EvidenceEffect(
                direction=str(raw_effect["direction"]) if raw_effect.get("direction") else None,
                type=str(raw_effect["type"]) if raw_effect.get("type") else None,
                magnitude=_safe_float(raw_effect.get("magnitude")),
            )
        elif isinstance(raw_effect, EvidenceEffect):
            effect_obj = raw_effect

        consequence = raw.get("consequence")
        if consequence is not None and not isinstance(consequence, str):
            consequence = str(consequence)

        return EvidenceRecord(
            source=str(effective_source),
            source_id=str(raw["source_id"]) if raw.get("source_id") is not None else None,
            entity_a=str(entity_a),
            entity_b=str(raw["entity_b"]) if raw.get("entity_b") is not None else None,
            relationship=str(relationship),
            effect=effect_obj,
            consequence=consequence,
            source_score=_safe_float(raw.get("source_score")),
            provenance=provenance,
            metadata=dict(raw["metadata"]) if isinstance(raw.get("metadata"), dict) else {},
        )
    except NormalizationError:
        raise
    except Exception as exc:
        raise NormalizationError(f"Failed to normalize evidence: {exc}") from exc


def normalize_records(
    raws: list[dict[str, Any]],
    *,
    source: str | None = None,
) -> list[EvidenceRecord]:
    """Normalize a batch of raw dicts, skipping malformed entries.

    Malformed entries are logged and silently dropped rather than
    aborting the entire batch.
    """
    records: list[EvidenceRecord] = []
    for raw in raws:
        try:
            records.append(normalize_record(raw, source=source))
        except NormalizationError as exc:
            logger.warning("Skipping malformed evidence: %s — raw=%s", exc, raw)
    return records


def _safe_float(value: Any) -> float | None:
    """Coerce a value to float or return None."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
