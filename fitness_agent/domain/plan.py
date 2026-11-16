"""The TrainingPlan Composite and its Memento (stubs agreed in step 7; owner: Rahul).

TrainingPlan -> Week -> Session (composites) -> PlannedExercise (leaf). Every
level offers total_volume(), duration() and scale_intensity(); the bodies are
written in step 9.
"""

from typing import Literal

from pydantic import BaseModel, Field

SessionStatus = Literal["planned", "done", "missed", "dropped"]


class PlannedExercise(BaseModel):
    """Leaf: one exercise with its prescription."""

    exercise_id: str
    sets: int
    reps: int
    load: float
    rest_s: int
    notes: str = ""

    def total_volume(self) -> float:
        """Sets x reps (x load for kg exercises)."""
        raise NotImplementedError

    def duration(self) -> int:
        """Estimated duration in seconds."""
        raise NotImplementedError

    def scale_intensity(self, factor: float) -> None:
        """Scale the load by factor."""
        raise NotImplementedError


class Session(BaseModel):
    """Composite: one training day."""

    day_of_week: int = Field(ge=1, le=7)
    focus: str
    status: SessionStatus = "planned"
    exercises: list[PlannedExercise] = []

    def total_volume(self) -> float:
        """Sum of the exercises' volume."""
        raise NotImplementedError

    def duration(self) -> int:
        """Sum of the exercises' duration in seconds."""
        raise NotImplementedError

    def scale_intensity(self, factor: float) -> None:
        """Scale every exercise."""
        raise NotImplementedError


class Week(BaseModel):
    """Composite: one week of sessions."""

    number: int = Field(ge=1, le=4)
    sessions: list[Session] = []

    def total_volume(self) -> float:
        """Sum of the sessions' volume."""
        raise NotImplementedError

    def duration(self) -> int:
        """Sum of the sessions' duration in seconds."""
        raise NotImplementedError

    def scale_intensity(self, factor: float) -> None:
        """Scale every session."""
        raise NotImplementedError


class PlanMemento(BaseModel):
    """Snapshot of a TrainingPlan before a change, plus the rule that fired."""

    snapshot: dict
    reason: str


class TrainingPlan(BaseModel):
    """Composite root: the 4-week plan."""

    weeks: list[Week] = []
    coach_summary: str = ""
    llm_generated: bool = True
    held_patterns: dict[str, int] = {}
    last_increase_week: dict[str, int] = {}

    def total_volume(self) -> float:
        """Sum of the weeks' volume."""
        raise NotImplementedError

    def duration(self) -> int:
        """Sum of the weeks' duration in seconds."""
        raise NotImplementedError

    def scale_intensity(self, factor: float) -> None:
        """Scale every week."""
        raise NotImplementedError

    def create_memento(self, reason: str) -> PlanMemento:
        """Return a snapshot of the current plan (Memento originator)."""
        raise NotImplementedError

    def restore(self, memento: PlanMemento) -> None:
        """Restore the plan from a snapshot."""
        raise NotImplementedError
