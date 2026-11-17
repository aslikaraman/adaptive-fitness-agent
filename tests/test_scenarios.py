"""Scenario tests: one row of the FUNCTIONAL_FLOW.md §12 table per test.

They run **end to end without a real LLM** (``FakeLLMClient``), on a plan the Strategy built
(the deterministic fallback of ``PlanService``), through the real pipeline and the real
``AdaptationService``: profile -> plan -> Feedback -> adapted plan. Where §12 names a number,
the test asserts that number; where it names a direction, the test compares the plan before
and after the cycle.

The two metrics of §12 are covered as well: the **adaptation safety rate** (pain never leads
to a load increase, `test_no_pain_scenario_ever_raises_a_load`) and the **guardrails**
(≤ +10 % load and ≤ +1 set per exercise per week, `test_no_scenario_breaks_the_guardrails`).
"""

import pytest

from fitness_agent.application.adaptation import NO_PLAN, AdaptationService
from fitness_agent.application.planning import PlanService
from fitness_agent.domain.adaptation import (AdaptationFilter, AdaptationPipeline, LoadFilter,
                                             SafetyFilter, ScheduleFilter)
from fitness_agent.domain.models import Feedback, UserProfile
from fitness_agent.domain.plan import TrainingPlan
from fitness_agent.domain.strategies import StrategyFactory
from fitness_agent.infrastructure.json_catalog_loader import JsonCatalogLoader
from tests.fakes import FakeLLMClient, InMemoryStorage

# the strength profile: 3 sessions per week (push / pull / legs), the legs day squats
STRENGTH = UserProfile(age=30, fitness_level="intermediate", goal="strength", days_per_week=3,
                       equipment=["barbell", "dumbbells", "bodyweight"])
# the fat-loss profile: day 5 is "cardio and core" and contains a knee-stressing burpee
CARDIO = UserProfile(age=30, fitness_level="intermediate", goal="fat_loss", days_per_week=3,
                     equipment=["dumbbells", "bodyweight"])
# six sessions a week: the only free day can no longer take a moved session
FULL_WEEK = UserProfile(age=30, fitness_level="intermediate", goal="strength", days_per_week=6,
                        equipment=["dumbbells", "bodyweight"])

WARNING = "see a doctor"


def plan_for(profile: UserProfile) -> TrainingPlan:
    """A plan the Strategy built (the LLM is down, so the deterministic fallback runs)."""
    return PlanService(FakeLLMClient(failures=99), JsonCatalogLoader(), InMemoryStorage(),
                       StrategyFactory()).generate(profile)


def adaptation(profile: UserProfile, plan: TrainingPlan, pipeline=None,
               llm=None) -> tuple[AdaptationService, InMemoryStorage]:
    """The real adaptation service, on a storage that already holds the profile and plan."""
    storage = InMemoryStorage(profile, plan)
    return AdaptationService(storage, JsonCatalogLoader(), pipeline=pipeline, llm=llm), storage


def cycle(service: AdaptationService, storage: InMemoryStorage, entry: Feedback) -> list[str]:
    """One feedback cycle: save the Feedback, then adapt, as the feedback state does."""
    storage.save_feedback(entry)
    return service.adapt(entry)


def feedback(session_ref: str = "w1d1", rpe: int = 6, **kwargs) -> Feedback:
    """A Feedback about one session."""
    options = {"pain": False, "all_sets_done": True, "missed_sessions": 0, **kwargs}
    return Feedback(session_ref=session_ref, rpe=rpe, **options)


def state(plan: TrainingPlan) -> dict:
    """Every (week, day, exercise) -> (sets, reps, load), so two plans can be diffed."""
    return {(week.number, session.day_of_week, item.exercise_id):
            (item.sets, item.reps, item.load)
            for week in plan.weeks for session in week.sessions for item in session.exercises}


