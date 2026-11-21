"""Plan Commands.

PlanCommand is a Template Method: execute() stores a Memento of the plan and
then calls _apply(), which each concrete Command implements. undo() restores the Memento.
A Command changes only the remaining (planned) sessions; sessions that are done, missed or
dropped are never changed (FUNCTIONAL_FLOW.md §6.3).
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator

from fitness_agent.domain.plan import PlanMemento, PlannedExercise, Session, TrainingPlan, Week

MIN_TIMED_LOAD = 5
MIN_SETS = 2


def round_load(load: float, load_type: str) -> float:
    """A load rounded the way the catalog counts: 0.5 kg, 5 seconds, 0 for bodyweight."""
    if load_type == "kg":
        return round(load * 2) / 2
    if load_type == "time":
        return max(MIN_TIMED_LOAD, round(load / 5) * 5)
    return 0.0


def remaining_sessions(plan: TrainingPlan) -> Iterator[Session]:
    """Every session that is still planned."""
    for week in plan.weeks:
        for session in week.sessions:
            if session.status == "planned":
                yield session


def occurrences(plan: TrainingPlan, exercise_id: str) -> Iterator[PlannedExercise]:
    """Every remaining occurrence of one exercise."""
    for session in remaining_sessions(plan):
        for planned in session.exercises:
            if planned.exercise_id == exercise_id:
                yield planned


class PlanCommand(ABC):
    """A change to a TrainingPlan that can be undone."""

    def __init__(self, reason: str) -> None:
        """Create the command; reason names the rule that fired."""
        self.reason = reason
        self._plan: TrainingPlan | None = None
        self._memento: PlanMemento | None = None

    def execute(self, plan: TrainingPlan) -> None:
        """Store a Memento of the plan, then apply the change."""
        self._plan = plan
        self._memento = plan.create_memento(self.reason)
        self._apply(plan)

    def undo(self) -> None:
        """Restore the plan as it was before execute()."""
        if self._plan is None or self._memento is None:
            raise RuntimeError("undo() called before execute()")
        self._plan.restore(self._memento)

    @abstractmethod
    def _apply(self, plan: TrainingPlan) -> None:
        """Change the plan (implemented by each concrete Command)."""


def _hold(plan: TrainingPlan, pattern: str | None, until_week: int) -> None:
    """Hold a movement pattern (no increase) until the end of until_week."""
    if pattern:
        plan.held_patterns[pattern] = max(plan.held_patterns.get(pattern, 0), until_week)


class AdjustVolumeCommand(PlanCommand):
    """Change sets, reps and/or load of one exercise in all its remaining occurrences."""

    # A Command holds all parameters it needs as members (lecture slide "Command").
    def __init__(self, reason: str, exercise_id: str,  # pylint: disable=too-many-arguments,too-many-positional-arguments
                 sets_delta: int = 0, reps_delta: int = 0, factor: float = 1.0,
                 increase: bool = False, week: int = 0) -> None:
        """An increase records the week, so the exercise is raised at most once a week."""
        super().__init__(reason)
        self.exercise_id = exercise_id
        self.sets_delta = sets_delta
        self.reps_delta = reps_delta
        self.factor = factor
        self.increase = increase
        self.week = week

    def _apply(self, plan: TrainingPlan) -> None:
        """Apply the deltas and the load factor to every remaining occurrence.

        A set decrease never goes below MIN_SETS in any occurrence (FUNCTIONAL_FLOW.md §6.4),
        even if that occurrence has fewer sets than the logged one (e.g. in the deload week).
        """
        for planned in occurrences(plan, self.exercise_id):
            if self.sets_delta < 0:
                planned.sets = max(planned.sets + self.sets_delta, min(planned.sets, MIN_SETS))
            else:
                planned.sets += self.sets_delta
            planned.reps = max(1, planned.reps + self.reps_delta)
            if self.factor != 1.0:
                planned.load = round_load(planned.load * self.factor, planned.load_type)
        if self.increase:
            plan.last_increase_week[self.exercise_id] = self.week


class SwapExerciseCommand(PlanCommand):
    """Replace one exercise by another in all its remaining occurrences, and hold the pattern."""

    # A Command holds all parameters it needs as members (lecture slide "Command").
    def __init__(self, reason: str, old_id: str,  # pylint: disable=too-many-arguments,too-many-positional-arguments
                 new_id: str, load_type: str, reps: int, load: float, *,
                 hold_pattern: str | None = None, until_week: int = 0) -> None:
        """The replacement starts with the given reps and load; the sets stay."""
        super().__init__(reason)
        self.old_id = old_id
        self.new_id = new_id
        self.load_type = load_type
        self.reps = reps
        self.load = load
        self.hold_pattern = hold_pattern
        self.until_week = until_week

    def _apply(self, plan: TrainingPlan) -> None:
        """Swap every remaining occurrence."""
        for planned in occurrences(plan, self.old_id):
            planned.exercise_id = self.new_id
            planned.load_type = self.load_type
            planned.reps = self.reps
            planned.load = self.load
        _hold(plan, self.hold_pattern, self.until_week)


class RemoveExerciseCommand(PlanCommand):
    """Remove one exercise from the remaining sessions (no safe alternative), and hold it."""

    def __init__(self, reason: str, exercise_id: str, *, hold_pattern: str | None = None,
                 until_week: int = 0) -> None:
        """The pattern is held until the end of until_week."""
        super().__init__(reason)
        self.exercise_id = exercise_id
        self.hold_pattern = hold_pattern
        self.until_week = until_week

    def _apply(self, plan: TrainingPlan) -> None:
        """Remove every remaining occurrence."""
        for session in remaining_sessions(plan):
            session.exercises = [planned for planned in session.exercises
                                 if planned.exercise_id != self.exercise_id]
        _hold(plan, self.hold_pattern, self.until_week)


class RescheduleCommand(PlanCommand):
    """Set the status of one session and, optionally, move it to another day."""

    def __init__(self, reason: str, week: int, day: int, *, new_day: int | None = None,
                 status: str = "planned") -> None:
        """week and day find the session; status is planned, done, missed or dropped."""
        super().__init__(reason)
        self.week = week
        self.day = day
        self.new_day = new_day
        self.status = status

    def _apply(self, plan: TrainingPlan) -> None:
        """Change the session's status and day."""
        week = self._week(plan)
        session = next((s for s in week.sessions if s.day_of_week == self.day), None)
        if session is None:
            raise ValueError(f"week {self.week} has no session on day {self.day}")
        session.status = self.status
        if self.new_day is not None:
            session.day_of_week = self.new_day
            week.sessions.sort(key=lambda item: item.day_of_week)

    def _week(self, plan: TrainingPlan) -> Week:
        """The week this command changes."""
        for week in plan.weeks:
            if week.number == self.week:
                return week
        raise ValueError(f"the plan has no week {self.week}")
