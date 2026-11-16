"""Tests for OnboardingService and PlanService (retry rule and fallbacks)."""

import pytest

from fitness_agent.application.onboarding import OnboardingService
from fitness_agent.application.planning import PlanService
from fitness_agent.domain.models import DraftSession, Exercise, PlanDraft, UserProfile
from tests.fakes import (FakeLLMClient, FakeStrategyFactory, InMemoryStorage, ListCatalogLoader,
                         SimpleBuilder)

PROFILE = UserProfile(age=25, fitness_level="beginner", goal="strength", days_per_week=3,
                      equipment=["dumbbells"])
CATALOG = [
    Exercise(id="goblet_squat", name="Goblet squat", movement_pattern="squat",
             required_equipment=["dumbbells"], is_compound=True, default_rep_range=(8, 12),
             load_type="kg", level="beginner"),
    Exercise(id="push_up", name="Push-up", movement_pattern="push",
             required_equipment=["bodyweight"], is_compound=True, default_rep_range=(8, 20),
             load_type="bw", level="beginner"),
    Exercise(id="barbell_deadlift", name="Barbell deadlift", movement_pattern="hinge",
             required_equipment=["barbell"], is_compound=True, default_rep_range=(3, 6),
             load_type="kg", level="advanced"),
]
GOOD_DRAFT = PlanDraft(sessions=[DraftSession(focus="legs", exercise_ids=["goblet_squat"]),
                                 DraftSession(focus="push", exercise_ids=["push_up"])])


@pytest.fixture(autouse=True)
def reset_builder():
    """SimpleBuilder keeps its rejection counter on the class."""
    SimpleBuilder.rejections = 0


def make_service(llm, storage=None):
    """A PlanService with the fakes."""
    return PlanService(llm, ListCatalogLoader(CATALOG), storage or InMemoryStorage(),
                       FakeStrategyFactory(), builder_class=SimpleBuilder)


def test_onboarding_retries_then_gives_up():
    """Three failed extractions return None (the state asks the fixed questions)."""
    llm = FakeLLMClient(profile=PROFILE, failures=3)
    assert OnboardingService(llm, InMemoryStorage()).extract("answers") is None
    assert llm.calls == ["extract_profile"] * 3


def test_onboarding_succeeds_on_a_retry_with_the_error():
    """The second attempt gets the first error and succeeds."""
    llm = FakeLLMClient(profile=PROFILE, failures=1)
    assert OnboardingService(llm, InMemoryStorage()).extract("answers") == PROFILE
    assert llm.previous_errors == [None, "fake failure in extract_profile"]


def test_valid_draft_becomes_the_saved_plan():
    """The LLM's choice plus the Strategy's numbers, built and saved, with the summary."""
    storage = InMemoryStorage()
    plan = make_service(FakeLLMClient(plan_draft=GOOD_DRAFT), storage).generate(PROFILE)
    first = plan.weeks[0].sessions[0].exercises[0]
    assert plan.llm_generated and plan.coach_summary == "Fake summary."
    assert (first.exercise_id, first.sets, first.reps, first.load) == ("goblet_squat", 3, 10, 20)
    assert [s.day_of_week for s in plan.weeks[0].sessions] == [1, 4]
    assert storage.plan is plan


def test_builder_violations_share_the_retry_budget():
    """Two Builder rejections, then success: three LLM calls, errors passed on."""
    SimpleBuilder.rejections = 2
    llm = FakeLLMClient(plan_draft=GOOD_DRAFT)
    plan = make_service(llm).generate(PROFILE)
    assert plan.llm_generated
    assert llm.calls.count("generate_plan") == 3
    assert llm.previous_errors == [None, "fake rejection", "fake rejection"]


def test_exercise_outside_the_pool_is_a_failed_attempt():
    """An exercise the user may not do is rejected; after 3 attempts the fallback is used."""
    bad = PlanDraft(sessions=[DraftSession(focus="a", exercise_ids=["barbell_deadlift"]),
                              DraftSession(focus="b", exercise_ids=["push_up"])])
    plan = make_service(FakeLLMClient(plan_draft=bad)).generate(PROFILE)
    assert not plan.llm_generated


def test_wrong_session_count_and_unknown_id_are_failed_attempts():
    """Both are reported to the LLM on the retry."""
    llm = FakeLLMClient(plan_draft=PlanDraft(sessions=[DraftSession(focus="a",
                                                                    exercise_ids=["x"])]))
    make_service(llm).generate(PROFILE)
    assert llm.previous_errors[1] == "expected 2 sessions, got 1"
    llm = FakeLLMClient(plan_draft=PlanDraft(sessions=[DraftSession(focus="a", exercise_ids=["x"]),
                                                       DraftSession(focus="b", exercise_ids=[])]))
    make_service(llm).generate(PROFILE)
    assert llm.previous_errors[1] == "unknown exercise id x"


def test_model_down_uses_the_fallback_and_the_template_summary():
    """Without a model the Strategy builds the plan and the summary is a template."""
    plan = make_service(FakeLLMClient(plan_draft=GOOD_DRAFT, failures=4)).generate(PROFILE)
    assert not plan.llm_generated
    assert plan.weeks[0].sessions[0].focus == "fallback"
    assert plan.coach_summary == "This strength plan has 2 sessions per week for 4 weeks."


def test_summary_adds_the_notes_for_minors_and_other_limitations():
    """Minors and free-text limitations get a note in the summary."""
    teen = UserProfile(age=16, fitness_level="beginner", goal="endurance", days_per_week=3,
                       injuries=[{"region": "elbow"}])
    plan = make_service(FakeLLMClient(plan_draft=GOOD_DRAFT)).generate(teen)
    assert "under 18" in plan.coach_summary and "elbow" in plan.coach_summary


def test_onboarding_saves_the_profile():
    """save() stores the profile."""
    storage = InMemoryStorage()
    OnboardingService(FakeLLMClient(), storage).save(PROFILE)
    assert storage.profile == PROFILE
