"""Tests for the domain data models (validation rules from FUNCTIONAL_FLOW.md §3 and §5)."""

import pytest
from pydantic import ValidationError

from fitness_agent.domain.models import Exercise, Feedback, Injury, UserProfile

BASE = {"age": 25, "fitness_level": "beginner", "goal": "strength", "days_per_week": 3}


@pytest.mark.parametrize("field, value", [("age", 13), ("age", 91), ("days_per_week", 0),
                                          ("days_per_week", 8), ("goal", "yoga"),
                                          ("fitness_level", "pro")])
def test_profile_rejects_invalid_values(field, value):
    """Out-of-range or unknown values are rejected (the CLI re-asks)."""
    with pytest.raises(ValidationError):
        UserProfile(**{**BASE, field: value})


def test_profile_drops_unknown_equipment_and_adds_bodyweight():
    """Unknown equipment is dropped; bodyweight is always available."""
    profile = UserProfile(**BASE, equipment=["dumbbells", "rowing machine"])
    assert profile.equipment == ["dumbbells", "bodyweight"]


def test_profile_moves_unknown_injury_region_to_notes():
    """A region outside the known list is kept as free text in injury_notes."""
    profile = UserProfile(**BASE, injuries=[{"region": "knee", "note": "left"},
                                            {"region": "elbow", "note": "tennis elbow"}])
    assert [injury.region for injury in profile.injuries] == ["knee"]
    assert profile.injury_notes == ["elbow tennis elbow"]


def test_profile_accepts_injury_objects():
    """Injuries can be given as Injury objects, not only as dicts."""
    profile = UserProfile(**BASE, injuries=[Injury(region="wrist")])
    assert profile.injuries == [Injury(region="wrist")]


def test_minor_is_derived_from_age():
    """Users under 18 are minors."""
    assert UserProfile(**{**BASE, "age": 17}).minor
    assert not UserProfile(**{**BASE, "age": 18}).minor


def test_feedback_requires_region_when_pain():
    """Pain without a region is invalid (the fixed region question is asked)."""
    with pytest.raises(ValidationError):
        Feedback(session_ref="w1d1", rpe=7, pain=True, all_sets_done=True)


def test_feedback_clears_region_without_pain():
    """Without pain there is no pain region."""
    feedback = Feedback(session_ref="w1d1", rpe=7, pain=False, pain_region="knee",
                        all_sets_done=True)
    assert feedback.pain_region is None


@pytest.mark.parametrize("rpe", [0, 11])
def test_feedback_rpe_range(rpe):
    """RPE is 1..10."""
    with pytest.raises(ValidationError):
        Feedback(session_ref="w1d1", rpe=rpe, pain=False, all_sets_done=True)


def test_exercise_rejects_invalid_rep_range():
    """The rep range must be at least 1 and low <= high."""
    with pytest.raises(ValidationError):
        Exercise(id="x", name="X", movement_pattern="core", required_equipment=["bodyweight"],
                 is_compound=False, default_rep_range=(12, 8), load_type="bw", level="beginner")
