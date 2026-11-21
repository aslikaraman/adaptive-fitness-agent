"""Planning Strategies, created by a Factory Method.

A PlanningStrategy holds the rules of one goal (FUNCTIONAL_FLOW.md §4.2): the session days,
the prompt constraints, the training numbers for each exercise, the weekly set limits, the
deterministic fallback week and the progression for weeks 2-4.

`SplitStrategy` implements what all three goals share (the split, the constraints text, the
fallback week and the progression) as a Template Method: each concrete strategy only supplies
the tables and the numbers of its goal. The LLM never sees these numbers - it only chooses
exercises, and the Strategy prescribes sets, reps, load and rest for them.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from fitness_agent.domain.models import Exercise, UserProfile
from fitness_agent.domain.plan import PlannedExercise

MAX_WEEKS = 4
REST_DAYS_PER_WEEK = 1
MAX_SESSIONS_PER_WEEK = 7 - REST_DAYS_PER_WEEK
MINOR_MAX_SESSIONS = 4

# which equipment makes an exercise the "biggest" version of a movement pattern; the
# fallback prefers it so a user with a barbell does not get bodyweight push-ups
EQUIPMENT_WEIGHT = {"barbell": 6, "dumbbells": 5, "kettlebell": 4, "machines": 3,
                    "pullup_bar": 2, "bands": 1, "bodyweight": 0}


def _weight(exercise: Exercise) -> int:
    """How heavy the heaviest equipment of an exercise is."""
    return max(EQUIPMENT_WEIGHT[item] for item in exercise.required_equipment)


def _round_to(value: float, step: float) -> float:
    """Round value to the nearest multiple of step."""
    return round(value / step) * step


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


class SplitStrategy(PlanningStrategy):
    """The shared behaviour of the three goal strategies (Template Method).

    A subclass supplies the goal's tables and numbers: the SPLIT (available days -> sessions),
    FOCUS_PATTERNS (the movement patterns of one focus, compounds first), the set/rep/rest
    numbers, the start loads, the weekly limits and, if the goal deviates from the default
    progression, one of the hooks _week_two(), _week_three() or _deload().
    """

    GOAL: str = ""
    EXERCISES_PER_SESSION: int = 4

    # available days per week -> ((day of week, focus), ...)
    SPLITS: dict[int, tuple[tuple[int, str], ...]] = {}
    # focus -> the movement patterns it wants, in this order
    FOCUS_PATTERNS: dict[str, tuple[str, ...]] = {}

    # (sets, reps, rest_s) for compound and for isolation exercises
    COMPOUND: tuple[int, int, int] = (3, 5, 180)
    ISOLATION: tuple[int, int, int] = (3, 10, 90)
    # seconds per timed exercise for (level, "cardio" or "short"): a cardio exercise is one
    # long bout, anything else (plank, carry, wall sit) is a few short ones
    TIMED_SECONDS: dict[tuple[str, str], int] = {}
    # start load in kg for (level, compound exercise)
    START_LOAD: dict[tuple[str, bool], float] = {}

    # progression: the most reps a set may reach, the load step of week 3 and the deload of week 4
    REP_CEILING: int = 8
    LOAD_STEP: float = 0.025
    DELOAD_SETS: int = 1
    DELOAD_LOAD: float = 0.9
    MIN_SETS: int = 2
    # a minor trains with less weight (FUNCTIONAL_FLOW.md §3)
    MINOR_LOAD: float = 0.75
    MINOR_SETS: int = 3

    # ------------------------------------------------------------------ the split
    def _sessions(self, profile: UserProfile) -> tuple[tuple[int, str], ...]:
        """The (day, focus) pairs for the profile's days, at most 6 so one rest day is left
        (a minor trains at most 4 days, FUNCTIONAL_FLOW.md §3)."""
        days = min(profile.days_per_week, MAX_SESSIONS_PER_WEEK)
        if profile.minor:
            days = min(days, MINOR_MAX_SESSIONS)
        return self.SPLITS[days]

    def session_days(self, profile: UserProfile) -> list[int]:
        """The days of the week that get a session (FUNCTIONAL_FLOW.md §4.2)."""
        return [day for day, _ in self._sessions(profile)]

    def constraints(self, profile: UserProfile) -> str:
        """The skeleton as prompt text, including the limits the Builder will check."""
        sessions = self._sessions(profile)
        low, high = self.weekly_set_limits(profile)
        lines = [f"Plan week 1 with exactly {len(sessions)} sessions:",
                 f"- {self.EXERCISES_PER_SESSION} exercises per session",
                 f"- between {low} and {high} sets in the whole week",
                 "- compound exercises before isolation exercises",
                 "- no exercise twice in the same session"]
        for day, focus in sessions:
            patterns = ", ".join(self.FOCUS_PATTERNS[focus])
            lines.append(f'- day {day}, focus "{focus}": movement patterns in this '
                         f'order: {patterns}')
        return "\n".join(lines)

    # -------------------------------------------------------------- the numbers
    def prescribe(self, exercise: Exercise, profile: UserProfile) -> Prescription:
        """Sets, reps, load and rest for one exercise in week 1.

        The app does not know the user's strength, so a loaded exercise starts at a
        conservative estimate for the level; the adaptation rules move it from there.
        """
        if exercise.load_type == "time":
            return Prescription(sets=self._timed_sets(exercise), reps=1,
                                load=self._timed_seconds(exercise, profile),
                                rest_s=self.ISOLATION[2])
        sets, reps, rest_s = self.COMPOUND if exercise.is_compound else self.ISOLATION
        if profile.minor:
            sets = min(sets, self.MINOR_SETS)
        low, high = exercise.default_rep_range
        return Prescription(sets=sets, reps=min(max(reps, low), max(low, high)),
                            load=self._start_load(exercise, profile),
                            rest_s=self._rest(exercise, rest_s))

    @staticmethod
    def _timed_sets(exercise: Exercise) -> int:
        """A cardio exercise is one long bout, a plank or a carry is done in a few sets."""
        return 1 if exercise.movement_pattern == "cardio" else 3

    def _timed_seconds(self, exercise: Exercise, profile: UserProfile) -> int:
        """How long one timed set lasts: the level's cardio time, or a short hold."""
        kind = "cardio" if exercise.movement_pattern == "cardio" else "short"
        return self.TIMED_SECONDS[(profile.fitness_level, kind)]

    @staticmethod
    def _rest(exercise: Exercise, rest_s: int) -> int:
        """Bodyweight work rests like isolation work: the load cannot be heavy."""
        return rest_s if exercise.load_type == "kg" else min(rest_s, 90)

    def _start_load(self, exercise: Exercise, profile: UserProfile) -> float:
        """0 for bodyweight, otherwise the level's start load (less for a minor)."""
        if exercise.load_type == "bw":
            return 0.0
        load = self.START_LOAD[(profile.fitness_level, exercise.is_compound)]
        if profile.minor:
            load *= self.MINOR_LOAD
        return _round_to(load, 0.5)

    def weekly_set_limits(self, profile: UserProfile) -> tuple[int, int]:
        """(min, max) sets per week.

        The minimum is deliberately low (two sets per session) so that the deterministic
        fallback still passes for a heavily restricted profile with a small allowed pool;
        the maximum leaves room for the one extra set that week 3 may add.
        """
        sessions = len(self._sessions(profile))
        return sessions * self.MIN_SETS, sessions * self.EXERCISES_PER_SESSION * self.set_ceiling

    @property
    def set_ceiling(self) -> int:
        """The most sets one exercise may have: the plan's sets plus the one week 3 adds."""
        return max(self.COMPOUND[0], self.ISOLATION[0]) + 1

    # ------------------------------------------------------- week 1 without the LLM
    def add_fallback_week(self, builder, profile: UserProfile, pool: list[Exercise]) -> None:
        """Build week 1 with fixed selection rules: the focus's patterns, compounds first."""
        builder.start_week(1)
        for day, focus in self._sessions(profile):
            builder.add_session(day, focus)
            for exercise in self._select(pool, focus):
                numbers = self.prescribe(exercise, profile)
                builder.add_exercise(exercise.id, numbers.sets, numbers.reps, numbers.load,
                                     numbers.rest_s)

    def _select(self, pool: list[Exercise], focus: str) -> list[Exercise]:
        """The exercises of one session: the focus's patterns first, then whatever is allowed."""
        chosen: list[Exercise] = []
        for pattern in self.FOCUS_PATTERNS[focus]:
            if len(chosen) == self.EXERCISES_PER_SESSION:
                break
            wanted = sorted(
                (exercise for exercise in pool
                 if exercise.movement_pattern == pattern and exercise not in chosen),
                key=lambda item: (-_weight(item), item.id))
            if wanted:
                chosen.append(wanted[0])
        for exercise in sorted(pool, key=lambda item: (not item.is_compound, -_weight(item),
                                                       item.id)):
            if len(chosen) == self.EXERCISES_PER_SESSION:
                break
            if exercise not in chosen:
                chosen.append(exercise)
        # a stable sort keeps the pattern order and puts the compounds first
        return sorted(chosen, key=lambda item: not item.is_compound)

    # ------------------------------------------------------------ weeks 2, 3 and 4
    def add_progression_weeks(self, builder, profile: UserProfile) -> None:
        """Add weeks 2-4: the sessions of week 1 with the goal's progression rule applied."""
        week_one = builder.weeks[-1]
        for number in range(2, MAX_WEEKS + 1):
            builder.start_week(number)
            for session in week_one.sessions:
                builder.add_session(session.day_of_week, session.focus)
                for exercise in session.exercises:
                    sets, reps, load, rest_s = self._progress(exercise, number, profile)
                    builder.add_exercise(exercise.exercise_id, sets, reps, load, rest_s)

    def _progress(self, exercise: PlannedExercise, week: int, profile: UserProfile):
        """The numbers of one exercise in week 2, 3 or 4 (the goal's progression rule)."""
        if week == 2:
            return self._week_two(exercise, profile)
        if week == 3:
            return self._week_three(exercise, profile)
        return self._deload(exercise, profile)

    def _more_reps(self, exercise: PlannedExercise) -> int:
        """One rep more per set - but never fewer than now, and never above the ceiling."""
        return exercise.reps + 1 if exercise.reps < self.REP_CEILING else exercise.reps

    def _week_two(self, exercise: PlannedExercise, profile: UserProfile):
        """Week 2: one rep more per set; a timed exercise runs 10 % longer."""
        del profile
        if exercise.load_type == "time":
            return exercise.sets, exercise.reps, _round_to(exercise.load * 1.1, 5), exercise.rest_s
        return exercise.sets, self._more_reps(exercise), exercise.load, exercise.rest_s

    def _week_three(self, exercise: PlannedExercise, profile: UserProfile):
        """Week 3: one rep more, or - at the ceiling - more load or one set more."""
        del profile
        if exercise.load_type == "time":
            return exercise.sets, exercise.reps, _round_to(exercise.load * 1.2, 5), exercise.rest_s
        if exercise.reps < self.REP_CEILING:
            return exercise.sets, exercise.reps + 1, exercise.load, exercise.rest_s
        if exercise.load_type == "kg":
            return exercise.sets, exercise.reps, \
                _round_to(exercise.load * (1 + self.LOAD_STEP), 0.5), exercise.rest_s
        return min(exercise.sets + 1, self.set_ceiling), exercise.reps, exercise.load, \
            exercise.rest_s

    def _deload(self, exercise: PlannedExercise, profile: UserProfile):
        """Week 4: one set less and 10 % less load, so the body recovers before the next cycle."""
        del profile
        sets = min(exercise.sets, max(self.MIN_SETS, exercise.sets - self.DELOAD_SETS))
        if exercise.load_type in ("kg", "time"):
            load = _round_to(exercise.load * self.DELOAD_LOAD, 0.5)
        else:
            load = exercise.load
        return sets, exercise.reps, load, exercise.rest_s


