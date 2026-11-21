"""TrainingPlanBuilder: assembles the TrainingPlan Composite step by step (Builder pattern).

start_week() -> add_session() -> add_exercise() -> ... -> build(). Two callers direct the same
steps: the plan service (the LLM's draft) and the Strategy (the fallback week and weeks 2-4).
build() is the only way to get a TrainingPlan and runs the validation gate
(FUNCTIONAL_FLOW.md §4.5); a broken rule raises PlanValidationError naming it.
"""

from pydantic import ValidationError

from fitness_agent.domain.models import Exercise, UserProfile
from fitness_agent.domain.plan import PlannedExercise, Session, TrainingPlan, Week
from fitness_agent.domain.strategies import PlanningStrategy

MAX_SESSIONS_PER_WEEK = 6  # at least one rest day


class PlanValidationError(Exception):
    """The assembled plan breaks a rule of the validation gate; the message says which."""


class TrainingPlanBuilder:
    """Builds a TrainingPlan step by step and validates it in build()."""

    def __init__(self, catalog: list[Exercise], allowed_pool: list[Exercise],
                 strategy: PlanningStrategy, profile: UserProfile) -> None:
        """The catalog, the allowed pool and the Strategy's limits are what build() checks."""
        self._catalog = {exercise.id: exercise for exercise in catalog}
        self._allowed = {exercise.id for exercise in allowed_pool}
        self._strategy = strategy
        self._profile = profile
        self.weeks: list[Week] = []

    def start_week(self, number: int) -> None:
        """Start a new week; the following sessions belong to it."""
        self.weeks.append(Week(number=number))

    def add_session(self, day_of_week: int, focus: str) -> None:
        """Add a session to the current week."""
        if not self.weeks:
            raise PlanValidationError("add_session() before start_week()")
        self.weeks[-1].sessions.append(Session(day_of_week=day_of_week, focus=focus))

    def add_exercise(self, exercise_id: str, sets: int, reps: int, load: float,
                     rest_s: int) -> None:
        """Add an exercise to the current session; its load type comes from the catalog."""
        if not self.weeks or not self.weeks[-1].sessions:
            raise PlanValidationError("add_exercise() before add_session()")
        if exercise_id not in self._catalog:
            raise PlanValidationError(f"unknown exercise id {exercise_id}")
        try:
            planned = PlannedExercise(exercise_id=exercise_id,
                                      load_type=self._catalog[exercise_id].load_type,
                                      sets=sets, reps=reps, load=load, rest_s=rest_s)
        except ValidationError as error:
            raise PlanValidationError(f"invalid numbers for {exercise_id}: {error}") from error
        self.weeks[-1].sessions[-1].exercises.append(planned)

    def build(self) -> TrainingPlan:
        """Validate and return the plan; raise PlanValidationError naming the broken rule."""
        if not self.weeks:
            raise PlanValidationError("the plan has no week")
        low, high = self._strategy.weekly_set_limits(self._profile)
        max_sessions = min(self._profile.days_per_week, MAX_SESSIONS_PER_WEEK)
        for week in self.weeks:
            self._check_week(week, max_sessions, low, high)
        return TrainingPlan(weeks=self.weeks)

    def _check_week(self, week: Week, max_sessions: int, low: int, high: int) -> None:
        """Sessions, rest day and weekly volume of one week."""
        days = [session.day_of_week for session in week.sessions]
        if not days:
            raise PlanValidationError(f"week {week.number} has no session")
        if len(set(days)) != len(days):
            raise PlanValidationError(f"week {week.number} has two sessions on one day")
        if len(days) > max_sessions:
            raise PlanValidationError(f"week {week.number} has {len(days)} sessions; at most "
                                      f"{max_sessions} are allowed (one rest day)")
        for session in week.sessions:
            self._check_session(session)
        sets = week.total_sets()
        if not low <= sets <= high:
            raise PlanValidationError(f"week {week.number} has {sets} sets; it must have "
                                      f"between {low} and {high}")

    def _check_session(self, session: Session) -> None:
        """Allowed pool, no duplicates, compounds first."""
        ids = [planned.exercise_id for planned in session.exercises]
        if not ids:
            raise PlanValidationError(f"the session on day {session.day_of_week} is empty")
        if len(set(ids)) != len(ids):
            raise PlanValidationError(f"an exercise appears twice on day {session.day_of_week}")
        for exercise_id in ids:
            if exercise_id not in self._allowed:
                raise PlanValidationError(f"{exercise_id} is not allowed for this profile "
                                          "(equipment, injury or level)")
        compound = [self._catalog[exercise_id].is_compound for exercise_id in ids]
        if compound != sorted(compound, reverse=True):
            raise PlanValidationError(f"on day {session.day_of_week} an isolation exercise "
                                      "comes before a compound one")
