from typing import Literal

from pydantic import BaseModel, Field

class RunConstraints(BaseModel):
    max_edits: int
    preserve_fertility: bool
    maximize_diversity: bool

class RunRequest(BaseModel):
    species: str
    research_objective: str
    candidate_genes: list[str]
    constraints: RunConstraints
    presets: list[Literal["minimal", "redundant"]]