"""The adaptation pipeline: Pipes & Filters plus Commands (FUNCTIONAL_FLOW.md §6).

    AdaptationContext -> SafetyFilter -> ScheduleFilter -> LoadFilter -> Commands

All filters share one interface, `process(context) -> AdaptationContext`. A filter reads the
context and may add Commands, flags and messages; **it never executes a Command**. Only the
application service executes them, as one history entry, after the whole pipe has run.

Why this order: `SafetyFilter` and `ScheduleFilter` can both set `no_increase`, so
`LoadFilter` - the only filter that increases load - runs last and respects the flag. Pain has
the highest precedence, so it is handled first.

Error handling: a filter that raises (or a context that does not hold what a filter needs)
stops the pipe. **No Command is executed, the plan stays unchanged**, and the user is told
that the plan could not be adapted; the feedback stays saved, so the user can retry.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from fitness_agent.domain.commands import (AdjustVolumeCommand, PlanCommand, RemoveExerciseCommand,
                                           RescheduleCommand, SwapExerciseCommand)
from fitness_agent.domain.commands import round_load as rounded
from fitness_agent.domain.models import Exercise, Feedback, UserProfile
from fitness_agent.domain.plan import PlannedExercise, Session, TrainingPlan, Week
from fitness_agent.domain.strategies import PlanningStrategy

Classification = Literal["SAFETY", "TOO_HARD_SEVERE", "TOO_HARD", "ON_TARGET", "TOO_EASY",
                         "INCOMPLETE_LOW"]

SAFETY = "SAFETY"
TOO_HARD_SEVERE = "TOO_HARD_SEVERE"
TOO_HARD = "TOO_HARD"
ON_TARGET = "ON_TARGET"
TOO_EASY = "TOO_EASY"
INCOMPLETE_LOW = "INCOMPLETE_LOW"

# one load step, by load type (FUNCTIONAL_FLOW.md §6.3)
MAJOR_PATTERNS = ("squat", "hinge")
BIG_LOAD_STEP = 1.05
SMALL_LOAD_STEP = 1.025
LOAD_STEP_DOWN = 0.9
TIME_STEP_UP = 1.1
TIME_STEP_DOWN = 0.9
RESTART_LOAD = 0.7
REP_STEP_DOWN = 2
MIN_SETS = 2
MIN_REPS = 1

HINT_INCOMPLETE = ("Plan unchanged. If time is the problem, choose 'Redo onboarding' with "
                   "fewer days per week.")
COULD_NOT_ADAPT = "The plan could not be adapted this time. Your feedback is saved; try again."
SEE_PROFESSIONAL = ("You reported pain. We changed the exercise and lowered the load. If the "
                    "pain is sharp, in a joint, or still there at your next session, stop "
                    "training that area and see a doctor or physiotherapist. This app does not "
                    "diagnose injuries.")

SESSION_REF = re.compile(r"^w(?P<week>\d+)d(?P<day>\d+)$")


class AdaptationError(Exception):
    """A filter cannot process this feedback: the pipe stops and the plan stays unchanged."""


@dataclass
class AdaptationContext:  # pylint: disable=too-many-instance-attributes
    """The data format passed along the pipe.

    It carries the feedback (and the one before it), the plan, the plan's rules, the Commands
    the filters have emitted so far, and the flags later filters respect - one field per
    thing a filter may read or set, which is why it is wider than pylint's default.
    """

    feedback: Feedback
    plan: TrainingPlan
    profile: UserProfile
    catalog: list[Exercise]
    pool: list[Exercise]
    previous_feedback: Feedback | None = None
    strategy: PlanningStrategy | None = None
    commands: list[PlanCommand] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    session: Session | None = None
    week: Week | None = None
    no_increase: bool = False
    see_professional: bool = False
    classification: str = ""
    error: str = ""

    @property
    def failed(self) -> bool:
        """True when a filter stopped the pipe."""
        return bool(self.error)

    @property
    def exercises(self) -> list[PlannedExercise]:
        """The exercises of the logged session."""
        return [] if self.session is None else list(self.session.exercises)

    def by_id(self, exercise_id: str) -> Exercise:
        """The catalog entry of one exercise."""
        for exercise in self.catalog:
            if exercise.id == exercise_id:
                return exercise
        raise AdaptationError(f"exercise {exercise_id} is not in the catalog")

    def say(self, message: str) -> None:
        """Add a line for the user."""
        if message not in self.messages:
            self.messages.append(message)


class AdaptationFilter(ABC):
    """One step of the pipe."""

    @abstractmethod
    def process(self, context: AdaptationContext) -> AdaptationContext:
        """Read the context, emit Commands and flags, and pass it on."""


# ----------------------------------------------------------------------- the pipe
class AdaptationPipeline:
    """Runs the filters in order and collects the Commands they emit."""

    def __init__(self, filters: list[AdaptationFilter] | None = None) -> None:
        """filters defaults to SafetyFilter -> ScheduleFilter -> LoadFilter."""
        self._filters = filters or [SafetyFilter(), ScheduleFilter(), LoadFilter()]

    @property
    def filters(self) -> list[AdaptationFilter]:
        """The filters of this pipe, in order."""
        return list(self._filters)

    def run(self, context: AdaptationContext) -> AdaptationContext:
        """Run the pipe; on any error drop the Commands and leave the plan untouched."""
        try:
            context.week, context.session = find_session(context.plan,
                                                         context.feedback.session_ref)
            context.commands.append(RescheduleCommand(
                "session done", context.week.number, context.session.day_of_week,
                status="done"))
            for step in self._filters:
                context = step.process(context)
        except AdaptationError as error:
            context.error = str(error)
        except (KeyError, IndexError, ValueError, TypeError) as error:
            # invalid input, e.g. a plan the filters cannot work on: same way out
            context.error = f"{type(error).__name__}: {error}"
        if context.failed:
            context.commands.clear()
            context.say(COULD_NOT_ADAPT)
        return context


def default_pipeline() -> AdaptationPipeline:
    """The pipe of FUNCTIONAL_FLOW.md §6.1."""
    return AdaptationPipeline()


def find_session(plan: TrainingPlan, session_ref: str) -> tuple[Week, Session]:
    """The week and session a session_ref like "w1d3" points at."""
    match = SESSION_REF.match(session_ref.strip().lower())
    if not match:
        raise AdaptationError(f"the session reference {session_ref!r} is not w<week>d<day>")
    number, day = int(match.group("week")), int(match.group("day"))
    for week in plan.weeks:
        if week.number != number:
            continue
        for session in week.sessions:
            if session.day_of_week == day:
                return week, session
    raise AdaptationError(f"the plan has no session {session_ref}")


def weekly_sets(week: Week) -> int:
    """The sets of one week."""
    return sum(exercise.sets for session in week.sessions for exercise in session.exercises)


# ----------------------------------------------------------------- one load step
def step_up(context: AdaptationContext, planned: PlannedExercise) -> tuple[int, int, float]:
    """One load step up as (sets delta, reps delta, load factor); (0, 0, 1.0) means nothing."""
    exercise = context.by_id(planned.exercise_id)
    if planned.load_type == "kg":
        factor = BIG_LOAD_STEP if (exercise.is_compound
                                   and exercise.movement_pattern in MAJOR_PATTERNS
                                   and not context.profile.minor) else SMALL_LOAD_STEP
        if rounded(planned.load * factor, "kg") > planned.load:
            return 0, 0, factor
        if planned.reps < exercise.default_rep_range[1]:
            return 0, 1, 1.0
        return 0, 0, 1.0
    if planned.load_type == "bw":
        if planned.reps < exercise.default_rep_range[1]:
            return 0, 1, 1.0
        return 1, 0, 1.0
    return 0, 0, TIME_STEP_UP


def step_down(planned: PlannedExercise) -> tuple[int, int, float]:
    """One load step down as (sets delta, reps delta, load factor)."""
    if planned.load_type == "bw":
        return (0, -REP_STEP_DOWN, 1.0) if planned.reps > MIN_REPS else (0, 0, 1.0)
    return 0, 0, LOAD_STEP_DOWN if planned.load_type == "kg" else TIME_STEP_DOWN


def may_increase(context: AdaptationContext, planned: PlannedExercise, adds_set: bool) -> bool:
    """The guardrails of FUNCTIONAL_FLOW.md §6.4: may this exercise go up?"""
    if context.no_increase or not context.feedback.all_sets_done or context.week is None:
        return False
    exercise = context.by_id(planned.exercise_id)
    held_until = context.plan.held_patterns.get(exercise.movement_pattern, 0)
    if held_until >= context.week.number:
        return False
    if context.plan.last_increase_week.get(planned.exercise_id, 0) >= context.week.number:
        return False
    if adds_set and context.strategy is not None:
        _, maximum = context.strategy.weekly_set_limits(context.profile)
        if weekly_sets(context.week) >= maximum:
            return False
    return True


def may_decrease(context: AdaptationContext, loses_set: bool) -> bool:
    """A decrease never goes below the strategy's weekly minimum (§6.4)."""
    if not loses_set or context.strategy is None or context.week is None:
        return True
    minimum, _ = context.strategy.weekly_set_limits(context.profile)
    return weekly_sets(context.week) > minimum


