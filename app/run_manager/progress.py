"""
Progress tracking for the Run Manager pipeline.

``ProgressTracker`` accumulates fractional progress as pipeline stages
complete.  Each stage contributes a fixed weight; the weights sum to 1.0.
A partial weight reflects work done up to a failure point, giving Shell a
meaningful progress value even for failed runs.
"""

from __future__ import annotations

from app.run_manager.state import PipelineStage

# Fractional weight of each stage in the overall run progress [0.0, 1.0].
# Sum: 0.10 + 0.25 + 0.30 + 0.10 + 0.25 = 1.00
STAGE_WEIGHTS: dict[PipelineStage, float] = {
    PipelineStage.OBJECTIVE_RESOLUTION: 0.10,
    PipelineStage.RETRIEVAL: 0.25,
    PipelineStage.PLANNING: 0.30,
    PipelineStage.VALIDATION: 0.10,
    PipelineStage.POST_PLAN: 0.25,
}


class ProgressTracker:
    """Accumulates fractional progress as pipeline stages complete."""

    def __init__(self) -> None:
        self._progress: float = 0.0

    @property
    def progress(self) -> float:
        """Current progress in [0.0, 1.0], rounded to 4 decimal places."""
        return round(self._progress, 4)

    def stage_started(self, stage: PipelineStage) -> None:
        """Hook called when a stage begins (reserved for sub-stage granularity)."""

    def stage_completed(self, stage: PipelineStage) -> None:
        """Advance progress by the weight assigned to the completed stage."""
        self._progress = min(1.0, self._progress + STAGE_WEIGHTS[stage])

    def complete(self) -> None:
        """Force progress to exactly 1.0 at successful run completion."""
        self._progress = 1.0
