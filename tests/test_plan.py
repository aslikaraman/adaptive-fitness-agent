"""Tests for the TrainingPlan Composite, its Memento and PlanCommand."""

import pytest

from fitness_agent.domain.commands import PlanCommand
from fitness_agent.domain.plan import PlannedExercise, Session, TrainingPlan, Week


def make_plan() -> TrainingPlan:
    """A one-week plan with one session of three exercises (kg, bodyweight, time)."""
    session = Session(day_of_week=1, focus="full body", exercises=[
        PlannedExercise(exercise_id="goblet_squat", load_type="kg", sets=3, reps=10, load=20,
                        rest_s=60),
        PlannedExercise(exercise_id="push_up", load_type="bw", sets=3, reps=12, load=0, rest_s=60),
        PlannedExercise(exercise_id="plank", load_type="time", sets=2, reps=1, load=30, rest_s=30),
    ])
    return TrainingPlan(weeks=[Week(number=1, sessions=[session])])


def test_volume_is_the_same_at_every_level():
    """total_volume() works on the leaf and is summed by every composite."""
    plan = make_plan()
    session = plan.weeks[0].sessions[0]
    assert session.exercises[0].total_volume() == 30
    assert session.total_volume() == 30 + 36 + 2
    assert plan.weeks[0].total_volume() == session.total_volume() == plan.total_volume()


def test_duration_uses_time_load_for_timed_exercises():
    """Timed exercises count their seconds; the others count reps x 3 s; rest is added per set."""
    exercises = make_plan().weeks[0].sessions[0].exercises
    assert exercises[0].duration() == 3 * (10 * 3 + 60)
    assert exercises[2].duration() == 2 * (30 + 30)


def test_scale_intensity_reaches_every_leaf():
    """One call on the plan scales every exercise, each by its own load type."""
    plan = make_plan()
    plan.scale_intensity(0.9)
    squat, push_up, plank = plan.weeks[0].sessions[0].exercises
    assert squat.load == 18.0
    assert push_up.reps == 11
    assert plank.load == 25


def test_scale_intensity_rejects_non_positive_factor():
    """A factor of 0 or less makes no sense."""
    with pytest.raises(ValueError):
        make_plan().scale_intensity(0)


def test_memento_restores_the_plan_in_place():
    """restore() brings back the exact state of create_memento()."""
    plan = make_plan()
    before = plan.model_dump()
    memento = plan.create_memento("test")
    plan.scale_intensity(2)
    plan.held_patterns["squat"] = 2
    plan.restore(memento)
    assert plan.model_dump() == before


class _DoubleLoad(PlanCommand):
    """Minimal concrete Command for the test."""

    def _apply(self, plan: TrainingPlan) -> None:
        """Double every load."""
        plan.scale_intensity(2)


def test_plan_command_execute_and_undo():
    """execute() stores a Memento before changing the plan; undo() restores it."""
    plan = make_plan()
    before = plan.model_dump()
    command = _DoubleLoad("too easy")
    command.execute(plan)
    assert plan.weeks[0].sessions[0].exercises[0].load == 40
    command.undo()
    assert plan.model_dump() == before


def test_undo_before_execute_is_an_error():
    """undo() without execute() has nothing to restore."""
    with pytest.raises(RuntimeError):
        _DoubleLoad("x").undo()