# ----------------------------------------------------------------------- filters
class SafetyFilter(AdaptationFilter):
    """Precedence 1: pain. Swap the offending exercises, lower the load, hold the pattern."""

    def process(self, context: AdaptationContext) -> AdaptationContext:
        """Handle pain, or pass the context on unchanged."""
        if not context.feedback.pain:
            return context
        if context.session is None or context.week is None:
            raise AdaptationError("the feedback has no session in this plan")
        region = context.feedback.pain_region
        context.classification = SAFETY
        context.no_increase = True
        context.see_professional = True
        context.say(SEE_PROFESSIONAL)
        offending = [planned for planned in context.exercises
                     if region in context.by_id(planned.exercise_id).contraindicated_regions]
        if not offending:
            context.say(f"Nothing in that session is known to affect the {region}, "
                        "so the whole session gets one load step less.")
            for planned in context.exercises:
                self._lower(context, planned)
            return context
        until_week = context.week.number + 1
        for planned in offending:
            entry = context.by_id(planned.exercise_id)
            replacement = self._replacement(context, entry, region)
            if replacement is None:
                context.commands.append(RemoveExerciseCommand(
                    f"no safe alternative for {entry.name}", planned.exercise_id,
                    hold_pattern=entry.movement_pattern, until_week=until_week))
                context.say(f"{entry.name} is removed from the remaining sessions: no exercise "
                            "in your pool trains the same movement safely.")
                continue
            context.commands.append(SwapExerciseCommand(
                f"{entry.name} hurts the {region}", planned.exercise_id, replacement.id,
                replacement.load_type, self.reps_for(replacement, planned),
                self.restart_load(context, planned, replacement),
                hold_pattern=entry.movement_pattern, until_week=until_week))
            context.say(f"{entry.name} is replaced by {replacement.name}, starting at 70 % of "
                        "the old load.")
        return context

    @staticmethod
    def _replacement(context: AdaptationContext, entry: Exercise,
                     region: str | None) -> Exercise | None:
        """The first exercise of the pool that trains the same movement safely."""
        used = {planned.exercise_id for planned in context.exercises}
        for candidate in context.pool:
            if (candidate.movement_pattern == entry.movement_pattern
                    and candidate.id not in used
                    and region not in candidate.contraindicated_regions):
                return candidate
        return None

    @staticmethod
    def reps_for(replacement: Exercise, planned: PlannedExercise) -> int:
        """The bottom of the replacement's rep range, or the reps it replaces."""
        if replacement.load_type == "kg":
            return planned.reps
        return max(1, replacement.default_rep_range[0])

    @staticmethod
    def restart_load(context: AdaptationContext, planned: PlannedExercise,
                      replacement: Exercise) -> float:
        """70 % of the old load for weights; a timed replacement starts at the Strategy's time."""
        if replacement.load_type == "kg":
            return rounded(planned.load * RESTART_LOAD, "kg")
        if replacement.load_type == "time":
            if context.strategy is not None:
                return float(context.strategy.prescribe(replacement, context.profile).load)
            return rounded(planned.load * RESTART_LOAD, "time")
        return 0.0

    def _lower(self, context: AdaptationContext, planned: PlannedExercise) -> None:
        """One load step down, if the guardrails allow it."""
        sets_delta, reps_delta, factor = step_down(planned)
        context.commands.append(AdjustVolumeCommand(
            "pain: one load step less", planned.exercise_id, sets_delta, reps_delta, factor,
            week=0 if context.week is None else context.week.number))


