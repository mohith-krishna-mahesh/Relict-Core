from typing import Literal

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    rationale: str | None = None
    confidence: Literal["evidence", "model_estimated", "unknown"] | None = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    confidence: Literal["evidence", "model_estimated", "unknown"]
    weight: float
    rationale: str | None = None