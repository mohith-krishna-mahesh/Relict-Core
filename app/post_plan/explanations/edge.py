"""
Deterministic Edge Explanations for Relict Core.

Generates structured explanations for biological relationships / graph edges
without invoking an LLM (architecture §2.5, §15, §19).
"""

from __future__ import annotations

from typing import Any

from app.models.evidence import EffectDirection, EffectType, EvidenceEffect


def explain_edge(
    source_node: str,
    target_node: str,
    relationship: str,
    source_db: str,
    source_score: float | None = None,
    provenance: str = "",
    effect: EvidenceEffect | Any | None = None,
    consequence: str | None = None,
) -> str:
    """
    Produce a deterministic explanation for a single graph edge.

    Preserves uncertainty:
    - Never transforms 'associated_with' into 'causes'.
    - If effect direction is unknown, describes relationship without asserting directionality.
    - Formats source score strictly as evidence score.

    Format:
    Gene A — Gene B
    Functional association.
    Effect: Activation (direction: increases).
    Source: STRING.
    Evidence score: 0.91.
    """
    prefixes = ("gene:", "pathway:", "protein:", "phenotype:", "trait:", "process:", "disease:")
    src_clean = source_node
    tgt_clean = target_node
    for p in prefixes:
        if src_clean.startswith(p):
            src_clean = src_clean[len(p) :]
        if tgt_clean.startswith(p):
            tgt_clean = tgt_clean[len(p) :]
    rel_clean = relationship.replace("_", " ").capitalize()

    lines = [
        f"{src_clean} — {tgt_clean}",
        f"{rel_clean}.",
    ]

    # Add effect details if present
    if effect:
        eff_type = getattr(effect, "type", None)
        eff_dir = getattr(effect, "direction", None)
        eff_mag = getattr(effect, "magnitude", None)

        type_str = (
            eff_type.value
            if hasattr(eff_type, "value")
            else str(eff_type)
            if eff_type
            else "Biological effect"
        )
        dir_str = (
            eff_dir.value
            if hasattr(eff_dir, "value")
            else str(eff_dir)
            if eff_dir
            else "uncharacterized"
        )

        effect_line = f"Effect: {type_str} (direction: {dir_str}"
        if eff_mag is not None:
            effect_line += f", magnitude: {eff_mag}"
        effect_line += ")."
        lines.append(effect_line)

    if consequence:
        lines.append(f"Consequence: {consequence}.")

    lines.append(f"Source: {source_db}.")

    if source_score is not None:
        lines.append(f"Evidence score: {source_score:.2f}.")

    if provenance:
        lines.append(f"Provenance: {provenance}")

    return "\n".join(lines)