class ScheduleFilter(AdaptationFilter):
    """Missed sessions: move them to a free day, or drop them if the week is full."""

    def process(self, context: AdaptationContext) -> AdaptationContext:
        """Reschedule the missed sessions of the current week, if there are any."""
        missed = context.feedback.missed_sessions
        if missed <= 0:
            return context
        if context.session is None or context.week is None:
            raise AdaptationError("the feedback has no session in this plan")
        week, logged_day = context.week, context.session.day_of_week
        skipped = [session for session in week.sessions
                   if session.status == "planned" and session.day_of_week < logged_day]
        for session in skipped[-missed:]:
            free_day = self._free_day(week, logged_day)
            if free_day is None:
                context.commands.append(RescheduleCommand(
                    "no free day left this week", week.number, session.day_of_week,
                    status="dropped"))
                context.no_increase = True
                context.say(f"The session of day {session.day_of_week} is dropped: the week "
                            "has no free day left for it.")
            else:
                context.commands.append(RescheduleCommand(
                    "missed session moved", week.number, session.day_of_week,
                    new_day=free_day, status="planned"))
                context.say(f"The missed session of day {session.day_of_week} is moved to "
                            f"day {free_day}.")
        return context

    @staticmethod
    def _free_day(week: Week, after_day: int) -> int | None:
        """The next free day of the week, if one can be added without losing the rest day."""
        used = {session.day_of_week for session in week.sessions}
        for day in range(after_day + 1, 8):
            if day not in used and len(used) + 1 <= 6:
                return day
        return None