def exercises_of(plan: TrainingPlan, week: int, day: int) -> list[str]:
    """The exercise ids of one session."""
    return [item.exercise_id for session in plan.weeks[week - 1].sessions
            if session.day_of_week == day for item in session.exercises]


def loads_of(plan: TrainingPlan, exercise_id: str) -> dict:
    """Every remaining occurrence of one exercise: (week, day) -> load."""
    return {(week.number, session.day_of_week): item.load
            for week in plan.weeks for session in week.sessions
            for item in session.exercises if item.exercise_id == exercise_id}


def snapshot(plan: TrainingPlan) -> dict:
    """A copy of the whole plan, to compare against after an undo."""
    return plan.model_dump()


# ------------------------------------------------------------------------- §12 row 1
def test_too_easy_raises_every_exercise_of_the_session():
    """RPE 3, all sets done, no pain: every exercise of the session +1 load step.

    The step lands on the **remaining** occurrences (§6.3): the session the user just did is
    marked done, so weeks 2-4 of that day change, and every exercise of the session is raised.
    """
    plan = plan_for(STRENGTH)
    service, storage = adaptation(STRENGTH, plan)
    before = state(plan)
    messages = cycle(service, storage, feedback("w1d1", rpe=3))
    after = state(plan)
    for key in [key for key in before if key[0] > 1 and key[1] == 1]:
        if before[key][2] > 0:                              # a loaded exercise: +2.5 or +5 %
            assert after[key][2] > before[key][2]
        else:                                               # bodyweight: +1 rep per set
            assert after[key][1] == before[key][1] + 1
    assert messages[-1].startswith("Changed:")


def test_the_load_step_is_five_percent_for_a_squat_and_two_and_a_half_for_the_rest():
    """§6.3: a compound squat/hinge goes up 5 %, every other exercise 2.5 %."""
    plan = plan_for(STRENGTH)
    service, storage = adaptation(STRENGTH, plan)
    squat = loads_of(plan, "back_squat")[(2, 5)]             # the legs day of week 2
    press = loads_of(plan, "barbell_bench_press")[(2, 1)]    # the push day of week 2
    cycle(service, storage, feedback("w1d5", rpe=3))
    cycle(service, storage, feedback("w1d1", rpe=3))
    assert loads_of(plan, "back_squat")[(2, 5)] == round(squat * 1.05 * 2) / 2
    assert loads_of(plan, "barbell_bench_press")[(2, 1)] == round(press * 1.025 * 2) / 2


# ------------------------------------------------------------------------- §12 row 2
def test_the_second_increase_in_the_same_week_is_skipped():
    """TOO_EASY twice in one week: the second increase is skipped (one increase per week).

    ``bird_dog`` is in all three sessions of the week, so the second cycle hits an exercise
    that was already raised this week.
    """
    plan = plan_for(STRENGTH)
    service, storage = adaptation(STRENGTH, plan)
    cycle(service, storage, feedback("w1d1", rpe=3))         # bird_dog: 10 -> 11 reps
    raised = state(plan)
    assert state(plan)[(2, 1, "bird_dog")][1] == raised[(2, 1, "bird_dog")][1]
    assert raised[(2, 1, "bird_dog")][1] == 11
    messages = cycle(service, storage, feedback("w1d3", rpe=3))
    assert state(plan)[(2, 3, "bird_dog")] == raised[(2, 3, "bird_dog")]
    assert any("stays where it is" in message for message in messages)


# ------------------------------------------------------------------------- §12 row 3
def test_on_target_leaves_the_plan_alone():
    """RPE 6, all sets done, no pain: no prescription changes (the session is marked done)."""
    plan = plan_for(STRENGTH)
    service, storage = adaptation(STRENGTH, plan)
    before = state(plan)
    cycle(service, storage, feedback("w1d1", rpe=6))
    assert state(plan) == before
    assert plan.weeks[0].sessions[0].status == "done"


