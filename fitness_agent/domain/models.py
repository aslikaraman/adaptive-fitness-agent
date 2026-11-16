"""Domain data models.

Field names and validation rules follow FUNCTIONAL_FLOW.md §2, §3 and §5.
"""

from typing import Literal, get_args

from pydantic import BaseModel, Field, model_validator

FitnessLevel = Literal["beginner", "intermediate", "advanced"]
Goal = Literal["strength", "fat_loss", "endurance"]
EquipmentItem = Literal[
    "bodyweight", "dumbbells", "barbell", "kettlebell", "bands", "pullup_bar", "machines"
]
BodyRegion = Literal["knee", "shoulder", "lower_back", "wrist", "ankle", "neck", "hip"]
MovementPattern = Literal["squat", "hinge", "push", "pull", "carry", "core", "cardio"]
LoadType = Literal["kg", "bw", "time"]

KNOWN_EQUIPMENT: tuple[str, ...] = get_args(EquipmentItem)
KNOWN_REGIONS: tuple[str, ...] = get_args(BodyRegion)
LEVELS: tuple[str, ...] = get_args(FitnessLevel)


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

    @model_validator(mode="before")
    @classmethod
    def _clean_equipment_and_injuries(cls, data):
        """Drop unknown equipment, always add bodyweight, move unknown regions to injury_notes."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        equipment = [item for item in data.get("equipment") or [] if item in KNOWN_EQUIPMENT]
        if "bodyweight" not in equipment:
            equipment.append("bodyweight")
        data["equipment"] = equipment

        injuries = []
        notes = list(data.get("injury_notes") or [])
        for injury in data.get("injuries") or []:
            if isinstance(injury, Injury):
                injuries.append(injury)
                continue
            region = injury.get("region")
            if region in KNOWN_REGIONS:
                injuries.append(injury)
            else:
                text = " ".join(str(part) for part in (region, injury.get("note")) if part)
                if text:
                    notes.append(text)
        data["injuries"] = injuries
        data["injury_notes"] = notes
        return data

    @property
    def minor(self) -> bool:
        """True for users under 18 (minor caps apply)."""
        return self.age < 18


class Exercise(BaseModel):
    """One entry of the exercise catalog."""

    id: str
    name: str
    movement_pattern: MovementPattern
    required_equipment: list[EquipmentItem] = Field(min_length=1)
    contraindicated_regions: list[BodyRegion] = []
    is_compound: bool
    default_rep_range: tuple[int, int]
    load_type: LoadType
    level: FitnessLevel

    @model_validator(mode="after")
    def _check_rep_range(self):
        """The rep range must be at least 1 and low <= high."""
        low, high = self.default_rep_range
        if low < 1 or low > high:
            raise ValueError(f"invalid default_rep_range {self.default_rep_range} for {self.id}")
        return self


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

    @model_validator(mode="after")
    def _check_pain_region(self):
        """Pain needs a known region; without pain there is no region."""
        if self.pain and self.pain_region is None:
            raise ValueError("pain_region is required when pain is reported")
        if not self.pain:
            self.pain_region = None
        return self


class DraftSession(BaseModel):
    """One session in the LLM's week-1 draft: a focus and the chosen exercises, in order."""

    focus: str
    exercise_ids: list[str]


class PlanDraft(BaseModel):
    """The structured output of LLMClient.generate_plan(): week 1 only.

    The LLM only chooses the exercises; the Strategy sets days, sets, reps, load and rest.
    """

    sessions: list[DraftSession]
