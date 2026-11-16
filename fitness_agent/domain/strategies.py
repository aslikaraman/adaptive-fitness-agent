"""Planning Strategies, chosen by a Simple Factory (interface; implemented with plan generation).

A PlanningStrategy holds the rules of one goal (FUNCTIONAL_FLOW.md §4.2): the session days,
the prompt constraints, the training numbers for each exercise, the weekly set limits, the
deterministic fallback week and the progression for weeks 2-4.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from fitness_agent.domain.models import Exercise, UserProfile


class Prescription(BaseModel):
    """The training numbers the Strategy sets for one exercise."""

    sets: int = Field(ge=1)
    reps: int = Field(ge=1)
    load: float = Field(ge=0)
    rest_s: int = Field(ge=0)


class PlanningStrategy(ABC):
    """The rules of one training goal."""

    @abstractmethod
    def session_days(self, profile: UserProfile) -> list[int]:
        """The days of the week (1-7) that get a session, with at least one rest day."""

    @abstractmethod
    def constraints(self, profile: UserProfile) -> str:
        """The plan skeleton written as prompt text: sessions, focus and exercises per session."""

    @abstractmethod
    def prescribe(self, exercise: Exercise, profile: UserProfile) -> Prescription:
        """Sets, reps, load and rest for one exercise in week 1."""

    @abstractmethod
    def weekly_set_limits(self, profile: UserProfile) -> tuple[int, int]:
        """The minimum and maximum total sets per week."""

    @abstractmethod
    def add_fallback_week(self, builder, profile: UserProfile, pool: list[Exercise]) -> None:
        """Build week 1 without the LLM, with fixed selection rules, through the builder."""

    @abstractmethod
    def add_progression_weeks(self, builder, profile: UserProfile) -> None:
        """Add weeks 2-4 through the builder, applying the progression rule to week 1."""


class StrategyFactory:
    """Simple Factory: returns the Strategy for the profile's goal."""

    def create(self, profile: UserProfile) -> PlanningStrategy:
        """Return the Strategy for profile.goal."""
        raise NotImplementedError
