"""Unit tests for the planning Strategies and the adaptation filters (one rule at a time)."""

import pytest

from fitness_agent.domain.adaptation import (INCOMPLETE_LOW, ON_TARGET, TOO_EASY, TOO_HARD,
                                             TOO_HARD_SEVERE, AdaptationContext, LoadFilter,
                                             SafetyFilter, ScheduleFilter, classify, find_session)
from fitness_agent.domain.catalog import allowed_pool
from fitness_agent.domain.commands import AdjustVolumeCommand, RescheduleCommand
from fitness_agent.domain.models import Feedback, UserProfile
from fitness_agent.domain.strategies import (EnduranceStrategy, FatLossStrategy, StrategyFactory,
                                             StrengthStrategy)
from fitness_agent.infrastructure.json_catalog_loader import JsonCatalogLoader
from tests.test_scenarios import STRENGTH, plan_for

CATALOG = JsonCatalogLoader().load()


def profile(goal="strength", days=3, age=30) -> UserProfile:
    """A dumbbell user with the given goal."""
    return UserProfile(age=age, fitness_level="intermediate", goal=goal, days_per_week=days,
                       equipment=["dumbbells"])


def numbers(plan, week):
    """(exercise, sets, reps, load, rest) of every exercise of one week, in order."""
    return [(e.exercise_id, e.sets, e.reps, e.load, e.rest_s, e.load_type)
            for s in plan.weeks[week - 1].sessions for e in s.exercises]


# ----------------------------------------------------------------------------- Strategies
@pytest.mark.parametrize("goal, strategy", [("strength", StrengthStrategy),
                                            ("fat_loss", FatLossStrategy),
                                            ("endurance", EnduranceStrategy)])
def test_the_factory_returns_the_strategy_of_the_goal(goal, strategy):
    """Simple Factory: one lookup from goal to Strategy."""
    assert isinstance(StrategyFactory().create(profile(goal)), strategy)


def test_the_factory_rejects_an_unknown_goal():
    """A goal without a Strategy is an error, not a silent default."""
    with pytest.raises(ValueError):
        StrategyFactory().create(UserProfile.model_construct(goal="yoga"))


@pytest.mark.parametrize("days, age, expected", [(7, 30, 6), (6, 16, 4), (2, 30, 2)])
def test_session_days_keep_a_rest_day_and_the_minor_cap(days, age, expected):
    """At most 6 sessions (one rest day); a minor at most 4; one session per day."""
    session_days = StrengthStrategy().session_days(profile(days=days, age=age))
    assert len(session_days) == expected == len(set(session_days))


def test_prescription_for_minors_and_timed_exercises():
    """A minor gets at most 3 sets and 75 % of the start load; cardio is one long bout."""
    by_id = {e.id: e for e in CATALOG}
    adult = StrengthStrategy().prescribe(by_id["goblet_squat"], profile())
    minor = StrengthStrategy().prescribe(by_id["goblet_squat"], profile(age=16))
    assert minor.sets <= 3 and minor.load == adult.load * 0.75
    assert StrengthStrategy().prescribe(by_id["brisk_walk"], profile()).sets == 1


def test_constraints_name_the_sessions_and_the_limits():
    """The prompt skeleton contains the session count and the weekly set limits."""
    text = StrengthStrategy().constraints(profile())
    low, high = StrengthStrategy().weekly_set_limits(profile())
    assert "exactly 3 sessions" in text and f"between {low} and {high} sets" in text


def test_the_fallback_week_uses_only_allowed_exercises_compounds_first():
    """The plan without the LLM keeps the safety filter and the compound-first rule."""
    plan = plan_for(STRENGTH)
    pool = {e.id for e in allowed_pool(CATALOG, STRENGTH)}
    compound = {e.id: e.is_compound for e in CATALOG}
    for session in plan.weeks[0].sessions:
        ids = [e.exercise_id for e in session.exercises]
        assert set(ids) <= pool
        assert [compound[i] for i in ids] == sorted((compound[i] for i in ids), reverse=True)