# ------------------------------------------------------------------------- §12 rows 4-6
def test_too_hard_takes_a_set_off_the_hardest_exercise():
    """RPE 8, no pain: the highest-volume exercise of the session loses a set."""
    plan = plan_for(STRENGTH)
    service, storage = adaptation(STRENGTH, plan)
    before = state(plan)
    cycle(service, storage, feedback("w1d1", rpe=8))
    after = state(plan)
    changed = [key for key in before if before[key] != after[key]]
    assert changed and all(after[key][0] == before[key][0] - 1 for key in changed)


def test_a_second_too_hard_feedback_deloads_the_week():
    """RPE 8 after a previous RPE 8: every exercise of the session loses a set."""
    plan = plan_for(STRENGTH)
    service, storage = adaptation(STRENGTH, plan)
    cycle(service, storage, feedback("w1d1", rpe=8))         # the previous feedback
    before = state(plan)
    cycle(service, storage, feedback("w1d3", rpe=8))
    after = state(plan)
    session = [key for key in before if key[0] > 1 and key[1] == 3]
    for exercise in {key[2] for key in session}:
        keys = [key for key in session if key[2] == exercise]
        lost_a_set = all(after[key][0] == max(2, before[key][0] - 1) for key in keys)
        lost_a_step = all(after[key][1] < before[key][1] or after[key][2] < before[key][2]
                          for key in keys)
        assert lost_a_set or lost_a_step                   # §6.3: -1 set, or -1 load step


def test_a_severe_feedback_deloads_the_session():
    """RPE 10: every exercise of the session loses a set, but never below two."""
    plan = plan_for(STRENGTH)
    service, storage = adaptation(STRENGTH, plan)
    before = state(plan)
    cycle(service, storage, feedback("w1d1", rpe=10))
    after = state(plan)
    for key in [key for key in before if key[0] > 1 and key[1] == 1]:
        assert after[key][0] == max(2, before[key][0] - 1)


# -------------------------------------------------------------------------- §12 row 7
def test_knee_pain_swaps_the_offending_exercise():
    """Knee pain: the offending exercise is swapped, the pattern held, the load down."""
    plan = plan_for(CARDIO)
    service, storage = adaptation(CARDIO, plan)
    assert "burpee" in exercises_of(plan, 1, 5)              # the cardio session
    messages = cycle(service, storage, feedback("w1d5", rpe=6, pain=True, pain_region="knee"))
    for week in (2, 3, 4):                                   # the remaining occurrences
        assert "burpee" not in exercises_of(plan, week, 5)
        assert "mountain_climber" in exercises_of(plan, week, 5)
    assert plan.held_patterns == {"cardio": 2}               # held until the end of next week
    assert any(WARNING in message for message in messages)
    assert any("70 %" in message for message in messages)


def test_knee_pain_on_a_squat_removes_it_because_no_squat_is_knee_safe():
    """Knee pain on a squat: every squat stresses the knee, so rule 1 removes the exercise.

    §6.3 rule 1 says "no safe alternative -> remove it". The catalog tags **every** squat
    variation with ``knee``, so this is the documented fallback, not a missing swap.
    """
    plan = plan_for(STRENGTH)
    service, storage = adaptation(STRENGTH, plan)
    messages = cycle(service, storage, feedback("w1d5", rpe=6, pain=True, pain_region="knee"))
    text = "\n".join(messages)
    for week in (2, 3, 4):
        assert "back_squat" not in exercises_of(plan, week, 5)
    assert "no exercise in your pool" in text
    assert WARNING in text
    assert plan.held_patterns == {"squat": 2}


