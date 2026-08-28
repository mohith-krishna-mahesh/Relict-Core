import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from app.core_model.inference.ollama import generate

PROMPT_PATH = Path(__file__).parent / "prompts" / "objective_resolution.txt"


class StructuredObjective(BaseModel):
    target_phenotypes: Optional[list[str]]
    biological_processes: Optional[list[str]]
    desired_change: Optional[str]
    relevant_concepts: Optional[list[str]]
    retrieval_targets: Optional[list[str]]
    ambiguity_status: str  # "CLEAR" or "CLARIFICATION_REQUIRED"


def _load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _extract_json(raw_output: str) -> dict:
    """Model output sometimes wraps JSON in markdown fences or extra text.
    Try direct parse first, fall back to extracting the {...} block."""
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        start = raw_output.find("{")
        end = raw_output.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"No JSON object found in model output: {raw_output!r}")
        return json.loads(raw_output[start : end + 1])


def resolve_objective(objective_text: str) -> StructuredObjective:
    template = _load_prompt_template()
    prompt = template.format(objective=objective_text)

    raw_output = generate(prompt)
    parsed = _extract_json(raw_output)

    return StructuredObjective(**parsed)