def test_each_goal_progresses_in_its_own_way():
    """The goals differ in behaviour: strength adds reps, fat loss shortens rests,
    endurance makes timed work longer (week 2 against week 1)."""
    strength = plan_for(profile("strength"))
    assert any(w2[2] > w1[2] for w1, w2 in zip(numbers(strength, 1), numbers(strength, 2))
               if w1[5] != "time")
    fat_loss = plan_for(profile("fat_loss"))
    assert all(w2[4] <= w1[4] for w1, w2 in zip(numbers(fat_loss, 1), numbers(fat_loss, 2)))
    assert any(w2[4] < w1[4] for w1, w2 in zip(numbers(fat_loss, 1), numbers(fat_loss, 2)))
    endurance = plan_for(profile("endurance"))
    assert all(w2[3] > w1[3] for w1, w2 in zip(numbers(endurance, 1), numbers(endurance, 2))
               if w1[5] == "time")


def test_week_four_is_a_deload():
    """Week 4 has fewer sets than week 3 (never below 2) and no more load."""
    plan = plan_for(STRENGTH)
    for w3, w4 in zip(numbers(plan, 3), numbers(plan, 4)):
        assert w4[1] <= w3[1] and w4[3] <= w3[3]
    assert plan.weeks[3].total_sets() < plan.weeks[2].total_sets()


# ------------------------------------------------------------------------------- filters
@pytest.mark.parametrize("rpe, all_sets, previous, expected", [
    (9, True, None, TOO_HARD_SEVERE),
    (8, True, 8, TOO_HARD_SEVERE),
    (8, True, None, TOO_HARD),
    (7, False, None, TOO_HARD),
    (6, False, None, INCOMPLETE_LOW),
    (6, True, None, ON_TARGET),
    (3, True, None, TOO_EASY),
])
def test_classification_table(rpe, all_sets, previous, expected):
    """FUNCTIONAL_FLOW.md §6.2, one row per case."""
    before = None if previous is None else Feedback(session_ref="w1d1", rpe=previous,
                                                    pain=False, all_sets_done=True)
    now = Feedback(session_ref="w1d3", rpe=rpe, pain=False, all_sets_done=all_sets)
    assert classify(now, before) == expected


def context(**feedback) -> AdaptationContext:
    """A context on the strength plan, positioned on the logged session (like the pipe does)."""
    plan = plan_for(STRENGTH)
    entry = Feedback(**{"session_ref": "w1d3", "rpe": 6, "pain": False, "all_sets_done": True,
                        **feedback})
    result = AdaptationContext(feedback=entry, plan=plan, profile=STRENGTH, catalog=CATALOG,
                               pool=allowed_pool(CATALOG, STRENGTH),
                               strategy=StrategyFactory().create(STRENGTH))
    result.week, result.session = find_session(plan, entry.session_ref)
    return result


def test_each_filter_passes_on_what_is_not_its_business():
    """No pain, no missed session, on target: no filter emits anything."""
    ctx = context()
    for step in (SafetyFilter(), ScheduleFilter(), LoadFilter()):
        ctx = step.process(ctx)
    assert ctx.commands == [] and not ctx.no_increase


def test_safety_filter_sets_the_flags_for_pain():
    """Pain: no increase anywhere this cycle, and the warning."""
    ctx = SafetyFilter().process(context(pain=True, pain_region="neck"))
    assert ctx.no_increase and ctx.see_professional and ctx.commands


def test_schedule_filter_moves_a_missed_session():
    """One missed session before the logged one: moved to a free later day."""
    ctx = ScheduleFilter().process(context(missed_sessions=1))
    assert [type(c) for c in ctx.commands] == [RescheduleCommand]
    assert ctx.commands[0].new_day == 4


def test_load_filter_respects_the_no_increase_flag_of_earlier_filters():
    """Too easy, but an earlier filter forbade increases: nothing goes up."""
    ctx = context(rpe=3)
    ctx.no_increase = True
    ctx = LoadFilter().process(ctx)
    assert not any(isinstance(c, AdjustVolumeCommand) and c.increase for c in ctx.commands)
