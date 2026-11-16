"""Tests for CoachSession and its states (State pattern)."""

import pytest

from fitness_agent.application.session import CoachSession
from fitness_agent.application.text import describe_plan
from fitness_agent.application.states import (AdaptationState, FeedbackState, OnboardingState,
                                              PlanReviewState)
from fitness_agent.domain.models import Feedback, UserProfile
from fitness_agent.domain.plan import PlannedExercise, Session, TrainingPlan, Week
from tests.fakes import FakeAgent, InMemoryStorage

PROFILE = UserProfile(age=25, fitness_level="beginner", goal="strength", days_per_week=3)


def make_plan() -> TrainingPlan:
    """A plan with two planned sessions of 3 sets each."""
    def session(day):
        """One planned session."""
        return Session(day_of_week=day, focus="full body", exercises=[PlannedExercise(
            exercise_id="push_up", load_type="bw", sets=3, reps=10, load=0, rest_s=60)])
    return TrainingPlan(weeks=[Week(number=1, sessions=[session(1), session(4)])])


class FakeOnboarding:
    """Stands in for OnboardingService."""

    def __init__(self, profile=None):
        """profile is what extract() returns (None = extraction failed)."""
        self.profile = profile
        self.saved = None

    def extract(self, _answers):
        """Return the fixed result."""
        return self.profile

    def save(self, profile):
        """Remember the saved profile."""
        self.saved = profile


class FakePlanner:
    """Stands in for PlanService."""

    def generate(self, _profile):
        """Return a fixed plan."""
        return make_plan()


def make_session(storage=None, onboarding=None, agent=None):
    """A CoachSession with fakes; adapt records the feedback it gets."""
    adapted = []

    def adapt(feedback):
        """Record the feedback."""
        adapted.append(feedback)
        return ["Plan adapted."]

    session = CoachSession(onboarding or FakeOnboarding(PROFILE), FakePlanner(),
                           storage or InMemoryStorage(), adapt, agent)
    return session, adapted


def answer_all(session, answers):
    """Send several input lines; return the last output."""
    output = ""
    for answer in answers:
        output = session.handle(answer)
    return output


def test_new_user_starts_with_onboarding_and_gets_a_plan():
    """Six free-text answers -> profile saved -> plan shown."""
    onboarding = FakeOnboarding(PROFILE)
    session, _ = make_session(onboarding=onboarding)
    assert "How old are you?" in session.start()
    output = answer_all(session, ["25", "beginner", "strength", "3", "dumbbells", "none"])
    assert isinstance(session.state, PlanReviewState)
    assert onboarding.saved == PROFILE and session.profile == PROFILE
    assert "Week 1" in output and "1) Give feedback" in output


def test_failed_extraction_switches_to_fixed_questions_and_re_asks():
    """After the LLM fails, each field is asked with a fixed choice; bad answers are re-asked."""
    onboarding = FakeOnboarding(profile=None)
    session, _ = make_session(onboarding=onboarding)
    session.start()
    output = answer_all(session, ["x"] * 6)
    assert "Age (14-90)?" in output
    assert "whole number from 14 to 90" in session.handle("12")
    answer_all(session, ["30", "intermediate", "fat loss", "4", "dumbbells, rowing machine",
                         "knee, elbow"])
    profile = onboarding.saved
    assert (profile.age, profile.goal, profile.equipment) == (30, "fat_loss",
                                                              ["dumbbells", "bodyweight"])
    assert [i.region for i in profile.injuries] == ["knee"] and profile.injury_notes == ["elbow"]
    assert isinstance(session.state, PlanReviewState)


def test_returning_user_starts_with_the_saved_plan():
    """A saved plan skips onboarding."""
    session, _ = make_session(InMemoryStorage(PROFILE, make_plan()))
    assert "Week 1" in session.start()
    assert isinstance(session.state, PlanReviewState)


def test_menu_quit_and_unknown_choice():
    """q ends the session; anything else repeats the menu."""
    session, _ = make_session(InMemoryStorage(PROFILE, make_plan()))
    session.start()
    assert "Please choose 1, 2 or q" in session.handle("hello")
    session.handle("q")
    assert session.finished