def test_lower_back_pain_swaps_the_squat_for_a_safe_squat():
    """Lower-back pain on a squat: the squat is swapped for the first safe squat of the pool.

    §6.3 rule 1 says "the first catalog exercise with the same movement pattern ... in the
    allowed pool": here that is the bodyweight squat, so the sets stay and the reps start at
    the bottom of its range. (A kg replacement would start at 70 % of the old load - that is
    asserted in ``tests/test_adaptation.py``.)
    """
    plan = plan_for(STRENGTH)
    service, storage = adaptation(STRENGTH, plan)
    before = state(plan)
    messages = cycle(service, storage, feedback("w1d5", rpe=6, pain=True,
                                                pain_region="lower_back"))
    after = state(plan)
    assert "back_squat" not in exercises_of(plan, 2, 5)
    assert "bw_squat" in exercises_of(plan, 2, 5)
    assert after[(2, 5, "bw_squat")] == (before[(2, 5, "back_squat")][0], 10, 0.0)
    assert plan.held_patterns == {"squat": 2}
    assert WARNING in "\n".join(messages)


# -------------------------------------------------------------------------- §12 row 8
def test_pain_in_a_region_no_exercise_is_tagged_for_lowers_the_whole_session():
    """Pain no exercise is tagged for: no swap, every exercise -1 load step, warning shown."""
    plan = plan_for(STRENGTH)
    service, storage = adaptation(STRENGTH, plan)
    before = state(plan)
    messages = cycle(service, storage, feedback("w1d1", rpe=6, pain=True, pain_region="neck"))
    after = state(plan)
    assert not plan.held_patterns                            # nothing was held: no offender
    for key in [key for key in before if key[0] > 1 and key[1] == 1]:
        if before[key][2] > 0:                              # a loaded exercise: -10 %
            assert after[key][2] < before[key][2]
        else:                                               # bodyweight: -2 reps per set
            assert after[key][1] < before[key][1]
    assert WARNING in "\n".join(messages)


# -------------------------------------------------------------------------- §12 row 9
def test_incomplete_and_easy_leaves_the_plan_alone_and_shows_the_hint():
    """RPE 4 with unfinished sets: the plan stays, the hint is shown."""
    plan = plan_for(STRENGTH)
    service, storage = adaptation(STRENGTH, plan)
    before = state(plan)
    messages = cycle(service, storage, feedback("w1d1", rpe=4, all_sets_done=False))
    assert state(plan) == before
    assert any("Plan unchanged" in message for message in messages)


# ------------------------------------------------------------------------- §12 rows 10-11
def test_a_missed_session_is_moved_and_the_rest_day_is_kept():
    """One missed session and a free day: the session is moved, the week keeps a rest day."""
    plan = plan_for(STRENGTH)
    service, storage = adaptation(STRENGTH, plan)
    messages = cycle(service, storage, feedback("w1d3", rpe=6, missed_sessions=1))
    days = sorted(session.day_of_week for session in plan.weeks[0].sessions)
    assert days == [3, 4, 5]                                 # day 1 moved behind the session
    assert len(days) < 7                                     # at least one rest day is left
    assert any("moved to day 4" in message for message in messages)


def test_a_missed_session_without_a_free_day_is_dropped_and_blocks_the_increase():
    """No free day left: the session is dropped and the load is not raised, even at RPE 3."""
    plan = plan_for(FULL_WEEK)
    service, storage = adaptation(FULL_WEEK, plan)
    before = state(plan)
    messages = cycle(service, storage, feedback("w1d6", rpe=3, missed_sessions=1))
    after = state(plan)
    statuses = {session.day_of_week: session.status for session in plan.weeks[0].sessions}
    assert statuses[5] == "dropped"
    assert any("dropped" in message for message in messages)
    for key in [key for key in before if before[key][2] > 0]:
        assert after[key][2] == before[key][2]               # no increase anywhere


