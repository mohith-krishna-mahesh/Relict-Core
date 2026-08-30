"""
Deterministic Node Explanations for Relict Core.

Generates structured explanations for individual biological entities / graph nodes
without invoking an LLM (architecture §2.5, §15).
"""

from __future__ import annotations


def explain_node(
    node_id: str,
    role: str = "Biological entity in target pathway",
    why_it_matters: str = "Selected because it provides evidence-supported coverage of the target biological pathway.",
    evidence_sources: list[str] | None = None,
) -> str:
    """
    Produce a deterministic, structured explanation for a single graph node.

    Format:
    Gene A
    Role:
    Pigmentation-associated gene.
    Why it matters:
    Selected because it provides evidence-supported coverage of the target pigmentation pathway.
    Evidence:
    STRING · Reactome
    """
    sources_str = " · ".join(evidence_sources) if evidence_sources else "Knowledge Graph"
    clean_name = node_id.replace("gene:", "").replace("pathway:", "")

    return (
        f"{clean_name}\n"
        f"Role:\n"
        f"{role}\n\n"
        f"Why it matters:\n"
        f"{why_it_matters}\n\n"
        f"Evidence:\n"
        f"{sources_str}"
    )