class StrengthStrategy(SplitStrategy):
    """Strength: few reps, long rest, the load goes up from week to week."""

    GOAL = "strength"
    EXERCISES_PER_SESSION = 4
    SPLITS = {
        1: ((3, "full body"),),
        2: ((1, "full body A"), (4, "full body B")),
        3: ((1, "push"), (3, "pull"), (5, "legs")),
        4: ((1, "upper"), (2, "lower"), (4, "upper"), (5, "lower")),
        5: ((1, "push"), (2, "pull"), (3, "legs"), (5, "upper"), (6, "lower")),
        6: ((1, "push"), (2, "pull"), (3, "legs"), (4, "push"), (5, "pull"), (6, "legs")),
    }
    FOCUS_PATTERNS = {
        "full body": ("squat", "push", "pull", "core"),
        "full body A": ("squat", "push", "pull", "core"),
        "full body B": ("hinge", "push", "pull", "core"),
        "push": ("push", "push", "core", "core"),
        "pull": ("pull", "pull", "hinge", "core"),
        "legs": ("squat", "hinge", "core", "core"),
        "upper": ("push", "pull", "push", "core"),
        "lower": ("squat", "hinge", "core", "core"),
    }
    COMPOUND = (3, 5, 180)
    ISOLATION = (3, 10, 90)
    REP_CEILING = 8
    TIMED_SECONDS = {
        ("beginner", "cardio"): 300, ("intermediate", "cardio"): 420, ("advanced", "cardio"): 600,
        ("beginner", "short"): 30, ("intermediate", "short"): 45, ("advanced", "short"): 60,
    }
    START_LOAD = {
        ("beginner", True): 20.0, ("beginner", False): 6.0,
        ("intermediate", True): 40.0, ("intermediate", False): 12.0,
        ("advanced", True): 60.0, ("advanced", False): 20.0,
    }


