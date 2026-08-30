"""
Core Model Task 1 — Objective Resolver for Relict Core.

Interprets the natural-language objective into a StructuredObjective.
Uses the configured ModelClient when available, and falls back to robust
deterministic extraction if the external model service is unreachable.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import settings
from app.core_model.inference.base import ModelClient
from app.core_model.objective_parser import _extract_json, _load_prompt_template
from app.models.requests import (
    AmbiguityStatus,
    ProjectContext,
    RunConfiguration,
    StructuredObjective,
)

logger = logging.getLogger(__name__)


def _is_vague_or_ambiguous(text: str) -> bool:
    """Heuristic detector for ambiguous/vague objectives when running without an LLM."""
    text_lower = text.lower().strip()
    # Check for short or completely non-specific objectives
    if len(text_lower.split()) < 4:
        return True

    # Common vague patterns without specified targets/changes
    vague_starters = [
        "enhance wild species resilience",
        "improve endangered animal survival",
        "apply molecular tools to assist",
        "recreate ancestral traits",
        "resurrect extinct phenotypic",
        "improve crop resilience and yield",
        "enhance livestock growth traits",
        "optimize industrial microbial chassis",
        "engineer metabolic flux in cellular",
        "control pest insect populations",
        "suppress disease vector transmission",
        "develop therapeutic gene editing approaches",
        "investigate precision molecular therapies",
    ]
    for starter in vague_starters:
        if text_lower.startswith(starter) and len(text_lower) < len(starter) + 40:
            return True

    # Direction ambiguous patterns
    ambig_patterns = [
        r"^modulate (?:the expression (?:level )?of )?([a-zA-Z0-9_-]+) in (.+) to alter (.+)\.?$",
        r"^shift (?:cellular )?activity of ([a-zA-Z0-9_-]+) in (.+) to impact (.+)\.?$",
        r"^adjust (?:the regulation of )?([a-zA-Z0-9_-]+) in (.+) to modify (.+)\.?$",
        r"^alter (?:the physiological function of )?([a-zA-Z0-9_-]+) in (.+) to change (.+)\.?$",
    ]
    for pat in ambig_patterns:
        if re.match(pat, text_lower):
            return True

    return False


def _heuristic_resolve(
    project: ProjectContext, run_config: RunConfiguration
) -> StructuredObjective:
    """Deterministic fallback parser for StructuredObjective."""
    text = project.objective.strip()

    if _is_vague_or_ambiguous(text):
        return StructuredObjective(
            target_phenotypes=None,
            biological_processes=None,
            desired_change=None,
            relevant_concepts=None,
            retrieval_targets=None,
            ambiguity_status=AmbiguityStatus.CLARIFICATION_REQUIRED,
        )

    genes = list(run_config.candidate_genes)
    species = project.species or "target species"

    # Extract potential gene symbols (e.g. uppercase symbols of 2-8 chars)
    symbol_pat = re.findall(r"\b[A-Z][A-Za-z0-9_-]{1,7}\b", text)
    known_non_genes = {
        "Increase",
        "Decrease",
        "Upregulate",
        "Downregulate",
        "Improve",
        "Restore",
        "Enhance",
        "Apply",
        "Using",
        "Through",
        "Design",
        "Target",
        "Genetic",
        "Mutations",
        "Precise",
        "Gorilla",
        "Gorillas",
        "Human",
        "Mammoth",
        "Elephant",
        "Wheat",
        "Plant",
        "Animal",
    }
    extracted_genes = [s for s in symbol_pat if s not in known_non_genes and s not in genes]
    effective_genes = list(genes) + extracted_genes

    # Extract concise phenotype keywords/phrases from objective text
    raw_words = [w.strip(".,;:()\"'") for w in text.split() if len(w) > 2]
    stop_words = {
        "the",
        "and",
        "via",
        "for",
        "with",
        "into",
        "from",
        "over",
        "under",
        "reconstitute",
        "introduce",
        "targeted",
        "genetic",
        "precise",
        "mutations",
        "restore",
        "achieve",
        "enhance",
        "apply",
        "through",
        "using",
        "confer",
        "alter",
        "modify",
        "design",
        "strategy",
        "simultaneously",
        "operating",
        "increase",
        "increasing",
        "decrease",
        "decreasing",
        "upregulate",
        "upregulating",
        "downregulate",
        "downregulating",
        "improve",
        "improving",
        "in",
        "by",
        "of",
        "to",
        "a",
        "an",
        "is",
        "are",
        "on",
        "as",
        "at",
        "target",
        "pathway",
        "pathways",
        "cellular",
        "metabolic",
        "function",
        "expression",
        "activity",
        "traits",
        "phenotypes",
        "species",
        "animals",
        "plants",
        "organism",
        "gorillas",
        "gorilla",
        "elephant",
        "mammoth",
    }
    pheno_terms = [w for w in raw_words if w.lower() not in stop_words and w not in effective_genes]
    target_phenos = pheno_terms[:5] if pheno_terms else [text[:40]]

    bio_procs = [f"{species} metabolic and cellular regulation"]
    concepts = [project.scope.value.lower(), f"{species} genetics"] + target_phenos
    retrieval_targets = list(effective_genes) + target_phenos + [f"{species} target pathways"]

    return StructuredObjective(
        target_phenotypes=target_phenos,
        biological_processes=bio_procs,
        desired_change=f"Implement targeted interventions in {species} to achieve {text}",
        relevant_concepts=concepts,
        retrieval_targets=retrieval_targets,
        ambiguity_status=AmbiguityStatus.CLEAR,
    )


class CoreModelObjectiveResolver:
    """
    Production ObjectiveResolver satisfying app.run_manager.stages.ObjectiveResolver.
    """

    def __init__(self, model_client: ModelClient | None = None) -> None:
        self.model_client = model_client

    async def resolve(
        self,
        project: ProjectContext,
        run_config: RunConfiguration,
    ) -> StructuredObjective:
        """Resolve a natural-language objective into a StructuredObjective."""
        objective_text = project.objective.strip()

        # If a live model client is provided or configured, try model-based parsing
        if self.model_client is not None:
            try:
                template = _load_prompt_template()
                prompt = template.format(objective=objective_text)
                raw_output = self.model_client.generate(prompt)
                parsed = _extract_json(raw_output)

                ambiguity = parsed.get("ambiguity_status", "CLEAR")
                if ambiguity == "CLARIFICATION_REQUIRED":
                    return StructuredObjective(
                        target_phenotypes=None,
                        biological_processes=None,
                        desired_change=None,
                        relevant_concepts=None,
                        retrieval_targets=None,
                        ambiguity_status=AmbiguityStatus.CLARIFICATION_REQUIRED,
                    )

                return StructuredObjective(
                    target_phenotypes=parsed.get("target_phenotypes") or [],
                    biological_processes=parsed.get("biological_processes") or [],
                    desired_change=parsed.get("desired_change") or objective_text,
                    relevant_concepts=parsed.get("relevant_concepts") or [],
                    retrieval_targets=parsed.get("retrieval_targets") or [],
                    ambiguity_status=AmbiguityStatus.CLEAR,
                )
            except Exception as exc:
                logger.warning(
                    "Model-based objective resolution failed (%s); falling back to deterministic resolution.",
                    exc,
                )

        # Fallback to deterministic resolution
        return _heuristic_resolve(project, run_config)