def test_fixed_feedback_questions_with_follow_ups_reach_the_adaptation():
    """Without an agent: session choice, four questions plus follow-ups -> saved -> adapted."""
    storage = InMemoryStorage(PROFILE, make_plan())
    session, adapted = make_session(storage)
    session.start()
    assert "Which session did you do?" in session.handle("1")
    assert "How hard was it" in session.handle("2")
    session.handle("8")
    assert "Which region" in session.handle("yes")
    session.handle("knee")
    assert "How many sets" in session.handle("no")
    assert "whole number from 0 to 3" in session.handle("9")
    session.handle("2")
    output = session.handle("0")
    expected = Feedback(session_ref="w1d4", rpe=8, pain=True, pain_region="knee",
                        all_sets_done=False, completed_sets=2, missed_sessions=0)
    assert storage.feedbacks == [expected] and adapted == [expected]
    assert "Plan adapted." in output and isinstance(session.state, PlanReviewState)


def test_agent_reads_free_text_feedback():
    """With an agent, one free-text answer produces the Feedback."""
    agent_feedback = Feedback(session_ref="?", rpe=3, pain=False, all_sets_done=True)
    session, adapted = make_session(InMemoryStorage(PROFILE, make_plan()),
                                    agent=FakeAgent(agent_feedback))
    session.start()
    session.handle("1")
    assert "own words" in session.handle("1")
    session.handle("too easy, all sets done")
    assert adapted[0].session_ref == "w1d1" and adapted[0].rpe == 3


def test_agent_failure_falls_back_to_the_fixed_questions():
    """If the agent fails, the four fixed questions are asked instead."""
    session, adapted = make_session(InMemoryStorage(PROFILE, make_plan()), agent=FakeAgent(None))
    session.start()
    session.handle("1")
    session.handle("1")
    assert "Four short questions" in session.handle("blah")
    answer_all(session, ["5", "no", "yes", "0"])
    assert adapted[0].rpe == 5


def test_no_planned_session_left_goes_back_to_the_plan():
    """When every session is done, feedback is not possible."""
    plan = make_plan()
    for session_ in plan.weeks[0].sessions:
        session_.status = "done"
    session, _ = make_session(InMemoryStorage(PROFILE, plan))
    session.start()
    assert "All sessions are done" in session.handle("1")
    assert isinstance(session.state, PlanReviewState)


def test_redo_onboarding_from_the_menu():
    """2 starts the onboarding again."""
    session, _ = make_session(InMemoryStorage(PROFILE, make_plan()))
    session.start()
    assert "How old are you?" in session.handle("2")
    assert isinstance(session.state, OnboardingState)


def test_states_choose_their_successors():
    """Each state returns the next state itself (who makes the transitions)."""
    session, _ = make_session(InMemoryStorage(PROFILE, make_plan()))
    session.start()
    review = session.state
    assert isinstance(review.handle(session, "1"), FeedbackState)
    feedback = Feedback(session_ref="w1d1", rpe=6, pain=False, all_sets_done=True)
    assert isinstance(AdaptationState(feedback).handle(session, ""), PlanReviewState)


def test_invalid_answers_are_re_asked():
    """Non-numbers and anything but yes/no get a hint and the question again."""
    session, _ = make_session(InMemoryStorage(PROFILE, make_plan()))
    session.start()
    session.handle("1")
    assert "whole number from 1 to 2" in session.handle("first")
    session.handle("1")
    session.handle("5")
    assert "Please answer yes or no." in session.handle("maybe")


def test_handle_before_start_is_an_error():
    """The session must be started first."""
    session, _ = make_session()
    with pytest.raises(RuntimeError):
        session.handle("hi")


def test_plan_text_shows_each_load_type():
    """kg, seconds and bodyweight are shown in their own way."""
    plan = make_plan()
    plan.weeks[0].sessions[0].exercises += [
        PlannedExercise(exercise_id="goblet_squat", load_type="kg", sets=3, reps=8, load=12.5,
                        rest_s=90),
        PlannedExercise(exercise_id="plank", load_type="time", sets=2, reps=1, load=30, rest_s=30)]
    text = describe_plan(plan)
    assert "goblet_squat: 3 x 8, 12.5 kg" in text and "plank: 2 x 1, 30 s" in text
    assert "push_up: 3 x 10, bodyweight" in text