class EnduranceStrategy(SplitStrategy):
    """Endurance: the sessions get longer week by week, with short rests between sets."""

    GOAL = "endurance"
    EXERCISES_PER_SESSION = 3
    SPLITS = {
        1: ((3, "endurance"),),
        2: ((2, "intervals"), (5, "long session")),
        3: ((1, "intervals"), (3, "easy session"), (6, "long session")),
        4: ((1, "intervals"), (2, "easy session"), (4, "tempo"), (6, "long session")),
        5: ((1, "intervals"), (2, "easy session"), (3, "tempo"), (5, "strength"),
            (6, "long session")),
        6: ((1, "intervals"), (2, "easy session"), (3, "tempo"), (4, "strength"),
            (5, "intervals"), (6, "long session")),
    }
    FOCUS_PATTERNS = {
        "endurance": ("cardio", "cardio", "core", "core"),
        "intervals": ("cardio", "cardio", "core", "core"),
        "easy session": ("cardio", "cardio", "core", "carry"),
        "tempo": ("cardio", "cardio", "carry", "core"),
        "long session": ("cardio", "cardio", "core", "core"),
        "strength": ("squat", "hinge", "push", "pull"),
    }
    COMPOUND = (3, 15, 45)
    ISOLATION = (3, 12, 45)
    REP_CEILING = 20
    TIMED_SECONDS = {
        ("beginner", "cardio"): 600, ("intermediate", "cardio"): 900, ("advanced", "cardio"): 1200,
        ("beginner", "short"): 45, ("intermediate", "short"): 60, ("advanced", "short"): 90,
    }
    START_LOAD = {
        ("beginner", True): 10.0, ("beginner", False): 4.0,
        ("intermediate", True): 15.0, ("intermediate", False): 6.0,
        ("advanced", True): 20.0, ("advanced", False): 8.0,
    }

    def _week_two(self, exercise: PlannedExercise, profile: UserProfile):
        """Week 2: the sessions run 10 % longer, or one rep more per set."""
        del profile
        if exercise.load_type == "time":
            return exercise.sets, exercise.reps, _round_to(exercise.load * 1.1, 5), exercise.rest_s
        return exercise.sets, self._more_reps(exercise), exercise.load, exercise.rest_s

    def _week_three(self, exercise: PlannedExercise, profile: UserProfile):
        """Week 3: another 20 % longer than week 1, or one set more of the strength work."""
        del profile
        if exercise.load_type == "time":
            return exercise.sets, exercise.reps, _round_to(exercise.load * 1.2, 5), exercise.rest_s
        return min(exercise.sets + 1, self.set_ceiling), exercise.reps, exercise.load, \
            exercise.rest_s


