"""Tests for TrainingPlanBuilder (validation gate) and the plan Commands."""

import pytest

from fitness_agent.domain.builder import PlanValidationError, TrainingPlanBuilder
from fitness_agent.domain.commands import (AdjustVolumeCommand, RemoveExerciseCommand,
                                           RescheduleCommand, SwapExerciseCommand)
from fitness_agent.domain.models import UserProfile
from fitness_agent.domain.plan import PlannedExercise, Session, TrainingPlan, Week
from fitness_agent.infrastructure.json_catalog_loader import JsonCatalogLoader
from tests.fakes import FakeStrategy

CATALOG = JsonCatalogLoader().load()
PROFILE = UserProfile(age=30, fitness_level="intermediate", goal="strength", days_per_week=3,
                      equipment=["dumbbells"])
POOL = [e for e in CATALOG if e.id in ("goblet_squat", "db_row", "dead_bug", "push_up")]


def builder() -> TrainingPlanBuilder:
    """A builder with one week and one session started."""
    result = TrainingPlanBuilder(CATALOG, POOL, FakeStrategy(), PROFILE)
    result.start_week(1)
    result.add_session(1, "full body")
    return result


def test_valid_plan_is_built_with_load_types_from_the_catalog():
    """A plan that keeps every rule is returned; the load type comes from the catalog."""
    b = builder()
    b.add_exercise("goblet_squat", 3, 10, 20, 90)
    b.add_exercise("dead_bug", 3, 10, 0, 60)
    plan = b.build()
    assert [e.load_type for e in plan.weeks[0].sessions[0].exercises] == ["kg", "bw"]


@pytest.mark.parametrize("ids, message", [
    (["back_squat"], "not allowed"),                 # needs a barbell
    (["goblet_squat", "goblet_squat"], "twice"),
    (["dead_bug", "goblet_squat"], "isolation exercise comes before"),
])
def test_build_rejects_a_broken_rule(ids, message):
    """Allowed pool, duplicates and compounds first are checked in build()."""
    b = builder()
    for exercise_id in ids:
        b.add_exercise(exercise_id, 3, 10, 20, 90)
    with pytest.raises(PlanValidationError, match=message):
        b.build()


def test_unknown_id_and_missing_steps_are_rejected():
    """Unknown ids and steps in the wrong order fail at once."""
    with pytest.raises(PlanValidationError, match="unknown exercise id"):
        builder().add_exercise("moon_walk", 3, 10, 0, 60)
    fresh = TrainingPlanBuilder(CATALOG, POOL, FakeStrategy(), PROFILE)
    with pytest.raises(PlanValidationError):
        fresh.add_session(1, "x")
    with pytest.raises(PlanValidationError, match="no week"):
        fresh.build()


def test_too_many_sessions_and_too_many_sets_are_rejected():
    """At least one rest day, and the weekly sets within the Strategy's limits."""
    b = builder()
    b.add_exercise("goblet_squat", 3, 10, 20, 90)
    for day in (2, 3, 4):
        b.add_session(day, "extra")
        b.add_exercise("goblet_squat", 3, 10, 20, 90)
    with pytest.raises(PlanValidationError, match="at most 3"):
        b.build()
    heavy = builder()
    heavy.add_exercise("goblet_squat", 41, 10, 20, 90)
    with pytest.raises(PlanValidationError, match="between 1 and 40"):
        heavy.build()


# --------------------------------------------------------------------------- Commands
def make_plan() -> TrainingPlan:
    """Two weeks with the same session; week 1 is done."""
    def session(status):
        """One session with a squat and a push-up."""
        return Session(day_of_week=1, focus="a", status=status, exercises=[
            PlannedExercise(exercise_id="goblet_squat", load_type="kg", sets=3, reps=10,
                            load=20, rest_s=90),
            PlannedExercise(exercise_id="push_up", load_type="bw", sets=2, reps=12, load=0,
                            rest_s=60)])
    return TrainingPlan(weeks=[Week(number=1, sessions=[session("done")]),
                               Week(number=2, sessions=[session("planned")])])


def test_adjust_changes_only_remaining_sessions_and_records_the_increase():
    """Done sessions stay; an increase records the week."""
    p = make_plan()
    AdjustVolumeCommand("easy", "goblet_squat", factor=1.05, increase=True, week=1).execute(p)
    assert p.weeks[0].sessions[0].exercises[0].load == 20
    assert p.weeks[1].sessions[0].exercises[0].load == 21
    assert p.last_increase_week == {"goblet_squat": 1}


def test_a_set_decrease_never_goes_below_two_sets():
    """push_up has 2 sets: one set less keeps it at 2."""
    p = make_plan()
    AdjustVolumeCommand("hard", "push_up", sets_delta=-1).execute(p)
    assert p.weeks[1].sessions[0].exercises[1].sets == 2


def test_swap_remove_and_reschedule_with_undo():
    """Each Command changes the plan and undo() brings it back exactly."""
    p = make_plan()
    before = p.model_dump()
    commands = [SwapExerciseCommand("knee", "goblet_squat", "wall_sit", "time", 1, 30,
                                    hold_pattern="squat", until_week=2),
                RemoveExerciseCommand("wrist", "push_up", hold_pattern="push", until_week=2),
                RescheduleCommand("moved", 2, 1, new_day=3)]
    for command in commands:
        command.execute(p)
    session = p.weeks[1].sessions[0]
    assert [e.exercise_id for e in session.exercises] == ["wall_sit"]
    assert session.day_of_week == 3 and p.held_patterns == {"squat": 2, "push": 2}
    for command in reversed(commands):
        command.undo()
    assert p.model_dump() == before


def test_reschedule_of_a_missing_session_is_an_error():
    """The service turns this into "the plan could not be adapted"."""
    with pytest.raises(ValueError):
        RescheduleCommand("x", 2, 5).execute(make_plan())


def test_a_kg_replacement_starts_at_70_percent_of_the_old_load():
    """Pain swap (§6.3 rule 1): a kg replacement restarts at 70 % of the old load."""
    from fitness_agent.domain.adaptation import SafetyFilter  # pylint: disable=import-outside-toplevel
    by_id = {e.id: e for e in CATALOG}
    planned = PlannedExercise(exercise_id="romanian_deadlift", load_type="kg", sets=3, reps=10,
                              load=40, rest_s=90)
    assert SafetyFilter.restart_load(None, planned, by_id["hip_thrust"]) == 28.0
    assert SafetyFilter.reps_for(by_id["hip_thrust"], planned) == 10
    assert SafetyFilter.reps_for(by_id["glute_bridge"], planned) == 10  # bottom of its range
