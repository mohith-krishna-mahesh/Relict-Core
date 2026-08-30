"""
Deterministic Edge Explanations for Relict Core.

Generates structured explanations for biological relationships / graph edges
without invoking an LLM (architecture §2.5, §15).
"""

from __future__ import annotations


def explain_edge(
    source_node: str,
    target_node: str,
    relationship: str,
    source_db: str,
    source_score: float | None = None,
    provenance: str = "",
) -> str:
    """
    Produce a deterministic explanation for a single graph edge.

    Format:
    Gene A — Gene B
    Functional association.
    Source: STRING.
    Evidence score: 0.91.
    """
    src_clean = source_node.replace("gene:", "").replace("pathway:", "")
    tgt_clean = target_node.replace("gene:", "").replace("pathway:", "")
    rel_clean = relationship.replace("_", " ").capitalize()

    score_line = f"\nEvidence score: {source_score:.2f}." if source_score is not None else ""
    prov_line = f"\nProvenance: {provenance}" if provenance else ""

    return (
        f"{src_clean} — {tgt_clean}\n"
        f"{rel_clean}.\n"
        f"Source: {source_db}.{score_line}{prov_line}"
    )
