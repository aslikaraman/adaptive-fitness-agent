"""Domain data models (stubs agreed in step 7; owner: Rahul).

Field names follow FUNCTIONAL_FLOW.md §2. Validation rules beyond the basic
ranges are added in step 9.
"""

from typing import Literal

from pydantic import BaseModel, Field

FitnessLevel = Literal["beginner", "intermediate", "advanced"]
Goal = Literal["strength", "fat_loss", "endurance"]
EquipmentItem = Literal[
    "bodyweight", "dumbbells", "barbell", "kettlebell", "bands", "pullup_bar", "machines"
]
BodyRegion = Literal["knee", "shoulder", "lower_back", "wrist", "ankle", "neck", "hip"]
MovementPattern = Literal["squat", "hinge", "push", "pull", "carry", "core", "cardio"]
LoadType = Literal["kg", "bw", "time"]


class Injury(BaseModel):
    """An injury in a known body region, with an optional note."""

    region: BodyRegion
    note: str | None = None


class UserProfile(BaseModel):
    """The result of onboarding."""

    age: int = Field(ge=14, le=90)
    fitness_level: FitnessLevel
    goal: Goal
    days_per_week: int = Field(ge=1, le=7)
    equipment: list[EquipmentItem] = ["bodyweight"]
    injuries: list[Injury] = []
    injury_notes: list[str] = []

    @property
    def minor(self) -> bool:
        """True for users under 18 (minor caps apply)."""
        return self.age < 18


class Exercise(BaseModel):
    """One entry of the exercise catalog."""

    id: str
    name: str
    movement_pattern: MovementPattern
    required_equipment: list[EquipmentItem]
    contraindicated_regions: list[BodyRegion] = []
    is_compound: bool
    default_rep_range: tuple[int, int]
    load_type: LoadType
    level: FitnessLevel


class Feedback(BaseModel):
    """The user's answers after a session."""

    session_ref: str
    rpe: int = Field(ge=1, le=10)
    pain: bool
    pain_region: BodyRegion | None = None
    all_sets_done: bool
    completed_sets: int | None = Field(default=None, ge=0)
    missed_sessions: int = Field(default=0, ge=0)
    note: str | None = None


class DraftExercise(BaseModel):
    """One exercise in the LLM's week-1 draft."""

    exercise_id: str
    sets: int
    reps: int
    load: float
    rest_s: int


class DraftSession(BaseModel):
    """One session in the LLM's week-1 draft."""

    day_of_week: int = Field(ge=1, le=7)
    focus: str
    exercises: list[DraftExercise]


class PlanDraft(BaseModel):
    """The structured output of LLMClient.generate_plan(): week 1 only."""

    sessions: list[DraftSession]
