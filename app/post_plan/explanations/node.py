"""
Deterministic Node Explanations for Relict Core.

Generates structured explanations for individual biological entities / graph nodes
without invoking an LLM (architecture §2.5, §15, §18).
"""

from __future__ import annotations

from typing import Any

from app.models.evidence import EvidenceRecord


def explain_node(
    node_id: str,
    role: str = "Biological entity in target pathway",
    why_it_matters: str = "Selected because it provides evidence-supported coverage of the target biological pathway.",
    evidence_sources: list[str] | None = None,
    evidence_records: list[EvidenceRecord] | None = None,
    effects: list[str] | None = None,
    consequences: list[str] | None = None,
) -> str:
    """
    Produce a deterministic, structured explanation for a single graph node.

    Format:
    Gene A
    Role:
    Pigmentation-associated gene.
    Why it matters:
    Selected because it provides evidence-supported coverage of the target pigmentation pathway.
    Supported Biological Effects:
    * Activation (direction: increases) supported by STRING (score: 0.91)
    Evidence:
    STRING · Reactome
    """
    prefixes = ("gene:", "pathway:", "protein:", "phenotype:", "trait:", "process:", "disease:")
    clean_name = node_id
    for p in prefixes:
        if clean_name.startswith(p):
            clean_name = clean_name[len(p) :]

    # Extract distinct sources from records if passed
    sources_list: list[str] = list(evidence_sources) if evidence_sources else []
    effect_descriptions: list[str] = list(effects or [])

    if evidence_records:
        seen_sources = set(sources_list)
        for rec in sorted(evidence_records, key=lambda r: (r.source, r.source_id or "")):
            if (
                rec.entity_a == clean_name
                or rec.entity_b == clean_name
                or rec.entity_a == node_id
                or rec.entity_b == node_id
            ):
                if rec.source not in seen_sources:
                    seen_sources.add(rec.source)
                    sources_list.append(rec.source)

                if rec.effect and getattr(rec.effect, "type", None):
                    eff_type = getattr(rec.effect.type, "value", rec.effect.type)
                    eff_dir = (
                        getattr(rec.effect.direction, "value", rec.effect.direction)
                        if rec.effect.direction
                        else None
                    )
                    dir_str = f"direction: {eff_dir}" if eff_dir else "direction: uncharacterized"
                    score_str = (
                        f", score: {rec.source_score:.2f}" if rec.source_score is not None else ""
                    )
                    desc = f"* {eff_type} ({dir_str}) supported by {rec.source}{score_str}"
                    if desc not in effect_descriptions:
                        effect_descriptions.append(desc)

    sources_str = " · ".join(sources_list) if sources_list else "Knowledge Graph"

    lines = [
        f"{clean_name}",
        "Role:",
        f"{role}",
        "",
        "Why it matters:",
        f"{why_it_matters}",
    ]

    if effect_descriptions:
        lines.extend(["", "Supported Biological Effects:"] + effect_descriptions)

    lines.extend(["", "Evidence:", f"{sources_str}"])

    return "\n".join(lines)
