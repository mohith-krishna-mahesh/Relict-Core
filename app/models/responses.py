from pydantic import BaseModel
from datetime import datetime
from typing import Any, Literal
from graph import GraphNode, GraphEdge

class StartRunResponse(BaseModel):
    run_id: str

class Strategy(BaseModel):
    id: str
    included: list[str]
    excluded: list[str]
    risk_score: float
    rationale: str
    stages: list[dict[str, Any]] | None = None


class RunResult(BaseModel):
    run_id: str
    status: Literal["queued", "running", "complete", "failed"]
    objective: str | None = None
    created_at: datetime | None = None
    duration_ms: int | None = None
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    strategies: list[Strategy]