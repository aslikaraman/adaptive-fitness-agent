"""The TrainingPlan Composite and its Memento.

TrainingPlan -> Week -> Session (composites) -> PlannedExercise (leaf). Every
level offers the same operations: total_volume(), duration() and
scale_intensity(). A composite forwards each call to its children; the leaf
does the actual work.
"""

from typing import Literal

from pydantic import BaseModel, Field

from fitness_agent.domain.models import LoadType

SessionStatus = Literal["planned", "done", "missed", "dropped"]

SECONDS_PER_REP = 3


def _round_to(value: float, step: float) -> float:
    """Round value to the nearest multiple of step."""
    return round(value / step) * step


class PlannedExercise(BaseModel):
    """Leaf: one exercise with its prescription.

    load is kg for "kg", 0 for "bw" (bodyweight) and seconds per set for "time".
    """

    exercise_id: str
    load_type: LoadType
    sets: int = Field(ge=1)
    reps: int = Field(ge=1)
    load: float = Field(ge=0)
    rest_s: int = Field(ge=0)
    notes: str = ""

    def total_volume(self) -> int:
        """Sets x reps."""
        return self.sets * self.reps

    def duration(self) -> int:
        """Estimated duration in seconds: per set the work time plus the rest."""
        work = self.load if self.load_type == "time" else self.reps * SECONDS_PER_REP
        return round(self.sets * (work + self.rest_s))

    def scale_intensity(self, factor: float) -> None:
        """Scale the intensity: kg load (0.5 kg steps), time (5 s steps) or bodyweight reps."""
        if factor <= 0:
            raise ValueError("factor must be positive")
        if self.load_type == "kg":
            self.load = _round_to(self.load * factor, 0.5)
        elif self.load_type == "time":
            self.load = max(5, _round_to(self.load * factor, 5))
        else:
            self.reps = max(1, round(self.reps * factor))


class Session(BaseModel):
    """Composite: one training day."""

    day_of_week: int = Field(ge=1, le=7)
    focus: str
    status: SessionStatus = "planned"
    exercises: list[PlannedExercise] = []

    def total_volume(self) -> int:
        """Sum of the exercises' volume."""
        return sum(exercise.total_volume() for exercise in self.exercises)

    def duration(self) -> int:
        """Sum of the exercises' duration in seconds."""
        return sum(exercise.duration() for exercise in self.exercises)

    def scale_intensity(self, factor: float) -> None:
        """Scale every exercise."""
        for exercise in self.exercises:
            exercise.scale_intensity(factor)


class Week(BaseModel):
    """Composite: one week of sessions."""

    number: int = Field(ge=1, le=4)
    sessions: list[Session] = []

    def total_volume(self) -> int:
        """Sum of the sessions' volume."""
        return sum(session.total_volume() for session in self.sessions)

    def duration(self) -> int:
        """Sum of the sessions' duration in seconds."""
        return sum(session.duration() for session in self.sessions)

    def scale_intensity(self, factor: float) -> None:
        """Scale every session."""
        for session in self.sessions:
            session.scale_intensity(factor)

    def total_sets(self) -> int:
        """All sets of the week."""
        return sum(exercise.sets for session in self.sessions for exercise in session.exercises)


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

    def total_volume(self) -> int:
        """Sum of the weeks' volume."""
        return sum(week.total_volume() for week in self.weeks)

    def duration(self) -> int:
        """Sum of the weeks' duration in seconds."""
        return sum(week.duration() for week in self.weeks)

    def scale_intensity(self, factor: float) -> None:
        """Scale every week."""
        for week in self.weeks:
            week.scale_intensity(factor)

    def create_memento(self, reason: str) -> PlanMemento:
        """Return a snapshot of the current plan (Memento originator)."""
        return PlanMemento(snapshot=self.model_dump(), reason=reason)

    def restore(self, memento: PlanMemento) -> None:
        """Restore the plan from a snapshot, in place."""
        restored = TrainingPlan.model_validate(memento.snapshot)
        for name, value in restored:
            setattr(self, name, value)