# ------------------------------------------------------------------------- §12 row 12
def test_pain_and_too_easy_swaps_without_increasing_anything():
    """Pain + RPE 3: rule 1 wins, so the swap happens and nothing is raised."""
    plan = plan_for(STRENGTH)
    service, storage = adaptation(STRENGTH, plan)
    before = state(plan)
    cycle(service, storage, feedback("w1d5", rpe=3, pain=True, pain_region="lower_back"))
    after = state(plan)
    for key in [key for key in before if key in after and key[2] != "back_squat"]:
        assert after[key][2] <= before[key][2] and after[key][1] <= before[key][1]
    assert plan.held_patterns == {"squat": 2}


# ------------------------------------------------------------------------- §12 row 13
@pytest.mark.parametrize("entry", [
    feedback("w1d1", rpe=3),
    feedback("w1d1", rpe=8),
    feedback("w1d1", rpe=10),
    feedback("w1d5", rpe=6, pain=True, pain_region="lower_back"),
    feedback("w1d3", rpe=6, missed_sessions=1),
])
def test_undo_restores_the_plan_of_the_previous_cycle(entry):
    """Any rule fires, then undo: the plan is exactly as it was before that cycle."""
    plan = plan_for(STRENGTH)
    service, storage = adaptation(STRENGTH, plan)
    before = snapshot(plan)
    cycle(service, storage, entry)
    assert snapshot(plan) != before                          # the rule really fired
    service.undo_last_change()
    assert snapshot(plan) == before


# ------------------------------------------------------------------------- §12 row 14
@pytest.mark.parametrize("entry", [
    feedback("w1d1", rpe=3),
    feedback("w1d5", rpe=3),
    feedback("w1d3", rpe=6, missed_sessions=1),
    feedback("w1d5", rpe=6, pain=True, pain_region="lower_back"),
    feedback("w1d1", rpe=8),
])
def test_no_scenario_breaks_the_guardrails(entry):
    """≤ +10 % load and ≤ +1 set per exercise per week, whatever the rule."""
    plan = plan_for(STRENGTH)
    service, storage = adaptation(STRENGTH, plan)
    before = state(plan)
    cycle(service, storage, entry)
    after = state(plan)
    for key in before:
        if key not in after:                                 # an exercise was removed
            continue
        assert after[key][0] <= before[key][0] + 1           # at most one set more
        if before[key][2] > 0:
            assert after[key][2] <= round(before[key][2] * 1.1 * 2) / 2   # at most +10 %


# ------------------------------------------------------------------------- §12 row 15
def test_a_failing_filter_changes_nothing():
    """A filter that raises: no Command is executed and the plan stays as it was."""
    plan = plan_for(STRENGTH)
    before = snapshot(plan)

    class Broken(AdaptationFilter):
        """A filter with a bug in it."""

        def process(self, context):
            """Raise something the pipeline did not expect."""
            raise ValueError("unexpected")

    service, storage = adaptation(
        STRENGTH, plan,
        pipeline=AdaptationPipeline([SafetyFilter(), ScheduleFilter(), Broken(), LoadFilter()]))
    messages = cycle(service, storage, feedback("w1d1", rpe=3))
    assert snapshot(plan) == before
    assert any("could not" in message.lower() for message in messages)


# ------------------------------------------------------ the §12 "safety rate" metric
@pytest.mark.parametrize("region", ["knee", "lower_back", "shoulder", "wrist", "neck", "hip"])
def test_no_pain_scenario_ever_raises_a_load(region):
    """Adaptation safety rate 100 %: reported pain never leads to a load increase."""
    plan = plan_for(STRENGTH)
    service, storage = adaptation(STRENGTH, plan)
    before = state(plan)
    cycle(service, storage, feedback("w1d1", rpe=3, pain=True, pain_region=region))
    after = state(plan)
    for key in before:
        if key in after:
            assert after[key][2] <= before[key][2] and after[key][1] <= before[key][1]


def test_without_a_plan_the_service_says_so():
    """No plan saved yet: a message instead of an exception."""
    service = AdaptationService(InMemoryStorage(), JsonCatalogLoader())
    assert service.adapt(feedback()) == [NO_PLAN]