class LoadFilter(AdaptationFilter):
    """Precedence 2-6: how hard the session felt. The only filter that increases load."""

    def process(self, context: AdaptationContext) -> AdaptationContext:
        """Classify the feedback and emit the Commands of the rule that won."""
        if context.feedback.pain:
            context.classification = SAFETY
            return context
        if context.session is None or context.week is None:
            raise AdaptationError("the feedback has no session in this plan")
        classification = classify(context.feedback, context.previous_feedback)
        context.classification = classification
        if classification == ON_TARGET:
            return context
        if classification == INCOMPLETE_LOW:
            context.say(HINT_INCOMPLETE)
            return context
        if classification == TOO_EASY:
            self._raise_load(context)
            return context
        if classification == TOO_HARD_SEVERE:
            for planned in context.exercises:
                self._lower_or_step(context, planned, "deload")
            context.say("That was too much: the whole session is deloaded by one set.")
            return context
        hardest = self._hardest(context)
        if hardest is not None:
            self._lower_or_step(context, hardest, "too hard")
            context.say(f"{context.by_id(hardest.exercise_id).name} was the hardest exercise: "
                        "it loses a set.")
        return context

    def _raise_load(self, context: AdaptationContext) -> None:
        """Too easy: one load step up for every exercise of the session."""
        for planned in context.exercises:
            sets_delta, reps_delta, factor = step_up(context, planned)
            if (sets_delta, reps_delta, factor) == (0, 0, 1.0):
                continue
            if not may_increase(context, planned, adds_set=sets_delta > 0):
                context.say(f"{context.by_id(planned.exercise_id).name} stays where it is: "
                            "only one increase per week, and never after pain or an "
                            "unfinished session.")
                continue
            context.commands.append(AdjustVolumeCommand(
                "too easy: one load step up", planned.exercise_id, sets_delta, reps_delta,
                factor, increase=True,
                week=0 if context.week is None else context.week.number))

    def _lower_or_step(self, context: AdaptationContext, planned: PlannedExercise,
                       reason: str) -> None:
        """One set less, or - at the minimum - one load step less."""
        if planned.sets > MIN_SETS and may_decrease(context, loses_set=True):
            context.commands.append(AdjustVolumeCommand(
                f"{reason}: one set less", planned.exercise_id, sets_delta=-1,
                week=0 if context.week is None else context.week.number))
            return
        sets_delta, reps_delta, factor = step_down(planned)
        context.commands.append(AdjustVolumeCommand(
            f"{reason}: one load step less", planned.exercise_id, sets_delta, reps_delta,
            factor, week=0 if context.week is None else context.week.number))

    @staticmethod
    def _hardest(context: AdaptationContext) -> PlannedExercise | None:
        """The exercise with the highest volume (sets x reps); ties go to the first one."""
        exercises = context.exercises
        if not exercises:
            return None
        return max(exercises, key=lambda planned: (planned.sets * planned.reps,
                                                   -exercises.index(planned)))


def classify(feedback: Feedback, previous: Feedback | None) -> Classification:
    """The classification of FUNCTIONAL_FLOW.md §6.2: the first matching row wins."""
    if feedback.rpe >= 9 or (feedback.rpe >= 8 and previous is not None and previous.rpe >= 8):
        return TOO_HARD_SEVERE
    if feedback.rpe == 8:
        return TOO_HARD
    if not feedback.all_sets_done:
        return TOO_HARD if feedback.rpe >= 7 else INCOMPLETE_LOW
    if feedback.rpe >= 5:
        return ON_TARGET
    return TOO_EASY