class FatLossStrategy(SplitStrategy):
    """Fat loss: high reps, short rests, and the rests keep getting shorter."""

    GOAL = "fat_loss"
    EXERCISES_PER_SESSION = 4
    SPLITS = {
        1: ((3, "full body circuit"),),
        2: ((1, "circuit A"), (4, "circuit B")),
        3: ((1, "circuit A"), (3, "circuit B"), (5, "cardio and core")),
        4: ((1, "circuit A"), (2, "circuit B"), (4, "cardio and core"), (5, "circuit A")),
        5: ((1, "circuit A"), (2, "circuit B"), (3, "cardio and core"), (5, "circuit A"),
            (6, "circuit B")),
        6: ((1, "circuit A"), (2, "circuit B"), (3, "cardio and core"), (4, "circuit A"),
            (5, "circuit B"), (6, "cardio and core")),
    }
    FOCUS_PATTERNS = {
        "full body circuit": ("squat", "push", "pull", "cardio"),
        "circuit A": ("squat", "push", "pull", "cardio"),
        "circuit B": ("hinge", "push", "pull", "cardio"),
        "cardio and core": ("cardio", "core", "cardio", "core"),
    }
    COMPOUND = (3, 12, 45)
    ISOLATION = (3, 15, 30)
    REP_CEILING = 15
    SHORTER_REST_S = 5
    MIN_REST_S = 30
    TIMED_SECONDS = {
        ("beginner", "cardio"): 600, ("intermediate", "cardio"): 900, ("advanced", "cardio"): 1200,
        ("beginner", "short"): 30, ("intermediate", "short"): 45, ("advanced", "short"): 60,
    }
    START_LOAD = {
        ("beginner", True): 12.5, ("beginner", False): 4.0,
        ("intermediate", True): 25.0, ("intermediate", False): 7.5,
        ("advanced", True): 40.0, ("advanced", False): 12.5,
    }

    def _week_two(self, exercise: PlannedExercise, profile: UserProfile):
        """Week 2: the rests get shorter, so the same work is done in less time."""
        del profile
        return exercise.sets, exercise.reps, exercise.load, \
            max(self.MIN_REST_S, exercise.rest_s - self.SHORTER_REST_S)

    def _week_three(self, exercise: PlannedExercise, profile: UserProfile):
        """Week 3: one rep more per set, or one set more at the ceiling."""
        del profile
        if exercise.load_type == "time":
            return exercise.sets, exercise.reps, _round_to(exercise.load * 1.2, 5), exercise.rest_s
        if exercise.reps < self.REP_CEILING:
            return exercise.sets, exercise.reps + 1, exercise.load, exercise.rest_s
        return min(exercise.sets + 1, self.set_ceiling), exercise.reps, exercise.load, \
            exercise.rest_s


class StrategyFactory:
    """Factory Method (lecture: "some means - method or own class - to create the actual
    object somewhere else"): returns the Strategy for the profile's goal.

    It is the one place that knows which concrete Strategy belongs to which goal, so a new
    goal is a new Strategy class plus one line here (PATTERNS.md: "Factory Method").
    """

    STRATEGIES: dict[str, type[SplitStrategy]] = {
        "strength": StrengthStrategy,
        "fat_loss": FatLossStrategy,
        "endurance": EnduranceStrategy,
    }

    def create(self, profile: UserProfile) -> PlanningStrategy:
        """Return the Strategy for profile.goal."""
        strategy = self.STRATEGIES.get(profile.goal)
        if strategy is None:
            raise ValueError(f"no planning strategy for goal {profile.goal!r}")
        return strategy()
