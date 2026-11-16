"""TrainingPlanBuilder (interface; implemented with plan generation).

The TrainingPlan Composite is assembled step by step: start_week() -> add_session() ->
add_exercise() -> ... -> build(). build() is the only way to get a TrainingPlan and runs the
validation gate (FUNCTIONAL_FLOW.md §4.5).
"""

from fitness_agent.domain.models import Exercise, UserProfile
from fitness_agent.domain.plan import TrainingPlan
from fitness_agent.domain.strategies import PlanningStrategy


class PlanValidationError(Exception):
    """The assembled plan breaks a rule of the validation gate; the message says which."""


class TrainingPlanBuilder:
    """Builds a TrainingPlan step by step and validates it in build()."""

    def __init__(self, catalog: list[Exercise], allowed_pool: list[Exercise],
                 strategy: PlanningStrategy, profile: UserProfile) -> None:
        """The catalog, the allowed pool and the Strategy's limits are what build() checks."""
        self.catalog = catalog
        self.allowed_pool = allowed_pool
        self.strategy = strategy
        self.profile = profile

    def start_week(self, number: int) -> None:
        """Start a new week; the following sessions belong to it."""
        raise NotImplementedError

    def add_session(self, day_of_week: int, focus: str) -> None:
        """Add a session to the current week."""
        raise NotImplementedError

    def add_exercise(self, exercise_id: str, sets: int, reps: int, load: float,
                     rest_s: int) -> None:
        """Add an exercise to the current session."""
        raise NotImplementedError

    def build(self) -> TrainingPlan:
        """Validate and return the plan; raise PlanValidationError naming the broken rule."""
        raise NotImplementedError
